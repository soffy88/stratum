"""AII Layer-4 六分类本体抽取 prompt 库 (业务判据).

oskill.ontology_extract 自 v4.0.0 改为通用两遍法框架, 业务 prompt 必须由 AII 注入.
本模块提供 6 个注入参数; 文本源自 oskill v3.25.x 内置版(已验证成立),
其中 PASS2_CHUNK 已把 six_class_rules 烤入(v4 的 pass2_chunk_tmpl 只接 {outline}/{chunk_text}).
"""

PASS1_CHUNK_SYSTEM = """You are a knowledge analyst. Extract structured information from text chunks. Output valid JSON only."""

PASS1_CHUNK_TMPL = """Analyze this text chunk and extract structured knowledge metadata.

Text chunk:
{chunk_text}

Output JSON with:
{{
  "concepts": ["list of core concepts mentioned"],
  "topics": ["main topics covered"],
  "chapter": "chapter or section heading if identifiable, else empty string"
}}"""

PASS1_OUTLINE_SYSTEM = """You are a knowledge architect. Synthesize chunk analyses into a coherent book outline. Output valid JSON only."""

PASS1_OUTLINE_TMPL = """Synthesize these chunk analyses into a full-book outline.

doc_type: {doc_type}
source_credibility: {source_credibility}

Chunk analyses:
{chunk_analyses}

Output JSON with:
{{
  "chapters": ["list of chapter/section names inferred"],
  "core_concepts": ["unified list of core concepts"],
  "main_thread": "one-sentence description of the main argument/thread",
  "stance": "author's overall stance or perspective",
  "doc_type": "{doc_type}",
  "source_credibility": "{source_credibility}"
}}"""

PASS2_SYSTEM = """You are a knowledge unit extractor. Extract structured KUs from text using strict classification rules. Output valid JSON only."""

PASS2_CHUNK_TMPL = """Extract knowledge units from this text chunk.

Full-book outline (context):
{outline}

Text chunk:
{chunk_text}

Classification priority (apply in order — first match wins):
1. why / mechanism / reason (揭示"所以然"/为何如此/必然机制) → knowledge_type = "rationale"
2. how / steps / procedure     → knowledge_type = "procedural"
3. learning strategy/reflection → knowledge_type = "metacognitive"
4. no truth value / relative position / opinion → knowledge_type = "positional"
   ⚠ MUST set stance_holder (non-empty string, who holds this position)
5. essence / principle / definition → knowledge_type = "conceptual"
   sub_type (conceptual ONLY): classification | principle | theory | conditional
   (if uncertain → leave sub_type NULL, do NOT guess)
   procedural sub_type: skill | technique | conditional
   metacognitive sub_type: strategic | task_knowledge | self_knowledge
   factual / rationale / positional → sub_type MUST be NULL
   ⚠ sub_type must be one of the values above for its knowledge_type, or NULL.
     NEVER invent values like "definition", "concept", "formula" — they will be rejected.
6. verifiable fact              → knowledge_type = "factual"

GATE (strictly enforced):
- Arguments, examples, supporting evidence → NOT standalone KUs
  → Demote: add as 'example' field on a KU, or create a 'supported_by' edge
- Do NOT create KUs for mere illustrations or anecdotes

ACTIVE WHY-EXTRACTION (required):
- For each key concept found, ask WHY it works / what mechanism underlies it
- If a mechanism exists → create a rationale KU (the WHY/所以然) + an 'explains' edge

CONCEPT LAYER — ONLY for conceptual KUs that DEFINE a concept (else leave all four NULL):
  defines_concept:    the core concept this KU defines (which concept it carries)
  concept_level:      "concrete" (bound to specific objects, e.g. price elasticity, Pythagorean theorem)
                   or "abstract" (itself abstract / cross-domain, e.g. entropy, equilibrium, derivative,
                      marginal, convexity — these recur across physics/math/economics)
  concept_discipline: the discipline this concept belongs to (economics/math/physics/...), or "general"
                      if cross-domain with consistent meaning (e.g. causality, ratio).
                      ★Judge PER-CONCEPT, not per-book — e.g. price elasticity of SUPPLY vs DEMAND
                      are DIFFERENT concepts.
  concept_invariant:     ONLY if concept_level="abstract" AND you can identify it. The concept's intrinsic
                      LAW / NECESSARY TENDENCY — "how it MUST behave / where it MUST tend" (道) — NOT
                      "what it looks like" (mere appearance/相).
                      e.g. entropy's invariant = "without external force, can only increase over time,
                      irreversible, has a direction" — NOT "a measure of disorder".
                      Math example: a derivative's invariant = "the instantaneous rate of change at a point —
                      how a quantity changes at an instant" (道) — NOT "the limit of the difference
                      quotient" (its formal definition/相). ★Mathematical/abstract concepts HAVE invariants
                      too — extract the intrinsic law/behaviour they capture, not the formal definition.
                      Find it any way: same word across domains (thermodynamic vs information entropy →
                      strip the domain shells, find the shared law); or different words same law (natural
                      selection / market competition); or any insight your understanding reveals.
                      ★Leave NULL if you genuinely cannot. NEVER fabricate an invariant — NULL is correct.
- Non-conceptual KUs (procedural/rationale/factual/positional/metacognitive) do NOT output these
  four fields — they reference concepts but do not define them.

grade: always set to "unverified" regardless of evidence strength

BILINGUAL (one-pass, required for every KU):
- content    = the KU written in the SOURCE language of the text chunk (faithful, used as-is).
- content_zh = a precise Chinese (中文) rendering of `content`, for Chinese readers.
  ★ Keep all $...$ and $$...$$ LaTeX EXACTLY — never translate inside a formula.
  ★ Domain terms must be precise; if unsure, append the English in parens, e.g. 边际成本(marginal cost).
  ★ Do not add, drop, or embellish content — translate only.
  ★ If `content` is already Chinese, set content_zh identical to content.

Output JSON with:
{{
  "ku_candidates": [
    {{
      "id": "temp_<n>",
      "title": "concise KU title",
      "content": "KU content (source language)",
      "content_zh": "中文译文 (Chinese rendering of content)",
      "knowledge_type": "<one of six types>",
      "grade": "unverified",
      "sub_type": "<sub_type or null>",
      "stance_holder": "<required for positional, else null>",
      "example": "<supporting example if demoted, else null>",
      "concepts": ["referenced concepts"],
      "defines_concept": "<conceptual KU only: the concept it defines, else null>",
      "concept_level": "<conceptual KU only: concrete|abstract, else null>",
      "concept_discipline": "<conceptual KU only: discipline or general, else null>",
      "concept_invariant": "<abstract concept only: intrinsic law (道), else null>"
    }}
  ],
  "edge_candidates": [
    {{"source": "<ku_id>", "target": "<ku_id or concept>", "relation_type": "<controlled type>"}}
  ],
  "concept_candidates": ["new concepts discovered in this chunk"]
}}"""


