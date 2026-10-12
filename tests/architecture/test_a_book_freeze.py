"""A-P9: real book freeze + in-book KU annotation (rule-based, idempotent)."""

from __future__ import annotations

from stratum.knowledge.a_repository import book_freeze as bf

ZH = """目录
第一章 函数与极限 …… 1
第二章 导数与微分 …… 71
习题1-1(15)
正文开始
定义 1 设 X, Y 是两个非空集合, 如果存在一个法则 f, 那么称 f 为从 X 到 Y 的映射.
定理 1(极限的唯一性) 如果数列收敛, 那么它的极限唯一.
证 用反证法. 假设同时有两个极限.
例 1 证明数列 x_n=(-1)^{n+1} 是发散的.
证 如果这数列收敛, 根据定理1它有唯一的极限, 矛盾.
习题1-1
1. 求下列函数的自然定义域.
第一章释疑解难
问题一 说明.
定理 1(极限的唯一性) 如果数列收敛, 那么它的极限唯一 (复述).
例 2 根据定理 1 再算一次.
第二章释疑解难
"""

EN = """DEFINITION A **function** f from a set D to a set Y is a rule that assigns a unique value.

THEOREM 1—Limit Laws If L, M, c and k are real numbers then the sum rule holds.

EXAMPLE 1  Use Theorem 1 to evaluate the limit of a polynomial at a point.

Summary
We discussed Limit Laws and how to evaluate limits.
"""


def test_zh_roles_chapters_and_toc_skipped():
    ex = bf.extract(ZH)
    roles = ex.role_counts()
    assert roles["DEFINITION"] == 1
    assert roles["THEOREM"] == 2
    assert roles["EXAMPLE"] == 2
    assert roles["EXERCISE"] == 1  # the TOC line "习题1-1(15)" is not a KU
    first = ex.kus[0]
    assert first.chapter.startswith("第1章 函数与极限")
    assert ex.kus[-1].chapter.startswith("第2章")
    thm = next(k for k in ex.kus if k.role == "THEOREM")
    assert thm.name == "极限的唯一性"
    assert "证" not in thm.statement  # proof stripped from the statement


def test_zh_hints_in_book_only():
    ex = bf.extract(ZH)
    kinds = ex.hint_counts()
    assert (
        kinds["APPLIES"] == 2
    )  # 例 1 -> first 定理 1, 例 2 -> restated 定理 1 (nearest, same chapter)
    assert kinds["RESTATES"] == 1
    for h in ex.hints:
        assert h.from_index != h.to_index


def test_en_markers_and_summary():
    ex = bf.extract(EN)
    assert ex.role_counts()["DEFINITION"] == 1
    thm = next(k for k in ex.kus if k.role == "THEOREM")
    assert thm.name == "Limit Laws"
    assert ex.hint_counts()["APPLIES"] == 1
    assert ex.hint_counts()["SUMMARIZES"] == 1


def test_rows_are_deterministic_and_located():
    ex = bf.extract(ZH)
    a = bf.build_rows("SRC1", "Book", ZH, ex)
    b = bf.build_rows("SRC1", "Book", ZH, bf.extract(ZH))
    assert [o["occurrence_hash"] for o in a.occurrences] == [
        o["occurrence_hash"] for o in b.occurrences
    ]
    assert [u["id"] for u in a.units] == [u["id"] for u in b.units]
    assert len({u["content_hash"] for u in a.units}) == len(a.units)
    assert all(o["quote_status"] == "LOCATED" and not o["review_required"] for o in a.occurrences)
    assert all(o["role"] in bf.ROLES for o in a.occurrences)
    assert {h["kind"] for h in a.hints} <= {"RESTATES", "SUMMARIZES", "APPLIES"}
    unit_ids = {u["id"] for u in a.units}
    assert all(h["from_unit_id"] in unit_ids and h["to_unit_id"] in unit_ids for h in a.hints)


def test_unlocated_quote_goes_to_review():
    assert not bf.locate("abc def", 0, "zzz")
    assert bf.locate("  abc def", 0, "abc")


class _Cur:
    def __init__(self, store):
        self.store = store
        self.rowcount = 0

    def execute(self, sql, row):
        table = sql.split("INSERT INTO stratum.")[1].split(" ")[0]
        key = (table, row["id"])
        self.rowcount = 0 if key in self.store else 1
        self.store.add(key)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self):
        self.store = set()

    def cursor(self):
        return _Cur(self.store)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_persist_is_idempotent_and_insert_only():
    rows = bf.build_rows("SRC1", "Book", ZH, bf.extract(ZH))
    conn = _Conn()
    first = bf.persist(rows, conn)
    second = bf.persist(rows, conn)
    assert first["ku_occurrence"] == len(rows.occurrences) > 0
    assert sum(second.values()) == 0
