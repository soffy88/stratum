# s1 曲沃代翼 · 补料终裁记录（G1–G3 落地 + 4 事件 cand→KU + thesis:zhengbo-ke-duan 新立）· 2026-07-24

> 判定人=顾问 Claude（Wiki 全权授权，逐字裁决在 FULL AUTO 块内）。裁决落 `arc/arc-jin-decline.json`（member_event_refs + theses）。承接 `arc/CURATION-s1-supplement.md`（候选送裁件）与 `arc/ADJUDICATION-s1-s2.md`（既有 2 KU 事件、同一格式）。

## 一、4 事件晋级（cand→KU 转正，id 去 `cand:` 前缀正式化）

| KU 事件 | D1 时间窗 | D2 主体集 | D3 地点 | D4 事理骨架 | 白文锚 | 同一性 |
|---|---|---|---|---|---|---|
| `ev:zhuangbo-shi-xiaohou`（庄伯弑孝侯于翼，翼人立鄂侯） | 惠王中期，介于 s1 两既有 KU（前745 / 前716–679，后者经 OP-D-066 更正为前709，见下）之间 | 曲沃庄伯 / 晋孝侯 / 鄂侯 | 翼 | 弑君·新君拥立 | `4YW6S9BRHDQVDGZDYXH2E8Z7HE:0207`（左传，主）+ 史记 `3EX2FF5S4Q1M0K27M27QVNWEYH:0013`（佐） | 似而非同（对 s1 既有 2 KU 及全 25 gold：D1 区间不重合、D2 主体不交、D4 型异于分封/伐翼灭国） |
| `ev:zhuangbo-lei-fa-yi`（庄伯累次伐翼：逐翼侯奔隨 / 曲沃叛王败退，晋人历次拥立鄂侯·哀侯） | 同上区间，**内部排序未完全对齐（见下"诚实标注·冲突未平滑"）** | 曲沃庄伯 / 周平王 / 虢公 / 鄂侯（卒）/ 哀侯 | 翼 / 曲沃 / 隨 | 战役·反复拥立 | `…:0083`+`…:0086`+`…:0097`（左传，主）+ 史记 `…:0015`（佐） | 似而非同（同上理由） |
| `ev:wugong-you-sha-xiaozihou`（曲沃武公诱杀晋小子侯） | 同上区间 | 曲沃武公 / 晋小子侯 | 曲沃 / 翼 | 诱杀 | `…:0262`（左传，主）+ 史记 `…:0018` 前半（佐） | 似而非同 |
| `ev:huanwang-ming-min`（周桓王命虢仲立晋哀侯弟缗于晋，武公退保曲沃） | 同上区间 | 周桓王 / 虢仲 / 晋侯缗 / 曲沃武公 | 曲沃 / 晋 | 王命废立 | `…:0270`（左传，主）+ 史记 `…:0018` 后半（佐） | 似而非同（D4：王命废立型，异于 `ev:quwo-wugong-mie-yi` 之伐翼灭国型，虽同含武公） |

**同一性判读**：4 事件两两之间、对 s1 既有 2 KU、对全部 25 gold 事件，D1（年代区间不重合）/D2（主体集不交）/D4（事理骨架型异）均判**似而非同**——无假合风险。手工核对 `identity_pipeline.py::propose()` 现行规则逐条对表（4 事件缺 canonical_date/actors 结构化字段，未达脚本喂入最小 shape，同 `ADJUDICATION-s1-s2.md` 先例"本裁只固 id+锚+归属"）。

## 二、诚实标注·冲突未平滑（不作 cf: 正式对象——事件层未建结构化 JSON，无 schema 归宿，此处 prose 显式记录、留后续弧灌注建 cf:）

### （一）`ev:zhuangbo-lei-fa-yi` 内部排序/谱系分歧

- **左传**：`:0207`『莊伯伐翼，弒孝侯。翼人立**其弟**鄂侯。鄂侯**生**哀侯。』——鄂侯 = 孝侯之**弟**，哀侯 = 鄂侯之**子**。
- **史记**：`:0013`『莊伯弒其君晉孝侯于翼……晉人復立**孝侯子**郄爲君，是爲鄂侯。』——鄂侯 = 孝侯之**子**（非弟）。
- **真冲突，非精粗差**：两源对"鄂侯与孝侯的血缘关系"（弟 vs 子）给出**互斥**断言，非同一事实的详略差异——性质同 `cf:jinyang-weicheng-duration`（岁余 vs 三年）通则 a："同指涉对齐前置"下的真分歧。
- **另**：左传 `:0083`（庄伯以郑人邢人伐翼，翼侯奔隨）/`:0086`（曲沃叛王，王命虢公伐曲沃，立哀侯于翼）/`:0097`（迎晋侯于隨纳诸鄂称鄂侯）三段，与史记 `:0015`（庄伯闻鄂侯卒兴兵伐晋、周平王使虢公伐庄伯、庄伯败退、晋人立哀侯）**叙事顺序/触发因果未逐年互证对齐**——左传三段是否对应史记单段所述"鄂侯卒方伐"这一因果链，本裁**未能坐实**。
- **处置（宁碎片，不调和）**：本条**不判定**鄂侯与孝侯的确切血缘关系、**不判定**左传三段与史记单段的精确因果对应，作为**候选 `cf:zhuangbo-lei-fa-yi-xishi`（拟建，dimension=date/genealogy 复合，待事件层结构化 JSON 建立时正式落 `conflict_id`/`account_refs`/`independence_analysis`）**转正随行——**转正入 KU 不代表分歧已消解**，事件层灌注时须显式带此 cf，不得择一方坐实（如既往 D-017"hint 不得私裁"同一纪律）。**★正式落地更名**：弧灌注（OP-D-064，本文档 §五）实际建为 `cf:egou-di-vs-zi`（dimension=actor，非本处拟名 `cf:zhuangbo-lei-fa-yi-xishi`/dimension=date/genealogy——结构化时判定该分歧本质是"行动者身份"而非"日期"，dimension 改归 actor 更准确），见 `arc/events/s1-quwo.json`。

