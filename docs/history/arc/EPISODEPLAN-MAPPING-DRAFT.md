# 子簇 → EpisodePlan 映射草案（P2 出口件⑤ · OP-D-042⑤）· 2026-07-23

> **性质**：**草案送裁、不实施**。契约 bump 仍留 **P3**（D-025：Arc/Thesis 仓内对象、不进查询契约；EpisodePlan 系下游视频制作消费对象）。本件只钉『弧对象如何喂 EpisodePlan』的字段映射 + 消费形状提案，供 Wiki 裁映射范式，**不改任何 schema、不动 G1b 钉点**。判定人=顾问 Claude（Wiki 全权授权）。

## 一、EpisodePlan 拟议字段（下游，P3 落地）

一弧 → 一集或一季（ARC-SPEC §2）；一子簇（sub_arc）→ 一集（episode）或一段（segment）。拟议 EpisodePlan 形状：

| EpisodePlan 字段 | 语义 | 上游来源（弧对象） |
|---|---|---|
| `episode_id` | 集标识 | `sub_arc_id`（如 `arc:jin-decline/s2-liji` → `ep:jin-decline-s2`） |
| `title` | 集标题 | `sub_arc.title` |
| `time_window` | 集时间跨度 | 成员事件 canonical_date 包络（min–max） |
| `throughline_thesis` | 主线论点（贯串旁白） | 子簇 mainline `thesis_ref`（如 s1=shifu-modabizhe / s2=liji-luandi-a） |
| `counterpoint_theses[]` | 并陈/异框架（对照段） | mainline thesis 之 `counter_refs`（如 s1 并陈 shimo-changbian） |
| `beats[]` | 分镜/叙事拍 | 有序拍；**★双轨（OP-D-051①）**：每 beat 拆 `fact_refs`（事件轴）+ `thesis_refs`（论点轴），二轨独立 |
| `beats[].fact_refs[]` | 史实轴（事件拍） | `member_event_refs`（每事件 → ≥1 beat） |
| `beats[].thesis_refs[]` | 论点轴（旁白/对照拍） | throughline/counterpoint thesis（史/论可区分落到 beat 级 R10） |
| `beats[].evidence_spans[]` | 旁白引文（逐字白文） | 事件/thesis 锚 `para_ulid` → 语料库白文 span（R5 逐字，透传素材标 genre） |
| `beats[].mapstate_cues[]` | 地图状态提示 | 事件 `place_refs`（dimension=place 冲突→并陈两说，D-006/D-017） |
| `beats[].conflict_callouts[]` | 冲突角标（S12 并陈） | 事件 `conflicts`（cf:*，presentation_hint=S12） |

> **★形状约束（OP-D-051①）**：本 EpisodePlan 形状为**生产 spec EpisodePlan 之超集、不分叉**——仓内映射产物是生产字段的超集（多带溯源/双轨/检索记录元数据），生产端取子集消费，二者同名同义、不另立平行形状。
| `provenance` | 集级溯源指纹 | 成员 KU 内容指纹集（SHA-256，KU-SPEC §226；升版不追溯已发布集） |

## 二、子簇 → EpisodePlan 映射范式（以已终裁 s1/s2 为例）

