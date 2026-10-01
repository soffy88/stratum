# A P5 KU EVOLUTION SPEC — KU 生命周期

TASK=A_P5_KNOWLEDGE_UNIT_EVOLUTION
AUTHORITY=A_REPOSITORY_ONLY
BASELINE=A_P4_1_KU_DURABLE_WRITER (79dce2d)
STATUS=FROZEN (re-frozen 2026-10-01, see A_P5_FREEZE_REPORT.md)
VERDICT_CONTRACT=FAIL > BLOCKED > PASS, derived from gate_results

## 1. Objective

在不破坏 A仓事实权威的前提下，建立 KU 生命周期管理。

P4 冻结了一个 knowledge unit，P4.1 把它写成数据库里的行。两者都没有给它
一段历史：行是不可变的，唯一发生在它身上的事是那次 freeze。A仓仍然需要
能够表达「这个单元被复核过、被判定不足、复核记录在这里」——而它不能靠改
那一行来表达，因为那一行正是下游引用的东西。

所以生命周期写在单元旁边，不写在单元里面：

```
    Frozen KU (P4)  ->  Durable KU (P4.1)  ->  Evolving KU (P5)
```

| 表 | 职责 |
|---|---|
| `ku_revision` | 存在后继单元；被替换的行一字未改 |
| `ku_review_event` | 发生过一次复核，且引用了复核者读的那段跨度 |
| `ku_confidence_evolution` | 一次测量，只追加，不覆盖 |
| `ku_relation` | 两行之间已经成立的事实 |

## 2. Migration

`075_a_ku_evolution.sql` — **CREATED and APPLIED to staging.**

- additive only, no `DROP`, no `ALTER`, no backfill (`INSERT` count 0)
- 四个新表，九个索引
- 唯一的外键目标：`knowledge_unit`、`reading_evidence`，全部
  `ON DELETE RESTRICT`
- 070–074 **逐字节未改**

### 2.1 为什么是四张表而不是 knowledge_unit 上的几列

`knowledge_unit.freeze_status` 在 `FROZEN` 是终态，
`knowledge_unit_frozen_at_required` 约束加上 RESTRICT 外键使「更新一个
已冻结的行」正是本仓库存在的意义所要阻止的事。一个只能表达为 `UPDATE`
的生命周期，就是这个 schema 拒绝存在的生命周期。

因此 status 存放在事件流里，由折叠（fold）得出——就像账户余额由分录账
推导，而不是把余额再存一份。

### 2.2 与草稿的偏差

- **不引入 `SUPERSEDED` status 到 `ku_freeze_event.to_status`。** 074 把该列
  限死为 `FREEZE_PENDING` / `FROZEN` / `FAILED`，而 additive-only 不允许
  ALTER。supersession 不改变单元的 freeze 状态——它仍然 frozen、仍然可被
  引用——只是不再是 current，所以两端都是 `FROZEN`，含义由 event_type 承载。
  074 当初把 SUPERSEDED 定义成 **event type** 而不是 status，正是为此。
- **`ku_review_event` 的幂等键不是 `(unit, type)`。** 草稿若用后者，单元
  就无法「隔离 → 释放 → 再隔离」，一个真实存在的生命周期将无法表达。
  改为 `UNIQUE(unit, sequence)` + `UNIQUE(review_hash)`：完全相同的重放仍然
  碰撞，真实发生的第二次隔离则被保留。
- **`ku_relation.from_unit_id < to_unit_id` 是 CHECK 而非应用层排序。**
  无向关系只存一份，与哪一端先被发现无关，重放因此无法追加它的镜像。

## 3. 生命周期

```
    ACTIVE ──> QUARANTINED ──> ACTIVE
       │             │
       └─────────────┴──────> SUPERSEDED   (terminal)
```

`SUPERSEDED` 无出边：`ku_revision` 的 `UNIQUE(prior_unit_id)` 给出至多
一个后继，已经有后继的单元就结束了。这与 074 的
`UNIQUE(knowledge_unit_id, event_type)` 一致——它本来就只允许每个单元
发一次 SUPERSEDED。

