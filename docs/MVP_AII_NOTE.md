# AII Note MVP — 范围冻结（v1.0）

> 日期：2026-07-29  
> 一句话总控：**可迁移的 Markdown 知识库 + 英文资料自动消化 + 新知识自动补到旧页**  
> 产品域名：`aiinote.com`（aegis-caddy:8086 → aii-web）

---

## 1. 必须交付（MVP 核心）

| 模块 | 必须交付 |
|------|----------|
| **数据主权** | Markdown + YAML 导出；可选本地文件夹 / 用户网盘作主存储；删除即真删 |
| **Ingest** | PDF / 网页 URL / RSS / 本地 Markdown 入库；PDF 用 Docling（保留表格+代码） |
| **AI 加工** | 英文→中文翻译；单篇摘要；阅读伙伴问答（**带出处**） |
| **知识生长** | 新资料自动提取概念/人物/公司/主题，并**补充到已有页面**（非只建孤立笔记） |
| **检索** | BM25 + 向量混合；结果带来源定位 |
| **基础图谱** | 概念节点 + 关联资料；反向链接 / wikilink |
| **稳定性** | 真实入库通；核心 Agent 不再 501；主链路可每天用 |

## 2. 明确后置（不做进 MVP）

- 完整桌面端原生 App  
- 复杂多 Agent 编排平台 / 工作流画布  
- 企业协作、权限、多租户精细管控  
- 音频朗读、插图生成高优先级（可留开关，不阻塞主路径）  
- 完美 Git 全历史（先做文件级变更记录即可）  
- 对外智能客服 / 脱敏开放  

## 3. 成功标准（验收）

用户可以：

1. 上传英文 PDF 或粘贴网页 → 自动翻译 + 摘要  
2. 问「这个观点和以前哪些材料有关」→ 得到**带出处**的回答  
3. 看到某概念/人物页面被新资料**自动补充**  
4. 一键导出整个知识库为可迁移的 **Markdown 文件夹**  

## 4. 数据流（自我生长闭环）

```
源材料 (PDF/URL/RSS/MD)
    → Ingest（解析 / raw / substrate）
    → Extract Agent（概念·人物·公司·判断·待办 + 锚点）
    → Link & Merge Agent（新建 / 追加 / 矛盾标记 → 写回知识页）
    → Index（BM25 + 向量 + 图谱边）
    → 可查询（阅读伙伴 / 搜索 / 图谱 / 早报）
```

原则：

- 人只负责投喂与最终判断  
- AI 负责提取 → 关联 → 写回  
- **原始材料永远保留**，总结不能覆盖原文  

## 5. Agent 职责（MVP）

| Agent | 优先级 | 职责 |
|-------|--------|------|
| Ingest Worker | P0 | 解析、存 raw + metadata |
| Translation Worker | P0 | 英→中，保留结构 |
| Extract Agent | P0 | 抽概念/实体/判断/待办 |
| Link & Merge Agent | P0 | 匹配已有页并追加 |
| Reading Companion | P0 | 检索+生成，强制出处 |
| Lint Bot | P1 | 孤立页/矛盾/缺失关联 |
| Daily/Weekly Digest | P1 | 简报写回 |
| Skill Compiler | P2 | 后置 |

## 6. 执行节奏

| 周次 | 目标 |
|------|------|
| **1–2** | 入库阻塞清零；Translation + Extract + Reading Companion 真实可跑；Docling 接入 |
| **3–4** | Link & Merge 上线；混合检索带来源；Markdown 完整导出 |
| **5–6** | 本地/网盘同步最小版；Lint + 简单日报；主链路测试与稳定性 |

## 7. 与现仓对照（差距快照 2026-07-29）

| MVP 项 | 现仓状态 | 缺口 |
|--------|----------|------|
| PG + pgvector 主库 | ✅ stratum → aii-postgres | 残留 DuckDB 引用（abuse/search 遗留） |
| substrate / inbox / feeds | ✅ 有 routers | 入库可观测性、失败原因要硬化 |
| 翻译 Worker | ⚠️ agents 有 translation_worker | 需确认每日主路径稳定、非 stub |
| Reading Companion | ⚠️ 已挂 Agent-class | 强制出处 + 锚点未验收 |
| Extract / Link&Merge | ⚠️ AII 飞轮/B仓有抽取；Stratum concepts 偏 CRUD | **P0 缺口**：统一到「补旧页」闭环 |
| BM25+向量 | ⚠️ retrieval/search 有实现 | 统一 corpus/user 隔离 + 段落锚点 |
| Markdown 导出 | ⚠️ export/md_export 存在 | 非整库可迁移包 + YAML 规范未定死 |
| 网盘同步 | ⚠️ folder_watch / gdrive 脚本 | 用户级最小可用未产品化 |
| Docling PDF | ❌ 未切默认 | OCR/旧解析仍主路径 |
| 真删 | ⚠️ soft_delete 为主 | 需「删除即真删」策略与同步 |
| 康奈尔/B仓 | ✅ 旁路能力 | **不阻塞 MVP**；可作增强，非验收阻塞 |
| 音频/插图 | 后置 | 符合 MVP |

## 8. 周 1–2 开工包（可感知进展）

1. **入库阻塞清零**：schema 对齐、失败可观测、集成测试「上传→substrate 有记录」  
2. **Docling 接入 PDF**（表格+代码保留），失败回退可观测  
3. **Translation Worker** 主路径 E2E 绿  
4. **Extract Agent** 产出结构化 JSON + 锚点并落库  
5. **Reading Companion** 回答必须带 `sources[]` 出处  

---

*本文件为 MVP 范围权威文档。范围变更需显式改本文件版本号。*
