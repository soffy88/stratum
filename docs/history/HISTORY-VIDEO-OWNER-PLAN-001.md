# HISTORY-VIDEO-OWNER-PLAN-001

## 中国历史深度视频库 · 全权执行计划 v1.0

| 项 | 值 |
|---|---|
| 目标（Wiki 原话锚定） | B 线：stratum 拉中国历史书 → 抽 KU → 聚为主题簇；A 线：hevi 以簇为基础自动生成视频。深度要求：非原文照搬（范例：从晋国建国挖衰亡原因）。发表不着急，先全链稳定出片 |
| 授权 | Wiki 2026-07-22 全权委托顾问实现，方式自决，不回问 |
| 治理（D-023） | 全部 Wiki 闸口转为**顾问裁决 + Wiki 终否决权**，签字工件格式不变（decided_by = 顾问 Claude·Wiki 全权授权 2026-07-22）；每阶段末一页汇报，只报不问；Wiki 仅保留 CC↔顾问 转发通道。决策日志由顾问随本文维护（附录 D） |

---

## 1. 关键路径 P0–P4

| 阶段 | 内容 | 出口判据 | 状态 | 据 |
|---|---|---|---|---|
| **P0 收尾** | 在途件清账：F1 撤 cf + U7 关闭 + 契约 tag 沿革（已令）；F10+F8 尾段补送裁决；MinerU conformance 汇报对账；G1b 重跑（等 tag） | 案头零 PENDING；G1b 全弧闭 | **闭**（G1b PASS） | `docs/signoffs/GATE-P2-20260724.md`（判据④） |
| **P1 W-H1a 开灌** | 首弧牵引书目入语料层（ARC-SPEC §4）；既有 25 fixtures 的 para_ulid 回填；全部引文机核（终结"凭记忆备录"）；抽取器选型协议实测定型；自动抽取首跑对回归网验收 | 语料在库可寻址；引文机核 100%；抽取器 P/R 过基线且回归网零倒退 | **PASS** | `docs/signoffs/GATE-P1-20260722.md` |
| **P2 首弧策展** | 晋国衰亡弧手工策展（Arc + 论点层第一次实装，顾问主笔判定）；源内论点入库；子簇→EpisodePlan 映射 | 首弧全对象过 harness；七子簇各有 mainline 论点与并陈记录 | **PASS** | `docs/signoffs/GATE-P2-20260724.md` |
| **P3 双 agent + 批量** | N0 改造 spec 届时出（撰稿 W / 审核 R，硬门机械化：事实句溯 KU、论断句溯 thesis、E-banner、冲突不抹平）；G2 批量 = 晋国衰亡季 | 一集净稿人工分钟 ≤ 阈（P2 实测后定）；批内成本收敛 | **进行中**（CC-A 执行 `HEVI-N0-DUALAGENT-SPEC-001`，试点 s1 曲沃代翼） | 本文附录D `OP-D-055` |
| **P4 发表** | **冻结零设计**。触发条件：连续稳定出片 ≥N 集（N 由 P3 定） | — | 冻结（不变） | — |

