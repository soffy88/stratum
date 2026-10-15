"""stratum.services.web_ingest — ingest a URL (webpage or WeChat article) into the AII flywheel.

Fetches the URL with the cascade/WeChat fetchers, converts it to a Markdown file with the
frontmatter the file-based flywheel expects, and drops it into the paper flywheel's intake
directory. From there ``aii/scripts/paper_discover.py`` (aii-flywheel-paper) picks it up
directly — no feeder/classify step, no new flywheel.

Intake resolution (first match wins, see :func:`intake_dir`):

1. ``STRATUM_AII_INTAKE_DIR`` if set (explicit override, used as-is);
2. the first *existing, writable* entry of :data:`_PAPER_INTAKE_CANDIDATES` — these mirror
   ``paper_discover.PAPER_DIRS``: ``aii/gdrive_staging/MD/论文`` (local staging; the real
   intake while ``/home/soffy/books`` is the read-only GDrive rclone mount), then
   ``/home/soffy/books/MD/论文`` (only when that mount is writable/local);
3. legacy ``/home/soffy/shared/stratum-to-aii`` as a last resort (only consumed by
   ``classify_md.py`` when the GDrive mount is *not* active).

The old default ``/home/soffy/books/MD/论文`` sits on a ``ro`` FUSE mount in production, so
writing there raised ``OSError: Read-only file system``; and ``stratum-to-aii`` is skipped by
``pull_ingest.sh`` in GDrive mode — articles dropped there were never consumed.

Why the *paper* (document) bucket: ``classify_md.py`` only routes a non-book document into
a consumed bucket when its frontmatter carries ``doc_type: paper``. The API's own webpage
path stamps ``doc_type: article``, which classify_md drops as 低质 (<60000 chars) or, in
``其它``, requires ≥3 chapters — so a normal web article dead-ends there. The paper pipeline
is the one that handles a standalone document with no chapter structure (BU two-layer
understanding, no per-chapter split), which is exactly what an article is. We therefore set
``doc_type: paper`` as the routing key while recording the true nature in ``source_type`` /
``doc_kind`` so provenance stays honest.

CLI::

    python -m stratum.services.web_ingest ingest-url <url> [--domain X] [--sink DIR]
                                                       [--force] [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from stratum.services.wechat_fetch import fetch_wechat_article, is_wechat_url
from stratum.services.web_fetch_cascade import (
    WebFetchResult,
    fetch_web_markdown,
    is_fetchable_url,
)

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Must stay in sync with aii/scripts/paper_discover.py PAPER_DIRS (the dirs the paper flywheel scans).
_PAPER_INTAKE_CANDIDATES: tuple[Path, ...] = (
    _REPO_ROOT / "aii" / "gdrive_staging" / "MD" / "论文",
    Path("/data/soffy/projects/stratum/aii/gdrive_staging/MD/论文"),
    Path("/home/soffy/books/MD/论文"),
)
_LEGACY_INTAKE = Path("/home/soffy/shared/stratum-to-aii")
_DEFAULT_INTAKE = str(_PAPER_INTAKE_CANDIDATES[0])
_MAX_STEM = 80  # keep filenames well under the 255-byte limit even for CJK titles


@dataclass
class IngestResult:
    success: bool
    url: str
    path: str = ""
    title: str = ""
    author: str = ""
    published: str = ""
    strategy: str = ""
    source_type: str = ""  # "web" | "wechat"
    domain: str = ""
    char_count: int = 0
    skipped: bool = False  # file already existed (idempotent re-run)
    error: str | None = None
    deep_read_path: str = ""  # optional BU2/KU supplement JSON sidecar


def _writable_dir(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


def intake_dir() -> Path:
    """Directory the paper flywheel (paper_discover.py) actually scans and we can write to."""
    override = os.environ.get("STRATUM_AII_INTAKE_DIR")
    if override:
        return Path(override)
    for cand in _PAPER_INTAKE_CANDIDATES:
        if _writable_dir(cand):
            return cand
    return _LEGACY_INTAKE


def _maybe_auto_deep_read(path: Path) -> str:
    """Run the optional supplement only when explicitly enabled; preserve ingestion on failure."""
    enabled = (os.environ.get("STRATUM_DEEP_READ_ENABLED") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return ""
    try:
        from stratum.services.deep_read_enrichment import enrich_file

        artifact = enrich_file(path)
        log.info("web_ingest: deep-read supplement wrote %s", artifact.name)
        return str(artifact)
    except Exception as exc:  # optional enrichment must never block core ingestion
        log.warning(
            "web_ingest: optional deep-read failed for %s (%s)", path.name, type(exc).__name__
        )
        return ""


def _slug(text: str, max_len: int = _MAX_STEM) -> str:
    """Filesystem-safe stem: drop control/path chars, collapse whitespace, trim to max_len."""
    text = unicodedata.normalize("NFKC", text or "").strip()
    text = re.sub(r"[/\\:*?\"<>|\x00-\x1f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text.encode("utf-8")) > max_len:
        # Trim by characters until the byte length fits (CJK is 3 bytes/char).
        while text and len(text.encode("utf-8")) > max_len:
            text = text[:-1]
    return text or "untitled"


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:10]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _yaml_str(value: str) -> str:
    """Quote a scalar so colons/quotes in titles never break the frontmatter."""
    return '"' + (value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_frontmatter(
    *,
    title: str,
    url: str,
    author: str,
    published: str,
    source_type: str,
    strategy: str,
    domain: str,
) -> str:
    """Frontmatter block for an ingested document.

    ``doc_type: paper`` is the classify_md routing key (see module docstring); the real
    nature of the source is recorded in ``source_type`` / ``doc_kind``.
    """
    lines = [
        "---",
        "doc_type: paper",  # routing key → books/MD/论文 → paper/document pipeline
        "doc_kind: article",  # honest: this is a web/WeChat article, not an academic paper
        f"title: {_yaml_str(title)}",
        f"source_type: {source_type}",
        f"source_url: {_yaml_str(url)}",
    ]
    if author:
        lines.append(f"author: {_yaml_str(author)}")
    if published:
        lines.append(f"published: {_yaml_str(published)}")
    if domain:
        lines.append(f"domain: {_yaml_str(domain)}")
    lines.append(f"fetch_strategy: {strategy}")
    lines.append(f"ingested_at: {_iso_now()}")
    lines.append("---")
    return "\n".join(lines)


def render_markdown(title: str, body: str, frontmatter: str) -> str:
    heading = f"# {title}\n\n" if title and not body.lstrip().startswith("# ") else ""
    return f"{frontmatter}\n\n{heading}{body.strip()}\n"


def _fetch(
    url: str, *, client: httpx.Client | None, timeout: float | None
) -> tuple[WebFetchResult, str]:
    """Dispatch to the WeChat or generic cascade fetcher. Returns (result, source_type)."""
    if is_wechat_url(url):
        art = fetch_wechat_article(url, client=client, timeout=timeout)
        res = WebFetchResult(
            success=art.success,
            url=url,
            markdown=art.markdown,
            title=art.title,
            author=art.author,
            published=art.published,
            strategy=art.strategy,
            error=art.error,
        )
        return res, "wechat"
    res = fetch_web_markdown(url, client=client, timeout=timeout)
    return res, "web"


def ingest_url(
    url: str,
    *,
    domain: str | None = None,
    sink: str | Path | None = None,
    client: httpx.Client | None = None,
    timeout: float | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> IngestResult:
    """Fetch ``url`` and drop a Markdown document into the AII intake directory.

    Idempotent: the filename embeds a hash of the URL, so re-running the same URL maps to
    the same path and is skipped unless ``force=True``. ``dry_run`` fetches and renders but
    writes nothing.
    """
    url = (url or "").strip()
    if not is_fetchable_url(url):
        return IngestResult(
            success=False, url=url, source_type="web", error="unsupported or non-public url"
        )

    res, source_type = _fetch(url, client=client, timeout=timeout)
    if not res.success:
        return IngestResult(
            success=False,
            url=url,
            source_type=source_type,
            strategy=res.strategy,
            error=res.error or "fetch failed",
        )

    domain = (domain or "").strip()
    title = res.title or _slug(res.markdown[:60], 60)
    frontmatter = build_frontmatter(
        title=title,
        url=url,
        author=res.author,
        published=res.published,
        source_type=source_type,
        strategy=res.strategy,
        domain=domain,
    )
    markdown = render_markdown(title, res.markdown, frontmatter)

    dest_dir = Path(sink) if sink else intake_dir()
    filename = f"{_slug(title)}__{source_type}_{_url_id(url)}.md"
    dest = dest_dir / filename

    if dest.exists() and not force:
        log.info("web_ingest: skip existing %s", dest.name)
        return IngestResult(
            success=True,
            url=url,
            path=str(dest),
            title=title,
            author=res.author,
            published=res.published,
            strategy=res.strategy,
            source_type=source_type,
            domain=domain,
            char_count=len(res.markdown),
            skipped=True,
            deep_read_path=_maybe_auto_deep_read(dest) if not dry_run else "",
        )

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(markdown, encoding="utf-8")
        log.info(
            "web_ingest: wrote %s (%d chars, strategy=%s)",
            dest.name,
            len(res.markdown),
            res.strategy,
        )

    return IngestResult(
        success=True,
        url=url,
        path=str(dest),
        title=title,
        author=res.author,
        published=res.published,
        strategy=res.strategy,
        source_type=source_type,
        domain=domain,
        char_count=len(res.markdown),
        deep_read_path=_maybe_auto_deep_read(dest) if not dry_run else "",
    )


# ── CLI ─────────────────────────────────────────────────────────────────────────


def _cmd_ingest_url(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m stratum.services.web_ingest ingest-url",
        description="Fetch a URL (webpage / WeChat article) into the AII flywheel intake dir.",
    )
    ap.add_argument("url", help="URL to ingest")
    ap.add_argument("--domain", default=None, help="optional domain/subject tag (frontmatter)")
    ap.add_argument("--sink", default=None, help="intake dir (default: paper flywheel intake)")
    ap.add_argument("--force", action="store_true", help="overwrite if the file already exists")
    ap.add_argument("--dry-run", action="store_true", help="fetch + render but write nothing")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--timeout", type=float, default=None, help="per-request timeout (seconds)")
    args = ap.parse_args(argv)

    result = ingest_url(
        args.url,
        domain=args.domain,
        sink=args.sink,
        timeout=args.timeout,
        force=args.force,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    elif result.success:
        verb = (
            "skipped (exists)" if result.skipped else ("would write" if args.dry_run else "wrote")
        )
        print(f"✅ {verb}: {result.path}")
        print(f"   title:    {result.title}")
        print(f"   strategy: {result.strategy} ({result.source_type})")
        print(f"   chars:    {result.char_count}")
    else:
        print(f"❌ failed: {result.error}", file=sys.stderr)
    return 0 if result.success else 1


def _cmd_deep_read(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m stratum.services.web_ingest deep-read",
        description="Create a 12-question three-round BU2/KU supplement from Markdown, text, or EPUB.",
    )
    ap.add_argument("path", help="source Markdown, text, or EPUB file")
    ap.add_argument("--kind", choices=("book", "article", "document"), default=None)
    ap.add_argument(
        "--output", default=None, help="JSON sidecar destination (default next to source)"
    )
    ap.add_argument("--force", action="store_true", help="regenerate an existing JSON sidecar")
    ap.add_argument("--json", action="store_true", help="print result metadata as JSON")
    args = ap.parse_args(argv)
    try:
        from stratum.services.deep_read_enrichment import enrich_file

        output = enrich_file(args.path, output_path=args.output, kind=args.kind, force=args.force)
        artifact = json.loads(output.read_text(encoding="utf-8"))
        result = {
            "success": True,
            "path": str(output),
            "source_title": artifact["source"]["title"],
            "source_kind": artifact["source"]["kind"],
            "question_count": artifact["question_count"],
        }
    except Exception as exc:
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["success"]:
        print(f"✅ deep-read supplement: {result['path']} ({result['question_count']} questions)")
    else:
        print(f"❌ deep-read failed: {result['error']}", file=sys.stderr)
    return 0 if result["success"] else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "usage: python -m stratum.services.web_ingest {ingest-url <url>|deep-read <path>} ..."
        )
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "ingest-url":
        return _cmd_ingest_url(rest)
    if cmd == "deep-read":
        return _cmd_deep_read(rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
