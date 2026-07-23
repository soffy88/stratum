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

> ★**D-028～D-032 权威文本（W-H1a-5，2026-07-22，Wiki 逐字于 FULL AUTO 块内下达）**。**曾用留痕**：W-H1a-2/4 曾由 CC-B 渲染 D-028~032（『文本我已定』当时未在块内附逐字，OP-D-035 即因此立）；**渲染稿作废、以下逐字为权威**。渲染稿承载的事实（语料库仓内自包含、Qwen3-8B 获取/VRAM 实测）未随号消失，正文仍在 `corpus/SOURCE-MACHINE-CHECK-STATUS.md`（语料/dump）与 `arc/EXTRACTOR-SELECTION-W-H1a.md`（Qwen3/VRAM），只是不再占 OP-D 号。

- D-028（权威）**canonical_date 永不由抽取器产出**：一律 chronology 注册表查表/override（三模型编年实证，W-H1a-1）。
- D-029（权威）**抽取器定型 qwen3-8b**（字段均 0.94），档位 = **半自动偏自动**；全自动门 = 注册表解析率稳定 + 同一性判定一致率验收。
- D-030（权威）**抽验门全关**——F12 实质错已修（v0.3）/ F8 通过 / F10 通过；判定人 = 顾问 Claude（Wiki 授权，D-022/D-023）。
- D-031（权威）**cf:jinyang-weicheng-duration（岁余/三年）追认成立**——通则 a 下同指涉真冲突。
- D-032（权威）**舒州/徐州为地名 variant**（音近通假同地，双写署源）；『弑地/执地环节』读法降备注。
- D-033 **在库源机核 100% 口径 + 源级豁免清单**（W-H1a-4）：『机核 100%』= 有开放白文源且已入库者被引 account 逐字机核（在库源现 100%）；无开放白文源者**显式豁免**——竹书古本（辑佚无 canonical 白文）、战国策（wikisource 仅注本 R5 禁）；三国志/水经注/国语其余/史记卷65 为 **PENDING 续抓**（有白文，本会话限流受阻）。详 `corpus/SOURCE-MACHINE-CHECK-STATUS.md`。
- D-034 **PERSON-INTAKE 协议**（W-H1a-4）：抽取新人物候选经**机械四查**（(a)实存 (b)泛称黑名单无氏不入 (c)撞名不自动并出 candidate-same (d)批次可回滚）批量入正式注册表（`per:i<批>-NNN`，status=candidate-verified），抽样15+全 candidate-same 送裁。协议 `PERSON-INTAKE-PROTOCOL.md`；首批 W-H1a-4-001 入库 76 条，person 解析率 5%→76%。
- D-035（权威）**凡指令引用的决策原话必须置于 FULL AUTO 块内**；块外文字视为未传达。本条即因块外原话未达而立。
- D-036（权威）**P1 出口判据重定域**——『同一性判定一致率』与『全自动放行』移为 **P2 入口件**；**P1 出口 = 语料在库可寻址 + 在库源机核 100%（豁免清单显式）+ 抽取器定型（半自动档）+ 100 新事件送裁 + 回归网零倒退 + PERSON-INTAKE 运转**。理由：同一性管线属 P2 建设内容。
- D-037（权威）**语料获取主路径改 zhwikisource dump**（一次下载全站白文，根除限流），raw 逐页降为补充。
- D-038（权威）**PERSON-INTAKE 修订**——黑名单匹配前 opencc 繁简归一；无名单称（X氏类）不作独立 person，标 referent-ambiguous；批内异名归一不由四查承担，归 P2 同一性管线；本批 76 维持 candidate-verified。
- D-039（权威）**外部阻塞归因必附证据**（HTTP 状态码 + 响应首行 + 重试记录）；无证据的『限流/网络不通』类结论不得入 BLOCKED。本条因两次误归因（ollama 代理、卷号 404 误读限流）而立。
- D-040（权威）**P1 终裁 PASS**，签字工件见 `docs/signoffs/GATE-P1-20260722.md`；P0 残项（F1/U7/契约 tag/G1b 重跑）并入 P2 首波补执行。
- D-041（权威）**PERSON-INTAKE 71 条维持 candidate-verified**；转正逐条发生于同一性管线通过之后，不整批转。
- D-042（权威）**P2 出口判据** = ①同一性管线一致率实测报数且回归网零倒退 ②七子簇策展包全数过裁 ③首弧全对象 harness 绿 ④G1b 全弧闭（P0 残项）⑤子簇→EpisodePlan 映射草案成文（契约 bump 仍留 P3，D-025 不变）。
- D-043（权威）**核查任何『已执行/未执行』论断必以 main 与 annotated tags 为据，工作树与分支视野不得作为存在性证据**；本条因工具分支视野差点误报失单而立。**落地**：执行状态核查一律对 `main` + tags（`git ls-tree main`/`git show main:<path>`/只读 worktree），禁以当前 checkout 工作树为据；与 m0 陈旧字节（D-018）、五波"tag 未动"失单误判同族——分支视野差是该族病的共因。
- D-044（CC-B 执行·据 dump 决策树预授权）**dump 收口两残留：水经注/苏秦策入库锚定，PENDING 清零；两条『无开放白文』结论证伪（OP-D-039 类）**。① dump 已完成（6.92GB，非上波所记 ~11%——ETA 结论无证据入档，实测推翻）。② **F18 水经注**：dump mainspace `水經注/35`（江水三）纯白文（郦道元古本非点校本，R5-clean），新建 `corpus/shuijingzhu.json`（substrate `YMVZ9FHEMJTEF77GB9PJ9D826Z`），锚 F18 `ac:chibi-p-shuijingzhu`（赤壁山/烏林/蒲圻縣治段）。③ **F14 苏秦策**：dump `戰國策 (士禮居叢書本)/秦/一` 白文，鮑本/姚本注封于 `{{*|…}}` 模板、**剥模板得纯白文（零注-leak 实测）**，R5-clean；`corpus/zhanguoce.json` +para 秦策一，锚 F14 `ac:sujin-zhanguoce`（该 account genre 仍降权、锚定不改证据权）。④ **R5 遵守**：两源皆入库**古本/剥注纯白文**、无点校本、无 ctext 越界（wikisource mainspace 即备，ctext 仅作过程佐证未入库）。⑤ **误归因纠正**：F18『node 未定位』实为未搜 mainspace；F14『仅注本 R5 禁』实为 ingest_raw 抓取清单从未含秦/燕策——皆 OP-D-039 所立"无证据不得入 BLOCKED"之复现，已纠。⑥ harness `ALL GREEN`（56/56 机核、7 corpus/5487 段、para_ulid 零悬空）；OP-D-040 遗留债"水经注/苏秦策 2 account 待 dump"**销**。契约 sample 未动（非 §8 契约、无 tag bump）；fixtures 字节变（F14/F18 加 locator 锚，gold 判定未改）打 `history-fixtures-v0.3.2` 留痕。
