# Layer 4 — md_export_service 实施指令书

**To**: Stratum CC（FULL AUTO）
**From**: Stratum advisor
**日期**: 2026-06-18
**前置**: oprim v3.10.15 / omodul v1.30.2（export_substrate_markdown 已补）/ oskill v3.25.5
**模式**: FULL AUTO，失败停，完工逐字报告

---

## §0 范围（§20 严守）

✅ Layer 4（Stratum repo 内）:
- src/stratum/services/md_export_service.py（新建）
- 入库钩子（inbox.py + folder_watcher_service.py）
- 存量补导脚本

❌ 不改主库（omodul.export_substrate_markdown / oprim 元素 都已就绪，只调用）

---

## §1 前置核对

```bash
# 容器拉新主库:
cd ~/projects/stratum/deploy
docker compose restart stratum-sl
sleep 10

# 确认 omodul import 恢复 + export 元素可用:
docker exec stratum-sl python3 -c "
from omodul.export_substrate_markdown import (
    export_substrate_markdown, ExportSubstrateMarkdownConfig, ExportSubstrateMarkdownInput
)
import inspect
print('export sig:', inspect.signature(export_substrate_markdown))
print('Config fields:', list(ExportSubstrateMarkdownConfig.model_fields.keys()))
"
# 拿到 ExportSubstrateMarkdownConfig 真实字段，下面装配按它对齐
```

**重要**：下面的 ExportConfig 字段是预期，CC 按上面 inspect 的真实字段对齐，不一致以主库为准。

---

## §2 md_export_service.py

```python
# src/stratum/services/md_export_service.py
"""
Layer 4: 调 omodul.export_substrate_markdown 把 substrate 导出为带 frontmatter
的 .md 到 AII 共享目录。

调用链（全主库元素，不改主库）:
  substrate (DB) → omodul.export_substrate_markdown
    (内部: text_clean_publish_noise + markdown_frontmatter_build)
  → 写 .md 到 /data/shared/stratum-to-aii/
"""
import logging
from pathlib import Path
from stratum.db import get_conn
from omodul.export_substrate_markdown import (
    export_substrate_markdown,
    ExportSubstrateMarkdownConfig,
    ExportSubstrateMarkdownInput,
)

log = logging.getLogger(__name__)

# AII 共享目录（容器内挂载路径，CC 核实 docker-compose mount）
EXPORT_DIR = Path("/data/shared/stratum-to-aii")


def _doc_type_from_medium(medium: str) -> str:
    """medium → AII doc_type（book/paper/article/report）"""
    mapping = {
        "paper": "paper",
        "book": "book",
        "epub": "book",
        "webpage": "article",
        "pdf": "paper",      # PDF 默认 paper，可被 classify 覆盖
        "text": "article",
    }
    return mapping.get(medium, "article")


def export_one(substrate_id: str) -> dict:
    """导出单个 substrate 为 .md（带 frontmatter）到 AII 共享目录。"""
    # 取 substrate 元数据 + markdown content
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.id, s.title, s.medium, s.language, s.source_path, d.content "
            "FROM substrates s "
            "JOIN derivative d ON s.id = d.substrate_id "
            "WHERE s.id = ? AND d.kind = 'markdown' "
            "AND d.content IS NOT NULL AND d.content != ''",
            (substrate_id,)
        ).fetchone()

    if not row:
        return {"status": "skipped", "reason": "no markdown content", "substrate_id": substrate_id}

    sid, title, medium, language, source_path, content = row
    doc_type = _doc_type_from_medium(medium)
    # author: 从 meta_json 或 substrate 字段取（CC 核实 author 来源）

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 装配 omodul.export_substrate_markdown
    # 注意: 字段名按 §1 inspect 的真实 ExportSubstrateMarkdownConfig 对齐
    config = ExportSubstrateMarkdownConfig(
        substrate_id=sid,
        title=title,
        author="",              # CC: 从 meta_json 取 author 如果有
        doc_type=doc_type,
        language=language or "zh",
        source="stratum",
        clean_noise=True,       # 启用 text_clean_publish_noise
    )

    result = export_substrate_markdown(
        config=config,
        input_data=ExportSubstrateMarkdownInput(content=content),
        output_dir=EXPORT_DIR,
    )

    if result.get("status") == "completed":
        log.info("md_export: exported %s → %s", title, result.get("file_path"))
    else:
        log.warning("md_export: failed %s: %s", title, result.get("error"))

    return result


def export_all(doc_type_filter: str | None = None) -> dict:
    """批量导出所有有 markdown 的 substrate。可按 doc_type 分批（AII 契约批次）。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT s.id, s.medium FROM substrates s "
            "JOIN derivative d ON s.id = d.substrate_id "
            "WHERE d.kind = 'markdown' AND d.content IS NOT NULL AND d.content != ''"
        ).fetchall()

    targets = []
    for sid, medium in rows:
        if doc_type_filter and _doc_type_from_medium(medium) != doc_type_filter:
            continue
        targets.append(sid)

    exported = 0
    skipped = 0
    for sid in targets:
        r = export_one(sid)
        if r.get("status") == "completed":
            exported += 1
        else:
            skipped += 1

    log.info("md_export: batch done — %d exported, %d skipped", exported, skipped)
    return {"total": len(targets), "exported": exported, "skipped": skipped}
```