### （二）册命两阶段/军制分歧（`ev:quwo-wugong-mie-yi` 的账户层，非新建独立事件）

- **左传** `:0500`『王使虢公命曲沃伯**以一軍**爲晉侯。』——紧邻"同盟于幽"（庄16年，前678，标准编年）年份簇，**推定同期**（前678 前后）。
- **史记** `:0020`『釐王命曲沃武公爲晉君，**列爲諸侯**，於是**盡併晉地而有之**。』——同为周王正式承认武公为晋君，但**不载"一军"编制限定**，反强调完整兼并。
- **判读**：两段年代邻近（同期或同一事件），**核心分歧在"承认的范围/编制"**——左传暗示有限度承认（"以一军"，编制受限的降格待遇），史记径叙全兼并无保留。**未能坐实二者是否同一次册命事件的不同侧写、抑或先后两次册命**（先"一军"限定承认、后正式全兼并）——**本裁不强行判定为两阶段、也不判定为同一事件的详略差**，如实并存。
- **处置**：G1 account `ac:shiji-wugong-huilu-mingzhu`（挂 `ev:quwo-wugong-mie-yi`）与新增 `ac:zuozhuan-yijun-mingjin`（左传 `:0500`）**并存、不合并**；候选冲突对象 `cf:wugong-mingjin-fanwei`（拟建，dimension=number/scope，"一军" vs "尽并晋地"编制范围分歧）待事件层结构化时正式落地。**★正式落地更名+改挂**：弧灌注实际建为 `cf:cebming-fanwei`（dimension=narrative，非本处拟名 `cf:wugong-mingjin-fanwei`/number），且改挂新立事件 `ev:quwo-mie-min-liehou`（非本处所写 `ev:quwo-wugong-mie-yi`——该事件经 OP-D-066 核实题旨收窄为"虏哀侯"，不再承载册命终局，G1 account 随之改挂），见 `arc/events/s1-quwo.json`。

> **本节纪律**：两处分歧均**如实入注，不平滑、不择一坐实**——与 `identity_pipeline.py` §5"宁碎片"、`cf:jinyang-weicheng-duration` 通则 a"同指涉对齐前置"一致。`cf:*` 正式 JSON 对象需要事件层 `conflicts`/`accounts` 数组（`arc-thesis.schema.json` 现无此层，事件对象本身未结构化）——待"弧灌注"阶段（`ADJUDICATION-s1-s2.md` 用语）建立事件 JSON 后补建，本裁只把冲突**存在性**钉入文档、不遗漏、不等到灌注才想起。

## 三、thesis 新立与修订

- **`thesis:zhengbo-ke-duan`（新立，源内，祭仲谏语，左传 `:0004`/`:0012`–`:0014`）**：见 `arc-jin-decline.json` 新增对象。充 s1 counterpoint（OP-D-062）。
- **`thesis:shifu-modabizhe` 修订**：① `attribution.locator.quote` 补全宗法层级前件（G3 account 落地方式——同段全量引用，非新增引证）；② `counter_refs` 由 `[thesis:shimo-changbian]` 改 `[thesis:zhengbo-ke-duan]`（shimo 否决维持 OP-D-057 不变，只是不复留在 counter_refs——之前"记入 counter_refs 以固关联"的暂存处置作废，改为正式移出、由 zhengbo-ke-duan 顶替）；③ 检索记录按 OP-D-061 补"同构候选扫描"一项。

## 四、诚实标注（总）

- 4 事件转正只入 `member_event_refs`（id + 锚 + 归属）；事件层 full KU 对象（actors/places/canonical_date 结构化 + 上节两 cf 的正式落地）随后续弧灌注补全，本裁不建。
- G3 `ac:zhengbo-ke-duan-jishi` 同理——郑事不入 `arc:jin-decline` 之 member_event（跨国比对素材，非弧内成员），evidence_refs 用此 informal id 占位，事件层对象留后续（如需正式独立弧再建）。
- `corpus/REGISTRY.md` 已按 OP-D-063 刷新至实测（另见该文件本轮编辑）。
- harness `validate_gold.py` **ALL GREEN**（25 fixtures · 6 samples · 7 corpus/5487 段 · 1 arc · registry 190 ids）——`arc-jin-decline.json` 改动通过 schema 校验，回归网零倒退。

