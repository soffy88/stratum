# 扩样例集（D-019）· 每事件一响应文件

> **交付方式**：G1b coverage gap（一集 11 拍 ≈ 5 ev/7 ac/2 cf/8 per）以**扩样例集**补齐——**形状零变更、无需 bump**（每文件仍是 §8 契约响应体，`contract_version: v0.2`）。**G1b 钉点 `../sample.sanjiafenjin.json` 字节不动**（tag `history-contract-v0.2` 的对拍基准依旧）。
> **生成**：`python3 tools/history/build_ep_samples.py`（samples = f(fixtures, seeds)，幂等重跑，零漂移）；校验随 `tools/history/validate_gold.py`（契约 schema + body 引用闭合 + 零下划线键）。

## ep_sanjia_fenjin（G1b gap 补齐 → PAIRING 指向建议）

| 拍 | 响应文件 | 事件 | 备注 |
|---|---|---|---|
| B01 | `jin-gongshi-bei.json` | ev:jin-gongshi-bei | 背景态（六卿彊公室卑）；registry 带 fo:jin |
| B02 | `zhixuanzi-liyao.json` | ev:zhixuanzi-liyao | 智果之论 ac + per:zhiguo |
| B03/B04 | `zhibo-suodi.json` | ev:zhibo-suodi | 任章语 ac（魏策一）+ per:renzhang；一事件覆两拍 |
| B05–B08 | `jinyang-zhizhan.json` | ev:jinyang-zhizhan | ★F23 束：+cf 水源（晋水/汾水，S12→DualAccountFact）+cf 围城年数（岁余/三年）+per:zhangmengtan；route_hint 已按 D-017 跟随 mainline 注异说 |
| B09 | `sanjiafenjin.json` | ev:sanjiafenjin | 父事件对象（parent_event 三节点） |
| B10/B11 | `minghou-403.json` | ev:minghou-403 | +臣光曰 ac（judgment 计 0，R8 归 per:simaguang） |

与冻结 sample 的已知可解释差异：jinyang 响应取 F23 束（account_id 命名 `ac:jinyang-shuiyuan-*`、新增两 cf、route_hint 改注）——皆 D-017/D-019 产物。B05 拍级合围路线**不在本批**（route_hint 单值系契约形状，拍级多路线属 G2 口径议题）。
