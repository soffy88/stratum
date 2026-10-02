#!/usr/bin/env python3
"""STRATUM_A dependency closure audit.

Answers one question: *what must be present for this layer to run from a clean
checkout?*

Two kinds of coupling, because P6 showed that checking one is not enough:

  IMPORT      a Python module named in an `import`/`from` statement
  FILE        a file read at runtime — an artifact, a migration, or another
              layer's test file invoked through subprocess

P6's first freeze commit passed every import check and still could not run from
a clean checkout, because `ku_identity_runner` read `p5_ku_evolution.json` and
its test shelled out to `test_a_repository_p5_evolution.py`. Both were
filesystem coupling, invisible to import analysis. This tool looks for both, and
`--verify` then proves the answer the only way that counts: build a throwaway
worktree at a commit, drop in nothing, and run the layer.

Usage:
    python3 scripts/a_dependency_closure.py --layer P5_EVOLUTION
    python3 scripts/a_dependency_closure.py --layer P6_IDENTITY --verify

Read-only. Creates and removes its own worktree under the system temp dir.

WHAT STATIC ANALYSIS CANNOT SEE — and why --verify is not optional:

A path built at RUNTIME from a computed name is invisible to a literal scan.
P7's own test compares against

    artifacts/a_repository/p7_projection/book_<book_id>_projection.json

where `book_id` is computed at run time, so no string literal in the source
names the file. Static closure reported P7 COMPLETE; only --verify found the
missing artifact, by running the layer and letting two tests fail.

Treat `complete=True` as "no *named* dependency is missing", never as
"runnable". Only --verify answers the second question.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).parents[1]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
ARTIFACTS = ROOT / "artifacts" / "a_repository"
TESTS = ROOT / "tests" / "architecture"

#: The layers, named the way the freeze records name them.
LAYERS: Dict[str, Dict[str, object]] = {
    "P4_1_DURABLE": {
        "modules": [],  # the P4.1 writer is reached through freeze.py
        "tests": ["test_a_repository_p4_1_persistence.py"],
    },
    "P5_0_CONDITION": {
        "modules": ["condition_boundary", "condition_boundary_runner"],
        "tests": ["test_a_condition_boundary_contract.py"],
    },
    # P5.1-P5.5 had no entry until the final acceptance needed a closure
    # figure for every layer that reports gates. A layer absent from this table
    # is a layer whose closure nobody has checked.
    "P5_1_MECHANISM": {
        "modules": ["mechanism", "mechanism_runner"],
        "tests": ["test_a_mechanism_authority.py"],
    },
    "P5_2_RELATION": {
        "modules": ["relation", "relation_runner"],
        "tests": ["test_a_relation_authority.py"],
    },
    "P5_3_PAPER": {
        "modules": ["paper_writer", "paper_runner"],
        "tests": ["test_a_paper_authority.py"],
    },
    "P5_4_CONSTRAINT": {
        "modules": ["constraint_writer", "constraint_runner"],
        "tests": ["test_a_constraint_authority.py"],
    },
    "P5_5_PAPER_EVIDENCE_FK": {
        "modules": ["paper_evidence_fk_runner"],
        "tests": [],
    },
    "P5_EVOLUTION": {
        "modules": ["evolution", "ku_evolution_runner"],
        "tests": ["test_a_repository_p5_evolution.py"],
    },
    "P6_IDENTITY": {
        "modules": ["identity", "ku_identity_runner"],
        "tests": ["test_a_repository_p6_identity.py"],
    },
    "P7_PROJECTION": {
        "modules": ["projection", "projection_builder"],
        "tests": ["test_a_repository_p7_projection.py"],
    },
}

#: Modules every layer inherits by sitting in the same package.
PACKAGE_INHERITED = ("freeze", "ingestion", "persistence", "quality", "types",
                     "verification", "pilot_corpus")


# ── git ──────────────────────────────────────────────────────────────────────

def tracked(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    result = subprocess.run(["git", "ls-files", "--error-unmatch", str(rel)],
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode == 0


def head_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=ROOT).stdout.strip()


# ── static analysis ──────────────────────────────────────────────────────────

def module_imports(path: Path) -> Set[str]:
    """Sibling modules named in import statements, by AST.

    AST rather than a regex: a regex over `import` lines matches the word in a
    comment or a docstring, which is the same class of false positive that has
    produced three separate defects in this project.
    """
    found: Set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # `from . import x` has module=None; `from .x import y` has
            # module='x'. Conflating the two records the imported SYMBOL
            # instead of the MODULE, and every sibling import then fails the
            # "does the .py exist" filter — which silently empties the closure.
            # That bug made an earlier run of this tool report P7 with no
            # dependency on identity, while projection_builder plainly does
            # `from .identity import KUIdentityService`.
            if node.level == 1 and node.module is None:
                found.update(alias.name for alias in node.names)
            elif node.level == 1 and node.module:
                found.add(node.module.split(".")[0])
            elif node.module and node.module.startswith(
                    "stratum.knowledge.a_repository"):
                found.add(node.module.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("stratum.knowledge.a_repository"):
                    found.add(alias.name.split(".")[-1])
    return {name for name in found if (PKG / f"{name}.py").exists()}


def module_file_reads(path: Path) -> Set[str]:
    """Sibling-layer FILES a module names as literal paths.

    Catches the coupling class P6 missed: a module can import cleanly and still
    need a JSON artifact or a sibling layer's test file that may not be
    committed. Only string literals are considered, so this reports what the
    code names rather than what happens to sit on disk.
    """
    found: Set[str] = set()
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    # Fragments of f-strings, gathered first. `ast.walk` also yields those
    # parts as ordinary Constant nodes, so without this the same literal is
    # reported twice: once correctly as a template and once as a missing file.
    fragments: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    name = Path(part.value).name
                    if name.endswith(".json") or name.endswith(".sql"):
                        fragments.add(name)
                        found |= _classify(part.value, template=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if Path(node.value).name not in fragments:
                found |= _classify(node.value)
    return found


def _classify(value: str, template: bool = False) -> Set[str]:
    """Classify a literal as another layer's artifact, migration or test."""
    found: Set[str] = set()
    name = Path(value).name
    suffix = "-template" if template else ""
    # Another layer's test file, by module or path.
    if value.startswith("test_") and value.endswith(".py"):
        found.add(f"test:{Path(value).name}")
    if "test_a_" in value and value.endswith(".py"):
        found.add(f"test:{Path(value).name}")
    # Classified by extension exactly once: an earlier version iterated the two
    # directories and added every .sql as BOTH kinds, so each migration also
    # surfaced as a missing artifact.
    if name.endswith(".json"):
        found.add(f"artifact{suffix}:{name}")
    elif name.endswith(".sql"):
        found.add(f"migration{suffix}:{name}")
    return found