> **★状态列以签字工件为唯一真理源，本表为派生视图**（OP-D-060）：每次 GATE cut 后本表须同轮刷新，不得滞留旧状态。

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
- D-045（权威）**thesis 的『无对立论点』结论必附检索记录（库内 theses 全扫 + 源内候选扫）；默认无对立视为未查、不得入册**。本条因 s1 曲沃代翼旧报『无对立论点』实为未查（史墨昭32 无常论在库未扫）而立。落地：s1 补并陈 `thesis:shimo-changbian`（史墨），旧结论作废（矫正一规则）。
- D-046（权威）**我方论点凡 evidence_refs 有缺环（关键源内事实无 ULID 锚）不得转正；缺环补齐自动转正**。落地：`thesis:liji-luandi-b`（诅无畜群公子→卿族坐大）缓转，续搜钉定 `:1454`（左传宣2）后自动转正；`thesis:liji-luandi-a`（源内乱嫡）不受此限即刻准。
- D-047（权威）**`chore/code-review-graph-tooling` 合流授权——按 D-018 三步协议（合流时 `git checkout main -- docs/history tools/history` + `git diff main` 该两目录为空 + `validate_gold.py` 全绿），合流 commit 单列；aii 产品线内容不在本授权审查范围**。因该分支带陈旧 v0.1 docs/history（第二个 m0），三步协议防 clobber main v0.2.2。
- D-048（权威）**事件晋级须 locator 锚定；PENDING-pin 事件缓转、钉定即自动转正**（OP-D-046 同构延伸至事件层）。落地：s5 `ev:fanzhonghang-benqi` 补钉 `:2809`（左传哀5）后自动转正，连带我方论点 `thesis:qiangzhe-jianruo` 缺环补齐自动转正。
- D-049（权威）**MINERU spec 合流保留追认；DEBT-3 完全销账以 conformance + §8.2 delta 处置在册为准，未在册则本仓补执行**。核查：MINERU 文件（合流入 main）conformance 附录 A.1 + A.3（D1–D5 delta 处置）+ §9（白文适用性判定，D3）+ A.5 销账**均在册**；补执行=KU-SPEC 附录 A.3 DEBT-3 行同步刷新为已销（合流取 main 侧致该行未反映 MINERU 侧销账）。DEBT-3 完全销账。
- D-050（权威）**凡我方论点任 mainline 而库内存在直指同题的源内论点者，该源内论点必入并陈**；s4 叔向昭3 为首例。落地：s4 `thesis:qingzu-jianbing`（我方）并陈叔向 `:2209`；s5 `thesis:qiangzhe-jianruo`（我方）并陈史墨 `:2592`（同规则连带适用）。
- D-051（权威）**EpisodePlan 四点裁决**：①字段准——beats 拆 `fact_refs`/`thesis_refs` 双轨；形状为生产 spec EpisodePlan 之**超集、不分叉**。②粒度默认一子簇一集、**可并可拆**；映射**不回写 arc**（arc 只读源）。③throughline/counterpoint 双轨准——**counterpoint 非装饰**：每集至少一次，或附检索记录的**显式无**。④P3 契约方向=**扩现有**（加性 `$defs` + `kind`，bump `contract_version` v0.3），不另立契约。落地：`EPISODEPLAN-MAPPING-DRAFT.md` 按本条修订（仍不实施、schema 不动）。
- D-052（权威）**策展包同格四件（事件 + mainline + 并陈 + 检索记录）为 OP-D-042② 判据口径；s6/s7 补齐前 ② 为 PENDING**。落地：s6/s7 论点层补齐（`ADJUDICATION-s6-s7.md`，事件引既有 gold 不重裁）后，② 达同格四件、转 PASS。
- D-053（权威）**P2 终裁**：①②③⑤ **封档不复审**；④（G1b 全弧闭）为**唯一未达项**。**P2 收口于 G1b 判 PASS 当轮自动生效**，GATE-P2 签字工件届时随裁决 cut。**门不作第二次重定域**（判据即 OP-D-042 五项，不再改口径）。
- D-054（权威）**extract/ 内未晋级候选（约 121 事件 + person 备查项）定性为原料池**，按需被策展**拉取消费（pull 模型）**、不做批量裁决；`is_gold=false` **恒真**，池内项**不入回归网**。
- D-055（权威）**P3 图纸 = `HEVI-N0-DUALAGENT-SPEC-001`**（**hevi 侧落仓**，P3 开工时由 **CC-A 执行 verbatim 入仓**，本仓不写 hevi）；**试点集 = s1 曲沃代翼**。
- D-044（CC-B 执行·据 dump 决策树预授权）**dump 收口两残留：水经注/苏秦策入库锚定，PENDING 清零；两条『无开放白文』结论证伪（OP-D-039 类）**。① dump 已完成（6.92GB，非上波所记 ~11%——ETA 结论无证据入档，实测推翻）。② **F18 水经注**：dump mainspace `水經注/35`（江水三）纯白文（郦道元古本非点校本，R5-clean），新建 `corpus/shuijingzhu.json`（substrate `YMVZ9FHEMJTEF77GB9PJ9D826Z`），锚 F18 `ac:chibi-p-shuijingzhu`（赤壁山/烏林/蒲圻縣治段）。③ **F14 苏秦策**：dump `戰國策 (士禮居叢書本)/秦/一` 白文，鮑本/姚本注封于 `{{*|…}}` 模板、**剥模板得纯白文（零注-leak 实测）**，R5-clean；`corpus/zhanguoce.json` +para 秦策一，锚 F14 `ac:sujin-zhanguoce`（该 account genre 仍降权、锚定不改证据权）。④ **R5 遵守**：两源皆入库**古本/剥注纯白文**、无点校本、无 ctext 越界（wikisource mainspace 即备，ctext 仅作过程佐证未入库）。⑤ **误归因纠正**：F18『node 未定位』实为未搜 mainspace；F14『仅注本 R5 禁』实为 ingest_raw 抓取清单从未含秦/燕策——皆 OP-D-039 所立"无证据不得入 BLOCKED"之复现，已纠。⑥ harness `ALL GREEN`（56/56 机核、7 corpus/5487 段、para_ulid 零悬空）；OP-D-040 遗留债"水经注/苏秦策 2 account 待 dump"**销**。契约 sample 未动（非 §8 契约、无 tag bump）；fixtures 字节变（F14/F18 加 locator 锚，gold 判定未改）打 `history-fixtures-v0.3.2` 留痕。
- D-056（权威）**凡指令宣称"已备好/见上面文件"的交付物，发令轮必须实附文件；未附视为未交付，执行方停等为正确行为**。本条因 P3 图纸（`HEVI-N0-DUALAGENT-SPEC-001`）宣称已备而未附、CC-A 正确停等而立。
- D-057（权威）**s1 counterpoint 裁决**——史墨昭公三十二年（前 510）晚于曲沃代翼二百余年、所论为六卿期，嫁接作 s1 对立论点判为**装饰**（违 OP-D-051③），**否决**；s1 判为**显式无对立论点**并附检索记录。`MAPPING-DRAFT` 与 `CURATION-s1-s2` 的不一致由本裁消解。判定人=顾问 Claude（经 Wiki 授权，提案来自 CC-A）。
- D-058（权威）**裁决署名格式统一为"顾问 Claude（经 Wiki 授权，裁决见对话记录）"**；不得以执行方（CC-A/CC-B）名义追认其未做出的判断。
- D-059（权威）**新会话开工前须核视野（branch + origin/main + tags），核毕方执行；合流/切换后工作分支归位 main 为收尾动作**。本条因合流后分支未归位、新会话在偏离分支上核查得零命中而立。
- D-060（权威）**阶段状态以签字工件为唯一真理源；OWNER-PLAN 总表为派生视图，每次 GATE cut 后同轮刷新**。本条因总表滞留 P1（P2/P0 已 PASS/闭多轮，表头仍显 P1"本轮启动"）而立。落地：§1 总表加"据"列、P0–P4 状态随 GATE-P1/GATE-P2 刷新（本轮同步执行）。
- D-061（权威）**结构性可比案的检索不得仅依关键词——论点同构判定为必需步骤；OP-D-045 检索记录须含"同构候选扫描"一项**。本条因 G3（s1 补料）关键词层扫描『大宗/小宗/贰宗/侧室/支庶/本大末小』查无独立对照对象、而结构判定层（叙事骨架比对，非关键词）扫描查有郑伯克段于鄢（同题异国结构对照）而立——两层扫描口径不同、结论不同，关键词层单独检索不足以支撑"确无对照"之诚实结论。
- D-062（权威）**s1 counterpoint 由"显式无"（OP-D-057 临时状态）改判为 `thesis:zhengbo-ke-duan`（郑伯克段于鄢，同期同题结构对照）；`thesis:shimo-changbian` 否决维持不变（OP-D-057 未变）**。落地：`arc-jin-decline.json` 新立 `thesis:zhengbo-ke-duan`（源内，祭仲谏语，左传 `:0004`/`:0012`–`:0014`），`thesis:shifu-modabizhe.counter_refs` 由 `[thesis:shimo-changbian]` 改 `[thesis:zhengbo-ke-duan]`；`EPISODEPLAN-MAPPING-DRAFT.md` s1 counterpoint 同步刷新。
- D-063（权威）**`corpus/REGISTRY.md` 为派生视图，每次语料入库同轮刷新**（OP-D-060 同族）。本条因该表滞留 W-H1a-1 首波逐段 WebFetch 快照（6 substrate·16 段·881 字）、D-037 起 zhwikisource dump 已令左传/史记/资治通鉴/三国志转全量（合计 7 substrate·5487 段·446659 字）而未同步刷新而立。落地：REGISTRY.md 本轮按 corpus/*.json 实测重算（本轮同步执行）。
- D-064（权威）**arc 成员事件须 JSON 化（h_event 形状，复用 gold-bundle/契约 $defs，不新造 schema）；事件层冲突须落正式 cf 对象；prose-only 记录为过渡态，不得跨波次留存**。本条因 s1 补料两处真冲突（谱系弟/子、册命范围）当轮无 schema 归宿、只能 prose 记录而立。落地：`arc/events/s1-quwo.json` 新建（s1 全 7 member + 1 外部对照事件的 h_event/h_account/h_conflict 对象）；`cf:egou-di-vs-zi`（dimension=actor）/`cf:cebming-fanwei`（dimension=narrative）正式落地；`tools/history/validate_gold.py` 新增第 9 项校验（arc/events/*.json 对 gold-bundle.schema.json + registry + 束内闭合）；`tools/history/identity_pipeline.py::load_events()` 扩展读取 arc/events/；seeds/persons.json+places.json+forces.json 新增 26 条注册（人 17/地 8/势力 1）。**弧灌注副产品发现**：结构化 `ev:quwo-wugong-mie-yi` 时核实其唯一锚点（左传:0217）实指"武公伐翼虏哀侯"（前709），非既往题旨所称"灭翼代晋"终局——题目/时间窗本轮更正收窄，member_event_refs 顺序相应调整，终局另立新事件 `ev:quwo-mie-min-liehou`（前678，承接原 G1 account）。
