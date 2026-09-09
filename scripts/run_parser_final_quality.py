"""Run the real HTTP ingest/parser pipeline against 30 real PDF documents."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "experiments/02-batch/samples/pdf"
BOOKS_DIR = Path("/data/soffy/books")
SAMPLES = [
    SAMPLE_DIR / name
    for name in (
        "S1-chinese-novel-history.pdf",
        "S2-marchenko-pastur-1998.pdf",
        "S3-real-analysis-notes.pdf",
        "S4-attention-is-all-you-need.pdf",
        "S5-pride-and-prejudice.pdf",
    )
]
DB = dict(host="127.0.0.1", port=5435, user="aii", password="aii_safe_pass", dbname="aii_kg")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _language(path: Path) -> str:
    sample = path.read_bytes()[:200_000].decode("utf-8", errors="ignore")
    cjk = sum("\u3400" <= char <= "\u9fff" for char in sample)
    latin = sum(char.isascii() and char.isalpha() for char in sample)
    if cjk and latin:
        return "mixed"
    return "zh" if cjk else "en"


def select_documents() -> list[Path]:
    selected = [path for path in SAMPLES if path.is_file() and path.stat().st_size > 0]
    seen = {path.resolve() for path in selected}
    candidates = sorted(
        (
            path
            for path in BOOKS_DIR.rglob("*.pdf")
            if path.is_file() and path.stat().st_size > 10_240 and path.resolve() not in seen
        ),
        key=lambda path: (path.stat().st_size, str(path)),
    )
    selected.extend(candidates[: max(0, 30 - len(selected))])
    if len(selected) != 30:
        raise RuntimeError(f"expected 30 real PDFs, selected {len(selected)}")
    return selected


def _multipart(path: Path, title: str) -> bytes:
    boundary = f"----aii-final-quality-{uuid.uuid4().hex}"
    data = path.read_bytes()
    fields = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\nContent-Type: application/pdf\r\n\r\n'
        ).encode()
        + data
        + b"\r\n",
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'
        ).encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="medium"\r\n\r\npaper\r\n'.encode(),
        f"--{boundary}--\r\n".encode(),
    ]
    return boundary.encode(), b"".join(fields)


def upload(path: Path, token: str, api_url: str, title: str) -> tuple[dict, float]:
    boundary, body = _multipart(path, title)
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/v1/inbox/submit",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary.decode()}",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload, time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _db_row(conn, substrate_id: str) -> tuple | None:
    cur = conn.cursor()
    for _ in range(30):
        cur.execute(
            """
            SELECT s.id, s.source_path, s.file_hash, s.parse_quality,
                   COALESCE((SELECT d.content FROM stratum.derivative d
                             WHERE d.substrate_id=s.id AND d.kind='markdown'
                             ORDER BY length(d.content) DESC LIMIT 1), '')
            FROM stratum.substrates s WHERE s.id=%s
            """,
            (substrate_id,),
        )
        row = cur.fetchone()
        if row and row[4]:
            cur.close()
            return row
        time.sleep(1)
    cur.close()
    return row


def _existing_row(conn, path: Path) -> tuple | None:
    cur = conn.cursor()
    if path.name == "S1-chinese-novel-history.pdf":
        cur.execute(
            "SELECT s.id, s.source_path, s.file_hash, s.parse_quality, "
            "COALESCE((SELECT d.content FROM stratum.derivative d WHERE d.substrate_id=s.id "
            "AND d.kind='markdown' ORDER BY length(d.content) DESC LIMIT 1), '') "
            "FROM stratum.substrates s WHERE s.user_id=%s AND s.title LIKE %s "
            "ORDER BY s.created_at DESC LIMIT 1",
            ("56d6bc01edc35765", "AII final-quality parser smoke S1%"),
        )
    else:
        cur.execute(
            "SELECT s.id, s.source_path, s.file_hash, s.parse_quality, "
            "COALESCE((SELECT d.content FROM stratum.derivative d WHERE d.substrate_id=s.id "
            "AND d.kind='markdown' ORDER BY length(d.content) DESC LIMIT 1), '') "
            "FROM stratum.substrates s WHERE s.user_id=%s AND s.title=%s "
            "ORDER BY s.created_at DESC LIMIT 1",
            ("56d6bc01edc35765", path.name),
        )
    row = cur.fetchone()
    cur.close()
    return row if row and row[4] else None


def _record_from_row(record: dict, row: tuple, reused: bool) -> dict:
    record.update(
        {
            "substrate_id": row[0],
            "source_path": row[1],
            "db_file_hash": row[2],
            "parse_quality": row[3],
            "content_sha256": hashlib.sha256((row[4] or "").encode()).hexdigest(),
            "content_chars": len(row[4] or ""),
            "content_nonempty": bool(row[4]),
            "reused_existing": reused,
            "source_exists": subprocess.run(
                ["docker", "exec", "stratum-sl", "test", "-s", row[1]],
                check=False,
                capture_output=True,
            ).returncode
            == 0,
        }
    )
    return record


def _process_document(index: int, path: Path, token: str, api_url: str) -> dict:
    started = time.perf_counter()
    record = {
        "case_id": f"parser-{index:02d}",
        "filename": str(path),
        "format": "pdf",
        "language": _language(path),
        "source_sha256": _sha256(path),
    }
    conn = psycopg2.connect(**DB)
    try:
        existing = _existing_row(conn, path)
        if existing:
            record.update({"parse_success": True, "upload": {"status": "reused_existing"}})
            record = _record_from_row(record, existing, True)
        else:
            payload, elapsed = upload(path, token, api_url, f"AII final-quality parser {index:02d}")
            record.update(
                {
                    "upload": payload,
                    "elapsed_sec": round(elapsed, 3),
                    "parse_success": payload.get("status") == "completed",
                    "substrate_id": payload.get("substrate_id"),
                }
            )
            if record["substrate_id"]:
                row = _db_row(conn, record["substrate_id"])
                if row:
                    record = _record_from_row(record, row, False)
                else:
                    record["exception"] = "database row/derivative not available"
    except Exception as exc:  # one failed document must not hide the rest
        record.update({"parse_success": False, "exception": f"{type(exc).__name__}: {exc}"})
    finally:
        conn.close()
    record["elapsed_sec"] = round(record.get("elapsed_sec", time.perf_counter() - started), 3)
    return record


def run(output: Path) -> int:
    token = os.environ.get("AII_TOKEN")
    if not token:
        raise SystemExit("AII_TOKEN is required")
    api_url = os.environ.get("AII_API_URL", "http://127.0.0.1:9304")
    documents = select_documents()
    workers = int(os.environ.get("PARSER_UPLOAD_WORKERS", "4"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_process_document, i, path, token, api_url) for i, path in enumerate(documents, 1)]
        records = []
        for future in futures:
            record = future.result()
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)

    reingest = {
        "same_source_id": False,
        "deduplicated": False,
        "status": "NOT_RETRIED_AFTER_OBSERVED_DUPLICATE_KEY",
        "observed": "A repeated S1 upload returned HTTP 500 duplicate key idx_substrates_user_file_hash",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "benchmark": "AII FINAL PRODUCT QUALITY CLOSURE parser",
                "entrypoint": "POST /api/v1/inbox/submit -> stratum.api.routers.inbox -> omodul.process_inbox_substrate",
                "documents_total": len(records),
                "substrate_ids": [r["substrate_id"] for r in records if r.get("substrate_id")],
                "records": records,
                "reingest": reingest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {output}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
