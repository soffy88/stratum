# STRATUM_PATCH_v0.1.1_to_v0.1.2.md

**任务**: 应用 STRATUM_SPEC v0.1.2 修订
**触发**: chief advisor 决策 — 实证项 #4 跳过手动测试, 直接按"Obsidian 原生兼容"方案走
**执行模式**: Claude Code (半自动, 主要是 SPEC 覆盖)
**前置**: v0.0.2 tag 已就位
**预期产物 tag**: v0.0.3

---

## 变更性质

**仅 SPEC 文档变更**, 无 schema / code 变更。

理由: v0.1 → v0.1.1 → v0.1.2 三个版本所有 schema 都不涉及 wikilink 语法
(schema 管 frontmatter, wikilink 在 markdown 主体)。已交付的 16 个 schema 和
32 个 example 文件**完全不需要修改**。

---

## 任务清单

### 任务 1: 覆盖 STRATUM_SPEC.md

把 `_hub/STRATUM_SPEC.md` 整个文件用 v0.1.2 版本覆盖
(chief advisor 会附上 v0.1.2 markdown 内容)。

### 任务 2: 跑 schema 自检 (确认无回归)

```bash
python _hub/pipelines/lint/schema_selfcheck.py
```

期望输出: 16 个 schema 全部通过。

理由: v0.1.2 不改 schema, 但跑一次自检是好习惯, 确保覆盖 SPEC 不知怎么影响了相关文件。

### 任务 3: 删除已废弃的 experiments/04 分支 (如存在)

```bash
# 检查是否存在
git branch | grep "experiment/04-obsidian-wikilink"

# 如存在, 切回 main 后删除
git checkout main
git branch -D experiment/04-obsidian-wikilink 2>/dev/null || true
```

理由: v0.1.2 通过架构决策解除了实证项 #4 的风险, 不再需要那个分支。
如果分支不存在 (Wiki 没跑实证), 这步是 no-op。

### 任务 4: 在 main 上 commit + tag

```bash
git checkout main  # 确保在 main
git add -A
git commit -m "fix: STRATUM_SPEC v0.1.2 - Obsidian-native wikilink decision

refs: STRATUM_SPEC §4.3 §14.3 §17 Changelog v0.1.2

核心变更:
- wikilink 语法改为 Obsidian 原生兼容: [[<slug>__<ULID-suffix>|display]]
- 段落锚点改用 ## para-<suffix> heading 形式 (原 <a id> 废弃)
- 实证项 #4 (Obsidian 兼容性) 通过架构调整解除, 跳过手动测试
- 批 2 实证项从 6 个减少到 4 个, 节省 2 天

无 schema/code 变更, 仅 SPEC 文档修订。
"
git tag v0.0.3
```

不要 `git push`。

---

## Acceptance Criteria

| AC | 验证 |
|----|------|
| AC1 | `head -1 _hub/STRATUM_SPEC.md` = `# STRATUM_SPEC v0.1.2` |
| AC2 | `grep -c "Obsidian 原生兼容" _hub/STRATUM_SPEC.md` ≥ 1 |
| AC3 | `grep -c "扩展 wikilink" _hub/STRATUM_SPEC.md` ≤ 3 (只允许出现在 changelog 和 §14.3 的"已解除"上下文里) |
| AC4 | `python _hub/pipelines/lint/schema_selfcheck.py` 全部通过 (16/16) |
| AC5 | `git tag` 显示 `v0.0.3` |
| AC6 | `git status` 干净 |
| AC7 | 当前分支是 `main` |
| AC8 | `git log --oneline -3` 显示 v0.0.1 / v0.0.2 / v0.0.3 三个 commit 链 |

---

## 不需要做的事

- 不要修改任何 schema 文件
- 不要修改任何 example 文件
- 不要修改 README (除非里面提到了"扩展 wikilink 语法", 那一处改成"Obsidian 原生 wikilink")
- 不要修改 .gitignore / .gitattributes / pyproject.toml

---

## 任务末尾报告

```
## v0.1.2 patch 完工报告

| AC | 状态 | 备注 |
|----|------|------|
| AC1 | ✅/❌ | ... |
| ... | ... | ... |

### SPEC 反馈
[如有发现新的 SPEC 不一致, 累积到这里]

### 不确定项
[需要 chief advisor 决定的事]
```

---

**End of STRATUM_PATCH_v0.1.1_to_v0.1.2.md**