---

## §3 共享目录挂载确认

```bash
# 确认容器内 EXPORT_DIR 路径 + rw:
docker exec stratum-sl ls -la /data/shared/stratum-to-aii/ 2>&1
grep -n "shared\|stratum-to-aii" ~/projects/stratum/deploy/docker-compose.yml
# 宿主机 /home/soffy/shared/stratum-to-aii → 容器内挂载路径
# 确认 md_export_service.py 的 EXPORT_DIR 跟挂载点一致（如果不是 /data/shared/... 改成实际路径）
```

---

## §4 入库钩子（自动导出）

```python
# 1. inbox.py — upload/url 入库后:
#    在 _fill_derivative_content(substrate_id, findings) 之后加:
from stratum.services.md_export_service import export_one
export_one(substrate_id)

# 2. folder_watcher_service.py — _scan_one_watch 里 _fill_derivative_content 之后:
#    套装情况: findings.substrate_ids 有多个，逐个导出
findings = result.get("findings", {})
sub_ids = findings.get("substrate_ids") or [substrate_id]
from stratum.services.md_export_service import export_one
for sid in sub_ids:
    export_one(sid)
# is_bundle=True 时 substrate_ids 含所有拆出的本（每本独立 substrate_id → 独立 .md）
```

---

## §5 存量补导

```bash
# 现有有 content 的 substrate 全部导出一遍:
docker exec stratum-sl python3 -c "
from stratum.services.md_export_service import export_all
r = export_all()
print(r)
"
# 期待: exported 接近 196（之前补跑 embedding 的数量）
```

---

## §6 验证

```bash
# 1. 单个导出验证:
docker exec stratum-sl python3 -c "
from stratum.db import get_conn
from stratum.services.md_export_service import export_one
with get_conn() as conn:
    sid = conn.execute(\"SELECT substrate_id FROM derivative WHERE kind='markdown' AND content IS NOT NULL LIMIT 1\").fetchone()[0]
print(export_one(sid))
"

# 2. 检查导出的 .md 有 frontmatter:
docker exec stratum-sl sh -c "head -15 /data/shared/stratum-to-aii/*.md | head -20"
# 期待: 文件开头是 ---\nsubstrate_id: ...\ntitle: ...\n---

# 3. 宿主机确认:
ls /home/soffy/shared/stratum-to-aii/ | head -10
ls /home/soffy/shared/stratum-to-aii/ | wc -l

# 4. 文件名是中文书名（不是 ULID）:
ls /home/soffy/shared/stratum-to-aii/ | grep -E "经济|数学|分析" | head -3
```

---

## §7 commit

```bash
cd ~/projects/stratum
git add -A
git commit -m "feat: md_export_service — 导出 substrate 为带 frontmatter 的 MD 到 AII 共享目录"
git push
```

---

## §8 R-1 / R-3 / §20

- R-1: ExportSubstrateMarkdownConfig 字段不匹配（§1 inspect 后对齐）/ 共享目录不可写 / 导出 0 个 → 停报告
- R-3: 真实导出 .md 文件 + frontmatter 含 substrate_id + 文件名是书名
- §20: 不改主库（只调 omodul.export_substrate_markdown）

**完工报告**:
- §1 ExportSubstrateMarkdownConfig 真实字段
- 共享目录挂载路径
- export_all 存量导出数（exported/skipped）
- frontmatter 样例（一个 .md 的头部）
- 入库钩子加入位置（行号）
- commit hash

---

**End**
— Stratum advisor, 2026-06-18
