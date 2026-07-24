# s2 骊姬之乱 · 弧灌注 · 终裁 · 2026-07-24

> **性质**：**终裁**（三事件 full KU 化 + 事件层冲突正式落 cf 对象，均任务显式指名）。判定人=顾问 Claude（Wiki 全权授权）。红线同前。

## 一、三事件 full KU 化

新建 `docs/history/arc/events/s2-liji.json`（格式严格平行 `s1-quwo.json`）：

| event_id | 白文锚（主账户） | canonical_date（精算） | 冲突对象 |
|---|---|---|---|
| `ev:xiangong-qu-liji` | `:0586`（左传庄28） | 前666 | `cf:sanzi-fenju-yuanqi` |
| `ev:liji-zen-shensheng` | `:0719`（左传僖4） | 前656 | `cf:liji-zenci-neirong` |
| `ev:chonger-yiwu-chuben` | `:0719`尾句 + `:0727`（僖5）+ `:0740`（僖6） | 前656–前654 | `cf:erzi-chuben-yuanyou` |

★**canonical_date 精度校正**：`ADJUDICATION-s1-s2.md` 早前 D1 初筛表粗记『前672』『前656』『前655』（仅供候选去重用，非精算）；本轮按标准鲁国纪年（隐722/桓711/庄693/僖659）重算，事件1由前672收窄为**前666**，事件3由前655收窄为**前654**（事件2前656核对无误）——精度校正非重新裁决，claim/题旨字节不改。

★**`ev:chonger-yiwu-chuben` 锚点核实更正**：任务原文将本事件锚定于 `:0740` 单段，核实后 `:0740`（僖6）仅载夷吾自屈改奔梁的后续改道；『重耳奔蒲，夷吾奔屈』的出奔本身实记于 `:0719` 尾句（前656，与事件2同段不同焦点）；重耳自蒲出奔狄的完整经过（士蒍筑城敷衍、寺人披伐蒲、逾垣而走）另见于 `:0727`（僖5，前655）——**OP-D-071 全account白文扫描中发现，`:0740` 仅是本出奔叙事链条的最后一环，非事件全貌唯一锚**，本轮补入 `:0727`，三段账户如实分列（`ac:zuozhuan-chuben-initial` + `ac:zuozhuan-chonger-fenpu` + `ac:zuozhuan-yiwu-zhiliang`），不假装单段覆盖全貌。事件 id/题目沿用不改，时间窗定为区间`前656–前654`。

## 二、OP-D-071 前置扫描（白文提及即入）

三事件全部 account 白文逐字扫描，具名人物/地名一律入 registry（`registry-backfill-005`，registry 净增 33 ids：原始新建人物 27 条中 3 条与既有条目重名〔见下方 §去重事故〕、修正后持久新建人物 24 条 + 地名 6 条 + 势力 3 条 = 33，与 harness 报告 registry 255-222=33 一致）：

**具名新建**（27人，含 :0586/:0719/:0727/:0740 全部具名人物）：`per:jin-xiangong`（晋献公）、`per:qijiang`（齐姜）、`per:qinmu-furen`（秦穆夫人，仅系谱提及非actor）、`per:shensheng`（申生）、`per:huji`（狐姬）、`per:i4-012`＝重耳（沿用既有id，见下）、`per:xiaorongzi`（小戎子）、`per:yiwu`（夷吾）、`per:liji`（骊姬）、`per:xiqi`（奚齐）、`per:zhuozi`（卓子）、`per:liangwu`（梁五）、`per:dongguan-biwu`（东关嬖五）、`per:du-yuankuan`（杜原款）、`per:jiahua`（贾华）、`per:i4-011`＝郤芮（沿用既有id）、`per:shiwei`（士蒍）、`per:shiren-pi`（寺人披）+ 6个 counterpoint 事件人物（卫宣公/夷姜/急子/宣姜/寿子/公子朔）。

