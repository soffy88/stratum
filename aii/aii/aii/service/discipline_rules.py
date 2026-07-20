"""substrate → 学科 的程序化判据(共享规则, 0 LLM, 每条结论可回溯到命中了哪些词)。

这套规则是 2026-07-20 给存量 189 个 substrate 定学科时用的那一套(见
aii/migrations/seed/substrate_discipline.tsv), 抽出来复用于【新书自动登记】——
存量和增量用同一把尺, 免得新书又长出第三套口径。

★为什么不按管线/前缀推(实证否掉的两条捷径):
  · advmath_zh 前缀 30 本里 23 本是经济学教材 —— 前缀记录的是"哪条管线灌的"
  · ingested_substrate.subject 同样不可信 —— misc_zh 登记'经济学', 实际一本经济书没有
  所以只认【书的实际内容】。

受控集合(Wiki 2026-07-20 拍板, 粗粒度): 数学/经济学/哲学/心理学/计算机/其他
判不出来的落 '其他' 而不是留空 —— 留空就是下个月又一堆 NULL; 落 '其他' 至少是
受控值, 且带 confirmed_by=NULL 等人复核, 在报告里看得见。
"""

CONTROLLED = ("数学", "经济学", "哲学", "心理学", "计算机", "其他")

# 刻意避开会互相污染的宽泛词: "行为"不给心理学(行为金融是经济学);
# "模型/分析/理论"这类各科通用词一律不收。
KEYWORDS: dict[str, tuple[str, ...]] = {
    "数学": (
        "定理",
        "引理",
        "推论",
        "微积分",
        "导数",
        "积分",
        "函数",
        "收敛",
        "极限",
        "矩阵",
        "向量",
        "概率",
        "随机变量",
        "分布",
        "凸函数",
        "凸集",
        "流形",
        "拓扑",
        "级数",
        "微分",
        "偏导",
        "连续性",
        "映射",
        "集合",
        "数列",
        "曲率",
        "范数",
        "特征值",
        "theorem",
        "lemma",
        "corollary",
        "derivative",
        "integral",
        "converge",
        "matrix",
        "probability",
        "manifold",
        "topolog",
        "continuity",
        "differentiab",
        "calculus",
        "eigen",
        "vector space",
        "injection",
        "surjection",
        "power rule",
        "phase plane",
    ),
    "经济学": (
        "经济",
        "市场",
        "需求",
        "供给",
        "价格",
        "均衡",
        "效用",
        "成本",
        "厂商",
        "货币",
        "通胀",
        "通货膨胀",
        "增长",
        "税收",
        "金融",
        "投资",
        "收益",
        "资本",
        "消费者",
        "生产者",
        "垄断",
        "博弈",
        "福利",
        "贸易",
        "失业",
        "利率",
        "宏观",
        "微观经济",
        "demand",
        "supply",
        "price",
        "equilibrium",
        "utility",
        "cost",
        "market",
        "inflation",
        "monetary",
        "fiscal",
        "capital",
        "monopol",
        "surplus",
        "elasticity",
        "nash",
        "game theor",
        "welfare",
    ),
    "哲学": (
        "哲学",
        "形而上",
        "认识论",
        "伦理",
        "本体论",
        "知识论",
        "道德",
        "存在论",
        "现象学",
        "辩证",
        "philosoph",
        "epistem",
        "metaphys",
        "ethic",
        "ontolog",
    ),
    "心理学": (
        "心理学",
        "认知心理",
        "认知科学",
        "记忆",
        "注意力",
        "情绪",
        "知觉",
        "潜意识",
        "psycholog",
        "cognitive science",
        "perception",
        "unconscious",
    ),
    "计算机": (
        "算法",
        "程序设计",
        "数据结构",
        "神经网络",
        "机器学习",
        "深度学习",
        "编程",
        "计算机",
        "决策树",
        "algorithm",
        "neural network",
        "machine learning",
        "data structure",
        "decision tree",
        "gradient descent",
    ),
}

TITLE_WEIGHT = 5  # 书名命中比正文命中更可信
MIN_SCORE = 3  # 低于此视为证据不足
RATIO = 1.6  # 第一名/第二名 低于此视为两科纠缠


def classify(texts: list[str], title: str | None = None) -> tuple[str, str]:
    """按关键词命中给一批文本定学科。返回 (discipline, evidence)。

    ★判不出来时返回 ('其他', 原因) —— 不抛异常、不留空: 调用方(新书自动登记)不能
    因为分不清学科就阻塞整条灌书管线; 落受控值 + confirmed_by=NULL 让人事后复核。
    """
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}

    def _add(text: str, weight: int):
        t = (text or "").lower()
        for disc, kws in KEYWORDS.items():
            got = [k for k in kws if k.lower() in t]
            if got:
                scores[disc] = scores.get(disc, 0) + len(got) * weight
                hits.setdefault(disc, []).extend(got)

    if title:
        _add(title, TITLE_WEIGHT)
    for x in texts:
        _add(x, 1)

    if not scores:
        return "其他", "无任何关键词命中(证据不足)"
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_d, top_s = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    why = ", ".join(dict.fromkeys(hits[top_d]))[:80]
    if top_s < MIN_SCORE:
        return "其他", f"最高分仅 {top_s}({top_d}), 证据不足: {why}"
    if second and top_s / second < RATIO:
        return "其他", f"{top_d}{top_s} vs {ranked[1][0]}{second} 纠缠, 未强判"
    return top_d, f"关键词命中: {why}"
