from stratum.services.bu_v2_concept_filter import display_label, is_noise_concept


def test_noise_labels_are_rejected():
    noise = [
        ("EXAMPLE 4 Show that the sum", "EXAMPLE"),
        ("steady-state value", "EXAMPLE"),
        ("EXERCISES 7", ""),
        ("21.", ""),
        ("(a) Vertical:", ""),
        ("(a)", ""),
        ("= _xy_", ""),
        ("( _t_ ) = _x_ ( _t_ )", "THEOREM"),
        ("习题1-6（第50页）", ""),
        ("总习题六", ""),
        ("例7 设 x = tan y 是直接函数", "CONCEPT"),
        ("caution", ""),
        ("Summary", "CONCEPT"),
        ("定理1 设", "THEOREM"),
        ("定义2 设数集 \\(D \\subset R\\), 则称映射", "DEFINITION"),
        ("推论2 如果 lim f(x) 存在, 而 n 是正整数, 那么", "THEOREM"),
        ("定理1 就是说: 可导函数的极值点必定是它的驻点", "THEOREM"),
        ("(instantaneous velocity)** is the derivative of", "CONCEPT"),
        ("is the absolute value of velocity", "CONCEPT"),
        ("limit of", "DEFINITION"),
        ("All the Limit Laws in Theorem 1 are true when we take limits", "THEOREM"),
        ("Suppose that ƒ is continuous on 3 _a_ , _b_ 4 and", "THEOREM"),
    ]
    for label, kind in noise:
        assert is_noise_concept(label, kind), label


def test_real_concepts_are_kept():
    for label, kind in [
        ("一致连续", "CONCEPT"),
        ("一致连续性定理", "THEOREM"),
        ("The Sandwich Theorem", "THEOREM"),
        ("antiderivative", "DEFINITION"),
        ("定理 1 两个无穷小的和是无穷小", "THEOREM"),
        ("(向上)凸", "CONCEPT"),
        ("Newton’s method", "CONCEPT"),
        ("Differentiability Implies Continuity", "THEOREM"),
        ("derivative of a function ƒ at a point", "DEFINITION"),
        ("准则Ⅱ 单调有界数列必有极限", "THEOREM"),
    ]:
        assert not is_noise_concept(label, kind), label


def test_display_label_truncates():
    assert display_label("短") == "短"
    assert display_label("x" * 100, 10) == "x" * 9 + "…"
