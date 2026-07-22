# AII History KU · Decision Trail

> 跨系统决策留痕（spec §8.3 decision_trail 闭合）。凡影响契约钉点、契约形状、gold 判定范式的决策记于此，逆序（新在上）。

---

## D-015 · 校验尺子立项 + 『全 validate』主张修正 + scratchpad 禁令扩 B 线

- **日期**：2026-07-22 · **决策人**：Wiki（立项）/ CC（落地）
- **★主张修正（诚实入账）**：commit `7ef49d2` 称『18 fixtures 全 validate』——按 README 冻结命令直测**不成立**（fixture 顶层是 gold 包裹格式非契约响应体，additionalProperties 全拒）。2026-07-22 复核：子对象级（events/accounts/conflicts 对契约 $defs）18/18 过、注册表引用零悬空——但该复核脚本自身漏了 `fo:` 前缀（写成 `frc:`），**F10 的 force 引用当时根本没被验过**。两层教训一并入册。
- **落地（平凡批前置件，本 commit）**：① `fixtures/gold-bundle.schema.json`——束格式（events/accounts/conflicts/rejected_alternatives/adjudication 判定元数据），内层 $ref 契约 $defs 零漂移；含 `work_log` 四段工时字段（D-011）与 `kind`(agent/human)。② harness `tools/history/validate_gold.py`——束级 schema + 注册表引用（前缀含 `fo:`）+ 束内引用闭合 + 零下划线键，exit code 硬门。③ README 冻结命令更新。实测：sample VALID + 18/18 ALL GREEN。
- **★scratchpad 禁令扩 B 线（通则）**：验证类脚本**一律入仓**——scratchpad 里的尺子等于没有尺子（本日第三次 scratchpad 吃掉或险些吃掉证据）。A/B 两线同令。
- **影响**：『全 validate』口头主张作废，今后以本 harness 输出为唯一口径；**平凡批开工条件即此尺子入仓**（Wiki 开工令，与抽验补课 D-010 并行）。

## D-014 · F2 收尾包：真签 GATE 工件 + 四行证据定位图 + 否弃项锚点回贴

- **日期**：2026-07-22 · **决策人**：Wiki（签）/ CC（记录）
- **留痕核查结论**：07-21 签署 commit `31c49c0` 仅翻转 `decided_by` 字段——**裁决原文无逐字留痕**，当时入账为 CC 备据承载的裁意、非 Wiki 签字工件。按 Wiki 指令**就地补真签**。
- **落地（一个 commit 全装）**：① 四行证据定位图入 `F2-zhaoshiguer.notes.md`（四冲突 × 两端定位 × indep × presentation，篇级）；② 签字记录升级 **A 线 GATE 工件格式**（被签对象不可变 ref = blob `1d23971`@v0.1/v0.2 同字节 + Wiki 裁决原文逐字引 + 日期）——07-21 之裁**追认**、2026-07-22 **真签**；③ 调和说否弃项回贴锚点 `F2-zhaoshiguer.json:281`（JUDGMENTS#F2 同步）。
- **影响**：F2 签署自此有可校验工件；今后签署一律 GATE 工件格式（被签对象不可变 ref + 裁决原文 + 日期），转述裁意不算签。

## D-013 · DEBT-4 裁定：评测集与候选模型解耦

- **日期**：2026-07-22 · **决策人**：Wiki
- **裁决**：AELLA-KU-EXTRACTOR-EVAL-001 **评测集与候选模型解耦**。框架文档照入仓；其 Aella-Qwen3-14B 段标 **historical**（该模型评估已放弃——29.5GB BF16 无官方量化装不进 9.65GB 卡，硬件现实，非烂尾）；**抽取器候选在 needed-by 时点重选**，本地与 API 皆开放。
- **影响**：DEBT-4 近期**零阻塞**；平凡 gold 兼作评测 easy 段的一鱼两吃（D-008）继续。附录 A.3 DEBT-4 行同步。

## D-012 · actor GAP 处置：追认非阻塞 + 平凡批必含 + 候选钉定

- **日期**：2026-07-22 · **决策人**：Wiki（裁）/ CC（分类判定）
- **裁决**：actor 维未覆盖**追认为非阻塞**（v0.2 tag 条件确未含"全维闭合"）；**平凡批必含 ≥1 个 actor 维 fixture**。
- **候选（Wiki 荐）**：**赵盾/赵穿**（左传·宣公二年）——实弑晋灵公者为赵穿，太史董狐书『赵盾弑其君』，赵盾辩而董狐申义（『子为正卿，亡不越竟，反不讨贼』）。**源内自我申明的归因分歧**，顺带测『书法 vs 事实』子机制。
- **分类（CC 判）**：**难例**——单事件，但源内自带归因分歧 + 书法子机制 + 孔子评语层，非『单事件·单述·零机制』，入难例 30% 份额；不占平凡名额。