- **s1 曲沃代翼** → `ep:jin-decline-s1`：throughline=`thesis:shifu-modabizhe`（师服『末大必折』预言，locator.quote 已补宗法层级前件）；counterpoint=`thesis:zhengbo-ke-duan`（郑伯克段于鄢，同题异国结构对照，OP-D-062；`thesis:shimo-changbian` 否决维持 OP-D-057 不变）。

  **★终态拍序（8 拍，弧灌注 + 灌注收尾后，OP-D-064/065/066，`arc/events/s1-quwo.json`）· `STATUS=READY-FOR-RELAY`**：

  | # | 拍 | 事件/来源 | 白文锚 | 备注 |
  |---|---|---|---|---|
  | 1 | 封桓叔+师服宗法公理 | `ev:quwo-feng-huanshu`（前745） | `…:0205` | throughline 起点；宗法公理句可独立旁白 |
  | 2 | 庄伯弑孝侯立鄂侯 | `ev:zhuangbo-shi-xiaohou`（前725） | `…:0207`+史记`…:0013` | 鄂侯/孝侯血缘弟·子真冲突 `cf:egou-di-vs-zi`，S12并陈 |
  | 3 | 庄伯累次伐翼/晋人历次拥立 | `ev:zhuangbo-lei-fa-yi`（前718起） | `…:0083/:0086/:0097`+史记`…:0015` | 内部排序未逐年互证，如实注记；与拍 4 曾误判"同事异述"（假合，`IDENTITY-DEBT-1`，OP-D-065）已复核排除，见 `ADJUDICATION-s1-supplement.md` §五 |
  | 4 | 武公伐翼虏哀侯 | `ev:quwo-wugong-mie-yi`（前709，OP-D-066 题旨/时间窗收窄追认） | `…:0217` | ★非"灭翼代晋"终局——原题旨误置已更正，本拍不承载终局叙事 |
  | 5 | 武公诱杀小子侯 | `ev:wugong-you-sha-xiaozihou`（前705） | `…:0262` | — |
  | 6 | 曲沃灭翼/桓王命缗立 | `ev:huanwang-ming-min`（前704） | `…:0267`+`…:0270` | 灭翼(春)+立缗(冬)同年两幕合一拍 |
  | 7 | 武公灭缗受命列诸侯 | `ev:quwo-mie-min-liehou`（前678，新立，OP-D-066） | 史记`…:0020`（`ac:shiji-wugong-huilu-mingzhu`） | throughline 收官；册命范围与左传`…:0500`"一军"分歧 `cf:cebming-fanwei`，S12并陈 |
  | 8（side-panel，非 member_event） | counterpoint：郑伯克段于鄢 | `thesis:zhengbo-ke-duan` | `…:0004`+`…:0012`–`:0014` | 结构对照拍、插于集内对照段（不占正片时间轴顺位，供 CC-A 按叙事节奏自定插入点——建议紧邻拍3或拍4后，呼应"支庶尾大不掉"主题峰值） |

  证据链逐字白文 span；无 place 冲突。终裁见 `ADJUDICATION-s1-supplement.md`（2026-07-24，4 事件转正 + 弧灌注 §五 + 灌注收尾追记）+ `arc/events/s1-quwo.json`（弧灌注：7 member 事件 JSON 化 + 2 正式 cf + identity_pipeline.py 复核）。
- **s2 骊姬之乱** → `ep:jin-decline-s2`：throughline=`thesis:liji-luandi-a`（源内乱嫡）；副线=`thesis:liji-luandi-b`（我方『诅无畜群公子→卿族坐大』，:1454 keystone）；beats=[娶骊姬(:0586)→谮杀申生缢新城(:0719)→二公子出奔(:0740)→诅无畜群公子(:1454)]；异名归一（郤芮=冀芮）供人物标注一致。

> **★s1 counterpoint 沿革（OP-D-057→OP-D-062，2026-07-24）**：原稿 counterpoint=`thesis:shimo-changbian`（史墨『物生有两』无常论，昭公三十二年〔前 510〕）经复核为**嫁接误植**——史墨所论时代为晋六卿坐大期（对应本弧 s3+），距曲沃代翼（前 745–前 678 一线）逾两百年，非同题异框架、系装饰性并陈（违 OP-D-051③"counterpoint 非装饰"），**否决维持不变**；`thesis:shimo-changbian` 改列 **arc 级 / s3+ 在题位置**（六卿期子簇落地时另行编入其 counterpoint，非 s1）。**矛盾来源**：`arc/CURATION-s1-s2.md`（s1 原已标『无对立论点（师服说为主流）』，2026-07-22）与旧稿（曾标 `thesis:shimo-changbian`，源自 OP-D-045 补并陈）互不一致，OP-D-057 曾以『显式无对立论点』暂消解。**OP-D-062 further 更正（2026-07-24，G3 补料后）**：『显式无』系 OP-D-061 所立"同构候选扫描"规则出台**前**的关键词层面检索结论；补做同构候选扫描后发现郑伯克段于鄢（同题异国结构对照），s1 counterpoint 由『显式无』改判为 `thesis:zhengbo-ke-duan`——非取代 OP-D-057（shimo 否决维持不变），是补上"显式无"阶段之后的新证据。

> **★粒度（OP-D-051②）**：默认**一子簇一集**（sub_arc → episode），**可并可拆**（多子簇合一集 / 一子簇拆多段，按叙事需要）；映射**只读 arc、不回写**（arc 是权威源，EpisodePlan 是下游派生）。
> **映射不变式**：① 一 beat 至少一条逐字白文 evidence_span（无锚不成拍——OP-D-046 精神下推至消费层）；② thesis 分 throughline/counterpoint 双轨（史/论可区分 R10 落到 beat 级）；③ place 冲突→并陈两说不私裁（D-017）；④ **★counterpoint 非装饰（OP-D-051③）**：每集 counterpoint **至少出现一次**，或**附检索记录的显式无**（『已扫库+源、确无同题异框架论点』），不得静默省略。

## 三、arc 消费形状提案（P3 契约面，本波不实施）

