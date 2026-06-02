"""灌入平台内容到 DuckDB platform_content 表.

内容来源: Stratum 任务书 + 设计文档 (build in public).
从项目根运行: python3 scripts/seed_platform_content.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from stratum.common import generate_ulid, now_utc  # noqa: E402
from stratum.db import insert, query  # noqa: E402

SEED_ITEMS = [
    {
        "title": "Phase 14: Stratum SaaS 后端完整实施过程",
        "type": "article",
        "author": "wiki",
        "path": "docs/design/PHASE_14_PART1_BACKEND_CC_v1.0.md",
        "domain": ["engineering", "knowledge_management"],
        "tags": ["phase14", "saas", "build_in_public"],
    },
    {
        "title": "Phase 14 Part2: 前端装配实施",
        "type": "article",
        "author": "wiki",
        "path": "docs/design/PHASE_14_PART2_FRONTEND_CC_v1.0.md",
        "domain": ["engineering", "frontend"],
        "tags": ["phase14", "frontend", "build_in_public"],
    },
    {
        "title": "STRATUM SL SPEC v1.1: DB 合并 PG → DuckDB",
        "type": "article",
        "author": "wiki",
        "path": "docs/design/STRATUM_SL_SPEC_v1.1.md",
        "domain": ["engineering", "architecture"],
        "tags": ["spec", "database", "build_in_public"],
    },
    {
        "title": "Stratum 全 API 规约 v1",
        "type": "reference",
        "author": "wiki",
        "path": "docs/STRATUM_API_v1.md",
        "domain": ["engineering", "api"],
        "tags": ["api", "openapi", "reference"],
    },
    {
        "title": "Phase 15 P1: 功能补足实施规格",
        "type": "article",
        "author": "wiki",
        "path": "docs/PHASE_15_P1_FUNCTIONAL_COMPLETION_CC_v1.0.md",
        "domain": ["engineering", "product"],
        "tags": ["phase15", "roadmap", "build_in_public"],
    },
]


def _already_seeded() -> set[str]:
    rows = query(
        "SELECT title FROM platform_content WHERE author = 'wiki' AND deleted_at IS NULL",
        limit=100,
    )
    return {r["title"] for r in rows}


def seed():
    existing = _already_seeded()
    seeded = 0
    skipped_file = 0
    skipped_dup = 0

    for item in SEED_ITEMS:
        if item["title"] in existing:
            print(f"⏭  already seeded: {item['title']}")
            skipped_dup += 1
            continue

        doc_path = _ROOT / item["path"]
        if not doc_path.exists():
            print(f"⚠️  skip (file not found): {item['path']}")
            skipped_file += 1
            continue

        body = doc_path.read_text(encoding="utf-8")
        record_id = generate_ulid()
        insert(
            "platform_content",
            {
                "id": record_id,
                "type": item["type"],
                "title": item["title"],
                "author": item["author"],
                "body_markdown": body,
                "body_html": None,
                "published_at": now_utc(),
                "version": 1,
                "domain": item["domain"],
                "tags": item["tags"],
                "access_tier": "free",
            },
        )
        print(f"✅ seeded: {item['title']} ({record_id})")
        seeded += 1

    print(f"\nDone: {seeded} seeded, {skipped_dup} already existed, {skipped_file} files missing.")
    return seeded


if __name__ == "__main__":
    seeded = seed()
    if seeded == 0 and not any((_ROOT / i["path"]).exists() for i in SEED_ITEMS):
        print("⛔ No files found — check docs/ directory.")
        sys.exit(1)