def subprocess_test_calls(path: Path) -> Set[str]:
    """Test files invoked by shelling out, which an import scan cannot see."""
    found: Set[str] = set()
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"test_a_[\w/]*\.py", text):
        found.add(f"test:{Path(match.group(0)).name}")
    for match in re.finditer(r'"(p[0-9a-z_]*_[\w]*\.json)"', text):
        found.add(f"artifact:{match.group(1)}")
    return found


# ── closure ──────────────────────────────────────────────────────────────────

def resolve(target: str) -> Optional[Path]:
    kind, _, name = target.partition(":")
    if kind == "artifact":
        return ARTIFACTS / name
    if kind == "migration":
        return MIGRATIONS / name
    if kind == "test":
        return TESTS / name
    return None


def closure(layer: str) -> Dict[str, object]:
    spec = LAYERS[layer]
    seeds = list(spec["modules"]) + [str(m) for m in PACKAGE_INHERITED]

    module_closure: Set[str] = set()
    file_targets: Set[str] = set()
    queue = [str(m) for m in seeds]

    while queue:
        name = queue.pop()
        if name in module_closure:
            continue
        path = PKG / f"{name}.py"
        if not path.exists():
            continue
        module_closure.add(name)
        file_targets |= module_file_reads(path)
        file_targets |= subprocess_test_calls(path)
        for dep in module_imports(path):
            if dep not in module_closure:
                queue.append(dep)

    files: List[Dict[str, object]] = []
    for target in sorted(file_targets):
        kind, _, name = target.partition(":")
        base = {"artifact": ARTIFACTS, "migration": MIGRATIONS,
                "test": TESTS}.get(kind.removesuffix("-template"))
        is_template = kind.endswith("-template")
        # A glob names a set of files, not one. `root.glob("0[78][0-9]_a_*.sql")`
        # is a real dependency on 13 migrations; resolving it as a literal path
        # reported it MISSING, which is indistinguishable from a real gap and so
        # trains the reader to ignore the line.
        if base is not None and any(c in name for c in "*?["):
            matches = sorted(p for p in base.glob(name) if p.is_file())
            files.append({
                "target": target, "kind": "glob",
                "resolved": None, "tracked": False, "present": False,
                "matches": [str(p.relative_to(ROOT)) for p in matches],
                "all_tracked": all(tracked(p) for p in matches) if matches
                else False,
                "count": len(matches),
            })
            continue
        path = resolve(target)
        # An f-string fragment cannot be resolved to a path. Report what it
        # could match so the coupling stays visible instead of vanishing.
        if path is None or (is_template and not path.exists()):
            matches = (sorted(q for q in base.rglob(f"*{name}") if q.is_file())
                       if base is not None else [])
            files.append({
                "target": target, "kind": "template",
                "resolved": None, "tracked": False, "present": False,
                "matches": [str(p.relative_to(ROOT)) for p in matches
                            if p.is_file()],
            })
            continue
        if not path.exists():
            files.append({"target": target, "kind": kind,
                          "resolved": None, "tracked": False,
                          "present": False})
            continue
        rel = path.relative_to(ROOT)
        files.append({
            "target": target,
            "path": str(rel),
            "tracked": tracked(path),
            "present": True,
        })

    modules: List[Dict[str, object]] = []
    for name in sorted(module_closure):
        path = PKG / f"{name}.py"
        modules.append({
            "module": name,
            "tracked": tracked(path),
            "seed": name in seeds,
        })

    # The layer's own tests are part of its closure and have their own
    # filesystem reach. P6's first freeze commit was not checkable because its
    # test shelled out to another layer's test file; nothing about that is
    # visible from the module graph.
    test_files: List[Dict[str, object]] = []
    for test_name in spec["tests"]:
        test_path = TESTS / str(test_name)
        entry: Dict[str, object] = {"test": str(test_name),
                                    "tracked": test_path.exists() and tracked(test_path)}
        if test_path.exists():
            reaches = subprocess_test_calls(test_path) | module_file_reads(test_path)
            entry["reaches"] = sorted(reaches)
            # Resolve each reach, so an illustrative literal in a docstring
            # (`psql -f a.sql`) is visibly not a real dependency rather than
            # being indistinguishable from one.
            resolved, unresolved = [], []
            for target in sorted(reaches):
                path = resolve(target)
                if path is None or not path.exists():
                    unresolved.append(target)
                    continue
                resolved.append(target)
                if not tracked(path):
                    entry.setdefault("untracked_reached", []).append(target)
            entry["reaches_resolved"] = resolved
            entry["reaches_unresolved"] = unresolved
        test_files.append(entry)

    untracked_test_files = [t["test"] for t in test_files
                            if not t["tracked"]]
    untracked_reached: List[str] = []
    for entry in test_files:
        untracked_reached.extend(entry.get("untracked_reached", []))

    untracked_modules = [m["module"] for m in modules if not m["tracked"]]
    untracked_files = [f["target"] for f in files
                       if f.get("present") and not f["tracked"]]

    return {
        "layer": layer,
        "head": head_sha(),
        "module_closure": sorted(module_closure),
        "seed_modules": sorted(seeds),
        "files": files,
        "test_files": test_files,
        "untracked_modules": untracked_modules,
        "untracked_files": untracked_files,
        "tests": [str(t) for t in spec["tests"]],
        "test_closure": test_files,
        "untracked_tests": untracked_test_files,
        "untracked_reached_by_tests": untracked_reached,
        "complete": not (untracked_modules or untracked_files
                         or untracked_test_files or untracked_reached),
    }


