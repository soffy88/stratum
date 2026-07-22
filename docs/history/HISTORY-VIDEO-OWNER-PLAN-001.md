# HISTORY-VIDEO-OWNER-PLAN-001

## 中国历史深度视频库 · 全权执行计划 v1.0

| 项 | 值 |
|---|---|
| 目标（Wiki 原话锚定） | B 线：stratum 拉中国历史书 → 抽 KU → 聚为主题簇；A 线：hevi 以簇为基础自动生成视频。深度要求：非原文照搬（范例：从晋国建国挖衰亡原因）。发表不着急，先全链稳定出片 |
| 授权 | Wiki 2026-07-22 全权委托顾问实现，方式自决，不回问 |
| 治理（D-023） | 全部 Wiki 闸口转为**顾问裁决 + Wiki 终否决权**，签字工件格式不变（decided_by = 顾问 Claude·Wiki 全权授权 2026-07-22）；每阶段末一页汇报，只报不问；Wiki 仅保留 CC↔顾问 转发通道。决策日志由顾问随本文维护（附录 D） |

---

## 1. 关键路径 P0–P4

| 阶段 | 内容 | 出口判据 | 状态 |
|---|---|---|---|
| **P0 收尾** | 在途件清账：F1 撤 cf + U7 关闭 + 契约 tag 沿革（已令）；F10+F8 尾段补送裁决；MinerU conformance 汇报对账；G1b 重跑（等 tag） | 案头零 PENDING；G1b 全弧闭 | 在途 |
| **P1 W-H1a 开灌** | 首弧牵引书目入语料层（ARC-SPEC §4）；既有 25 fixtures 的 para_ulid 回填；全部引文机核（终结"凭记忆备录"）；抽取器选型协议实测定型；自动抽取首跑对回归网验收 | 语料在库可寻址；引文机核 100%；抽取器 P/R 过基线且回归网零倒退 | **本轮启动** |
| **P2 首弧策展** | 晋国衰亡弧手工策展（Arc + 论点层第一次实装，顾问主笔判定）；源内论点入库；子簇→EpisodePlan 映射 | 首弧全对象过 harness；七子簇各有 mainline 论点与并陈记录 | 待 P1 |
| **P3 双 agent + 批量** | N0 改造 spec 届时出（撰稿 W / 审核 R，硬门机械化：事实句溯 KU、论断句溯 thesis、E-banner、冲突不抹平）；G2 批量 = 晋国衰亡季 | 一集净稿人工分钟 ≤ 阈（P2 实测后定）；批内成本收敛 | 待 P2 |
| **P4 发表** | **冻结零设计**。触发条件：连续稳定出片 ≥N 集（N 由 P3 定） | — | 冻结 |

原则不变：spec 按阶段 just-in-time 出，不预写会被上游学习推翻的文档。

## 2. 风险表（顾问自担监控）

- 抽取器质量不达（左传笔法、经传互文对小模型是硬仗）→ 退路：半自动抽取 + 顾问审加重，P1 出实测再定档
- GPU 争用（Hevi 生成 vs 抽取）→ 错峰调度，抽取批处理夜间跑
- 语料许可（wikisource 标点 CC BY-SA）→ 许可登记 + attribution，R5 纪律不破
- 深度内容的史论风险 → thesis 归属强制 + "史/论可区分"红线（ARC-SPEC §2）

## 附录 D. 决策日志（治理线，命名空间 OP-Dxxx；顾问维护，Wiki 可否决任何一条）

> ★账本合并（裁决3）：本附录号 = **OP-Dxxx**；KU 线（KU-Dxxx）在 `DECISIONS.md`。D-023..D-027 曾与 KU 线号碰撞，解消见 `DECISIONS-LEDGER-MAP.md`。

- D-023 闸口顾问化（本文治理节）
- D-024 主题簇命名定为 **Arc（弧）**，避免与 Stratum 章级 KC 撞名
- D-025 Arc/Thesis 为仓内 schema，不进查询契约；消费面到 P3 才 bump 契约
- D-026 抽取器云端 API 默认禁（Stratum 无云端原则），例外需显式裁决入册
- D-027 现代考订论点以自撰摘述 + 出处登记入 thesis，原文不入语料层（版权）

