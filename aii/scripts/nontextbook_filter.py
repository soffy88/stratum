"""非教材文件名黑名单 —— discover 阶段确定性预筛, 省 LLM 配额。

★为什么在这里(2026-10-01): 供给侧混进了答案册/习题册, 它们有章节、有密度,
但【没有可讲的知识点】。实测 edu_zh_6a3296264e = "2020春季《课堂作业》道德与法治
8年级下册答案.md", 整本只抽出 1 个 KU, 然后被质量门以"密度不足"拦下 ——
但走到质量门之前, 已经烧掉了抽取 + 质检(355 次判官调用)的配额。
这类书应该在 discover 阶段就出局。

★去重要求: cs_discover / misc_discover / edu_discover 三份是复制粘贴的同一份
12 词黑名单, 改一处漏两处的风险很高。统一从本模块取, 三处都改成 import。
"""

from __future__ import annotations

# ── 非知识内容(励志/文学/传记类): 有章节但无知识点密度 ──
_SKIP_WORDS: tuple[str, ...] = (
    "创业",
    "情商",
    "成功学",
    "散文",
    "小说",
    "漫画",
    "随笔",
    "传记",
    "精选",
    "合集",
    "情商课",
    "励志",
)

# ★新增(2026-10-01): 习题/答案/试卷类 —— 只有题和答案, 没有可讲授的知识点。
#   保守起见只收极明确的词; "练习" 可能出现在真教材标题里(如"分层练习")。
ANSWER_KEY_WORDS: tuple[str, ...] = (
    "答案",
    "习题",
    "试卷",
    "题库",
    "解析",
    "课后作业",
    "课堂作业",
    "同步练习",
    "单元测试",
    "期末测试",
    "答案册",
    "workbook",
    "answer key",
    "answers",
    "solution manual",
    "study guide",
    "test bank",
)

_SKIP_ALL: tuple[str, ...] = _SKIP_WORDS + ANSWER_KEY_WORDS


def is_skipped_name(stem: str) -> bool:
    """文件名命中非教材黑名单则跳过。stem 为不含扩展名的文件名。"""
    low = (stem or "").lower()
    return any(w in stem or w in low for w in _SKIP_ALL)


def skip_words() -> tuple[str, ...]:
    return _SKIP_ALL