# ── empirical verification ───────────────────────────────────────────────────

def verify(layer: str, commit: str) -> Dict[str, object]:
    """Prove the closure: a clean worktree at `commit`, run the layer, no help.

    This is the step that catches what static analysis cannot. It is deliberately
    the same shape as the R-10 check that caught P6's hidden coupling.
    """
    spec = LAYERS[layer]
    worktree = Path(tempfile.mkdtemp(prefix=f"closure-{layer.lower()}-"))
    target = worktree / "tree"
    try:
        subprocess.run(["git", "worktree", "add", "--detach", str(target),
                        commit], capture_output=True, text=True, cwd=ROOT)
        # Relative to the repository root, not to tests/architecture —
        # `TESTS.name` alone yields "architecture/test_x.py", which pytest
        # cannot find.
        test_dir = TESTS.relative_to(ROOT)
        tests = [str(test_dir / str(t)) for t in spec["tests"]]
        if not tests:
            return {"verified": False, "reason": "no test entry for this layer"}
        run = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q"],
            capture_output=True, text=True, cwd=target, timeout=1800)
        tail = (run.stdout or "").strip().splitlines()[-1:] or [""]
        return {
            "verified": run.returncode == 0,
            "returncode": run.returncode,
            "summary": tail[0],
            "stderr_tail": (run.stderr or "").strip().splitlines()[-3:],
        }
    finally:
        subprocess.run(["git", "worktree", "remove", str(target), "--force"],
                       capture_output=True, text=True, cwd=ROOT)
        shutil.rmtree(worktree, ignore_errors=True)


