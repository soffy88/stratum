# HISTORY-TEXTBOOK-MAINLINE-CC-SPEC-001 —— 初中历史教材主线 · 历史现场每日自动产片

| 项 | 值 |
|---|---|
| 状态 | **draft v0.1 · 2026-08-07 · 决策已拍板** |
| 所有者 | CC / Wiki |
| 所属 | 跨 mneme（教材语料源）· stratum（语料弧主权）· hevi（生产端 tongjian）三仓 |
| 姊妹 spec | `stratum/docs/history/AII-HISTORY-KU-SPEC-001.md`（事件中心·多源并陈·§8 tongjian 只读契约，本文承其全部约束，不重复定义） |
| 消费者 | hevi tongjian（历史现场）每日自动产片 + 四平台发布 |
| 成功定义 | 初中历史教材为主线、古籍为并陈辅助的"历史现场系列语料"入库 stratum 弧；历史现场每日自动产 1 集（按教材课节连载），产出经人工审核后发布抖音/B站/小红书/YouTube |

---

## 0. 决策记录（Wiki 拍板，2026-08-07）

| # | 决策 |
|---|------|
| D1 | **教材范围先中国历史 4 册**：七上/七下/八上/八下（世界史九上/九下另立系列，暂缓） |
| D2 | **每日一集**，按教材课节序连载（"历史现场·中国历史七上·第N课·标题"） |
| D3 | **发布渠道：抖音 + B站 + 小红书 + YouTube 全发**（人工审核 gate，见 §6） |
| D4 | **古籍灌注顺序由 CC 定**（见 §7） |
| D5 | **教材主述 + 古籍并陈**（见 §3；经全仓搜索确认无既有设计留痕，本文为新定义） |

---

## 1. 现状与留痕结论（2026-08-07 核查）

- **mneme**：`curriculum_standards/` 有中国历史七上/七下/八上/八下 + 世界历史九上/九下 PDF（2022 课标版）——纯 PDF 未提取；mneme 现有教材体系是数学/物理/语文（`textbooks`/`textbook_files`），**历史教材无 KU 提取**。
- **stratum**：`docs/history/AII-HISTORY-KU-SPEC-001.md` 已冻结历史 KU 规范（事件中心、多源并陈、注册表族 persons/places/chronology/forces、§8 tongjian 只读契约 `{event, accounts[], conflicts[], registry_bundle}`、locator 段落级 ULID、W-H0 fixtures）；`edge_onto` 事件超边 + `ku_onto`/`concept_onto` 已建表；辅助古籍书目已定（左传/国语/战国策/史记/汉书/后汉书/三国志+裴注/资治通鉴）。
- **"教材主述+古籍并陈"设计留痕：未找到**（唯一"教科书"命中在 AII-REFINED-REPO-SCHEMA 的 AII 适用性/version 讨论，非主述设计）。本文 §3 正式定义。
- **hevi tongjian**：`POST /tongjian/run{source_name, raw_text}` → L0-L8（剧本→角色→动画演绎→质检）已打通；黄金公式动画演绎 + 儿童卡通默认 + edge-tts + 沙箱质检；`publishStudioApi`（发布+确认发布）存在，四平台适配待建。

---

## 2. 目标架构

```
mneme 中国历史 4 册 PDF（主线教材）
  │ ① 教材提取（MinerU，承 MINERU-AII-INTEGRATION-SPEC-001）
  ▼
stratum AII 语料层（语料弧主权）
  ├─ 教材主线 KU   corpus_role=primary + chapter_order（课节序，本 spec §3）
  ├─ 古籍辅助 KU   corpus_role=auxiliary（事件中心+多源并陈，承 AII-HISTORY-KU-SPEC-001）
  ├─ 历史语料弧    事件超边（edge_onto）+ 教材↔古籍交叉引用弧
  └─ §8 只读接口   按课节/事件取 {event, accounts, conflicts, registry_bundle}
        │ ② 弧段消费（hevi arc_client）
        ▼
hevi tongjian 每日产线
  ├─ 调度器：教材课节队列 → 下一课弧段 → RunRequest 组装
  ├─ L0-L8：剧本 → 卡通动画演绎 → TTS → 质检
  ├─ 待发布队列（自动产出 ✅ + 人工审核 gate）
  └─ 四平台发布（抖音/B站/小红书/YouTube）
```

---

## 3. 教材主述设计（D5，本 spec 新定义）

### 3.1 主述规则
- **主线 = 教材**：系列叙事、观点倾向、历史分期、结论表述一律以人教版中国历史教材为准（"主述"）。
- **古籍 = 并陈证词**：同事件的古籍原文/细节作为第二层"证词"并陈——丰富演绎素材、展示原始史料，但**不覆盖教材结论**。
- **冲突不静默合并**（承 AII-HISTORY-KU-SPEC-001 P1）：教材与古籍纪年/细节冲突时（如下宫之难系年），画面/旁白以教材主述播报，古籍异说以**角标并陈**（"《史记·赵世家》系年：晋景公三年·前597；《左传》系年：前583"）。

