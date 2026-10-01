# A P6 KU IDENTITY SPEC — A仓唯一知识单元身份

TASK=A_P6_IDENTITY_CANONICALIZATION
AUTHORITY=A_REPOSITORY_ONLY
BASELINE=A_P5_KU_EVOLUTION (P5)
STATUS=FROZEN

## 1. Objective

解决 P4.1 双 ID 问题，建立 A仓唯一知识单元身份。

P4.1 记录了这个 open item，并说它**需要一个决定，而不是一个绕过**。这就是
那个决定：

> **`knowledge_unit.id` 就是 canonical id。** P4 的 freeze id 成为注册到它
> 名下的 alias。

```
    P4    froze    ku_<sha256(statement | evidence_fingerprint)[:12]>
    P4.1  persisted ku_<sha256(candidate_id | verification_id | content_hash)[:12]>

    11 个单元，11 对 id，全部不同。

    P6    canonical = P4.1 的 durable id（不变）
          alias     = P4 的 freeze id（注册，不改写）
```

为什么是 durable 那一个：

- 它绑定产生该单元的 **verification**，两个公式里溯源更强的一个；
- 它已经是 P4.1 写进数据库的东西，也是 P5 修订链 link 的东西——选它意味着
  **没有任何一行需要移动**；
- 选 P4 的公式反而要改写 11 行已持久化的 `knowledge_unit.id`，那才是对已
  冻结数据的篡改。

## 2. Migration

`076_a_ku_identity.sql` — **CREATED and APPLIED to staging.**

- additive only, no `DROP`, no `ALTER`, no backfill (`INSERT` count 0)
- 一张新表，三个索引
- 唯一外键：`ku_identity.canonical_ku_id → knowledge_unit(id)` `ON DELETE RESTRICT`
- 070–075 **逐字节未改**

### 2.1 本阶段刻意不做的事

- **不铸第三个 id。** 规范化是关于**解析**，不是关于重新编号。第三个公式会
  是每单元第三个 id，并让所有已写的行和修订链失效。
- **不改写 `knowledge_unit.id`。** 没有东西被重新编号；`renumber()` 只做
  一件事——抛 `EvolutionViolation`。
- **不建 `ku_canonical` 表。** canonical id 已经是该行的 PRIMARY KEY。再加
  一张表断言同一件事，就是给一个 id 造第三个真相来源——正是本阶段要治的
  病。

## 3. `ku_identity`

| Column | 含义 |
|---|---|
| `id` | 行自身的地址，内容派生 |
| `canonical_ku_id` | → `knowledge_unit(id)` RESTRICT |
| `alias_id` | 一个已退役但仍须能解析的 id |
| `alias_kind` | 封闭词表：`FREEZE_LEGACY` |
| `id_fingerprint` | 该 alias 的输入，可据以重算 |
| `identity_hash` | 确定性指纹，使重放变成 no-op |

**`UNIQUE(alias_id)` 是这张表的承重约束**：它让「一个 id 至多意味一个单元」
成为数据库不变量而非应用约定。

### 3.1 为什么没有 `DURABLE` 这个 alias_kind

durable id **就是** canonical id，它不是 alias，没有对应的行。加一个会让
`alias_id == canonical_ku_id`，而 `ku_identity_not_self` 本来也会拒绝它。
测试断言这个词表里没有 `DURABLE`。

### 3.2 为什么 `id_fingerprint` 不是冗余

`evidence_fingerprint` 来自 `verification.trace`，而 P4.1 的 emitter **从未把
该列写进数据库**。所以这一行是那个退役 id 的输入的**唯一持久记录**；没有
它，alias 无法重建，这张表就只能被信任而无法被检查。

编码为 JSON 而非 P4 那个 `|` 连接的 hash 输入：分隔符无法从恰好包含它的
statement 里拆出来，而一个会误解析自身输入的检查不是检查。有一个测试专门
用含 `|` 的 statement 验证这一点。

## 4. Resolution

```
    citation ──> 任何曾经发出过的 id
                   │
                   ├─ 已是 knowledge_unit.id ──> canonical
                   │
                   └─ 已退役公式 ──> ku_identity 查询 ──> canonical
                                                 │
                                                 └─ 无行 ──> UNRESOLVED
```