## D-011 · 工时口径钉定：D-008 四段 + 分段原则 + ROI 用途

- **日期**：2026-07-22 · **决策人**：Wiki
- **口径**：单 fixture 工时四段按 D-008 原文钉定——**抽取 / 注册表解析 / 判定 / 复核**。
- **原则（入册）**：**分段镜像该工种的真实流水线**。Q5 之『查证/编制/校对/修正』四段属**地图（数学线）工种**；各工种各自 derive 自身分段，**不跨线套用段名**。
- **★附加值**：『抽取』段工时即**将来 LLM 抽取器要替代的部分**——分段账直接喂 **W-H1 自动化 ROI 测算**（人肉抽取分钟数 = 自动化的上限收益）。
- **纪律**：平凡与难例**分账**；工时记录进 fixture 本体 `adjudication.work_log`（gold-bundle schema，D-015），标 `kind`（agent/human）不混计。

## D-010 · v0.2 抽验补课（不豁免）

- **日期**：2026-07-22 · **决策人**：Wiki
- **裁决**：tag 追认（D-009）**不豁免抽验**。从 F5–F13 选 **3 个五裁决未覆盖机制**的 fixture 打包送验：**F12 鸿门宴**（互见互补形态，**必选**）+ **F8 空城计**（按语否定改主线——carrier 三态之『否定』态）+ **F10 田氏代齐**（parent#2 + succession + 似而非同）。
- **包格式**：每份 = gold 要点 + JUDGMENTS 条目 + 原文引文，**Wiki 单份 10 分钟内可读**。落 `fixtures/SPOTCHECK-v0.2.md`。
- **后果预定**：发现实质错 → follow-up commit 修 gold + 打 `history-fixtures-v0.3`；**v0.2 记 known-deficient**（tag 不删、留痕）。

## D-009 · fixtures tag v0.2 追认 + 门槛冲突总则（PENDING-GATE）

- **日期**：2026-07-22 · **决策人**：Wiki
- **裁决**：`history-fixtures-v0.2` tag **(a) 追认**，三件配套：①本条记偏差 ②抽验补课（D-010）③F2 收尾包（D-014）。
- **偏差实录**：tag 打于两个门定义冲突之下——Wiki 门『矩阵齐 + 签署列零待签』 vs D-004 门『Wiki 抽验通过』。**CC 自选了较松的一个、事后报备**（矩阵中『抽验非阻塞 tag』一句系 CC 自判）。
- **★通则升格（A/B 两线统一为总则）**：① **门槛定义冲突取并集（最严），且事前报**，不自选；② **凡门槛含 Wiki 动作而 Wiki 缺席，一律标 `PENDING-GATE`**（与 A 线闸④同款）——不得以任何自判语句替代 Wiki 动作。
- **另（配套追认）**：F15 襄阳记处理**追认**——indep=2 与硬对/可链分层是 testimony/judgment 判分的正确适用；『内容链入物故线、不构成第四独立结局』正是回归网要的分辨率。
- **影响**：v0.2 tag 维持；抽验以补课形式完成（D-010）；今后打 tag 前凡涉 Wiki 门一律 PENDING-GATE 待动作。

## D-008 · 剩余批次（→30–50）构成规则 + 性质切换（设计→产线）

- **日期**：2026-07-22 · **决策人**：Wiki
- **构成规则**：剩余批次**以平凡事件为主体**（建议约 **7:3** 平凡:难例）。**平凡 gold = 单事件 · 单述 · 零机制触发**——回归网需要**假阳性侧的钉子**（全难例 gold 只会训出草木皆兵的判定器）。
- **一鱼两吃**：这批平凡 gold 顺手即 §9 **抽取器评测集的 easy 段**（文言事件抽取的基线）。
- **★性质切换点已到**：前 16（现 18）个是**设计工作**（定机制、钉范式）；后面是**产线工作**——**开始计量单 fixture 工时**（Q5 同款分段：抽取/注册表解析/判定/复核各段计时），**W-H1 灌注预算即指此工时数**。
- **落地**：`CANDIDATES.md` 记此规则；下批起以平凡事件为主、附单 fixture 工时。

## D-007 · F14 追认 D-005(A) + 三条附加（帛书出处 / DEBT-5 / W-H1 苏秦系年政策）

