# 决策日志映射表（账本合并 · 裁决 3）· 2026-07-22

> **问题**：历史线曾有**两本决策日志各自从 D 号起编**，号段重叠——① KU 线 `DECISIONS.md`（D-001..D-023）② 治理线 `HISTORY-VIDEO-OWNER-PLAN-001.md` 附录 D（D-023..D-032）。`D-023`..`D-027` 在两本里**指不同决策**（如 D-024 = KU 无 / OP『Arc 命名』；D-023 = KU『F1 撤 cf』 / OP『闸口顾问化』）。
> **合并（裁决 3）**：**不重排既有正文号**（避免改动已被 commit 引用的号），改用**命名空间前缀 + 指针化 + 曾用号**：
> - **`KU-Dxxx`** = KU 线（canonical 正文在 `DECISIONS.md`，契约/gold/fixtures 层）。
> - **`OP-Dxxx`** = 治理线（canonical 正文在 OWNER-PLAN 附录 D，全权委托后的治理/管线/抽取器层）。
> - 正文内的裸 `D-xxx` **曾用号**保留原样（不改字节），语义以本表 + 前缀为准。今后新决策一律带前缀入册。

## 命名空间与指针

| 命名空间 | canonical 正文 | 号段 | 层 |
|---|---|---|---|
| `KU-D001..KU-D023` | `docs/history/DECISIONS.md` | D-001..D-023 | 契约形状 / gold 判定 / fixtures / 校验尺子 |
| `OP-D023..OP-D032` | `docs/history/HISTORY-VIDEO-OWNER-PLAN-001.md#附录-D` | D-023..D-032 | 治理（闸口顾问化）/ Arc·Thesis / 语料管线 / 抽取器 |

## 碰撞区解消（D-023..D-027 · 曾用号 → 双义）

| 曾用号 | KU 线（KU-Dxxx） | 治理线（OP-Dxxx） |
|---|---|---|
| D-023 | **KU-D023** F1 撤 cf:jinyang-independence + 契约 v0.2.2 + U7 关闭 | **OP-D023** 闸口顾问化（Wiki 闸口→顾问裁决+Wiki 终否决权） |
| D-024 | —（KU 线无 D-024） | **OP-D024** 主题簇命名定为 Arc（弧） |
| D-025 | —（KU 线无 D-025） | **OP-D025** Arc/Thesis 为仓内 schema，不进查询契约 |
| D-026 | —（KU 线无 D-026） | **OP-D026** 抽取器云端 API 默认禁 |
| D-027 | —（KU 线无 D-027） | **OP-D027** 现代考订论点自撰摘述+出处，原文不入语料层 |

> KU 线正文到 D-023 为止（其后 W-H1a 的追加以**扩写既有条目**方式并入 KU-D019/KU-D022，无新号——见 DECISIONS.md 内『W-H1a-2 追加』标注）。治理线独占 D-024 及以后。故除 D-023 外无真双义正文，D-024..D-027 仅治理线有正文。

## 治理线全表（OP-D023..D-032 · 指针至 OWNER-PLAN 附录 D）

