# 失单补执行·先查后做核查报告 · 2026-07-22

> 指令『失单补执行（先查后做，若部分已做如实报）』。**核查结论：失单四项全部早已完成**（W-H1a-3 期 D-023 / commit `eaaf188`）；本波仅将 U7 文本转正为块内权威原话 + 重发 G1b 指针。

| 失单项 | 核查 | 状态 |
|---|---|---|
| 撤 cf:jinyang-independence（indep=1.5 移事件级，F1+sample 同步） | F1/sample 中 `cf:jinyang-independence` 出现数 **0** | ✅ **已做**（D-023/eaaf188，折算记录入 JUDGMENTS#F1 + notes 事件注记 + mainline rationale） |
| U7 关闭入 A.4 | A.4 有 U7 条 + 裁决 | ✅ **已做**（D-023）；**本波转正**为块内权威原话（多 account 挂同一事件=互见登记 + 重开条件=带查询形状消费者），D-023 版留痕 |
| 契约 tag 按沿革（samples 已入 tag → v0.2.2） | `history-contract-v0.2.2` 已打（samples 早入 v0.2.1，故沿革正确落 v0.2.2） | ✅ **已做**（D-023）；README+LEDGER 已同步 |
| G1b 钉点迁移通知（本仓落权威 + Wiki 转指针） | `contracts/samples/ep_sanjia_fenjin/KU-DELIVERY-*.md` 含 v0.2.2 + sha256 | ✅ **已做**（D-020/D-023）；**本波重发指针**（下附，经 Wiki 转 CC-A 重跑，属 P2 首波 G1b 全弧闭 OP-D042④） |

## G1b 钉点重发指针（经 Wiki 转 CC-A）

> stratum annotated tag **`history-contract-v0.2.2`**：G1b 对拍钉此；`sample.sanjiafenjin.json` 撤 cf:jinyang-independence（sha256 `4126c842…`）、schema 不变（`638fc28…`）。CC-A 更新 harness sha256、按 PAIRING 重跑，闭 G1b 全弧（P2 首波，OP-D042④）。**不写 hevi 仓**（D-021）；权威指针在本仓，经 Wiki 转发。