**★方向已裁（OP-D-051④）= 扩现有、不另立契约**：P3 落地时**扩 `history-query-response.schema.json`**（**加性 `$defs`**：arc/episode 响应 $def + beat 双轨 $def；响应体加 `kind` 判别 event/arc/episode），**bump `contract_version` v0.2 → v0.3**（一次协调：schema + sample + README + G1b 双端 sha256 同步 + decision trail，走 D-006 同款流程）。**不新立平行契约**（避免双契约漂移）。**在此之前一律仓内 `arc-thesis.schema.json` 承载、不进查询契约**（D-025 不变，bump 仍留 P3）。

## 四、送裁点 → **已裁（OP-D-051，2026-07-23）**

| # | 送裁点 | 裁决（OP-D-051 逐字权威） |
|---|---|---|
| ① | EpisodePlan 字段拟议准否 | **准**——beats 拆 `fact_refs`/`thesis_refs` 双轨；形状为生产 spec EpisodePlan 超集、不分叉。 |
| ② | 子簇→集 粒度 | **默认一子簇一集、可并可拆；映射不回写 arc。** |
| ③ | throughline/counterpoint 双轨范式 | **准**——counterpoint 非装饰：每集至少一次，或附检索记录的显式无。 |
| ④ | P3 契约方向 | **扩现有**（加性 `$defs` + `kind`，bump v0.3），不另立契约。 |

> 本草案已按 OP-D-051 修订上文（§一双轨字段 + §二粒度 + §三扩现有 v0.3 + §不变式 counterpoint 非装饰）。**仍不实施、不写代码、不动 schema**（契约 bump 留 P3，D-025 不变）。

## 五、跨仓交付清单（hevi 侧待更正——本仓不写，随本文档交付供 CC-A 重排）

> **边界**：本仓（stratum）不写 hevi 工作树，只列清单转发（同 hevi↔stratum 边界规矩）。以下条目由 CC-A 在 hevi 侧核实并更正。

- **回溯核查范围声明**：本仓（stratum）不持有、不可访问 hevi 工作树（边界规矩），故下述"N0 净稿含混叙句"一节**转述自任务指令方给出的信息，非本仓独立核实**——stratum 侧已穷尽本仓内可查范围（`arc/`、`docs/history/` 全目录 grep，见上文各处更正），未在**本仓**内找到"驱逐翼侯于汾隰，最终灭晋大宗，受周王册命"字样的独立文档。若该句确实存在于 hevi 侧 N0 试点 s1 净稿（如指令方所述），则待更正点如下（供 CC-A 在 hevi 侧自行核实字面后处置）：`ev:quwo-wugong-mie-yi` 的旧题旨（"曲沃武公灭翼·代晋"，混叙"伐翼虏哀侯"与"灭缗受命列诸侯"两桩事件为一句）与该混叙句同构——若净稿确有此句，系将本弧第 4 拍（虏哀侯，前709）与第 7 拍（灭缗受命，前678）两桩独立事件的叙事要素合并为一句，与 stratum 侧本轮更正（OP-D-066）后的 8 拍终态不符。
- **待更正点**（供 CC-A 核实）：
  1. 净稿中"驱逐翼侯于汾隰"句后紧接"最终灭晋大宗，受周王册命"——**应拆为两拍**：前者对应本文档拍 4（`ev:quwo-wugong-mie-yi`，前709，虏哀侯，非终局），后者对应拍 7（`ev:quwo-mie-min-liehou`，前678，灭缗受命列诸侯，隔约 31 年）。
  2. 若净稿叙事线在拍 4 与拍 7 之间跳过了拍 5/6（诱杀小子侯、曲沃灭翼与王命立缗），建议按本文档终态拍序补足，避免"虏哀侯→即刻终局"的因果跳跃误导观众（实际中间尚有两代傀儡晋侯的过渡）。
  3. counterpoint（郑伯克段于鄢，`thesis:zhengbo-ke-duan`）为本轮（OP-D-062）新定，若净稿早于本次更正制作、未收录该 counterpoint，按本文档拍 8（side-panel）位置建议补入。
- **stratum 侧已更正范围**（供 CC-A 核对本仓现状）：`arc/arc-jin-decline.json`（member_event_refs 顺序 + 新事件）、`arc/events/s1-quwo.json`（事件层 JSON，含 2 正式 cf）、`arc/ADJUDICATION-s1-s2.md`/`arc/CURATION-s1-s2.md`/`arc/CURATION-s1-supplement.md`/`arc/ADJUDICATION-s1-supplement.md`（原文字节保留 + 就地更正注记）、本文档（终态拍序）。