OP-D023 闸口顾问化 · OP-D024 Arc 命名 · OP-D025 Arc/Thesis 仓内 · OP-D026 云端禁 · OP-D027 现代考订不入库 · **OP-D028 canonical_date 永不由抽取器产出** · **OP-D029 抽取器定型 qwen3-8b·半自动偏自动** · **OP-D030 抽验门全关(F12修/F8/F10)** · **OP-D031 年数cf追认成立** · **OP-D032 舒州/徐州地名variant** · OP-D033 在库源机核100%口径+豁免 · OP-D034 PERSON-INTAKE协议 · **OP-D035 决策原话须在FULL AUTO块内** · **OP-D036 P1出口判据重定域(同一性/全自动移P2)** · **OP-D037 语料主路径改zhwikisource dump** · **OP-D038 PERSON-INTAKE修订** · **OP-D039 外部阻塞归因必附证据** · **OP-D040 P1终裁PASS(GATE-P1)** · **OP-D041 intake转正逐条** · **OP-D042 P2出口判据(5项)** · **OP-D043 存在性核查必以main+tags为据(工作树/分支视野不作证据)** · **OP-D044 dump收口水经注/苏秦策入库锚定·PENDING清零·两"无源"误归因证伪(OP-D-039类)** · **OP-D045 thesis"无对立论点"必附检索记录(默认无对立=未查)** · **OP-D046 我方论点evidence缺环不得转正·补齐自动转正** · **OP-D047 chore分支合流授权(D-018三步·aii内容不审查)** · **OP-D048 事件晋级须locator锚定·PENDING缓转钉定即自动转正** · **OP-D049 MINERU合流保留追认·DEBT-3销账(conformance+delta在册)** · **OP-D050 我方论点任mainline则同题源内论点必入并陈(s4叔向首例)** · **OP-D051 EpisodePlan四点裁(双轨beats/一子簇一集可并拆/counterpoint非装饰/P3扩现有v0.3)** · **OP-D052 策展包同格四件为②判据口径·s6/s7补齐前②PENDING** · **OP-D053 P2终裁(①②③⑤封档·④唯一未达·G1b PASS当轮自动收口·门不二次重定域)** · **OP-D054 extract未晋级候选(~121事件+person备查)定性原料池·pull消费·不入回归网** · **OP-D055 P3图纸=HEVI-N0-DUALAGENT-SPEC-001(hevi侧·CC-A verbatim入仓)·试点集s1曲沃代翼** · **OP-D056 指令交付物未附视为未交付·停等为正确行为(P3图纸CC-A案例)** · **OP-D057 s1 counterpoint裁决(史墨嫁接判装饰否决·s1显式无对立论点·消解MAPPING-DRAFT/CURATION矛盾)** · **OP-D058 裁决署名格式统一为"顾问Claude(经Wiki授权,裁决见对话记录)"·执行方不得追认未做出判断** · **OP-D059 新会话开工须核视野(branch+main+tags)·合流后分支归位main为收尾动作** · **GATE-P2 cut(2026-07-24,`docs/signoffs/GATE-P2-20260724.md`,判定人=顾问Claude)** · **OP-D060 阶段状态以签字工件为唯一真理源·OWNER-PLAN总表为派生视图·每次GATE cut后同轮刷新(总表滞留P1而立)** · **OP-D061 结构性可比案检索不得仅依关键词·须含同构候选扫描(G3郑伯克段案而立)** · **OP-D062 s1 counterpoint改判thesis:zhengbo-ke-duan(郑伯克段)·shimo否决维持不变** · **OP-D063 corpus/REGISTRY.md为派生视图·每次语料入库同轮刷新(OP-D-060同族)** · **OP-D064 arc成员事件须JSON化(h_event形状,复用契约$defs不新造)·事件层冲突须落正式cf对象·prose-only为过渡态不得跨波次留存(s1两真冲突无schema归宿而立)** · **OP-D065 identity_pipeline相邻事件共享交接角色型假合记为已知限制IDENTITY-DEBT-1·不为单例修改规则·同型3例触发评审·数据不得为消除假合而调整** · **OP-D066 ev:quwo-wugong-mie-yi题名/时间窗收窄至武公伐翼虏哀侯(前709)·终局另立ev:quwo-mie-min-liehou(前678)·id保留不重命名注记沿革** · **OP-D067 结构化字段值必须有原文字面依据·按在位区间/常识/推理填入的具体id一律不建·原文保留于account(per:jin-ehou无依据推定+per:zhou-huanwang误填两案而立)** · **OP-D068 跨仓术语须附来源仓与含义·查无即报不得推测对齐(H4=hevi侧R-hard第四门"名从注册表"·stratum查无·CC-B正确报查无而立；追认per:referent-ambiguous适配H4无需调整)** · **OP-D069 身份不明角色位以哨兵占位表达·不删除结构化条目(宁冗余不误删)·占位不得用于本可查实而未查者**。

> **OP-D028~032 状态（W-H1a-5）**：Wiki 逐字权威文本已下达（FULL AUTO 块内，OP-D035）；**渲染稿作废、标曾用留痕**（OWNER-PLAN 附录 D 头）。⚠ 权威 D-028~032 语义与渲染稿号位不同（如权威 D-030=抽验门全关，渲染 D-030=语料库现实）——以权威为准。

## KU 线全表（KU-D001..D023 · 指针至 DECISIONS.md）

KU-D001 契约冻结 v0.1 · D002 G1b 钉点 tag · D003 F2 签署+fixtures-v0.1 · D004 扩展批 Tier1 · D005 source.genre 取(A) · D006 契约 v0.2(place) · D007 F14 三附加 · D008 剩余批次规则 · D009 tag 追认+PENDING-GATE 总则 · D010 抽验补课 · D011 工时口径四段 · D012 actor GAP · D013 DEBT-4 解耦 · D014 F2 真签 GATE 工件 · D015 校验尺子 · D016 agent 分钟=运营单位 · D017 hint 不得私裁 · D018 m0 拆弹 · D019 Gap 批(+年数 cf 追认) · D020 契约 v0.2.1 · D021 跨线通知总则 · D022 抽验裁决(+抽验门全关) · D023 F1 撤 cf+v0.2.2+U7。

> **今后**：新决策带命名空间前缀（KU-Dxxx / OP-Dxxx）入册，不再裸号；本表随新增维护。**曾用号不改字节**（历史 commit 引用稳定）。
