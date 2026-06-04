# STRATUM_PATCH_v0.1_to_v0.1.1.md

**任务**: 应用 STRATUM_SPEC v0.1.1 修订到 v0.0.1 已交付的 schema 文件
**执行模式**: Claude Code (可半自动, 步骤简单)
**前置**: 批 1 v0.0.1 已 tag, 工作树干净
**预期产物 tag**: v0.0.2

---

## 修订背景

批 1 完工时,Claude Code 提出 4 处 SPEC 反馈,经 chief advisor 全部接受 (理由见 STRATUM_SPEC v0.1.1 §17 Changelog)。

本任务把 SPEC v0.1 → v0.1.1 的变更同步到实际 schema 文件,作为 v0.0.2 小补丁。

**3 项需要改 schema 文件**:
1. 全部 16 个 schema 的 `ingested_by` 枚举确认含 `"pipeline"` (批 1 已先行实现, 这里仅核验)
2. `substrate.webpage.schema.json` 把 `authors_or_site` 拆成 `site_name` (required) + `authors` (optional)
3. 同步更新 `substrate.webpage.valid.yaml` 和 `.invalid.yaml`

**1 项仅 SPEC 文档变更, 无 schema 改动** (§5.2 transcript / event 注释 / §5.4 references 适用范围说明) — 直接覆盖 SPEC 文件即可。

---

## 任务清单

### 任务 1: 覆盖 STRATUM_SPEC.md

把 `_hub/STRATUM_SPEC.md` 整个文件用 v0.1.1 版本覆盖 (Wiki 会附上 v0.1.1 markdown 内容)。

### 任务 1.5: 修正 README.md 中的仓库路径

检查 `README.md` 中是否含旧路径 `~/projects/_helios-platform/stratum/` 或 `/home/soffy/projects/STRATUM/` (大写):
- 全部替换为 `~/projects/stratum/`
- 如有提到 "本仓库位于" 之类的描述, 确保统一为小写 `stratum/`

### 任务 2: 修改 substrate.webpage.schema.json

**位置**: `_hub/schemas/substrate.webpage.schema.json`

**改动**:
- 删除 `authors_or_site` 字段定义
- 在 `properties` 下新增:
  ```json
  "site_name": {
    "type": "string",
    "minLength": 1,
    "description": "网站或出版方名称,例如 'Karpathy Blog' / '36kr' / 'NYTimes'"
  },
  "authors": {
    "type": "array",
    "items": { "type": "string" },
    "description": "文章作者列表,可选 (个人博客有作者, 企业新闻稿可能没有)"
  }
  ```
- 在 `required` 数组中:
  - 如果原来 `authors_or_site` 在 required, 替换为 `site_name`
  - `authors` 不进 required

### 任务 3: 更新 substrate.webpage 的 examples

**位置**:
- `_hub/schemas/examples/substrate.webpage.valid.yaml`
- `_hub/schemas/examples/substrate.webpage.invalid.yaml`

**改动**:
- valid.yaml: 把 `authors_or_site: [...]` 替换为 `site_name: "..."` + `authors: [...]`
- invalid.yaml: 调整 invalid case,确保至少包含 1 处 "缺 site_name" 类型的违规 (保持 ≥ 12 处不同违规的总量)

### 任务 4: 核验 ingested_by 枚举

跑一次:
```bash
grep -l '"ingested_by"' _hub/schemas/*.schema.json | xargs grep -L '"pipeline"'
```

输出应为空 (所有 schema 都含 `"pipeline"`)。若有 schema 缺,补上。

**预期**: 批 1 Claude Code 已先行实现,本步骤应为 no-op 验证。

### 任务 5: 跑 schema 自检

```bash
python _hub/pipelines/lint/schema_selfcheck.py
```

输出必须显示全部 16 个 schema 通过。如不通过,**停止并报告**,不要修复。

### 任务 6: commit + tag

```bash
git add -A
git commit -m "fix: apply STRATUM_SPEC v0.1.1 patches

refs: STRATUM_SPEC §17 Changelog v0.1.1

变更:
- substrate.webpage: authors_or_site → site_name + authors
- 核验所有 schema 的 ingested_by 含 'pipeline'
- 同步 SPEC 文档 (§5.1 §5.2 §5.4 §16 §17)

无破坏性变更,与 v0.0.1 数据兼容 (本批未入数据)。
"
git tag v0.0.2
```

不要 `git push`。

---

## Acceptance Criteria

| AC | 验证 |
|----|------|
| AC1 | `cat _hub/STRATUM_SPEC.md \| head -1` = `# STRATUM_SPEC v0.1.1` |
| AC1.5 | `grep -c "_helios-platform" README.md` = 0 且 `grep -c "STRATUM/" README.md` = 0 (大写不存在) |
| AC2 | `grep -c "authors_or_site" _hub/schemas/substrate.webpage.schema.json` = 0 |
| AC3 | `grep -c "site_name" _hub/schemas/substrate.webpage.schema.json` ≥ 1 |
| AC4 | `python _hub/pipelines/lint/schema_selfcheck.py` 全部通过 |
| AC5 | `git tag` 显示 `v0.0.2` |
| AC6 | `git status` 干净 |

如任一 AC 失败,**完整报告,不要假装通过**。

---

## 不需要做的事

- 不要修改其他 schema (只 webpage 一个变了)
- 不要修改 example 中除 webpage 之外的内容
- 不要新增 schema
- 不要修改目录结构

---

**End of STRATUM_PATCH_v0.1_to_v0.1.1.md**
