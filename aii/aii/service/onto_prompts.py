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
1. why / mechanism / reason    → knowledge_type = "explanatory"
2. how / steps / procedure     → knowledge_type = "procedural"
3. learning strategy/reflection → knowledge_type = "metacognitive"
4. no truth value / relative position / opinion → knowledge_type = "positional"
   ⚠ MUST set stance_holder (non-empty string, who holds this position)
5. essence / principle / definition → knowledge_type = "conceptual"
   sub_type (conceptual ONLY): classification | principle | theory | conditional
   (if uncertain → leave sub_type NULL, do NOT guess)
   procedural sub_type: skill | technique | conditional
   metacognitive sub_type: strategic | task_knowledge | self_knowledge
   factual / explanatory / positional → sub_type MUST be NULL
   ⚠ sub_type must be one of the values above for its knowledge_type, or NULL.
     NEVER invent values like "definition", "concept", "formula" — they will be rejected.
6. verifiable fact              → knowledge_type = "factual"

GATE (strictly enforced):
- Arguments, examples, supporting evidence → NOT standalone KUs
  → Demote: add as 'example' field on a KU, or create a 'supported_by' edge
- Do NOT create KUs for mere illustrations or anecdotes

ACTIVE WHY-EXTRACTION (required):
- For each key concept found, ask WHY it works / what mechanism underlies it
- If a mechanism exists → create an explanatory KU + an 'explains' edge

grade: always set to "unverified" regardless of evidence strength

Output JSON with:
{{
  "ku_candidates": [
    {{
      "id": "temp_<n>",
      "title": "concise KU title",
      "content": "KU content",
      "knowledge_type": "<one of six types>",
      "grade": "unverified",
      "sub_type": "<sub_type or null>",
      "stance_holder": "<required for positional, else null>",
      "example": "<supporting example if demoted, else null>",
      "concepts": ["referenced concepts"]
    }}
  ],
  "edge_candidates": [
    {{"source": "<ku_id>", "target": "<ku_id or concept>", "relation_type": "<controlled type>"}}
  ],
  "concept_candidates": ["new concepts discovered in this chunk"]
}}"""
