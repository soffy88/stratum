"""★回归测试: Query-first 红线 (AII-KNOWLEDGE-FIRST-SPEC-001 §3.2/§3.4).

守的是这条: B仓没覆盖时, 通用知识必须【显式标注】才能递给学习者。prompt 里要求了 LLM 自己
加声明, 但"要求"不是"保证"——这里测的是 Python 侧兜底(_coach_turn)真的会补, 以及不会在
B仓覆盖够/非教学回合乱加声明(那样红线会被稀释成套话, 学习者就不看了)。

LLM 用假的(不打网络), 只测我们自己那段确定性逻辑。

运行:
  python scripts/test_query_first.py
退出码: 0=全通过, 1=有失败
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "aii"))

from aii.api.routes import learning as L  # noqa: E402

PASS, FAIL = 0, 0


class _FakeRegistry:
    """顶掉 ProviderRegistry, 让 _coach_turn 拿到一个吐固定 JSON 的假 llm。"""

    def __init__(self, reply):
        self._reply = reply

    def llm(self, _name):
        async def _llm(**_kw):
            return {
                "content": [{"type": "text", "text": json.dumps(self._reply, ensure_ascii=False)}]
            }

        return _llm


def _turn(phase, ku_context, reply):
    L.ProviderRegistry.get = staticmethod(lambda: _FakeRegistry(reply))
    return asyncio.run(
        L._coach_turn(phase=phase, objective={"point_name": "边际成本"}, ku_context=ku_context)
    )


def check(label: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    print(f"  {'✅' if ok else '❌'} [{label}] {detail}")
    if ok:
        PASS += 1
    else:
        FAIL += 1


def main():
    print("Query-first 红线回归测试")

    # 1. B仓没覆盖 + 模型漏加声明 → Python 必须补上(核心: 别把通用知识冒充编译精华)
    r = _turn("present", "", {"message": "边际成本就是多生产一单位的成本。", "action": "present"})
    check(
        "无覆盖+模型漏声明→兜底补",
        r["ku_coverage"] == "insufficient" and r["message"].startswith(L._UNCOMPILED_MARKER),
        f"coverage={r['ku_coverage']}",
    )

    # 2. 模型自己加了 → 不重复加(重复声明反而像模板噪声)
    r = _turn("present", "", {"message": L._UNCOMPILED_MARKER + "\n讲解…", "action": "present"})
    check("模型已声明→不重复", r["message"].count("未经 AII 编译") == 1)

    # 3. B仓覆盖够 → 绝不加声明(加了等于污蔑自己的编译知识)
    r = _turn("present", "K" * 80, {"message": "基于教材讲解…", "action": "present"})
    check(
        "有覆盖→不加声明",
        r["ku_coverage"] == "sufficient" and L._UNCOMPILED_MARKER not in r["message"],
    )

    # 4. 判分后的反馈回合 → not_applicable, 不挂声明(它本来就不该吃教学材料)
    r = _turn("judged", None, {"message": "再试一次, 想想边际那步。", "action": "remediate"})
    check(
        "判分反馈→not_applicable",
        r["ku_coverage"] == "not_applicable" and L._UNCOMPILED_MARKER not in r["message"],
    )

    # 5. 答案泄漏红线优先 → 不能因为补声明就把泄漏的话放出去
    r = _turn("present", "", {"message": "答案是 42。", "action": "present"})
    check("泄漏优先于补声明", r["revealed_answer"] and "42" not in r["message"])

    # 6. 覆盖判据本身
    check("阈值: 60字符=sufficient", L._ku_coverage("present", "x" * 60) == "sufficient")
    check("阈值: 空材料=insufficient", L._ku_coverage("present", "  ") == "insufficient")

    print(f"\n通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
