# AII 概念与本性存储升级 SPEC

> **Doc ID:** AII-CONCEPT-STORAGE-001
> **依据:** AII-CONCEPT-NATURE-001(概念两层 + 本性维度 + 本性同源连接 + 向量统一标记)。
> **目标:** 把"概念向量唯一化 + 本性维度 + 本性向量收敛"落到存储，作为概念语义归一与本性同源连接的地基。
> **现状(实证):** concept_onto 是纯名字登记表(name 唯一/中文名/别名)，无向量、无 level/discipline/nature；去重只到字符串同名(语义同概念碎成多条)；extractor 只产裸概念名；nature 表不存在。
>
> **分两层落地:**
> - **存储层(AII 本地可做)**：扩 concept 表 + 建 nature 表 + 概念向量化与语义归一 + 本性向量收敛。**先建好，结构在那能存。**
> - **抽取层(主库 oskill，Owner SPEC)**：让 extractor 产 level/discipline/nature。**结构先到位，抽取跟上就填；未填的留空。**

---

## 一、向量统一标记机制(核心，先定死)

**所有向量(概念/本性/KU)在向量里留固定维度做类型标记。**

```
向量 = [ 语义维度(embedding 模型产出，如 BGE-M3 1024维) | 标记维度(固定，标识类型) ]

类型标记(标记维的值)：
  概念向量    concept
  本性向量    nature
  KU 向量     ku        (KU 已有 embedding，纳入统一标记体系)
```

**★实现要点(避免标记被语义维淹没)：**
- 标记维若只用 0/1，余弦相似度下会被语义维淹没，区分不出类型 → 必须处理。
- **方案 A(推荐)**：检索/比对时**先按标记维过滤分组**(只在"概念 vs 概念"、"本性 vs 本性"内部比相似度)，标记维只做硬分组，不参与相似度。简单、可靠。
- **方案 B**：标记维赋足够大的权重值，使不同类型向量在该维天然拉开、跨类型相似度被压低。需实测调权重。
- **CC 实现时实测**：确认"同类型之间能正确比相似度、跨类型不会误判为相似"。

> 作用：一个向量空间里能区分概念/本性/KU；**同一概念向同一处收敛(共指即连)、同一本性向同一处收敛(同源即连)**，都在各自类型分组内做，不串。

---

## 二、存储层(AII 本地)

### 2.1 concept 表扩字段

在 concept_onto 基础上加：

| 列 | 类型 | 说明 |
|---|---|---|
| level | text | concrete \| abstract(具体/抽象概念) |
| discipline | text | 学科归属(数学/经济/物理/.../通用)；同名+不同学科=不同概念 |
| vector | vector | 概念向量(带 concept 标记维) |
| nature | text \| null | 该抽象概念的本性(内在规律/必然趋势)；没有则 NULL |
| nature_vector | vector \| null | 本性向量(带 nature 标记维)；nature 为空则 NULL |
| nature_concept_id | uuid \| null | 若本性已凝结为本性概念，指向它 |

(保留原有 name/name_zh/aliases/created_at)

### 2.2 nature_concept 表(新建，涌现产生)

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| statement | text | 这个本性是什么(如"无外力则只增不可逆") |
| vector | vector | 带 nature 标记维 |
| member_concept_ids | jsonb | 共有此本性的抽象概念(≥2 才成立) |
| created_at | timestamptz | |

### 2.3 ★概念语义归一(同概念唯一向量)

存一个概念时，不再只按字符串名去重，而是**语义归一**：

```
抽出一个概念 →
  ① 判定 discipline(学科)
  ② 算概念向量(带 concept 标记)
  ③ 在【同 discipline】的已有概念里，按向量相似度找最近的
     - 相似度 ≥ 阈值 → 是同一个概念 → 认已有那条(不新建)，可补充别名
     - 相似度 < 阈值 → 新概念 → 新建一条向量
  ④ ★同名+不同 discipline = 不同概念(经济"弹性"≠物理"弹性")，各自独立
```

