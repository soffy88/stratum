# A_P5_4_CONSTRAINT SCHEMA REVIEW

TASK=A_P5_4_CONSTRAINT_IMPLEMENTATION
PHASE=0 (schema review) — **STOPPED BEFORE WRITING 081**
BASELINE=P5.3_PAPER=FROZEN (080), 079/078/077/075=FROZEN
STATUS=BLOCKED_PENDING_DECISION

---

## 0. 一句话结论

`081` 还没写。Phase 0 实测发现两件事：

1. **§10 的规则只能从原始跨度引用，不能从 KU statement 引用**——而两者的用词不同，
   有一处 KU statement 里的「上限」在原始跨度里**根本不存在**。
   按 KU statement 分类，等于把解释洗成来源声明，正是 §2 禁止的 derived constraint。
2. **pilot 的诚实产出是 1 条约束，不是「一组」。**
   7 个带限制标记的跨度里，3 个没有冻结 KU（§5 要求 `knowledge_unit_id NOT NULL`），
   而 `SOFT` 的词汇在本语料出现 **0 次**。

其余 5 条是可实现的偏离，逐条给出实测证据。

## 1. F1 — §10 与 KU statement 冲突（BLOCKER）

§10 要求 `quoted_text in evidence_span`。实测 KU statement 与原始跨度**用词不同**：

```
KU  : 巴比伦法定利率上限：银子贷款20%/年（按重量计）
SPAN: 银子贷款按重量计算每年20%

KU  : 罗马法定利率上限：8.333%/年
SPAN: 贷款的利息被限制为不得超过每年8.333%
```

```
「法定利率上限」出现在 3 个跨度里，但在 KU statement 里更多
「20%/年」  只在 KU statement 里，跨度写的是「每年20%」
「8.333%/年」 只在 KU statement 里，跨度写的是「每年8.333%」
```

后果很直接：`subject` / `predicate` / `object` / `boundary`
**必须从原始跨度逐字引用**。若从 KU statement 取，`boundary = "20%/年"`
在跨度里不存在，§10 直接违约。

## 2. F2 — 巴比伦 20% 无法被诚实地判为 HARD（BLOCKER）

这是 F1 最尖锐的一处：

```
KU statement : 巴比伦法定利率上限：银子贷款20%/年（按重量计）    <- 有「上限」
原始跨度     : 银子贷款按重量计算每年20%                       <- 没有任何禁止词
```

跨度里没有 不得超过 / 禁止 / 必须 / 限制，也没有「上限」。
**「上限」这个词是抽取器加进 KU statement 的，不是书里写的。**

所以：
- 若按 KU statement 判 HARD → 把解释当成来源声明 → §2 禁止的 derived constraint。
- 若按跨度判 → 跨度只陈述了一个利率，没有禁止语气，HARD 无依据。

对照之下，同一页的谷物贷款跨度**确实**写了「上限」：

```
p4 SPAN: 法定利率上限确定为谷物贷款每年33.333%，以实物偿还
```

说明「上限」在书里**可以**出现，只是银币贷款那句没有。
这不是随机的，是抽取器在两句上做了同样的框定。

## 3. F3 — pilot 的诚实产出是 1 条（BLOCKER）

全语料 18 个跨度（不是 17，`reading_evidence` 现有 18 行），
11 个有冻结 KU，7 个没有。带限制标记的 7 个跨度：

```
anchor         spans
NO FROZEN KU   3      p4 法定利率上限确定为谷物贷款每年33.333%…
                      p5 所有贷款都必须附有书面合约，并由官员作证
                      p7 他们减少或者豁免了许多债务…但是禁止个人劳役偿债
has frozen KU  4      p5 如果作弊收取的利息高于法定上限，那么债务的本金就会被免除
                      p6 …因而必须进行重大改革
                      p9 贷款的利息被限制为不得超过每年8.333%
                      p9 高于法定上限的利息将被处以4倍损害赔偿
```

§5 要求 `knowledge_unit_id NOT NULL` + FK 到 `knowledge_unit`，
所以**没有冻结 KU 的 3 个跨度写不进去**——
而其中恰好是全语料最干净的三条禁止性表述。

剩下 4 条里，只有一条四条字段都能从跨度逐字引用、且带明确禁止词：

```
p9  贷款的利息被限制为不得超过每年8.333%        ku_15a527238f5c   HARD 可判
    subject  = 利息
    predicate= 被限制为不得超过
    object   = 每年8.333%
    boundary = 8.333%

p5  如果作弊收取的利息高于法定上限，那么债务的本金就会被免除
    -> 条件性后果，不是对利率的限制
p6  …因而必须进行重大改革。
    -> 「必须」指向改革，不是信贷约束
p9  高于法定上限的利息将被处以4倍损害赔偿
    -> 罚则，boundary=4倍，但它是对上限的处罚而非上限本身
```

**所以 pilot 的诚实产出是 1 条 HARD 约束**，加上 2 条类型存疑的候选项。

## 4. F4 — `SOFT` 与 `SELF_DEFINED` 在本语料无支撑