- **日期**：2026-07-22 · **决策人**：Wiki
- **① 帛书注记必带考订出处**：出土文献之反证结论，注记**必须署考据出处**（谁做的考订，如帛书整理小组唐兰等 / 杨宽《战国史》）——考据结论的工程化，**不是本仓自读帛书**。F14 已补。
- **② 开 DEBT-5：出土文献 Source 化**（挂 Q3）——见 spec 附录 A.3 DEBT-5。这是 D-005(B) 的具体承载：Q3 考古/金文/简帛管线落地时，出土文献升一等 Source + 契约 v0.x 扩 `source.genre`。
- **③ ★W-H1 政策（先裁后灌）**：**涉苏秦诸事的 canonical 系年，一律从现代考订（override 表登记 + 出处），史记原系年降为 account `date_claim`**。这是**六国年表 override 政策的第一次大规模适用**——先裁定，免 W-H1 灌注中途撞上。已入 `chronology.json` 苏秦 override + F14 落地。将来涉苏秦/张仪/战国中晚期系年之灌注，按此办。

## D-006 · 契约 v0.1 → v0.2：`h_conflict.dimension` 增 `place` 值

- **日期**：2026-07-22 · **决策人**：Wiki（裁）
- **裁决**：§4.3 `dimension` 枚举**增 `place`**（地望之争）——地望直供 MapState / 标记，是视频产品的切身维度，枚举里原本没有。
- **契约影响**：这是**契约形状变更** → `contract_version` **v0.1 → v0.2**（schema `const` 与 `sample` 同步已改）。变更**加性向后兼容**（旧 v0.1 数据仍合法，`place` 为新增可选值），但按纪律 bump 版本 + 双端同步 + 本 decision trail。
- **落地**：schema `dimension` enum += `place`；`sample.sanjiafenjin.json` `contract_version`→v0.2；README 契约链引 v0.2；新 tag **`history-contract-v0.2`**（旧 `history-contract-v0.1` 保留为 v0.1 钉点，G1b 迁 v0.2）。补 fixture F18 赤壁地望（place 维首例）+ F17 赤壁 causality（causality 维早在枚举、此前无用例，一并补）。
- **G1b**：对拍钉点迁 `history-contract-v0.2`；v0.1→v0.2 差异 = dimension 多 `place`、`contract_version` 值——**可解释差异**。

## D-005 · `source.genre` enum 拍板 = (A) 不改契约；(B) 触发条件定义

- **日期**：2026-07-21
- **决策人**：Wiki（拍板）/ CC（建议 A、记录）
- **裁决**：`source.genre` enum 维持 `{编年|纪传|国别策论|注|辑佚}` **不变——取 (A) aspiration-note**。考古 / 金文 / 经（尚书、利簋、简帛之属）**暂不作一等 Source**。
- **理由**：① 契约 `history-query-response.schema.json` 已冻结、G1b 钉 `history-contract-v0.1`；改 enum＝契约形状变更（bump `contract_version` + 双端同步 + 风险）。② §6 考古 flag 本就 **Q3 远期再接**（先留字段）——当前无 live 需求。③ 现有及将来 fixtures（F9 牧野 / A4 苏秦帛书）以文献 account + `tier_override` 的 E0-候选注记表达，不失真。
- **★(B) 触发条件（明确，免将来再议）**：当 **Q3 考古 / 金文管线真正落地**（有实际简帛/金文源要入库）时，才做 (B) 扩 `source.genre` enum——且作为**一次协调的 v0.2 契约 bump**（`contract_version` → v0.2、README + G1b 双端同步、记 decision trail）。在此之前一律走 (A)。
- **落地**：A4 苏秦帛书（Tier 2）按 (A) 建——帛书《战国纵横家书》作 `tier_override` E0-候选注记，不登记为 Source。
- **与 fixtures gold tag 无关**（重申 D-004）：本裁决只定 enum；`history-fixtures-v0.2` tag 仍待 Wiki 抽验通过再打（契约 tag 与 gold tag 两回事）。

## D-004 · 扩展批 Tier 1 建完（F5–F10）交付抽验