**UNRESOLVED 是一个答案，不是要被掩盖的失败。** 发出它的阶段和没能解析它的
阶段都是值得保留的事实。

解析**不会**被 P5 的生命周期自动使用。生命周期以 canonical id 为键，所以
被退役的 id 刻意不在其中：调用方先解析、再查询。若 alias 也在 fold 里，就
会有两个身份需要保持同步。

## 5. GATE 与证据

| Gate | | Evidence |
|---|---|---|
| **G1** identity uniqueness | PASS | 22 个 id、11 个 canonical、11 个 alias，零歧义、零跨命名空间冲突、零孤儿、零重复 |
| **G2** historical replay | PASS | P4 artifact 里 10 个退役 id 全部解析；两次独立构建 fingerprint 一致；未知 id 返回 UNRESOLVED |
| **G3** revision chain intact | PASS | P5 的修订链在两个命名空间下都解析；被 supersede 的单元以其退役 id 读出仍是 SUPERSEDED，且仍指向同一后继 |
| **G4** P1-P5 regression | PASS | P4 仍产出它记录的 10 个退役 id；P5 仍产出 11/1/5/1 并与已提交 artifact 一致；P4/P4.1/P5 的版本号未变 |
| **G5** authority isolation | PASS | 076 只引用 `knowledge_unit`；identity.py 的导入只有 A 链加标准库；注册未改动任何单元行 |

另有 `schema=PASS`（ledger 070–076 来自真实查询）与 `idempotency=PASS`。

### 5.1 G1 的 schema 侧独立证据

每一条都由真实 PostgreSQL 拒绝：

| 探针 | 被谁拒绝 |
|---|---|
| 同一 alias 归两个单元 | `ku_identity_alias_uniq` |
| 单元作为自己的 alias | `ku_identity_not_self` |
| 未声明的 alias kind | `ku_identity_alias_kind_check` |
| 空白 fingerprint | `ku_identity_id_fingerprint_check` |
| 指向不存在单元的 alias | `ku_identity_canonical_ku_id_fkey` |
| 删除 alias 命名的单元 | RESTRICT |

## 6. 两个真实的 bug——都是执行出来的，不是读出来的

**076 最初没有 `id` 列。** sink 和 emitter 都以 `id` 为键，于是每一行插入
都在数据库失败。

**076 随后仍然没有 `identity_hash` 列。** 同一个 emitter 也写它。

两个都不是靠读 migration 或读 dataclass 能发现的——只有**两者不一致**才会
暴露。因此加了一条常驻测试：emitter 写的列、schema 声明的列、
`IdentityAlias` 带的字段，三者必须一致。

## 7. 已知限制

- **「alias 不得是另一单元的 canonical id」这条规则由 service 与 gate 强制，
  不由 schema 强制。** `UNIQUE(alias_id)` 能保证一个 alias 至多归一个单元，
  但要禁止 alias 取自 `knowledge_unit.id` 的取值域，就需要指向
  `knowledge_unit(id, id)` 的复合外键——那要 ALTER `knowledge_unit`，
  additive-only 不允许。`cross_namespace_collisions()` 是这条规则的读取。
  当前 11 个 id 上它为空，但这属于应用不变量，不是数据库不变量。
- **两个命名空间形状相同**（都是 `ku_<12 hex>`）。读者无法只凭 id 区分它们，
  这正是别名表必须存在的原因，也是上面那条限制存在的原因。
- **`resolve()` 扫描 alias 行。** `identity_id` 绑定 canonical id，只持有
  alias 的调用方算不出来，所以是扫描。单元级规模下无关紧要；目录级规模需要
  索引，数据库侧的 `UNIQUE(alias_id)` 已经提供了。
- **P4.1 的 durable id 公式未被触碰，这是有意的。** 若 P6 改了公式，所有已
  写的行和修订链都要失效。
- **持久性只对 staging 证明。** 070 以来没有任何迁移到达过生产数据库。
- **A-suite 未通过 mypy strict**，与既有基线一致。

IDENTITY_SPEC=PASS