# ── reporting ────────────────────────────────────────────────────────────────

def render(result: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append(f"LAYER            {result['layer']}")
    lines.append(f"HEAD             {result['head']}")
    lines.append("")
    lines.append("DEPENDENCY_GRAPH")
    lines.append(f"  module closure ({len(result['module_closure'])}): "
                 f"{', '.join(result['module_closure'])}")
    untracked_mod = result["untracked_modules"]
    lines.append(f"  untracked modules ({len(untracked_mod)}): "
                 f"{', '.join(untracked_mod) if untracked_mod else 'none'}")
    lines.append("")
    lines.append("RUNTIME_CLOSURE  (filesystem coupling — invisible to imports)")
    if not result["files"]:
        lines.append("  none named")
    for entry in result["files"]:
        kind = entry.get("kind")
        if kind == "glob":
            count = entry.get("count") or 0
            state = "all tracked" if entry.get("all_tracked") else (
                "NONE TRACKED" if count else "matched nothing")
            lines.append(f"  GLOB      {entry['target']} -> {count} file(s), "
                         f"{state}")
            if count:
                lines.append(f"             {', '.join(entry['matches'])}")
            continue
        if kind == "template":
            matches = entry.get("matches") or []
            if matches:
                lines.append(f"  TEMPLATE  {entry['target']} -> matches "
                             f"{len(matches)} tracked file(s)")
                lines.append(f"             {', '.join(matches)}")
            else:
                lines.append(f"  TEMPLATE  {entry['target']} -> f-string "
                             "fragment, runtime-computed, nothing to resolve")
            continue
        if not entry.get("present"):
            lines.append(f"  MISSING  {entry['target']}")
            continue
        state = "tracked" if entry["tracked"] else "UNTRACKED"
        lines.append(f"  {state:10} {entry['path']}")
    untracked_files = result["untracked_files"]
    lines.append(f"  untracked files ({len(untracked_files)}): "
                 f"{', '.join(untracked_files) if untracked_files else 'none'}")
    lines.append("")
    lines.append("TEST_CLOSURE  (a test file's own reach)")
    for entry in result["test_closure"]:
        state = "tracked" if entry["tracked"] else "UNTRACKED"
        good = entry.get("reaches_resolved") or []
        bad = entry.get("reaches_unresolved") or []
        extra = ""
        if entry.get("untracked_reached"):
            extra = (f"   <- REACHES UNTRACKED "
                     f"{entry['untracked_reached']}")
        lines.append(f"  {state:10} {entry['test']}")
        if good:
            lines.append(f"             reaches: {', '.join(good)}{extra}")
        if bad:
            lines.append(f"             not real files (docstring literals): "
                         f"{', '.join(bad)}")
    lines.append("")
    lines.append("FREEZE_SCOPE")
    lines.append(f"  tests: {', '.join(result['tests'])}")
    lines.append(f"  runnable from a clean checkout: "
                 f"{'YES' if result['complete'] else 'NO'}")
    lines.append("  (static only - a runtime-computed path cannot be seen;")
    lines.append("   --verify is what proves runnability)")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", required=True, choices=sorted(LAYERS))
    parser.add_argument("--verify", action="store_true",
                        help="also build a clean worktree and run the layer")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = closure(args.layer)
    if args.verify:
        result["verification"] = verify(args.layer, args.commit)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json
          else render(result))
    if args.verify and not result.get("verification", {}).get("verified"):
        sys.exit(1)


if __name__ == "__main__":
    main()