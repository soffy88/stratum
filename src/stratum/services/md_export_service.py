import re
from pathlib import Path
from stratum.db import get_conn

EXPORT_DIR = Path("/data/shared/stratum-to-aii")


def _safe_filename(title: str, fallback: str) -> str:
    name = title or fallback
    name = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return f"{name}.md"


def export_one(substrate_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.title, s.source_path, d.content "
            "FROM substrates s JOIN derivative d ON s.id=d.substrate_id "
            "WHERE s.id=? AND d.kind='markdown' AND d.content IS NOT NULL AND d.content != ''",
            (substrate_id,)
        ).fetchone()
    if not row or not row[2]:
        return False
    title, source_path, content = row
    fallback = Path(source_path).stem if source_path else substrate_id
    fname = _safe_filename(title, fallback)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = EXPORT_DIR / fname
    if target.exists() and target.read_text(encoding='utf-8') != content:
        stem = fname[:-3]
        fname = f"{stem}_{substrate_id[:8]}.md"
        target = EXPORT_DIR / fname
    target.write_text(content, encoding='utf-8')
    return True
