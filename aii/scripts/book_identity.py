"""统一的书身份 — 归一化 stem + 双键 sid, 供各飞轮 discover / classify_md 共用。

问题(实证): 各 discover 脚本用 `sid = prefix_md5(stem)[:10]`, 而 stem 是完整文件名
(含 md_export 追加的 `_01KWXXXX` ULID 后缀 + z-lib 噪声 + 各种标点/空格差异)。于是同一
本书不同文件名(如 "微积分的力量 (作者).md" vs "微积分的力量_(作者)_01KWP8AD.md")→
不同 md5 → 被当成两本书重复入库(实证: bu_econ_131d7dbd3b.json 与 bu_econ_zh_131d7dbd3b
.json 并存)。

修法(双键, 绝不重写历史):
  - legacy_sid = md5(原始 stem)[:10] —— 和现有所有 state.json / ingested_substrate 键一致。
  - new_sid    = md5(归一化 stem)[:10] —— 稳定身份, 折叠掉文件名变体。
  discover 排除判定 = 任一 alias 命中终态/已入库; 新产出只用 new_sid 落键。
  直接把 sid() 改成归一化会孤儿化全部现存键 → 大规模重入库(压力测试 H4), 双键规避。

只做纯函数, 无 DB / 无副作用, 便于各脚本 import 和单测。
"""

from __future__ import annotations

import hashlib
import re

# 统一终态口径(替代各飞轮各自为政: econ ku>100 / math ku>30 等)。
TERMINAL_KU_THRESHOLD = 100
TERMINAL_STATUSES = frozenset({"ingested", "quarantine", "precheck_fail", "skip", "abandoned"})

# md_export 追加的 ULID 前缀后缀: "_01KWP8AD" / "_01KWXCQF"(2026年 ULID 以 01 开头)。
_ULID_SUFFIX = re.compile(r"_0?1[0-9A-HJKMNP-TV-Z]{6,}$", re.I)
# z-lib / z-library / 1lib 下载噪声(括号内或裸串)。
_ZLIB = re.compile(r"\(?\s*z-?lib(?:rary)?[^)]*\)?|\(?[^)]*1lib[^)]*\)?|z-?lib\.[a-z.]+", re.I)
_EXT = re.compile(r"\.(pdf|epub|md|txt)$", re.I)
# 所有标点/空格/下划线/全半角括号 —— 折叠成空, 让文件名变体归一。
_PUNCT = re.compile(r"[\s_\-—–（）()【】\[\]{}·・,，.。、:：;；!！?？'\"“”‘’`~@#$%^&*+=|/\\<>]+")


def norm_stem(stem: str) -> str:
    """把文件名主干归一成稳定身份键: 去扩展名 → 去ULID后缀 → 去z-lib噪声 → 折叠标点 → 小写。"""
    s = _EXT.sub("", stem)
    s = _ULID_SUFFIX.sub("", s)
    s = _ZLIB.sub("", s)
    s = _PUNCT.sub("", s)
    return s.lower().strip()


def _md5_10(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


def sids(stem: str, prefix: str) -> list[str]:
    """返回该书在给定 channel prefix 下的候选 sid 列表 [new_sid, legacy_sid](去重)。

    new_sid 在前 —— 新产出用它落键; 两个都用于"是否已处理"的排除判定。
    """
    legacy = f"{prefix}_{_md5_10(stem)}"
    new = f"{prefix}_{_md5_10(norm_stem(stem))}"
    return [new, legacy] if new != legacy else [new]


def primary_sid(stem: str, prefix: str) -> str:
    """新产出该用的稳定 sid(= new_sid)。"""
    return sids(stem, prefix)[0]


def is_terminal(sid_aliases: list[str], state_processed: dict, ingested_ku: dict) -> bool:
    """任一 alias 命中终态即算已处理(不再重新发现):

    - state_processed: state.json 的 {sid: {status,...}} 映射。
    - ingested_ku:     {sid: ku_count} 映射(来自 ingested_substrate)。
    终态 = state 里是 TERMINAL_STATUSES 之一, 或 已入库 ku_count >= 阈值。
    """
    for sid in sid_aliases:
        st = state_processed.get(sid, {})
        if isinstance(st, dict) and st.get("status") in TERMINAL_STATUSES:
            return True
        if ingested_ku.get(sid, 0) >= TERMINAL_KU_THRESHOLD:
            return True
    return False


if __name__ == "__main__":
    # 手工核对: 同一本书的多个文件名变体应归一到同一 new_sid。
    # 真实生产重复案例: 同一书名, 仅差 ULID后缀/下划线/z-lib噪声/扩展名。
    cases = [
        "微积分的力量 (史蒂夫·斯托加茨 (Steven Henry Strogatz))",
        "微积分的力量_(史蒂夫·斯托加茨_(Steven_Henry_Strogatz)_01KWP8AD",
        "微积分的力量 (史蒂夫·斯托加茨 (Steven Henry Strogatz)) (z-library.sk, 1lib.sk).pdf",
    ]
    print("=== 归一化折叠验证(应三者 new_sid 相同) ===")
    for c in cases:
        norm = norm_stem(c)
        print(f"  new={primary_sid(c, 'math_prog')}  norm={norm[:30]!r}  <- {c[:45]!r}")
    same = len({primary_sid(c, "math_prog") for c in cases}) == 1
    print(f"三变体归一到同一身份: {'✓ OK' if same else '✗ FAIL'}")
    print()
    print("=== 双键(legacy≠new, 排除判定用两者) ===")
    stem = "叙事经济学_01KVKRSM"
    print(f"  sids('{stem}', 'econ_zh') = {sids(stem, 'econ_zh')}")
    print(f"  纯净名 sids = {sids('叙事经济学', 'econ_zh')}")
