"""KU 双语翻译 — 英文 KU → 中文译文 (natural_text_zh).

命门:
  - embedding 仍用英文原文 natural_text 计算，不受翻译影响
  - 原文 natural_text 不动，只填 natural_text_zh
  - $...$ LaTeX 公式完整保留，公式内不翻译
  - 专业术语精确；不确定的术语在中文后括号附英文原词，如 '鞅(martingale)'
  - 不增删内容，不发挥

翻译用 qwen3.5:9b via local Ollama。
"""
from __future__ import annotations

import logging
import re

import requests

logger = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"
_MODEL = "qwen3.5:9b"
_TIMEOUT = 300  # seconds — qwen3.5:9b cold start (model load) can take ~180s

# 含中日韩字符 → 本来就是中文，不需翻译
_CJK_RE = re.compile(r"[一-龥぀-ヿ가-힣]")

_SYSTEM_PROMPT = """\
你是一位专业的数学/金融/机器学习中英翻译专家。
你的任务是把一条知识单元的英文描述翻译成中文，供中文读者阅读。

严格规则:
1. ★ 保留所有 $...$ 和 $$...$$ LaTeX 公式，公式内部一个字也不翻。
2. ★ 数学/统计/金融/ML 专业术语必须精确；若你对某术语不确定，在中文译词后用括号附英文原词，例如「鞅(martingale)」「凸共轭(convex conjugate)」。
3. 只翻译说明性文字，不增加解释，不删减内容，不发挥。
4. 直接输出译文，不要输出"翻译如下""以下是译文"等前缀。
5. 如果原文本身已是中文或不需要翻译，原样输出。
"""


def _is_english(text: str) -> bool:
    return not bool(_CJK_RE.search(text))


def translate_ku_to_zh(natural_text: str, has_formula: bool = False) -> str:
    """Translate an English KU to Chinese.

    Returns empty string if the text is already Chinese or translation fails.
    """
    text = natural_text.strip()
    if not text:
        return ""
    if not _is_english(text):
        return ""  # already Chinese

    user_msg = text
    if has_formula:
        user_msg = (
            "【此条目含 LaTeX 公式，$...$内容不翻译】\n\n" + text
        )

    try:
        resp = requests.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={
                "model": _MODEL,
                "think": False,      # disable extended thinking for latency
                "keep_alive": "10m", # keep model warm during batch
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        zh = resp.json()["message"]["content"].strip()
        # Strip thinking tags if model outputs them
        zh = re.sub(r"<think>.*?</think>", "", zh, flags=re.DOTALL).strip()
        return zh
    except Exception as e:
        logger.warning("ku_translate: failed for '%s...': %s", text[:40], e)
        return ""
