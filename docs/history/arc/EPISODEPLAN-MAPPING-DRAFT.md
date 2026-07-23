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
| `beats[]` | 分镜/叙事拍 | 有序 `member_event_refs`（每事件 → ≥1 beat） |
| `beats[].evidence_spans[]` | 旁白引文（逐字白文） | 事件锚 `para_ulid` → 语料库白文 span（R5 逐字，透传素材标 genre） |
| `beats[].mapstate_cues[]` | 地图状态提示 | 事件 `place_refs`（dimension=place 冲突→并陈两说，D-006/D-017） |
| `beats[].conflict_callouts[]` | 冲突角标（S12 并陈） | 事件 `conflicts`（cf:*，presentation_hint=S12） |
| `provenance` | 集级溯源指纹 | 成员 KU 内容指纹集（SHA-256，KU-SPEC §226；升版不追溯已发布集） |

## 二、子簇 → EpisodePlan 映射范式（以已终裁 s1/s2 为例）

- **s1 曲沃代翼** → `ep:jin-decline-s1`：throughline=`thesis:shifu-modabizhe`（师服『末大必折』预言）；counterpoint=`thesis:shimo-changbian`（史墨无常律，异框架对照）；beats=[封桓叔(:0205)→武公灭翼(:0217)]；证据链逐字白文 span；无 place 冲突。
- **s2 骊姬之乱** → `ep:jin-decline-s2`：throughline=`thesis:liji-luandi-a`（源内乱嫡）；副线=`thesis:liji-luandi-b`（我方『诅无畜群公子→卿族坐大』，:1454 keystone）；beats=[娶骊姬(:0586)→谮杀申生缢新城(:0719)→二公子出奔(:0740)→诅无畜群公子(:1454)]；异名归一（郤芮=冀芮）供人物标注一致。

> **映射不变式**：① 一 beat 至少一条逐字白文 evidence_span（无锚不成拍——OP-D-046 精神下推至消费层）；② thesis 分 throughline/counterpoint 两轨（史/论可区分 R10 落到旁白与对照段）；③ place 冲突→并陈两说不私裁（D-017）。

## 三、arc 消费形状提案（P3 契约面，本波不实施）

P3 落地 EpisodePlan 时，查询契约需新增**弧/集响应形状**（`history-query-response` 之外的 arc-response 或扩展）：给定 `arc_id`/`sub_arc_id` 返回 {throughline+counterpoint theses（含 attribution 与 locator）, 有序 beats（event + 证据 span + place + conflict）}。**此系契约形状变更 → P3 一次协调 bump**（`contract_version`↑ + README + G1b 双端同步 + decision trail，走 D-006 同款流程）。**在此之前一律仓内 arc-thesis.schema.json 承载、不进查询契约**（D-025 不变）。

## 四、送裁点

① EpisodePlan 字段拟议准否；② 子簇→集 粒度（一子簇=一集 vs 一段）；③ throughline/counterpoint 双轨范式准否；④ P3 arc-response 契约扩展方向（新对象 vs 扩现有）预表态（不实施）。**草案止此、不写代码、不动 schema。**
