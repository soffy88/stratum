"""回归测试: 应有清单按本章范围 + 缺席通知清洗.

验证两件事:
1. clean_ku 现在能把"未覆盖/未涵盖/未出现"等句子清掉(之前漏了)
2. 清掉后是空壳的缺席通知KU, is_empty_shell 返回 True
"""
import sys
sys.path.insert(0, "scripts")
from clean_ku import clean, is_empty_shell

PASS = FAIL = 0

def check(label: str, zh: str, expect_shell: bool):
    global PASS, FAIL
    cleaned, _ = clean(zh)
    result = is_empty_shell(cleaned)
    ok = result == expect_shell
    status = "✅" if ok else "❌"
    print(f"{status} {label}: is_shell={result} (expect {expect_shell})")
    if not ok:
        print(f"   input:   {zh[:80]}")
        print(f"   cleaned: {cleaned[:80]}")
    if ok: PASS += 1
    else: FAIL += 1


# Case 1: 典型缺席通知 — 全是"（未覆盖）"，清后空壳
check(
    "全未覆盖缺席通知",
    "（未覆盖）。第1章文本中未出现该术语。"
    "（未覆盖）。该章未给出任何涉及该概念的内容。"
    "（未覆盖）。（未覆盖）。本章未描述该机制。",
    expect_shell=True,
)

# Case 2: 带"未覆盖"注记但有实质内容 → 清掉注记后不空壳
check(
    "有实质内容+未覆盖注记",
    "需求曲线向下倾斜，因为价格上升时消费者需求减少。"
    "（未覆盖：本章未给出具体数值示例。）",
    expect_shell=False,
)

# Case 3: "未涵盖" 也能清 (之前 _NONCOV 已有近义，确认新词也覆盖)
check(
    "未涵盖变体",
    "MPC + MPS = 1。（未涵盖：第1章未涵盖该等式的数学推导。）（未涵盖）。",
    expect_shell=True,
)

# Case 4: 实质内容完整，不含缺席标记 → 不空壳
check(
    "完整KU无缺席标记",
    "边际成本是总成本对产量的导数 MC = dTC/dQ。"
    "它衡量增加一单位产量时总成本的瞬时变化率。"
    "用于利润最大化条件 MR = MC 的推导。",
    expect_shell=False,
)

# Case 5: 全是"not covered"英文 → 空壳
check(
    "英文not covered",
    "This concept is not covered in Chapter 1. "
    "The chapter does not discuss injections and withdrawals. "
    "It is not addressed here.",
    expect_shell=True,
)

# Case 6: "未出现"句被清, 剩余不足 → 空壳
check(
    "未出现句被清后空壳",
    "第1章文本中未出现该术语。第1.5节供需分析中未出现该概念。",
    expect_shell=True,
)

# Case 7: 原来 _NONCOV 就有的"未涉及" 确保还在
check(
    "未涉及(已有词确保不退步)",
    "（未涉及）本章未涉及政府支出的分析。未涉及IS-LM框架。",
    expect_shell=True,
)

# Case 8: 混合 — 有实质段落 + 缺席注记段 → 清后有内容
check(
    "实质内容+缺席注记混合",
    "供求分析：价格由供需曲线交点决定均衡价格与均衡数量。"
    "需求曲线斜率为负，供给曲线斜率为正。"
    "（未覆盖：本章未给出弹性计算示例。）",
    expect_shell=False,
)

print(f"\n{'='*40}")
print(f"结果: {PASS}/{PASS+FAIL} 通过{'  ✅ 全过' if FAIL==0 else f'  ❌ {FAIL}失败'}")
if FAIL:
    sys.exit(1)