## 五、弧灌注追记（OP-D-064，2026-07-24 同日后续）

> 本节因 OP-D-064 立而补——上节"未做的事"（4 事件未 JSON 化、2 处冲突未落正式 cf）本轮全部落地，见 `arc/events/s1-quwo.json`。

- **事件层 JSON 化**：s1 全 7 member 事件（含既有 `ev:quwo-feng-huanshu`/`ev:quwo-wugong-mie-yi`，此前二者亦未结构化）+ 1 外部对照事件 `ev:zhengbo-ke-duan`，共 8 事件、11 账户、2 冲突，落 `arc/events/s1-quwo.json`（复用 gold-bundle.schema.json 顶层形状，内层 $ref 契约 h_event/h_account/h_conflict，不新造 schema）。
- **registry 新增 26 条**（人 17 / 地 8 / 势力 1，seeds/persons.json+places.json+forces.json）——s1 全体角色此前从未入注册表（含既有 2 KU 的师服/桓叔/栾宾/武公/翼侯/韩万/梁弘，一并补齐）。
- **正式 cf 对象落地**：
  - `cf:egou-di-vs-zi`（dimension=actor）：鄂侯与孝侯血缘关系，左传『弟』vs 史记『子』，indep=2（两传世系统各执一词），S12 并陈不坐实。
  - `cf:cebming-fanwei`（dimension=narrative）：册命范围，左传『一军为晋侯』vs 史记『尽并晋地』，indep=2；顾问候选解释（编制/领土非互斥）已如实注记为候选、未采信为 mainline 依据。
- **★重大发现（结构化副产品）**：为 `ev:quwo-wugong-mie-yi` 填 canonical_date 时，核实其唯一白文锚（左传:0217）地名『汾隰』与史记『虏哀侯』段之『汾旁』相合，确认该事件实指**武公伐翼虏获哀侯（前709）**，非既往（`ADJUDICATION-s1-s2.md`，2026-07-23）所定题旨"武公灭翼·代晋"之终局——终局（灭缗、赂宝器受命列诸侯，前678）另立为新事件 `ev:quwo-mie-min-liehou`，原挂靠该既有事件的 G1 account（`ac:shiji-wugong-huilu-mingzhu`）随之改挂新事件。**id 不动、题目与时间窗注记更正**（成本考量，见该事件 mainline_decision）；member_event_refs 顺序同轮调整（`ev:quwo-wugong-mie-yi` 前移至 `ev:zhuangbo-lei-fa-yi` 与 `ev:wugong-you-sha-xiaozihou` 之间）。
- **identity_pipeline.py 本体复核**（`load_events()` 扩展读取 `arc/events/`，非手工）：
  - 全样 N=33（gold 25 + 本轮新增 8）：机械一致率 **557/561 = 99.29%**。
  - **假合 1 处（`IDENTITY-DEBT-1`，OP-D-065 命名入册）**：`ev:quwo-wugong-mie-yi` × `ev:zhuangbo-lei-fa-yi` 被误判『同事异述』——归因：两事件共享行动者 `per:jin-aihou`（哀侯，先被庄伯一系拥立、后被武公所虏，是两事件的天然"交接点"角色）+ 事件类型均"战役" + 标题词重合（"伐翼"）+ canonical_date 因 `zhuangbo-lei-fa-yi` 用 `range` 类型致年窗宽泛重合——四项凑巧同时触发 D1/D2/D4 判准。**复核结论：两事件实为独立**（一为晋人拥立哀侯前的庄伯多次征伐、一为武公其后虏获哀侯，非同一事件重述），不合并、`member_event_refs` 维持两条独立记录。本发现印证 §5"假合率 0%"红线的价值——机械规则对"相邻事件共享交接角色"这类边界情形有已知盲区，属管线局限的诚实记录，非本次转正出错。**★处置（OP-D-065）**：记为已知限制 `IDENTITY-DEBT-1`（"相邻事件共享交接角色"型假合），**不为本单例修改 `propose()` 规则**；同型假合累计满 3 例方触发规则修订评审；**数据（事件 actors/canonical_date 等）不得为消除本假合而调整**——本事件的 actors/date 如实反映史料，不得因迁就管线而窄化或篡改。
  - 正例自识 30/33，退化 3（`ev:jin-gongshi-bei`/`ev:kongchengji`/`ev:yaoshun-shanrang`，与既往报告一致，非本轮新增，无纪年/actor 特征之保守退化）。
- **`tools/history/validate_gold.py` 扩第 9 项**：`arc/events/*.json` 对 gold-bundle.schema.json + registry 零悬空 + 束内闭合 + para_ulid 语料库解析，纳入常规 harness（此前该目录不存在、无校验路径）。
- harness **ALL GREEN**（本轮）：25 fixtures · 6 samples · 7 corpus/5487 段 · 1 arc · **1 event-bundle**(8 事件/11 账户/2 冲突) · registry **216** ids（190+26）。
