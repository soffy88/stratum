from stratum.services.bu_v2_producer import _fuzzy_find, _significant_terms


def test_fuzzy_find_ignores_ocr_spaces():
    text = "第一节  函 数\n设数集 D ⊂ R，则称映射 f : D → R 为定义在 D 上的函数。"
    assert _fuzzy_find(text, "函数") == text.index("函 数")
    assert _fuzzy_find(text, "设数集D⊂R") == text.index("设数集")
    assert _fuzzy_find(text, "导数") == -1


def test_significant_terms_include_chinese_runs():
    terms = _significant_terms("函数的极限是微积分的基础")
    assert "极限" in terms or "函数" in terms
