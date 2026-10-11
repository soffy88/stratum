"""Shared fixtures for the PPT export tests: a small Chinese book and a fake model."""

from __future__ import annotations

import json
import re
from typing import Any

from stratum.services.bu_v2_provider import ModelResponse
from stratum.services.ppt_export.material import BookMaterial, ChapterMaterial


def tiny_book() -> BookMaterial:
    """Two chapters of a calculus textbook, as BU2 would have stored them."""
    ch1 = ChapterMaterial(
        chapter_id="ch1",
        number=1,
        title="Chapter 1: 函数与极限",
        question="什么是函数与极限？",
        goal="理解函数、极限和连续性的基本概念。",
        thesis="函数是变量之间的依赖关系，极限是研究变量变化的基本方法。",
        concepts=["函数", "极限", "连续性"],
        claims=["函数是映射的一种。", "单调函数一定存在反函数。"],
        qualifications=["非单调函数的反函数需要另行讨论。"],
        subsections=["第一节 映射与函数", "第二节 数列的极限", "第三节 函数的连续性"],
        section_snippets={"第一节 映射与函数": "设 X、Y 是两个非空集合，如果存在一个法则……"},
        excerpt="函数是微积分研究的基本对象，极限方法是研究函数的基本方法。",
    )
    ch2 = ChapterMaterial(
        chapter_id="ch2",
        number=2,
        title="Chapter 2: 导数与微分",
        question="导数与微分是什么？",
        goal="理解导数和微分的概念并掌握计算方法。",
        # BU2 sometimes answered CJK chapters in English; the deck must not.
        thesis="The derivative is the limit of the ratio of increments.",
        concepts=["导数", "微分", "单侧导数"],
        claims=["常数的导数等于零。", "正弦函数的导数是余弦函数。", "可导必连续。"],
        subsections=["第一节 导数概念", "第二节 函数的求导法则"],
        excerpt="为了说明导数的概念，我们先讨论速度问题和切线问题。",
    )
    return BookMaterial(
        substrate_id="sub_tiny",
        title="高等数学 上册 (测试版)",
        language="zh",
        run_id="br_tiny",
        bu_status="VERIFIED",
        genre="本科数学",
        central_theses=["函数刻画变量间的依赖，导数精确度量变化。"],
        concept_defs={"导数": "函数增量与自变量增量之比的极限。"},
        chapters=[ch1, ch2],
    )


def zh_slides(n: int, tag: str = "") -> list[dict[str, Any]]:
    kinds = [
        {
            "type": "explain",
            "title": f"导数就是瞬时变化率的极限{tag}",
            "blocks": [
                {"label": "定义"},
                {"text": "增量之比在增量趋于零时的极限"},
                {"formula": r"$f'(x_0) = \lim_{\Delta x \to 0} \frac{\Delta y}{\Delta x}$"},
                {"rule": "极限存在才可导", "tone": "up"},
            ],
            "takeaway": "可导一定连续，连续不一定可导",
        },
        {
            "type": "definitions",
            "title": f"三个概念撑起整章内容{tag}",
            "side": {"title": "一句话", "body": "先懂概念再算题"},
            "items": [
                {"title": "函数", "text": "变量之间的依赖关系"},
                {"title": "极限", "text": "无限接近的过程"},
                {"title": "连续性", "text": "没有断开的函数"},
            ],
        },
        {
            "type": "warnings",
            "title": f"可导与连续别混为一谈{tag}",
            "items": [
                {"title": "可导必连续", "text": "反过来不一定成立"},
                {"title": "单侧导数", "text": "左右都存在且相等才可导"},
            ],
            "quote_lines": ["先连续", "再可导"],
        },
        {
            "type": "process",
            "title": f"求导按三步走最稳妥{tag}",
            "items": [
                {"title": "求增量", "text": "写出函数的增量"},
                {"title": "算比值", "text": "增量之比化简"},
                {"title": "取极限", "text": "令增量趋于零"},
            ],
        },
    ]
    out = []
    for i in range(n):
        s = json.loads(json.dumps(kinds[i % len(kinds)]))
        s["title"] = s["title"] + ("" if i < len(kinds) else str(i))
        s["notes"] = (
            "同学们，这一页我们来看书里的核心结论。导数描述的是函数在某一点的瞬时变化率，"
            "它通过极限来定义。理解了这个定义，后面的求导法则就都有了依据。"
        )
        out.append(s)
    return out


def en_slides(n: int) -> list[dict[str, Any]]:
    return [
        {
            "type": "grid",
            "title": "The derivative measures instantaneous change",
            "items": [
                {"title": "Limit", "text": "ratio of increments as dx goes to zero"},
                {"title": "Slope", "text": "tangent line slope at a point"},
                {"title": "Rate", "text": "velocity in physics problems"},
            ],
            "notes": "Today we look at what the derivative really means for a function.",
        }
        for _ in range(n)
    ]


FRAME_ZH = {
    "title": "导数让变化可以精确度量",
    "subtitle": "从极限到导数的一条主线",
    "storyline": "先建立极限，再用极限定义导数，最后学会计算。",
    "cover_notes": "今天我们用十几页把这本书的主线讲清楚：函数、极限、导数，一环扣一环。",
    "closing": {
        "headline": "先懂极限，导数自然就通",
        "body": "回到定义，计算才有依据",
        "notes": "最后总结一下：极限是地基，导数是在地基上盖的房子，回到定义，计算就不会只是背公式。",
    },
}


class FakeProvider:
    """Scripted model: answers frame prompts and chapter prompts differently.

    ``english_first`` makes each chapter batch answer in English on the first
    attempt; ``always_english`` makes it never comply.
    """

    name = "fake"
    model = "fake"

    def __init__(self, *, english_first: bool = False, always_english: bool = False):
        self.english_first = english_first
        self.always_english = always_english
        self.calls: list[dict[str, Any]] = []
        self._seen: dict[str, int] = {}

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        self.calls.append({"prompt": prompt, "system": system})
        if "封面和结尾" in prompt or "cover and closing" in prompt:
            return ModelResponse(json.dumps(FRAME_ZH, ensure_ascii=False), "fake", "fake")
        m = re.search(r"写 (\d+) 页", prompt)
        n = int(m.group(1)) if m else 2
        key = prompt.split("【本章资料】")[0]
        attempt = self._seen.get(key, 0)
        self._seen[key] = attempt + 1
        chap = re.search(r"“([^”]+)”这一章", prompt)
        tag = (chap.group(1)[-2:] if chap else "") + str(attempt)
        if self.always_english or (self.english_first and attempt == 0):
            slides = en_slides(n)
        else:
            slides = zh_slides(n, tag)
        return ModelResponse(json.dumps({"slides": slides}, ensure_ascii=False), "fake", "fake")