`CONFIRMED` 与 `CHALLENGED` 是**信号**，记录发现但不移动单元，所以
`from_status` 可以等于 `to_status`。

状态不是列，是 `ku_review_event` 按 `sequence` 折叠的结果。单元行本身
永远不变，每一步历史都留在记录上。

## 4. GATE 与证据

| Gate | 含义 | 证据 |
|---|---|---|
| **G1** SOURCE TRACEABILITY | 单元与复核都回得到书 | unit → verification → candidate → evidence → source_version，11/11；5/5 复核引用本单元同一 source_version 的证据 |
| **G2** IMMUTABILITY | 没有单元行被改动或删除 | 演化前后整表快照逐字段相等；唯一的差异是新增 |
| **G3** REVISION | 后继是追加的，不是合并进去的 | 先前行仍 FROZEN、仍带自己的 statement 与 canonical_text；后继有自己的 candidate 与 verification；链不分叉 |
| **G4** REPLAY | 同样的输入产生同样的 id | 两次独立构建 fingerprint 完全一致；0 重复行 |
| **G5** AUTHORITY | 没有无证据的单元，也没有无证据的复核 | 每个单元回得到证据链；每次复核引用真实证据且来自本单元同一本书 |
| **G6** DURABILITY | 重启可恢复，崩溃不留痕 | 第二次进程重建得到相同 id；revision 的 5 个写入位置逐一注入故障，无一行残留 |

Schema 与幂等另计两门，均 PASS。

## 5. 身份

```
    revision_id    = "krv_"  + sha256(prior | revised)[:12]
    review_id      = "kre_"  + sha256(unit | seq | type | version)[:12]
    relation_id    = "krl_"  + sha256(sorted(low,high) | type)[:12]
    observation_id = "kcx_"  + sha256(unit | seq | basis | value | version)[:12]
```

全部内容派生：没有 `uuid4`，没有序列，没有时间戳。`SUPERSEDED` 事件沿用
074 自己的 `event_id` / `event_hash` 公式，而不是另立一套。

**一个真实的 bug 被幂等门抓到。** 初版在检查是否已有等价行**之前**分配
下一个 `sequence`。重放时 sequence 1 已被占用，于是重放会铸造 sequence 2
并追加一条**第二条** CHALLENGED 记录——把重放变成了写入。身份因此改为内
容寻址：一条复核的身份是「它说了什么、它读了什么」，不是它的序号。

## 6. 复核账本

复核的输入冻结在 `pilot_corpus.KU_REVIEWS` / `KU_REVISIONS`，与候选者当初
被冻结的理由相同：输入住在 service 里的生命周期，谁都无法重放。

四条复核覆盖四种路径：

| 复核 | 类型 | 结果 |
|---|---|---|
| `kc_rome_rate_cap` | CONFIRMED | 跨度逐字给出利率与年度口径，无需改动 |
| `kc_solon_abolished_rate_cap` | CHALLENGED | 命题含「与巴比伦法典形成鲜明对比」，所引跨度不含；状态维持 ACTIVE，仅记录异议 |
| `kc_athens_debt_crisis` | QUARANTINED → RELEASED | 原文以「其部分起因」限定，命题写成因果断言并补入跨度未出现的「前6世纪」；复核后确认隔离理由不成立，回到 ACTIVE。**原隔离记录保留在事件流中** |
| `kc_hammurabi_code` | SUPERSEDED（经由 revision） | 命题断言「约前1800年」而所引跨度不含年代，引用者无法在跨度内核对该断言 |

## 7. 修订

一次修订**不是编辑**，因此不能跳过任何一级：同一证据行上生成新的候选者、
分类、核验、冻结、持久化，然后才记录链接。先前单元只被读取身份，从不被
写入。