```
通常 / 一般情况 / 一般而言 / 大多数 / 多半      0 次
可能 / 也许 / 或许 / 似乎 / 大概               2 次（hedge，不是 SOFT）
```

而 P5.0 冻结的 `TENDENCY_WORDS` 恰好把「通常/一般/可能/大多数/往往」这一组
**作为 condition 层的拒绝词**（「A tendency is not a condition.
Refused, never down-weighted.」）。

也就是说 P5.4 的 `SOFT` 定义词，与 077 已冻结的拒绝词表**是同一批词**。
不同层用同一批词不矛盾（一句倾向性陈述可以是软约束），
但本阶段 `SOFT` 一个也验证不了。

`SELF_DEFINED`（「来源作者自定义范围」）在这批语料里同样没有可判定的样本。

## 5. F5 — §8 要求的索引**已经存在**，081 不需要新建

```
knowledge_unit_id_source_version_uniq
  ON knowledge_unit (id, source_version_id)      <- 079 已建
```

§8 的 `Required index` 与 079 为跨书复合外键建的是同一个。
081 只需引用它，**不需要在对冻结表上新加任何索引**。
（080 为 source_version 建的那个是另一个，本次不需要。）

## 6. F6 — P5.0 已经为限制预留了槽位（P5.4 是它的指定去处）

077 的 `ku_boundary_candidate` 现在 **0 行**，且：

```python
NOT_YET_EXTRACTABLE_BOUNDARY_TYPES = ("SCOPE_LIMIT", "EXCEPTION")
```

P5.4 的 HARD 约束「不得超过 8.333%」正是 **SCOPE_LIMIT**——
077 明确以「没有抽取器」为由**扣住**的那个类型。

所以 **081 与 077 不是重复，是填坑**：077 声明了 TIME_LIMIT/ACTOR_LIMIT
（实测 0 命中）并扣住 SCOPE_LIMIT/EXCEPTION，P5.4 承接后者。
需要注意的是 081 之后 A仓 会有两套限制词表：
077 的 TIME_LIMIT/ACTOR_LIMIT（范围种类）vs 081 的 HARD/SOFT/SELF_DEFINED（强制强度）。
两者是不同的轴，可以共存，但要在文档里写明它们不可互相映射。

## 7. F7 — 077 的 TIME_LIMIT 标记有一个实测假阳性（不修，仅记录）

077 的注释称两个边界标记集「Both sets score 0/10 on the frozen pilot」。
实测现在有 1 处命中：

```
p10: 历史最初时期巴比伦王朝、古希腊和古罗马的这三个案例足以支持这样一个结论：
     即含息信贷在有文字历史出现之前就已经普及到了足以产生重大政治问题的程度。
```

命中的是 `之前`。这里是**叙事的「在……之前」**，不是 TIME_LIMIT 想要的
「不迟于 / 截至」这类期限。属于 077 已冻结标记的假阳性，本阶段不动它；
但它恰好印证 §4：**关键词只能用于召回，不能用于定类**。

## 8. F8 — `evidence_ids` 在 hash 里，排序规则未定义

§9 的 `constraint_hash` 包含 `evidence_ids`。这与 P5.3 的决定不同——
080 把证据放在 candidate 之外的可追加层，其重放键是 `evidence_hash`。
081 的证据是 candidate 的**一列**，所以它进入身份是合理的。

但排序规则必须写明：**证据 id 的遍历顺序不是声明，应当排序后进 hash**，
理由与 080 的 `evidence_hash` 相同。

## 9. F9 — `constraint_type` 的判定依据

§4 已经禁止「单纯关键词决定类型」，要求 span 存在 + constraint predicate 存在 +
evidence 锚定。但那三条**都不足以定 `constraint_type`**：

- HARD 要的是「来源明确禁止/限定」的**语气**，而语气不是字段。
- SOFT 要的是「倾向性」标记，实测 0 次（F4）。
- SELF_DEFINED 要的是「作者自定义」这一判断，实测无样本。

所以 `constraint_type` 最终仍需一个**服务层判定**，并如实记录：
本阶段只有一个样本可判（HARD），其余类型**未经检验**。

## 10. 需要你决定的六件事

1. **F1/F2（关键）**：`subject`/`predicate`/`object`/`boundary` 一律从**原始跨度**引用，
   不从 KU statement 引用——是否接受？接受则巴比伦 20% 因跨度无禁止词而**不入 pilot**，
   其「上限」定性记为抽取器解释。
2. **F3**：pilot 只落 **1 条**诚实的 HARD 约束（罗马 8.333%），
   p5 条件性后果 / p6 改革要求 / p9 罚则三条作为**已知未收**记录——是否接受？
   还是先扩摄取，把那 3 个没有冻结 KU 的跨度冻结成 KU？
3. **F4**：`SOFT` / `SELF_DEFINED` 保留在 CHECK 里（不可写），
   但如实记为未经检验——是否接受？
4. **F5**：081 复用 079 已建的 `knowledge_unit_id_source_version_uniq`，不新建索引。
5. **F8**：`evidence_ids` 排序后进 hash（遍历顺序不是声明）。
6. **F9**：`constraint_type` 由服务层判定，且本阶段只有 HARD 可验证，
   其余两类记为未经检验。