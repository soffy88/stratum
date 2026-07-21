# AII History KU · Decision Trail

> 跨系统决策留痕（spec §8.3 decision_trail 闭合）。凡影响契约钉点、契约形状、gold 判定范式的决策记于此，逆序（新在上）。

---

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