```
    kc_hammurabi_code → ku_59cb9040d0f0   statement 《汉谟拉比法典》（约前1800年）是最早的成文信贷法典之一
                                    cited  第一部已知最早的正式法典
                          │
                          │ SUPERSEDED  (append-only, prior row untouched)
                          v
                        kc_10fef8f2ffa4 → ku_10fef8f2ffa4   statement 《汉谟拉比法典》（约公元前1800年）是最早的成文信贷法典之一
                                                   cited  在大约公元前1800年，……制订了第一部已知最早的正式法典。
```

## 8. 关系：词表就是设计

`SHARES_EVIDENCE` · `SAME_SOURCE_SPAN` · `REVISES`

每一个值都是机器读两行就能判定的比较。**词表里没有任何一个值表示「这两条
说的是同一件事」或「这两条彼此冲突」**——判定其中任何一个都是语义判断，
属于 B仓，A仓对此没有权威。

因此 `merge_units` 与 `dedupe_units` 存在且只做一件事：抛出 `EvolutionViolation`。
`relate()` 没有接受「判定」的参数，也不允许添加。

`CHECK (from_unit_id < to_unit_id)` 使无向关系只存一份，与发现顺序无关。

## 9. 置信度

`(unit, sequence)` 上的只追加序列。`measured_confidence` 是「这个单元被支持
得有多好」的测量，不是世界为真的概率。列上的 CHECK 与 service 双重把它
限制在 [0, 1]——能存下 4.0 的行会被读成断言。

把单元压低的那次测量仍然留在那里，与抬高它的那些并列。**测量本身从不移动
单元**：只有复核移动单元，而这张表记录的是复核发现了什么。

## 10. 禁止项

| 禁止 | 如何被结构性保证 |
|---|---|
| B仓生成 | 075 中每个 `stratum.X` 必须是自己创建的表或允许的引用目标，migration 因此结构上无法伸到别的仓库 |
| concept dedup | `dedupe_units()` 抛异常；关系词表无等价值；测试断言词表不含 `EQUIVALENT` / `SAME_CONCEPT` / `DUPLICATE` / `MERGED` |
| semantic merge | `merge_units()` 抛异常；关系只记录两行已成立的事实 |
| claim promotion | 没有任何字段存「是否为真」；`basis` 是封闭词表，永远指明测量方法 |
| BU2 mutation | 060–074 逐字节未改；`test_bu2_and_b_are_untouched` 断言 BU2 迁移不含 P5 的任何表名 |

## 11. 已知限制

- **P4.1 的双 id 问题依旧。** 075 未改变也不应改变它：durable id 遵循 P4.1
  §5 的公式，P4 的内存 id 依旧不同。P5 的修订链走的是 durable id。仍然需要
  一个决定，而不是一个绕过。
- **P5 写了它自己的规范没提到的表。** 一次修订必须持久化一个新单元，而新
  单元有外键指向 `ku_candidate` 与 `ku_verification`，所以 ancestry 也必须
  一起写——与 P4.1 发现并记录的同一个原因。
- **`_require_traceable` 是下划线开头的方法。** gate 需要它，而 gate 是模块
  函数而非方法。没有把它提到公开 API 只是为了避免扩大这个已经很大的模块的
  表面积；这是一个取舍，不是设计。
- **持久性只对 staging 证明。** staging 是可丢弃的。070 以来没有任何迁移
  到达过生产数据库。
- **`UNIQUE(ku_revision.revised_unit_id)` 使一个单元只能被一个前驱逐逐。**
  这让历史成为链。若日后需要分叉（例如两个前驱逐逐同一修订），需要新迁移。
- **A-suite 未通过 mypy strict。** 与既有基线一致：P1–P4.1 的模块同样未按
  strict 标注，P5 与它们保持一致而不是独自成为一个例外。
- **复核的账本是冻结的，不是被执行的判断。** P5 记录复核者说了什么；它不
  复核那些复核。判断复核本身是否正确，是人的工作。

EVOLUTION_SPEC=PASS
