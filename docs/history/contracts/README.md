# AII History KU · §8 契约冻结包

> **Doc**: AII-HISTORY-KU-SPEC-001 §8 交付物 · v0.1 冻结 · 2026-07-21
> **红线**: 这是两仓（AII KU ⇄ tongjian 生产端）**唯一耦合面**。契约先行——生产端 G1a 以手工装配同形数据先跑；KU 实装后 G1b 逐字段对拍此包。

## 文件

| 文件 | 作用 |
|---|---|
| `history-query-response.schema.json` | ★冻结契约。§8.1 查询响应 JSON Schema（draft 2020-12）。形状严格取自 spec §3/§4/§8.1，无新增字段。`additionalProperties:false` 全程锁死。 |
| `sample.sanjiafenjin.json` | ★冻结完整静态样例（三家分晋·晋阳之战节点）。G1b 对拍的基准实例。**JSON 本体零下划线键，committed bytes 原样过 validate**（无 strip-before-validate 隐形预处理——那会让 G1b 要么复刻要么漂移）。 |
| `sample.sanjiafenjin.notes.md` | 人读注释（从 JSON 迁出）。非契约、不参与对拍。 |

## G1b 对拍协议（§8.4）

1. 生产端按 `history-query-response.schema.json` 装配 VisualFact 前的中间态（G1a 手工同形数据）。
2. KU 实装后，`GET`（§8.1 只读接口：时间窗/人物/势力/event_type/断代）→ 返回体**必须 validate 通过本 schema**。
3. 与 `sample.sanjiafenjin.json` **逐字段对拍**：一致，或**差异可解释**。已知可解释差异：
   - `locator.para_ulid`：样例为 `null`（语料未入库）；实装后填 `<substrate-ULID>:<para-suffix>`——**填值即可解释**。
   - `mainline_decision.date` / `decided_by`：随实际决策更新。
   - `contract_version`：必须仍为 `"v0.1"`；升版是显式决策（§8.3），须同步双方。
4. **禁**：任何一方私自增删字段。改契约 = 改 `contract_version` + 双端同步 + 本 README 记变更。

## 字段映射（→ 生产端 VisualFact，见 spec §8.2）

`canonical_date→VisualFact.date` · `actors[].force_ref→forces[]`（色生产侧配）· `geo.place_refs→regions[]`（(date,scope) 命中 MapState）· `actors[].person_ref→persons[]/Cutout` · `mainline account.number_claims→quantities[]`（带『《X》载』display）· `evidence_tier→evidence_tier`（E3/E4 强制 R9 banner）· `conflict(hint=S12)→DualAccountFact` · `account.dialogue_spans→演绎段素材（透传不消费）`。

## 版本 / 指纹（§8.3）

- 契约形状版本：`contract_version` 字段（本包 `v0.1`）。
- KU 内容版本：SHA-256 内容指纹（EpisodePlan 钉指纹集）；**KU 升版不追溯已发布集**。二者正交：形状契约稳定，内容随灌注生长。

## 校验命令

```bash
cd docs/history
python3 - <<'PY'
import json; from jsonschema import Draft202012Validator
schema=json.load(open("contracts/history-query-response.schema.json"))
s=json.load(open("contracts/sample.sanjiafenjin.json"))   # 本体零下划线键，原样 validate（无预处理）
errs=list(Draft202012Validator(schema).iter_errors(s))
print("VALID" if not errs else f"{len(errs)} errors")
PY
```

> **零下划线约定**：本包所有 JSON 本体不含 `_`-前缀键；人读注释一律在同名 `*.notes.md`。冻结契约的真理形态 = 落盘字节本身，validate 不得依赖任何 strip/预处理步骤。

## 相关交付

- 注册表种子：`../seeds/{sources,chronology,persons,places,forces}.json`（§3；derivation_edges 必填、六国 override 占位、fixtures 涉及实体）。
- W-H0 fixtures：`../fixtures/F1..F4*.json`（§10；四核心样本）。
- §5 同一性判定记录（A 类回归网首批 gold）：`../fixtures/JUDGMENTS.md`。
- 承自 conformance（Task 0）：`../AII-HISTORY-KU-SPEC-001.md` 附录 A。

> ⚠ **F2（赵氏孤儿）判定含边界案，`decided_by=Wiki-亲裁（待签署）`**——Wiki 签署前，F2 gold 未最终冻结（见 JUDGMENTS.md#F2）。契约 schema/sample 与 F1/F3/F4 gold 已冻结。
