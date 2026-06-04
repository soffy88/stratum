# GOVERNANCE_ADR_REPO_SPLIT_INSTRUCTIONS_v0.1.md

**任务**: 治理修复 — 把 advisor 的 DECISION_LOG.md 拆分到 stratum repo
**执行者**: 任一空闲 CC (推荐刚完工 ADR-021 的 CC, 上下文连贯)
**执行模式**: Claude Code FULL AUTO (文档拆分类, 不实施代码)
**触发**: ADR-021 完工时 CC R-1 披露 — stratum repo 中找不到 ADR-016/019 原文件
**工程量**: 0.5-1 天

---

## §0 背景

之前 advisor 维护单一聚合文件 `DECISION_LOG.md` (历史原因), 没有拆分到 stratum repo 的 `docs/decisions/` 目录。

后果:
- CC 在本地无法查阅 ADR
- ADR-021 完工时 CC 用 stub 补录方式就近修复 ADR-019/016
- 多 CC 并发场景下, 每个 CC 都得问 advisor 拿 ADR 内容
- 项目治理透明度差

**修复目标**: stratum repo 里 `docs/decisions/` 目录含完整 21 个 ADR (每个独立文件) + 一个聚合索引。

---

## §1 工作流程

### Wave 0: 准入检查

```bash
cd ~/projects/stratum
git status
git pull

mkdir -p docs/decisions/
ls -la docs/decisions/   # 当前状态: 可能有 0-2 个 stub (ADR-021 / ADR-019.stub / ADR-016.stub)
```

记录现状:
- 哪些 ADR 文件已存在
- ADR-021 是完整内容还是 stub
- ADR-019 / ADR-016 是 stub 还是完整

### Wave 1: advisor 转发 DECISION_LOG.md

**前提**: Wiki 转发 advisor 维护的 `DECISION_LOG.md` (816 行, 含 21 个 ADR) 给你。

如果文件不在 ~/projects/stratum 也不在 ~/Downloads, **停止报告等 Wiki 提供**。

收到后, 放到工作目录:
```bash
cp ~/Downloads/DECISION_LOG.md ~/projects/stratum/docs/decisions/_source.md
# 或 Wiki 提供其他路径
```

### Wave 2: 拆分

用 Python 脚本按 `## ADR-XXX:` header 拆分:

```python
# ~/projects/stratum/scripts/split_adr.py
import re
from pathlib import Path

SOURCE = Path.home() / "projects" / "stratum" / "docs" / "decisions" / "_source.md"
OUTPUT_DIR = Path.home() / "projects" / "stratum" / "docs" / "decisions"

content = SOURCE.read_text()

# 提取头部 (在第一个 ## ADR-001 之前的内容, 是 advisor 总览)
header_match = re.match(r"^(.*?)(?=^## ADR-001)", content, re.DOTALL | re.MULTILINE)
header_text = header_match.group(1) if header_match else ""

# 按 ## ADR-NNN: 切分
adr_pattern = re.compile(r"^## ADR-(\d{3}): (.+?)$\n(.*?)(?=^## ADR-\d{3}: |\Z)", re.DOTALL | re.MULTILINE)

count = 0
for m in adr_pattern.finditer(content):
    adr_num = m.group(1)
    adr_title = m.group(2).strip()
    adr_body = m.group(3).strip()
    
    # 文件名: ADR-001-mixed-verification-mode.md (slug from title)
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", adr_title.lower()).strip("-")
    filename = f"ADR-{adr_num}-{slug}.md"
    
    output_file = OUTPUT_DIR / filename
    
    full_content = f"""# ADR-{adr_num}: {adr_title}

{adr_body}
"""
    output_file.write_text(full_content)
    count += 1
    print(f"Written: {filename}")

# 单独提取依赖关系图作为 INDEX.md
dep_graph_match = re.search(r"^## 决策依赖关系图\n(.*)", content, re.DOTALL | re.MULTILINE)
if dep_graph_match:
    index_content = f"""# Stratum Decision Records Index

{header_text}

## 完整 ADR 列表 (21 个, {count} 已拆分)

详见 ADR-001 ~ ADR-021 各独立文件.

## 决策依赖关系图

{dep_graph_match.group(1)}
"""
    (OUTPUT_DIR / "INDEX.md").write_text(index_content)
    print(f"Written: INDEX.md")

print(f"Total: {count} ADRs written")
```