- **日期**：2026-07-21
- **决策人**：CC（交付）/ Wiki（抽验待）
- **内容**：扩展批 Tier 1 六条按 D-003 签署范式建成、判定人 CC（非边界）：F5 宁我负人 / F6 赤壁 / F7 隆中对 / F8 空城计 / F9 牧野克商 / F10 田氏代齐。覆盖机制——carrier/按语**三态**（F3/F5/F7/F8 综合钉死：引书计入 / 按语质疑不改主线 / 按语否定改主线 / 引书+按语裁断）、number（F6）、existence（F7/F8）、纪年override + 考古E0-aspiration（F9）、parent#2 + succession（F10）。
- **状态**：★CC 交付、**Wiki 抽验待**。`JUDGMENTS.md` 回归网登记齐，供抽验。
- **v0.2 tag**：★**暂缓**——待 Wiki 抽验通过再打 `history-fixtures-v0.2`（避免 stable-ref 钉未验证 gold；抽验若改则免移 tag）。
- **关联待决**：F9 牵出 `source.genre` enum 缺『出土/金文/经』类（D3 待决 A/B）——F9 走 **A**（aspiration-note，不改契约）；Tier 2 之 A4 苏秦帛书将再撞，届时未定 B 则同走 A。

## D-003 · F2 赵氏孤儿 gold 签署 + `history-fixtures-v0.1` tag

- **日期**：2026-07-21
- **决策人**：Wiki（亲裁）
- **决策**：F2 边界案（同事异述）gold 判定经 Wiki 亲裁**签署**。F2 全部 `decided_by`（7 处：event.tier_override / event.mainline_decision / 4 conflicts / rejected_alternatives）与 `JUDGMENTS.md#F2` 的"待签"翻为 `Wiki（亲裁·签署 2026-07-21）`。
- **F2 难例范式定稿（4 要素）**：① 史记篇内分裂作归因链首证；② 调和说"两次族诛"否弃项显式在录 + 理由；③ 冲突对象三挂 `presentation_hint=S12`（date/existence/narrative）；④ mainline=左传、异叙 account 全文保留 + genre_note 晚出敷演。**此范式为扩展批（→30–50）非边界 gold 的生产模板**（CC 照此判、Wiki 验收）。
- **落地**：W-H0 四核心 gold（F1–F4）全部冻结，另打 annotated tag **`history-fixtures-v0.1`**（与 `history-contract-v0.1` 并列：前者钉 gold 判定、后者钉 §8 契约形状；二者正交）。
- **影响**：扩展批"不铺开判定"闸门解除——范式已定稿，可按 `fixtures/CANDIDATES.md` 圈选逐条生产 gold。契约形状未变。

## D-002 · G1b 钉点改判：`history-contract-v0.1`（78ae13f）取代 `ab228ab`

- **日期**：2026-07-21
- **决策人**：Wiki
- **改判**：G1b 契约对拍钉点由此前指定的 commit `ab228ab` 改为 annotated tag **`history-contract-v0.1`**（指向 merge commit `78ae13f`，在 main）。`ab228ab` **作废为钉点**，仅存为首个冻结 commit（首冻结留痕，非对拍基准）。
- **原因**：`ab228ab` 之后发生 `_meta` 迁移（commit `9130820`），`contracts/sample.sanjiafenjin.json` 的**落盘字节演进**（移除下划线注释键 + 规整缩进，382 行变更）。G1b 逐字段/字节对拍——若仍钉 `ab228ab`，将对拍迁移前的陈旧 sample 字节。`history-query-response.schema.json` 自 `ab228ab` 起字节未变，仅 sample 演进。
- **为何用 tag 而非 commit hash**：tag 不可变且不惧承载分支（原 `feat/m0-concept-canonical`，及 `feat/history-ku-wh0`）后续 rebase/squash——commit hash 在分支被 squash-merge 后可能变为游离对象。tag 是稳定引用点。
- **落地**：`contracts/README.md` G1b 对拍协议钉点行已写 tag 名（非 hash）。
- **影响**：G1b 仅需改钉 tag 名，无契约形状变更（schema 未动）。

## D-001 · 契约冻结 v0.1

- **日期**：2026-07-21
- **决策人**：Wiki / CC
- **决策**：§8 查询响应契约（`history-query-response.schema.json` + `sample.sanjiafenjin.json`）冻结为 v0.1，tag `history-contract-v0.1`。形状严格取自 spec §3/§4/§8.1，`additionalProperties:false` 全锁。
- **首个冻结 commit**：`ab228ab`（feat 初次入仓）。字节最终态：见 D-002。
- **零下划线约定**：JSON 本体不含 `_`-前缀键，注释迁 `*.notes.md`，committed bytes 原样过 validate（无 strip 预处理）。
- **F2 gold**：见 D-003（已签署冻结）。

---

*格式约定：每条含 日期 / 决策人 / 决策或改判 / 原因 / 落地 / 影响。契约形状变更须同步 `contract_version` 与双端（spec §8.4）。*
