# STRATUM_A_DEPENDENCY_CLOSURE_AUDIT

VERSION=v1.0
STATUS=RECORDED
TASK=STRATUM_A_DEPENDENCY_CLOSURE_AUDIT
HEAD=dc66bd5
TOOL=`scripts/a_dependency_closure.py`
TOOL_SHA256=`163ea0acbf5326ce3b1cdbfe63719839f56352b69795d2df5373ae05a530959d`

---

## 0. 为什么要有这个工具

P6 的第一次冻结提交通过了所有 import 检查，却**无法从干净检出运行**：

```
ku_identity_runner.py  读取  artifacts/a_repository/p5_ku_evolution.json
其测试               shell 调用 tests/architecture/test_a_repository_p5_evolution.py
干净检出             17 failed，runner 抛 FileNotFoundError
```

两类依赖都是**文件系统耦合**，import 分析看不见。
所以冻结边界的审计必须同时看两种：

```
IMPORT   import / from 语句里出现的同包模块      —— AST
FILE     运行时读取的文件：artifact、migration、同层测试的 subprocess 调用
```

且必须包含**该层测试自身的 FILE reach**：P6 的耦合正是在测试里，不在模块图里。

工具只读。它在系统临时目录里自建并自删 worktree。

---

## 1. 工具自身的两个审计缺陷

一个用于审计冻结边界的工具，先得能信任。以下两个缺陷是本次审计过程中
**发现并修掉的**，且在修掉之前产出过错误结论。

### 1.1 AST import 解析错误（严重）

```
from .identity import KUIdentityService
```

被匹配到 `from . import x` 的分支，于是记录的是被 import 的**符号名**
（`KUIdentityService`）而不是**模块名**（`identity`）。
符号名随后过不了「`.py` 是否存在」的过滤，闭包被静默清空。

后果：第一次运行时 P7 的 module closure 里**没有 `identity`**，
而 `projection_builder` 明明写着 `from .identity import KUIdentityService`。

```
修正前  P7 closure = 9 modules（不含 identity）
修正后  P7 closure = 17 modules（含 identity / ku_identity_runner / evolution）
```

判据：`from . import x` 的 `node.module` 为 `None`；
`from .x import y` 的 `node.module` 为 `'x'`。两者曾被同一个条件匹配。

### 1.2 SQL 被双重分类

分类逻辑按目录迭代，导致每个 `.sql` 同时被登记为
`migration:` 与 `artifact:`，于是 6 个迁移各多出一条
`MISSING artifact:07x_....sql` 的假缺失。

修正：按扩展名**一次性**分类。

---

## 2. 审计结果

工具：`python3 scripts/a_dependency_closure.py --layer <LAYER> [--verify]`

| layer | module closure | file closure | complete @ dc66bd5 | verified |
|---|---|---|---|---|
| P5_EVOLUTION | 12 | 6 | **YES** | 116 passed |
| P6_IDENTITY | 15 | 9 | **YES** | 98 passed |
| P7_PROJECTION | 17 | 9 | **NO** | 未运行 |

### 2.1 P5_EVOLUTION

```
modules (12)  evolution, freeze, freeze_runner, ingestion, ku_evolution_runner,
              persistence, pilot_corpus, quality, quality_runner, types,
              verification, verification_runner
files    (6)  migrations 070..075
tests    (1)  test_a_repository_p5_evolution.py   tracked
```

module closure **不含** `identity` / `ku_identity_runner`。

### 2.2 P6_IDENTITY

```
modules (15)  上面的 12 个，加 identity, ku_identity_runner, ku_freeze_runner
files    (9)  migrations 070..076, artifacts p4_ku_freeze.json,
                   p5_ku_evolution.json
tests    (1)  test_a_repository_p6_identity.py   tracked
测试自身 reach  artifacts p4/p5/p6, migrations 063..065 + 076,
                并 shell 调用 test:test_a_repository_p5_evolution.py
```

最后一行就是 P6 暴露的那条边，现在被工具直接看见。

### 2.4 静态分析的盲区：运行时拼出的路径

P7 测试会比对自己的 artifact：

```
artifacts/a_repository/p7_projection/book_<book_id>_projection.json
```

`book_id` 是**运行时算出来的**，源码里没有任何字符串字面量提到这个文件名。
所以只扫字面量的闭包分析永远看不见它。

实测：

```
补齐缺口 1（提交测试文件）之后，静态分析报：
    complete = True     runnable from a clean checkout = YES

只有 --verify 报出真相：
    2 failed, 69 passed
    FAILED test_the_committed_artifact_matches_a_fresh_build
    FAILED test_artifact_is_named_by_an_a_repository_id
```

因此工具的契约改写为：

```
complete = True   只表示「没有 *被命名的* 依赖缺失」
                      绝不表示「可运行」

只有 --verify 能回答「可运行」
```

这条限制已写进工具 docstring 与输出末尾。一个用来审计冻结边界的工具，
必须自己先承认看不见的地方。

### 2.3 P7_PROJECTION

```
modules (17)  含 identity / ku_identity_runner / evolution / ku_evolution_runner
files    (9)  migrations 070..076
tests    (0)  test_a_repository_p7_projection.py   UNTRACKED   <-- 缺口 1
artifact (0)  artifacts/a_repository/p7_projection/book_<book_id>_projection.json
                                                            UNTRACKED   <-- 缺口 2
```

缺口 1 已由 `35a362e` 补齐。缺口 2 是本审计在**补齐缺口 1 之后**才暴露的，
而且静态分析**结构上看不见它**——见 §2.4。

注意：P7 测试自身只 reach **migration**，不 reach 任何前层 artifact。
所以 P7 的耦合比 P6 当初**更轻**——它的运行闭包只缺自己那一个测试文件。

---

