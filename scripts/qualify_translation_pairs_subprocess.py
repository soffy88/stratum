"""AII-owned child-process qualification for provider-boundary pair capture."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import sys
from pathlib import Path


def _child(argv: list[str], metadata_path: str) -> None:
    # The child constructs the final BabelDOC config and injects its own
    # recorder; no translator, recorder, DB connection, or service object is
    # passed through multiprocessing.
    sys.argv = argv
    from qualify_translation_pairs import run

    rc = asyncio.run(run())
    Path(metadata_path).write_text(
        json.dumps({"pid": os.getpid(), "returncode": rc}) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(rc)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: qualify_translation_pairs_subprocess.py PDF [pdf2zh args]")
    root = Path(os.environ.get("AII_PAIR_RUN_DIR", "/tmp/aii-translation-pairs"))
    root.mkdir(parents=True, exist_ok=True)
    pair_path = root / "pairs.json"
    sentinel_path = root / "sentinel.jsonl"
    metadata_path = root / "child.json"
    env = os.environ
    env["AII_TRANSLATION_PAIRS_OUTPUT"] = str(pair_path)
    env["AII_TRANSLATION_SENTINEL_PATH"] = str(sentinel_path)
    env.setdefault("AII_TRANSLATION_RUN_ID", "subprocess-qualification")
    argv = ["qualify_translation_pairs.py", *sys.argv[1:]]
    ctx = multiprocessing.get_context("spawn")
    parent_pid = os.getpid()
    child = ctx.Process(target=_child, args=(argv, str(metadata_path)))
    child.start()
    child.join(3600)
    if child.is_alive():
        child.terminate()
        child.join()
        raise SystemExit("translation child timed out")
    child_pid = (
        int(json.loads(metadata_path.read_text(encoding="utf-8"))["pid"])
        if metadata_path.exists()
        else child.pid
    )
    pairs = json.loads(pair_path.read_text(encoding="utf-8")) if pair_path.exists() else []
    print("PARENT_PID=", parent_pid)
    print("CHILD_PID=", child_pid)
    print("RECORDER_PID=", child_pid)
    print("RECORDED_PAIRS=", len(pairs))
    return child.exitcode or 0


if __name__ == "__main__":
    raise SystemExit(main())
