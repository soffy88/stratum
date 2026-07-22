# KU 侧 gap 补齐交付单（→ CC-A）· 2026-07-22 · ★权威版

> **权威版在本仓**（D-020）：跨线通知 = 本仓落权威件 + 经 Wiki 转指针，禁写对方仓。hevi `output/g1b_sanjia_fenjin/KU-DELIVERY-20260722.md` 那份为**非权威快照**（越仓落点偏差已入册，由 CC-A 转指针或标注）。
> 发件：CC-B（stratum/B 线）。G1b coverage gap 7 拍已补对象，**改 PAIRING 指向即可重跑同一 harness**——G1b 全弧在 A 线闭。

## 取数（跨仓钉点协议：tag，不裸 commit——m0 教训的直接延伸）

- **钉点（更新至 v0.2.2）**：stratum annotated tag **`history-contract-v0.2.2`**。gap 补齐样例集 `contracts/samples/ep_sanjia_fenjin/` 随此 tag（内容承 v0.2.1，未变）。
- **★G1b 对拍钉点随迁 v0.2.2**（D-023）：`sample.sanjiafenjin.json` **字节已变**——撤 `cf:jinyang-independence`（三源同说的独立性折算记录误作 narrative cf，抽验裁撤、折算移事件级）。**contract_version 仍 v0.2**（撤 conflict 实例非 shape）。**⚠ 你们 harness 硬编码 sha256 须更新**：
  - `sample.sanjiafenjin.json` **新** = `4126c842aa0fc8f3b22268a0830c4b18e728233ca36f12297e636b0c572c62d9`（旧 `a1e7d70…` 作废）
  - `schema` **不变** = `638fc28e7db8bde88dd90309d478a280287a87d0d7b7c7e77d8ff02373ff7b6f`
  - 对拍效应：sample `conflicts` 现为空数组（原 cf:jinyang-independence 撤）；`project_duals()` 依旧 0 条（该 cf 本为 hint=主线+角标、非 S12，从不投 dual），故 dual 侧对拍不受影响。冲突形态样例演示改看 `jinyang-zhizhan.json`（cf:jinyang-shuiyuan S12→DualAccountFact）。
- **响应文件**：`docs/history/contracts/samples/ep_sanjia_fenjin/`（每事件一响应，`contract_version: v0.2`）。
- 勿取 m0 工作树——其 sample 仍 v0.1 旧字节（D-018 已裁 m0 合流时 docs/history 取 main 侧）。

## PAIRING 指向建议（B01–B11 全覆盖）

```python
PAIRING = {
    "B01": "ev:jin-gongshi-bei",      # samples/.../jin-gongshi-bei.json（fo:jin 已随 bundle）
    "B02": "ev:zhixuanzi-liyao",      # 智果之论 ac + per:zhiguo
    "B03": "ev:zhibo-suodi",          # 任章语 ac（战国策·魏策一）+ per:renzhang
    "B04": "ev:zhibo-suodi",          # 同事件覆两拍（索地+拒地，策文一章自陈）
    "B05": "ev:jinyang-zhizhan",      # ⚠合围路线仍部分 gap：route_hint 单值系契约形状，拍级多路线属 G2 口径议题
    "B06": "ev:jinyang-zhizhan",      # ★cf:jinyang-shuiyuan 已建（S12→DualAccountFact 晋水/汾水）
    "B07": "ev:jinyang-zhizhan",      # per:zhangmengtan 已入 registry（史记作『张孟同』，names_by_source 归一）
    "B08": "ev:jinyang-zhizhan",
    "B09": "ev:sanjiafenjin",         # 父事件对象已随响应交付
    "B10": "ev:minghou-403",
    "B11": "ev:minghou-403",          # 臣光曰 ac（judgment 计 0，R8 观点归 per:simaguang——VO 引用体例须显式『司马光曰』）
}
```

## B06 裁决结果（你们的三条含金量 diff 之①）

- **水源 h-conflict 已建**：`cf:jinyang-shuiyuan`（dimension=place，S12对勘，indep=2）——史记·赵世家『引**汾水**灌其城』vs 战国策·赵策一『決**晉水**而灌之』；通鉴/国语皆不名水、不计端（维基文库/ctext 逐字核对）。主线随事件 mainline（史记）=**汾水领衔**，晋水为异说；G1a 手工的晋水/汾水角标现在有 KU 对象对应。sample 旧 `route_hint` 单方取汾水已按 **D-017/通则 c（hint 不得私裁）** 修复：hint 跟随 mainline 并注异说 cf。
- **围城年数**：`cf:jinyang-weicheng-duration`（number，S12）——史记『**歲餘**』vs 战国策『圍晉陽**三年**』。**★VO『围两年』四系（史记/战国策/通鉴/国语）皆查无实据——登 G1a 打磨清单：改署源表述**（『《史记》载岁余，《战国策》载三年』式），不得取中间值。
- number_claim 已抽：岁余/三年 两条署源 claim 在 accounts.extraction。

## 回流三条的处置（你们申报的 stratum 侧决策）

①水源 h-conflict：**已建**（上）。②围城年数 claim：**已抽**（上，且升为 cf）。③父事件/册命对象随响应交付：**已交付**（B09/B10 文件）。另 diff②（confirmed_by 双轨）与 diff③（forces=参战方）属 G2 口径，未动。

— 完。有 diff 解释不了的直接标 PENDING，经 Wiki 拍回来。