## 3. TAG_BASE_DECISION

### OPTION A（采纳）

```
P5_EVOLUTION_REFREEZE_BASE = stratum-a-p6-freeze   (dc66bd5)
```

理由是实测的，不是权宜：

```
在 stratum-a-p5-freeze (6265038) 上审计 P5_EVOLUTION
  complete = False
  tests    test_a_repository_p5_evolution.py   UNTRACKED
```

即 P5-evolution 的**自身**两个文件（`test_a_repository_p5_evolution.py`、
`artifacts/a_repository/p5_ku_evolution.json`）在 P5 tag 里根本不存在。
它们是在 P6 verdict 修复（`f2f14d7`）中才进入仓库的。

不重写历史、不制造回滚污染的前提下，P6 tag 是 P5-evolution 唯一可运行的基底。

### 措辞（重要区分）

**不写**：

> P5 evolution 依赖 P6

**写**：

> P5 evolution implementation predates P6.
> Its committed runnable closure was completed during P6 verdict repair.
> Therefore P5 evolution re-freeze is based on `stratum-a-p6-freeze`.

这是两件完全不同的事实：

```
时间关系
  P5 evolution implementation 存在
        ↓
  P6 repair 补交缺失的闭包文件

依赖关系
  P5 evolution  ──✗──>  P6
```

审计已确认这个方向是**单向**的：P5-evolution 的 module closure 里
既没有 `identity` 也没有 `ku_identity_runner`。它在 P5 tag 上不完整，
纯粹因为它自己的文件尚未提交，与 P6 无依赖关系。

---

## 4. P7_SPEC_PREREQUISITE

P7 的 SPEC **不得**在运行闭包已知不完整时写。否则会把一个缺口当成设计基线，
重复 P6 的路径：

```
代码存在 → 测试存在 → artifact 存在 → clean checkout 可运行
```

四项必须全部满足，缺一不可：

```
dependency_closure    COMPLETE
runtime_verify        PASS
filesystem_reach     COMPLETE
test_closure         COMPLETE
```

当前实测：`dependency_closure=INCOMPLETE`、`runtime_verify=FAIL`、
`test_closure` 缺 `test_a_repository_p7_projection.py`。

工具可直接判定：

```
python3 scripts/a_dependency_closure.py --layer P7_PROJECTION --verify
```

退出码非 0 即前置门未过。

---

## 5. 执行顺序（已锁定）

```
1  commit dependency closure audit      本文件 + 工具
2  commit P7 缺失的测试
3  rerun --verify，四项前置门转 PASS
4  draft A_P7_PROJECTION_REFREEZE_SPEC
```

---

## 6. 本审计不做的事

```
不改 076-082
不改 6265038 / dc66bd5
不修 ku_evolution_runner 的 verdict 缺陷（属 P5-evolution re-freeze）
不写 P7 设计
不提交 P7 测试（本提交之后单独一步）
```
---

## 2026-10-01 — tool blind spots: globs and f-strings

Re-running the closure for P7 surfaced two `MISSING` lines that were both
false, and both of the same kind: the tool could not express a pattern that is
a perfectly ordinary way to name a file.

```
MISSING  migration:0[78][0-9]_a_*.sql
MISSING  artifact:_projection.json
```

- the first is a **glob**. `ku_evolution_runner.migration_evidence()` reads the
  A chain with `root.glob("0[78][0-9]_a_*.sql")`. Resolved as a literal path it
  cannot exist, so it was reported missing.
- the second is an **f-string fragment**. `f"book_{book_id}_projection.json"`
  contributes the literal `_projection.json`, which is not a filename.

Both now report what they actually reach:

```
GLOB      migration:0[78][0-9]_a_*.sql -> 13 file(s), all tracked
TEMPLATE  artifact-template:_projection.json -> matches 1 tracked file(s)
           artifacts/a_repository/p7_projection/book_bs_04a94146a35f_projection.json
```

The change matters beyond tidiness. A scanner that prints `MISSING` for files
that are present is a scanner whose `MISSING` gets ignored — and the one line
that *would* have mattered then looks the same as the noise around it.

The tool was checked against planted failures rather than trusted:

```
planted                                     reported
artifact:p9_does_not_exist.json              MISSING          <- still caught
glob "999_*.sql" matching nothing            matched nothing  <- still caught
glob "0[78][0-9]_a_*.sql"                    13 files, tracked
```

The f-string case needed a second fix: `ast.walk` yields an f-string's parts as
ordinary `Constant` nodes, so the same literal was reported twice — once as a
template and once as a missing file. Fragments are now gathered first and
skipped in the plain-constant pass.

## Closure status at 163ea0a

```
layer            modules  missing  untracked  clean-checkout verify
P4_1_DURABLE          7        0         0    PASS
P5_0_CONDITION       20        0         0    FAIL  <- see below
P5_EVOLUTION         13        0         0    PASS
P6_IDENTITY          16        0         0    PASS
P7_PROJECTION        18        0         0    PASS
```

### OPEN: P5_0_CONDITION cannot be verified from a clean checkout

```
declared test : tests/architecture/test_a_condition_boundary_contract.py
on disk       : yes, 30193 bytes
tracked       : NO  (git status reports it as untracked)
--verify      : returncode 4, "file or directory not found"
```

This is **pre-existing and unrelated to the tool change above** — the tool only
surfaced it. P5.0 Condition/Boundary's contract test was never committed, so its
gates cannot be reproduced from a tagged tree the way P4.1, P5 Evolution, P6 and
P7 can.

It is left unfixed here on purpose. The file is untracked work belonging to
someone else's session; committing a 30KB test that no freeze has audited would
manufacture evidence for a layer nobody has re-verified. Recorded here so the
final acceptance cannot silently treat P5.0 as closed.