> 这解决现状的碎片化："price elasticity"和"Price Elasticity of Demand"(同学科、语义近) → 归一为一个概念，向量唯一。根因 B 里"概念名接不到 KU"的底层原因(概念碎片)由此根治。
> **阈值需实测调**(太高=该合不合，碎片仍在；太低=不该合错合，制造假同一)。同名不同学科靠 discipline 先隔离，降低错合风险。

### 2.4 ★本性向量收敛 → 凝结本性概念

```
抽出/已有抽象概念的本性 → 算 nature_vector(带 nature 标记) →
  在已有 nature_vector(及 nature_concept.vector)里找最近：
    - 与另一个(或多个)抽象概念的本性向量收敛(相似度≥阈值) →
        凝结为 nature_concept(若尚无)，相关抽象概念 nature_concept_id 指向它
        → 这些抽象概念之间自动成立【本性同源】强联系
    - 暂无收敛对象 → 留作该抽象概念自己的 nature(还不是本性概念)
```

> 同一个本性，无论从哪个概念、哪条途径、何时抽到，都向同一处收敛 → 共享即被发现，不靠逐对判断。**单个抽象概念的本性，在与别的收敛之前，只是它自己的 nature，不进 nature_concept 表。**

### 2.5 ku_concept 关联(已有，确认)

每条 KU 含哪些概念，写 ku_concept_onto(已存在)。概念归一后，多条 KU 自然挂到同一个唯一概念上。

---

## 三、抽取层(主库 oskill，Owner SPEC，后跟上)

extractor 当前只产裸概念名(concept_candidates: list[str])，不产新维度。要填上存储层的新字段，需主库改 Pass2：

**让 extractor 对每个概念产出：**
```
{
  name:        概念名
  level:       concrete | abstract       # 是具体概念还是抽象概念
  discipline:  学科 | 通用                # 学科归属
  nature:      该抽象概念的本性(若是抽象概念且能抽到；否则空)
}
```

**本性抽取(开放，不设上限)——prompt 引导 LLM：**
- 意识到抽象概念背后可能有本性(内在规律/必然趋势，非定义)
- 顺"同词跨领域"痕迹抓(热力学熵/信息熵 → 熵的本性)
- 也可凭理解直接看出"不同词、不同领域但本性同构"(自然选择/市场竞争)而抓
- 抽到则产 nature，没有则留空——不硬编

> **此为 Owner SPEC，走主库流程。在它完成前，存储层先建好、extractor 暂只填 name，level/discipline/nature 留空——结构在那，抽取跟上即填。**
> **过渡期可选**：AII 本地加一个"概念 enrichment 后处理"——抽完后用 LLM 对已存概念补判 level/discipline/nature(不动主库)。是否做由后续决定。

---

## 四、落地顺序

1. **存储层(本地，先做)**：concept 扩 6 字段 + 建 nature_concept 表 + 向量标记机制(先定方案A/B并实测) + 概念语义归一 + 本性收敛逻辑。
2. **在现有微观样本上验证**：把 micro_sample_body 的概念向量化、语义归一，看碎片化是否消除(price elasticity 系列是否归一)、根因 B 的"概念名接不到 KU"是否缓解。
3. **抽取层(主库，Owner SPEC)**：extractor 产 level/discipline/nature。
4. 抽取跟上后，本性维度真正充实，本性同源连接开始涌现。

---

## 五、命门

- **向量标记必须实测**(同类型能比、跨类型不混)——方案A(分组过滤)最稳。
- **概念语义归一的阈值**实测调；**同名不同学科靠 discipline 硬隔离**(降错合)。
- **本性没有就留空**——不硬编、不造假本性。
- **nature_concept 只在 ≥2 抽象概念本性收敛时涌现**——非预设。
- 存储层本地做；抽取层产新维度走 Owner SPEC，不在 AII 改主库。

