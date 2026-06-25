# AII 本性维度抽取落地(路A:骑 ku_candidate 字段)

> **Doc ID:** AII-NATURE-EXTRACT-001
> **依据:** AII-CONCEPT-NATURE-001(概念两层+本性维度) + AII-CONCEPT-STORAGE-001(存储层)。
> **边界:** 纯 AII 本地——扩 onto_prompts.py + onto_persist + 接 converge_invariants。**不动主库**(主库提供抽取动作，抽什么怎么抽是 AII 的事)。
>
> **路线选择(实证后定):**
> - ❌ 路C(改 oskill 收 dict 概念)：动主库 Owner SPEC，不走。
> - ❌ 路B(抽后 enrichment 单独跑 LLM 判)：多一遍调用、上下文割裂、贵。
> - ✅ **路A(骑 ku_candidate 字段)**：概念的 level/discipline/invariant 挂在"定义该概念的 KU"上产出。
>   实证③证实：oskill 只 coerce knowledge_type/sub_type/stance_holder，**KU 额外字段原样保留到 AII**。绕开 oskill 的 `isinstance(concept,str)` 过滤。抽取当下顺手判，上下文最全、不多花调用、最准。

---

## 一、核心机制：概念信息骑在"定义它的 KU"上

概念出现在很多 KU 里(价格弹性出现在 20 个 KU)，但**只有"定义/承载该概念的那条 KU"负责产出它的 level/discipline/invariant**，避免多条 KU 对同一概念给出冲突判断。

```
一条 conceptual KU(如"价格弹性的定义") 额外产出:
  defines_concept:  这条KU定义的核心概念名(它承载哪个概念)
  concept_level:    concrete | abstract     (该概念是具体/抽象)
  concept_discipline: 学科 | 通用            (该概念的学科归属，每概念判，非书级统一)
  concept_invariant:   (仅 abstract 且能抽到)   该抽象概念的本性
```

> 非 conceptual 的 KU(程序/解释/事实等)不产这些——它们引用概念，但不"定义"概念。
> 一个概念的 level/discipline/invariant，由**定义它的那条 conceptual KU**一次性产出。

---

## 二、PASS2 prompt 扩展(onto_prompts.py，AII 本地)

在 PASS2_CHUNK_TMPL 的 conceptual KU 部分，增加：

### 2.1 概念的 level / discipline(每个 conceptual KU 判其定义的概念)

```
For a conceptual KU that DEFINES a concept, additionally output:
  defines_concept:    the core concept this KU defines
  concept_level:      "concrete" (bound to specific objects, e.g. price elasticity, Pythagorean theorem)
                   or "abstract" (itself abstract, cross-domain, e.g. entropy, equilibrium)
  concept_discipline: the discipline this concept belongs to (economics/math/physics/...),
                      or "general" if cross-domain with consistent meaning (e.g. causality, ratio).
                      ★Judge per-concept, not per-book — distinguishes e.g. price elasticity of
                      SUPPLY vs DEMAND as different concepts.
```

### 2.2 本性抽取(仅 abstract 概念，开放、不设限)

```
If the concept is ABSTRACT, attempt to extract its NATURE (本性):
  The invariant is the concept's intrinsic LAW or NECESSARY TENDENCY —
  "how it must behave / where it must tend" — NOT "what it looks like" (that is mere appearance/相).
  Example: entropy's invariant = "without external force, can only increase over time, irreversible,
  has a direction" — NOT "a measure of disorder" (that is its appearance).

  Ways to find invariant (open, no upper limit):
  - Same word across domains: a word naming different things in different fields
    (thermodynamic entropy vs information entropy) — humans reuse one word because they
    sensed a shared invariant. Strip the domain shells, find the common intrinsic law.
  - Different words, same invariant: you may directly recognize that differently-named concepts
    in different fields share the same intrinsic law (natural selection / market competition).
  - And any other way your understanding reveals.

  Output concept_invariant if you can identify it; leave NULL if you genuinely cannot.
  ★Never fabricate a invariant. NULL is correct when there isn't a clear intrinsic law.
```