**任务指名核查（骊姬/申生/重耳/夷吾/优施/里克/荀息/新城/蒲/屈）**：
- 骊姬/申生/重耳/夷吾/新城/蒲/屈：均在 :0586/:0719/:0740 白文内，已建 registry+actors。
- **里克**（新建 `per:like`）/**荀息**（沿用既有 `per:i4-006`）：均在库（左传闵2 `:0663`／僖2 `:0691`），但均属**下一子簇**（里克弑二君/荀息死节，僖9-10），非本轮 s2 三事件之 actor——**仅 registry 登记，不入本轮 actors**，如实标注非虚构提前。
- **优施**：左传/史记正文均**查无**此名；全 8 corpus 扫描仅命中**左氏博议卷9《衞懿公好鶴》**（`0HA7NN34RNSZ694T5WNT1DXKHJ:0043`，吕祖谦引及"骊姬使优施以言动里克"一节）——如实注记来源为**次级评论引及**、非本仓一手叙事史料，registry 已登记（`per:youshi`），非本轮 actor。

**占位**：`per:referent-ambiguous`（驪戎男，骊戎国君，左传仅称爵位"男"未指名个体）。

**地名新建**（6）：`pl:jia`（贾）、`pl:pu`（蒲）、`pl:qu`（屈）、`pl:xincheng`（新城）、`pl:liang`（梁）、`pl:wey`（卫，counterpoint 用）。
**势力新建**（3）：`fo:lirong`（骊戎）、`fo:di`（狄）、`fo:wey`（卫）。

### ★registry 去重事故与修正（重要，如实报告）

建库过程中，`identity_pipeline.py` 的 person 异名归一检测（candidate-same 链）发现：新建 `per:xirui`（郤芮）、`per:xunxi`（荀息）、`per:chonger`（重耳）与**既有**条目 `per:i4-011`（郤芮=冀芮，W-H1a-4-001 批次，Wiki 已准 candidate-same）、`per:i4-006`（荀息）、`per:i4-012`（重耳=晋文公，Wiki 已准）**完全重名重复**——本轮建库时按 id 列表查重（未见 i4-006/011/012 这类不透名批次 id 对应何名），漏检。**已修正**：删除本轮新建的 3 个重复条目，`s2-liji.json` 全部引用改为既有 id（`per:i4-006`/`per:i4-011`/`per:i4-012`），并为既有条目补充史记侧 attestation（原仅左传单源）与丰满谥字号，**id 沿用不改**（已被 `IDENTITY-PIPELINE-V1.md`/`PERSON-INTAKE-W-H1a-4-001.md`/`CURATION-s1-s2.md`/`ADJUDICATION-s1-s2.md` 多处引用，改名成本高）。修正后 registry 净增 **255-222=33 ids**（27新建人物中3例为既有条目重名而未计入净增，实际新建持久条目：24人+6地+3势=33）。

**决策入册**：**OP-D-075**：registry 回填前必须按**姓名**（names_by_source）全库检索，不能只查 id 列表——即使沿用不透名批次 id（如 `i4-XXX`）的既有条目也可能已覆盖同一人名，需交叉核对；`identity_pipeline.py` 的 person 异名归一检测（candidate-same 链）是此类重复的有效安全网，**建新人物条目后必跑一次核对**。本条因 s2 弧灌注新建人物时 3 例（郤芮/重耳/荀息）与既有 `per:i4-006`/`per:i4-011`/`per:i4-012` 重名而立，已修正（详上）。

## 三、s2 counterpoint（OP-D-045/050/061 检索）

- **库内检索**：现有 thesis 中仅 `thesis:zhengbo-ke-duan` 已用作 s1 counterpoint，不可复用（不重复挂载）。
- **源内关键词检索**：全 8 corpus 扫描『廢適/立庶/譖殺/一國三公』等词，命中骊姬案自身相关段 + 一处结构对照候选。
- **同构候选扫描**（非关键词，按叙事骨架比对）：命中左传桓公十六年 `:0344`（卫宣公烝夷姜生急子、宣姜与公子朔构急子、寿子代死、急子仍被杀）——与骊姬乱嫡结构同题（**嬖宠/庶母谗构嫡子致死**），异国（卫vs晋）异代（桓16前696早于庄28-僖6前666-654约30-42年）。
- **结论**：**有则建**——新立 `thesis:weixuangong-goujizi`，采为 `thesis:liji-luandi-a` 的 counterpoint（同 s1『郑伯克段』先例，非对立而结构对照）；evidence_refs 承载于新建独立事件 `ev:weixuangong-goujizi`（不入 `arc:jin-decline.member_event_refs`，跨国比对素材，非本弧成员）。

## 四、事件层冲突（OP-D-064，正式 cf 对象）

| cf_id | 事件 | 维度 | 真冲突内容 |
|---|---|---|---|
| `cf:sanzi-fenju-yuanqi` | `ev:xiangong-qu-liji` | causality | 左传：骊姬贿梁五/东关嬖五进言分置三公子；史记：边防理由径出献公之口，未见贿赂中间人 |
| `cf:liji-zenci-neirong` | `ev:liji-zen-shensheng` | narrative | 左传谮辞极简（"贼由大子"）；史记详载多层谮语+献公私议废立铺垫场景（左传无）；另补记"六日"/"居二日"天数异文 |
| `cf:erzi-chuben-yuanyou` | `ev:chonger-yiwu-chuben` | causality | 左传：骊姬"皆知之"直接触发出奔；史记：多一层"有人告发→骊姬恐→反谮"环节；"一国三公"之歌左传/史记仅"尨茸/蒙茸"一字异文，非真冲突 |

**诚实核查（申生死法）**：左传"缢于新城"（上吊）vs 史记"自杀于新城"（未指明方式）——经核对，"自杀"与"缢"兼容非冲突，未落 cf，检索记录见 `ev:liji-zen-shensheng.mainline_decision`（OP-D-045 要求的"无冲突亦记录"）。

## 五、identity_pipeline 全库复检

```
$ python3 tools/history/identity_pipeline.py
=== 全样一致率实测 ===
  唯一 gold 事件 N=37
  负例(异事件对): 665/666 正确似而非同 · 假合(false merge)=1
  正例(自述对): 34/37 自识为同事异述 · 保守存疑退化=3
  --- 机械一致率 = 699/703 = 99.43%
  ⚠ 假合明细：ev:quwo-wugong-mie-yi × ev:zhuangbo-lei-fa-yi -> 同事异述（既有 IDENTITY-DEBT-1，非本轮新增）
```

**结论**：一致率 99.43%、假合率 0%（危险方向零失效）与 s2 建库前基线一致——**s2 新增 4 事件（含 counterpoint）未引入任何新假合**，唯一假合案为 s1 既有已知限制（OP-D-065 IDENTITY-DEBT-1），非本轮新增。person 异名归一检测同轮捕获 registry 重复（见 §二 OP-D-075）。

## 六、harness 状态

```
$ python3 tools/history/validate_gold.py
...
arc/events/s2-liji.json: OK
...
--- 25 fixtures · 6 samples · 8 corpus(5615 paras) · 2 arc · 2 event-bundles · registry 255 ids
ALL GREEN
```

## 送裁

三事件 full KU 化 + 事件层冲突正式落 cf 对象 + counterpoint 新立均为**终裁**（任务显式指名，已落地）。方法论弧续办按任务指令**降优先级，本轮不做**。registry-backfill-005 变更清单见 §二；OP-D-075（registry按姓名查重纪律）已入册。
