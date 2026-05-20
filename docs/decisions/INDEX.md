# Stratum Decision Records Index

Source: `_source.md` (advisor DECISION_LOG.md, 21 ADRs)
Split: `scripts/split_adr.py`

## ADR 列表

- [ADR-001: 批 2 实证混合模式](ADR-001.md)
- [ADR-002: MCP 框架选 anthropic 官方内置 FastMCP](ADR-002.md)
- [ADR-003: PDF 解析分层策略](ADR-003.md)
- [ADR-004: 向量库选 LanceDB (本地) + pgvector (服务端)](ADR-004.md)
- [ADR-005: Embedding 选 Qwen3-Embedding via DashScope](ADR-005.md)
- [ADR-006: 数据存"用户网盘 + 本地" 架构](ADR-006.md)
- [ADR-007: 平台内容 vs 用户内容分层存储](ADR-007.md)
- [ADR-008: 索引存储方案 C (混合)](ADR-008.md)
- [ADR-009: 国内网盘策略](ADR-009.md)
- [ADR-010: 微信集成边界](ADR-010.md)
- [ADR-011: hevi 作为内容生产引擎](ADR-011.md)
- [ADR-012: 订阅档位](ADR-012.md)
- [ADR-013: SPEC 文档纪律](ADR-013.md)
- [ADR-014: 商业模式 + 团队时间先不考虑](ADR-014.md)
- [ADR-015: 单一产品体验 (不分用户群)](ADR-015.md)
- [ADR-016: 部署全程本地, 商业化阶段单独迁云](ADR-016.md)
- [ADR-017: v1.0 不做 E2EE, v1.x 评估](ADR-017.md)
- [ADR-018: Translation 作为 Stratum 核心能力](ADR-018.md)
- [ADR-019: Stratum 外挂能力架构 — 同 Docker 网络解耦集成](ADR-019.md)
- [ADR-020: Phase 10 async provider 技术债务](ADR-020.md)
- [ADR-021: Stratum 跨机部署拓扑](ADR-021.md)

## 决策依赖关系图

```
ADR-001 (混合实证模式)
  ├── ADR-002 (MCP 框架) ← 实证 #4
  ├── ADR-003 (PDF 解析) ← 实证 #1
  ├── ADR-004 (向量库) ← 实证 #2
  ├── ADR-005 (Embedding) ← 实证 #3
  └── ADR-008 (索引方案 C) ← 实证 #5
       └── ADR-009 (国内网盘) ← 实证 #5

ADR-006 (用户网盘 + 本地)
  ├── ADR-007 (平台 vs 用户分层) ← Wiki 引入内容平台
  ├── ADR-008 (索引方案 C)
  └── ADR-009 (国内网盘)

ADR-010 (微信集成边界) ← 实证 #5
ADR-011 (hevi 内容生产) ← Wiki 校准
  ├── ADR-012 (订阅档位)
  └── [hevi-content-repo 协议需求 v0.1, 待 hevi advisor review]

ADR-013 (文档纪律) ← Wiki 多次强调
ADR-014 (先不考虑商业模式/团队) ← Wiki 校准
  └── ADR-016 (部署全程本地) ← Wiki 锁定边界
ADR-015 (单一产品体验) ← Wiki 校准
ADR-017 (v1.0 不做 E2EE) ← Wiki 校准
ADR-018 (Translation 核心能力, Phase 10) ← hydropix 仓库启发 + Wiki 确认
ADR-019 (外挂能力架构, Phase 11+) ← Wiki 确认 7 个仓库的解耦集成意图
  ├── 跟 ADR-011 (hevi 解耦) 同模式
  ├── ADR-018 是这个架构的第一个应用
  └── 跟 ADR-016 (本地部署) 一致
ADR-020 (Phase 10 async 技术债务) ← Phase 10 Gate 验收发现
  └── Phase 11 启动前必须偿还 → ✅ 已偿还 2026-05-19
ADR-021 (Stratum 跨机部署拓扑) ← Phase 11 启动前置
  ├── 修订 ADR-016 (本地部署 → 三机本地)
  ├── 修订 ADR-019 (同 Docker network → Tailscale mesh)
  └── 6 项 Phase 11 准入条件 (1 ✅ / 5 ⏳)
```

---

## 未决问题汇总 (来自 STRATUM_SPEC v0.5 §18)

### 已 resolved (本次对话末期)
- ~~**Q3**: 服务器部署区域~~ → ADR-016 (Wiki 本地基础设施, 商业化阶段单独迁云)
- ~~**Q8**: E2EE 是否纳入 v1.0~~ → ADR-017 (v1.0 不做, v1.x 评估)

### 仍未决 (按时机紧急程度排)

### 紧急 (Phase 2-3 启动前)
- **Q1**: hevi-content-repo 协议细节 (meta.yaml schema)
  - 状态: 需求草案 v0.1 已成, 待 hevi advisor review
  - 文档: /mnt/user-data/outputs/hevi-stratum-protocol/HEVI_CONTENT_REPO_PROTOCOL_REQUIREMENTS.md
- **Q9**: 内容备案合规细节 (找合规律师)
  - 状态: 待 Wiki 决策时机 (商业化阶段)

### 中期 (Phase 4-9 启动前)
- **Q2**: 阿里云盘开放平台凭证可行性
- **Q4**: 平台内容防盗版强度
- **Q5**: TTS 服务选型

### 长期 (Phase 11-12 启动前)
- **Q6**: 推荐算法 v1.x 升级 (规则 → ML)
- **Q7**: 移动端跨平台 vs 原生
- **Q10**: 公开 API 开放范围

---

**End of Decision Log**