> 抽取原则严格对齐 CONCEPT-NATURE-001：本性是"道"(必然怎么变)非"相"(是什么样)；途径开放不设限；抽不到留空，绝不造假。

---

## 三、持久化(onto_persist，AII 本地)

### 3.1 写概念的 level / discipline / invariant

```
对每条 conceptual KU，若它产了 defines_concept：
  → 找/建该概念的 concept_onto 行(经语义归一后的 canonical 概念)
  → 写入 concept_level → concept_onto.level
         concept_discipline → concept_onto.discipline (覆盖书级默认)
         concept_invariant → concept_onto.invariant (若非空)
冲突处理：同一 canonical 概念被多条 KU 赋值时，
  - level/discipline：取首个非空；若冲突，记日志(不同KU判同概念学科不一致=信号，待观察)
  - invariant：取首个非空(一个概念一个本性)
```

### 3.2 算 invariant_vector(接通 converge_invariants)

```
对有 invariant 的概念：
  invariant_vector = vector_encode(invariant)   # 带 invariant 类型(方案A:存 invariant_vector 字段，与 concept vector 隔离)
  写入 concept_onto.invariant_vector
→ 现成的 converge_invariants 此时才有数据：
   扫描所有 invariant_vector，≥2 个抽象概念的本性向量收敛(相似度≥阈值)
   → 凝结 invariant_concept + 相关概念 invariant_concept_id 指向它 + 本性同源连接
```

> 这接通了之前**空转的 converge_invariants**——invariant 有数据后，本性收敛才真正工作。

---

## 四、现实预期(诚实标注)

**单本微观教材里，本性维度大概率稀疏：**
- 微观经济学是**单一学科**，"同词跨领域"在单本书内几乎不触发(不会同时出现物理熵和信息熵)。
- 能抽到的本性，多是经济学内部抽象概念(如"均衡""弹性")的本性——数量有限。
- **本性同源(converge_invariants 凝结 invariant_concept)需要跨学科**：要等物理书、信息论书等不同学科的书摄入，"熵"在多领域出现，本性才收敛涌现。

**所以本性维度的真正威力，要等知识库跨学科后才显现**(呼应"几万 KU、多学科后用不同方式找联系")。**现在做：prompt + 持久化 + 接通 converge_invariants 的结构先建好、能抽就抽、结构充实；本性同源的涌现是后话。** 不因单本稀疏而不做——结构对了，跨学科书一进来，本性自动开始收敛。

---

## 五、落地步骤

1. 扩 PASS2_CHUNK_TMPL：conceptual KU 产 defines_concept/concept_level/concept_discipline/concept_invariant(§2)。
2. onto_persist：读这些字段，写 concept_onto.level/discipline/invariant(§3.1)。
3. 对有 invariant 的概念算 invariant_vector 写入，接通 converge_invariants(§3.2)。
4. 验证(等 API 余额)：在 micro_clean 或一章上跑，看：
   - concept_onto 的 level/discipline 填充率(discipline 是否每概念不同、不再书级统一)
   - 供给弹性 vs 需求弹性是否因 discipline 细分而不再误合
   - 抽到几个 invariant(单本经济学预期稀疏，有几个即证明 prompt 工作)
   - converge_invariants 是否空转(单本预期仍空，等跨学科)

---

## 六、命门

- 纯 AII 本地(扩 prompt + onto_persist + 接 converge_invariants)，**不动主库**。
- 概念信息骑"定义它的 KU"，避开 oskill 的 str 过滤。
- 本性：道非相；途径开放；**抽不到留空，绝不造假**。
- 一个概念一个 level/discipline/invariant(由定义它的 KU 产)，冲突取首个非空+记日志。
- invariant_vector 用方案A(独立字段隔离)，不在向量内塞标记维(实测证明会毁区分度)。
- 单本稀疏是正常的——结构先建好，本性同源等跨学科涌现。

