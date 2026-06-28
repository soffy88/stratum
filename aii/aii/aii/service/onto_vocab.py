"""AII 词表单一权威 (主库 oskill v4.1.0 / omodul v1.31.0 起词表外移, AII 自助注入).

抽取(ontology_extract)与持久化(register_ku_ontology)都注入这里的 frozenset,
单一来源避免漂移. ku_onto 的 CHECK 约束、onto_prompts 判据、文档都以此为准.

★knowledge_type 用 AII 自己的 "rationale"(释因性/所以然——揭示"为何如此/必然机制"),
  替代主库默认的 "explanatory". 其余三套与数据设计(AII-DATA-MODEL-001)一致.
"""

VALID_KNOWLEDGE_TYPES = frozenset({
    "conceptual",    # 概念性(是什么/本质/原理)
    "rationale",     # 释因性(为何如此/机制/所以然) —— 原 explanatory
    "factual",       # 事实性(可验证事实)
    "metacognitive", # 元认知(怎么学/反思)
    "positional",    # 立场性(无真值/相对立场)
    "procedural",    # 程序性(怎么做/步骤)
})

VALID_SUB_TYPES = frozenset({
    "classification", "conditional", "principle", "self_knowledge", "skill",
    "strategic", "task_knowledge", "technique", "theory",
})

VALID_RELATION_TYPES = frozenset({
    "causes", "contradicts", "contrasts_with", "explains", "opposes",
    "prerequisite_of", "same_as", "special_case_of", "subsumes", "supported_by",
})

VALID_GRADES = frozenset({
    "contradicted", "high", "low", "moderate", "pending", "refuted",
    "unverified", "verified",
})