跑:
```bash
python ~/projects/stratum/scripts/split_adr.py
```

期待输出 21 个 ADR 文件 + 1 个 INDEX.md。

### Wave 3: 整理重复 / 冲突

**关键步骤**: ADR-021 已经拆出 stub 文件 (ADR-019.stub / ADR-016.stub), Wave 2 拆出新文件后会重复. 处理:

```bash
cd ~/projects/stratum/docs/decisions/

# 列出当前所有 ADR 文件
ls -la ADR-*.md

# 如果 Wave 2 拆出 ADR-016-*.md 跟之前的 stub 冲突:
# - Wave 2 拆出的是完整内容, 是 source of truth
# - stub 文件删除

# 如果 Wave 2 拆出 ADR-021-*.md 跟 CC 之前写的 ADR-021.md 冲突:
# - CC 之前写的 ADR-021 是详细版 (373 行), 应保留
# - Wave 2 拆出的可能是 advisor summary 简版
# - 优先保留 CC 详细版, 但合并 advisor 的关联 / 含义部分

# 决策: Wave 2 输出作为 baseline, 然后 merge 已有 stub / CC 详细版的有用内容
```

合并规则:
- 优先 Wave 2 拆出的 advisor 版本 (source of truth)
- ADR-021 例外: 保留 CC 写的详细 373 行版本, 但加 advisor 关联章节
- 删除所有 .stub.md 文件 (已被完整版替换)

### Wave 4: 验证完整性

```bash
# 期待 21 个 ADR 文件
ls docs/decisions/ADR-*.md | wc -l   # 期待 21

# 验证每个文件以 # ADR-NNN: 开头
for f in docs/decisions/ADR-*.md; do
    head -1 "$f"
done

# 验证 INDEX.md 存在
test -f docs/decisions/INDEX.md && echo "INDEX OK"
```

### Wave 5: 加 .gitignore + commit

```bash
cd ~/projects/stratum
# _source.md 是 advisor 内部聚合, 不必入 git
echo "docs/decisions/_source.md" >> .gitignore

git add docs/decisions/
git commit -m "docs: split DECISION_LOG into per-ADR files (governance fix)

Resolves governance gap identified in ADR-021 R-1 disclosure:
advisor's monolithic DECISION_LOG.md not previously available in
stratum repo. This commit creates docs/decisions/ with 21 individual
ADR files + INDEX.md.

Source: advisor DECISION_LOG.md (816 lines, 21 ADRs)
Output: 21 ADR-NNN-*.md + 1 INDEX.md"

git push
```

---

## §2 Wave 完工报告

```
=== 治理修复完工报告 ===

完工内容:
- docs/decisions/ 目录创建
- 21 个 ADR 拆分: ADR-001 ~ ADR-021
- INDEX.md 含决策依赖关系图
- 删除 stub 文件 (ADR-019.stub / ADR-016.stub 已被完整版替换)
- .gitignore 加 _source.md

文件清单:
- docs/decisions/ADR-001-*.md  ✓
- ...
- docs/decisions/ADR-021-*.md  ✓
- docs/decisions/INDEX.md      ✓
- scripts/split_adr.py         ✓

ADR-021 特殊处理:
- 保留 CC 详细版 (373 行)
- Merged advisor 关联章节

commit: <hash>

后续 CC 都能本地查阅 ADR, 不必每次问 advisor.
```

---

## §3 异常处理

立即停止 + 报告:
- DECISION_LOG.md 不在预期位置, advisor 未转发
- 拆分脚本输出数量 ≠ 21
- ADR header pattern 不匹配 (e.g. 有 ADR-XX 不是 3 位数字)

非阻塞:
- ADR 文件名 slug 可能因中文标题略不规整, 不影响功能
- INDEX.md 内容可手动调整

---

**预估工程量**: 0.5-1 天 FULL AUTO

---

**End of GOVERNANCE_ADR_REPO_SPLIT_INSTRUCTIONS_v0.1.md**