# ───────────────────────────────────────────────────────────────────────────
# HQ 变体 (章节级高质量抽取测试): 六类要点边界清晰 + 闸门加严(例子数据/依赖上下文/换措辞重抽).
# 输出结构与 PASS2_CHUNK_TMPL 完全一致(可直接喂 ontology_extract), 仅判据更严.
# ───────────────────────────────────────────────────────────────────────────
PASS2_SYSTEM_HQ = """You are a precise knowledge-unit extractor. Extract only self-contained, non-redundant, universally-true knowledge units, following strict per-class rules. Output valid JSON only."""

PASS2_CHUNK_TMPL_HQ = """Extract high-quality knowledge units from this text chunk.

Full-book outline (context):
{outline}

Text chunk:
{chunk_text}

SIX CLASSES — each has a precise boundary (apply in order, first match wins):
1. rationale (释因/所以然): reveals WHY something holds / the MECHANISM behind it.
   ✗ NOT a restatement of a definition. ✗ NOT "X is important because it tells us Y" (that's filler).
   One distinct mechanism = ONE KU.
2. procedural (程序/步骤): a how-to / algorithm / calculation procedure. One complete procedure = ONE KU.
3. metacognitive: a learning strategy / reflection on how to study.
4. positional: an opinion/stance with NO truth value. ⚠ MUST set stance_holder (who holds it).
5. conceptual (概念/定义/规律): a definition OR a universal principle/law.
   ✗ Do NOT emit the SAME concept/law twice in different wording — emit it ONCE, the most complete form.
   sub_type (conceptual ONLY): classification | principle | theory | conditional (else NULL).
6. factual: a verifiable, UNIVERSAL fact.
   ✗ NOT example-specific data. "gasoline rose 33%, quantity fell 9%" / "tuition $100→$160" are EXAMPLE
     DATA, not factual KUs — they belong in the 'example' field of the KU they illustrate.

GATE (strictly enforced — drop or demote, do NOT emit as standalone KU):
- EXAMPLE DATA (specific numbers/instances illustrating a point: "$160 × 12.5 = $2,000", "elasticity 2.27
  for airline tickets") → put in the 'example' field of the KU it supports; NEVER a standalone KU.
- CONTEXT/FIGURE-DEPENDENT (cannot be understood alone: "the green rectangle", "total tuition increases
  because the reduction is insufficient" referring to a specific example) → either rewrite to be fully
  self-contained (state the general principle), or DROP it.
- REWORDED DUPLICATE: if a unit restates a knowledge point you already emitted from this chunk, do NOT
  emit it again. One knowledge point = one KU (its most complete form).
- Arguments / illustrations / anecdotes → NOT standalone KUs.

ACTIVE WHY-EXTRACTION: for each key concept, if a real mechanism exists → one rationale KU (the WHY) +
an 'explains' edge. (But a mechanism stated once is enough — do not paraphrase it into several KUs.)

CONCEPT LAYER — ONLY for conceptual KUs that DEFINE a concept (else all four NULL):
  defines_concept / concept_level (concrete|abstract) / concept_discipline (or "general") /
  concept_invariant (abstract only: intrinsic LAW/道, NOT formal definition/相; NULL if unsure — never fabricate).

grade: always "unverified".

BILINGUAL (one-pass, every KU): content = source language (faithful); content_zh = precise Chinese,
keep $...$ LaTeX exact, append English in parens for uncertain terms, translate only (no add/drop).

Output JSON with:
{{
  "ku_candidates": [
    {{
      "id": "temp_<n>", "title": "concise KU title",
      "content": "KU content (source language, self-contained, universal)",
      "content_zh": "中文译文",
      "knowledge_type": "<one of six>", "grade": "unverified",
      "sub_type": "<sub_type or null>", "stance_holder": "<required for positional, else null>",
      "example": "<demoted example DATA/instance if any, else null>",
      "concepts": ["referenced concepts"],
      "defines_concept": "<conceptual-defining KU only, else null>",
      "concept_level": "<concrete|abstract, else null>",
      "concept_discipline": "<discipline or general, else null>",
      "concept_invariant": "<abstract concept intrinsic law, else null>"
    }}
  ],
  "edge_candidates": [
    {{"source": "<ku_id>", "target": "<ku_id or concept>", "relation_type": "<controlled type>"}}
  ],
  "concept_candidates": ["new concepts discovered in this chunk"]
}}"""