### 3.2 教材 KU 标注
| 字段 | 值 |
|---|---|
| corpus_role | `primary`（教材） / `auxiliary`（古籍） |
| chapter_order | 教材课节序整数（七上第1课=1 … 八下收官），驱动连载游标 |
| volume | `中国历史七年级上册` 等 |
| locator | 教材：PDF 课节/页码；古籍：段落级 ULID（承 §D2） |
| viewpoint | 教材主述观点标签（如"唯物史观分期"），供并陈角标比对 |

### 3.3 教材↔古籍交叉弧
同一事件（超边）挂两个 account：`account.mainline`（教材述，主述）+ `account.classical`（古籍述，并陈），`conflicts[]` 显式列出差异。§8 查询按课节返回两述，hevi 侧组装时主述进旁白、古籍进演绎细节与角标。

---

## 4. 弧段 → RunRequest 组装（承 §8 契约）

| RunRequest 字段 | 来源 |
|---|---|
| source_name | `历史现场·中国历史七上·第N课·《课标题》` |
| raw_text | 教材 mainline account 原文（主述）+ 古籍 classical account 原文（并陈，标《书·篇》出处） |
| constitution 注入 | registry_bundle（人物/地点/纪年解析包）→ 角色 bible / 场景年代约束 |
| 演绎段素材 | account.dialogue_spans（透传不消费，供导演流水线） |
| 冲突角标 | conflicts[] → 并陈角标素材 |

---

## 5. 每日自动产线（D2）

- **调度**：cron 每日 03:00（中国历史 4 册连载游标取下一课；跨册自动续：七上收官 → 七下）。
- **幂等**：`arc_id + run_id` 绑定 state_json，已产课节跳过；失败次日补产（延续"不开天窗"哲学）。
- **单集时长**：约 5-10 分钟（一课内容量），黄金公式动画演绎 + 儿童卡通默认 + edge-tts 解说。
- **产出归档**：`data/cinematic_output/history_series/{volume}/{lesson}/` + 系列元数据（集数/课节/主述来源/并陈出处）。
- **质检**：veya video_sandbox v1+v2（时长/分辨率/音频/黑帧/响度/OCR）不通过 → 自动返工（SWITCH_PROVIDER 降级链），仍不过 → 待发布队列标记"需人工处置"。

---

## 6. 发布 gate（D3，硬约束）

- **自动产片 + 人工审核发布**：产出进"待发布队列"，历史现场控制台加"今日待发布"面板（预览 + 主述/并陈出处 + 质检报告）→ 人工逐条确认 → 发布。
- **四平台**：抖音 / B站 / 小红书 / YouTube。现有 `publishStudioApi` 需扩展四平台适配（各平台 API/凭据/上传/封面/标题标签约定，含 YouTube OAuth）；**本阶段不自动公开发布**，平台级自动发布开关另行解锁。
- 每集标题/简介模板：`历史现场｜中国历史七上 第N课：〈课标题〉（教材主述 + 古籍并陈）`。

---

## 7. 古籍灌注顺序（D4，CC 定）

按**教材课节相关性优先**灌注，随教材连载推进：

| 波次 | 教材覆盖 | 优先灌注古籍 | 理由 |
|---|---|---|---|
| W1 | 中国历史七上（远古→夏商周→秦汉→三国两晋南北朝） | 史记（纪传主体）、左传（春秋）、资治通鉴（战国秦汉）、汉书（西汉） | 七上各课直接对口的断代史料 |
| W2 | 中国历史七下（隋唐→宋元→明清） | 资治通鉴（隋唐部分）、旧/新唐书（隋唐）、宋史/辽史/金史/元史（宋元）、明史/清史稿（明清） | 与七下课节对齐 |
| W3 | 中国历史八上（近代：鸦片战争→解放战争） | 近代史料汇编/奏折条约原文（鸦片战争/洋务/辛亥革命等一手文件）、近现代史编 | 一手文件作并陈证词 |
| W4 | 中国历史八下（现代：建国→改革开放） | 官方文献/公报原文（共同纲领/宪法/改革开放文献） | 教材主述 + 原文并陈 |

每波次按 AII-HISTORY-KU-SPEC-001 §10 断代灌注流程执行（抽取一次，四处消费）。

---

## 8. 阶段计划

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| P0 | §8 契约 + W-H0 fixtures 对拍（hevi G1a 手工同形数据跑通消费路径） | tongjian 用同形 data 出片通过质检 |
| P1 | 教材主线入库：mneme 中国历史七上 PDF → MinerU → 教材 KU（primary+chapter_order）→ 教材↔古籍交叉弧 | 七上全册课节可查，§8 返回 mainline+classical 双述 |
| P2 | 自动产线：hevi arc_client + 每日调度器 + 待发布队列 + 系列元数据 | 连续 3 日自动产片（每日 1 集）全部过质检 |
| P3 | 四平台发布：publishStudioApi 四平台适配 + 人工审核发布 UI + 连载看板 | 每日一集经人工确认发布至四平台 |

---

## 9. 非目标
- 世界史九上/九下系列（D1 暂缓）；自动公开发布（§6 硬约束）；教材 OCR 之外的教辅题库；训练模型。
