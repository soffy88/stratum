# Stratum

Wiki 的本地知识库系统。

## 这是什么

按 [STRATUM_SPEC v0.1](_hub/STRATUM_SPEC.md) 设计的三层 + Hub 结构知识库:

- **substrate/** — 原始素材 (书 / 论文 / 网页快照 / 字幕 / 对话存档)
- **concepts/** — 概念图谱 (人物 / 事件 / 定理 / 技术 / 地点)
- **notes/** — 笔记 (ADR / 复盘 / 读书笔记 / 想法 / 日记)
- **_hub/** — 协调层 (schema / 索引 / 流水线 / 接口)

## 当前状态

**v0.0.1 (批 1 完成)**: 立宪期。schema 和目录骨架就绪,流水线和接口尚未实现。

下一步: 批 2 实证 → 批 3 流水线 MVP → 批 4 接口层 → 批 5 验收 → v1.0

## 快速开始

(批 3 之前不可用,见 [STRATUM_SPEC §13](_hub/STRATUM_SPEC.md))

## 重要约定

- 所有改动可追溯到 STRATUM_SPEC 某条款
- schema 升级需走 migration 流水线 (批 3+)
- AI 生成内容必须带 `draft: true` 标记直到 Wiki review

## 仓库结构

详见 [STRATUM_SPEC §3.1](_hub/STRATUM_SPEC.md)

## 给 Claude Code 的提示

在本仓库内工作时:
1. 必读 `_hub/STRATUM_SPEC.md` 全文
2. 任何写入操作必须遵守 schema (见 `_hub/schemas/`)
3. 不直接修改 substrate (原始素材层不可变)
4. 改 schema 必须走 migration 流水线 (尚未实现, v0.0.x 期间不允许改 schema)