> ★**D-028～D-032 已权威化（W-H1a-4，2026-07-22）**：经 Wiki 复核采纳，OP-D-028~032 文本**由 CC-B 渲染稿升为权威决策**（不再『待 Wiki 定字』）。**曾用留痕**：本五条初为 CC-B 据 W-H1a-2 指令任务列渲染（『文本我已定』未附逐字时的兜底），Wiki W-H1a-4 复核后采纳为权威；渲染→权威沿革在此留痕。⚠ 若 Wiki 本意为另附逐字文本替换，以后续裁决为准。号段碰撞已由账本合并（裁决3，`DECISIONS-LEDGER-MAP.md`）以命名空间 KU-Dxxx/OP-Dxxx 解消。

- D-028 **抽取器 date 不产出**：抽取器只产 事件/人物/地点/类型，**canonical_date 一律走 chronology 注册表 override**，不由白文抽取（W-H1a-1 实测：小模型编造年份，弑简公判前403实前481）。评测不计 date 字段。
- D-029 **F10 通过 + 抽验门全关 + 年数 cf 追认**：F8/F10/F12 三份抽验门全关（F10 引文改在库原文·史记主语『田氏之徒追执』、弑地舒州/执地徐州入 pl:shuzhou variant）；`cf:jinyang-weicheng-duration`（岁余/三年）追认留存。判定人=顾问 Claude。KU DECISIONS 交叉引本条。
- D-030 **语料库仓内自包含 + 全书全量入库现实**：语料库为**仓内 committed-bytes 可寻址存储**（不走已崩的 DuckDB/PG 生产管线）；R5 白文（wikisource CC BY-SA 逐字、禁点校本）。★『左传/国语/史记全书』verbatim 全量经 WebFetch **不可行**（逐页有损、体量十万字级）——全书需 wikisource dump/bulk 导入（另立工程事项，PENDING）；本波入库=首弧论点+fixtures 高价值被引段（6 书 19 段）。
- D-031 **Qwen3-8B 获取路径 + VRAM 实测**：解代理实为 curl 经 `127.0.0.1:7890` 直连 hf-mirror/hf（W-H1a-1 pull 失败系 ollama 进程未走代理）；路径 = hf GGUF（Qwen3-8B-Q4_K_M 5.03GB）→ `ollama create`。★VRAM 实测本机 **RTX 3080 10GB**（纠记忆 1050Ti）、qwen3-8b 负载 5.5GB used/4.4GB free；按令『装不上 14B 就 8B』取 **8B**（14B Q4 ~9GB 太挤未冒险）。
- D-032 **抽取器定型 = qwen3-8b**：正式评测（12 段 held-out，date 不产出）字段均 **0.94**（vs qwen2.5vl:7b 0.71），title/place/type 达/接近基线。定型为**半自动偏自动**抽取器（产候选经顾问审重入 gold，抽取候选永不直接成 gold）；**全自动**待 ① held-out ≥30 段（本波 12，全书语料 PENDING）② 同一性判定一致率验收。
- D-033 **在库源机核 100% 口径 + 源级豁免清单**（W-H1a-4）：『机核 100%』= 有开放白文源且已入库者被引 account 逐字机核（在库源现 100%）；无开放白文源者**显式豁免**——竹书古本（辑佚无 canonical 白文）、战国策（wikisource 仅注本 R5 禁）；三国志/水经注/国语其余/史记卷65 为 **PENDING 续抓**（有白文，本会话限流受阻）。详 `corpus/SOURCE-MACHINE-CHECK-STATUS.md`。
- D-034 **PERSON-INTAKE 协议**（W-H1a-4）：抽取新人物候选经**机械四查**（(a)实存 (b)泛称黑名单无氏不入 (c)撞名不自动并出 candidate-same (d)批次可回滚）批量入正式注册表（`per:i<批>-NNN`，status=candidate-verified），抽样15+全 candidate-same 送裁。协议 `PERSON-INTAKE-PROTOCOL.md`；首批 W-H1a-4-001 入库 76 条，person 解析率 5%→76%。
