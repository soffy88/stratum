# oprim Bug 反馈:元素模块间用「公开名」做 from-import → 运行时 ModuleNotFoundError

**日期**:2026-06-28
**报告方**:Stratum
**oprim 版本**:3.10.33
**严重度**:高 —— 波及查询扩展、支付宝全套、Stripe 全套、多个金融检测器,相关 API 加载即崩。

---

## 根因

`oprim` 通过 `__init__.py` 的惰性 `__getattr__` + `_ELEMENT_MAP`,把元素名映射到**下划线模块**
(`oprim._xxx.py`)暴露。因此 `oprim.foo` 作为**属性**可访问,但 `from oprim.foo import X`
(子模块路径导入)会失败 —— 因为根本不存在真实的 `oprim/foo.py`。

多个元素模块在顶部用了后者来引用「兄弟元素」的类型/类,导致该模块加载即 `ModuleNotFoundError`,
对应元素彻底不可用。`llm_judge_rerank` 自身没踩雷,只是因为它内部没有这种跨模块 from-import。

---

## 受影响位置(10 处,5 个目标,全部已运行时复现)

| 文件 | 错误的 import | 缺失目标 | 受损功能 |
|---|---|---|---|
| `_llm_query_expand.py:6` | `from oprim.llm_judge_rerank import LLMCaller` | `llm_judge_rerank` | 查询扩展 |
| `_alipay_query_order.py:9` | `from oprim.alipay_create_qr_order import ...` | `alipay_create_qr_order` | 支付宝查单 |
| `_alipay_refund_order.py:6` | `from oprim.alipay_create_qr_order import ...` | `alipay_create_qr_order` | 支付宝退款 |
| `_alipay_verify_notify_signature.py:5` | `from oprim.alipay_create_qr_order import ...` | `alipay_create_qr_order` | 支付宝验签 |
| `_detect_limit_board_explosion.py:13` | `from oprim.limit_status_calc import limit_status_calc` | `limit_status_calc` | 涨停板检测 |
| `_detect_news_shock.py:16` | `from oprim.financial_metric_extraction import ...` | `financial_metric_extraction` | 新闻冲击检测 |
| `_detect_volume_spike.py:13` | `from oprim.volume_ratio import volume_ratio` | `volume_ratio` | 放量检测 |
| `_stripe_refund_payment.py:8` | `from oprim.stripe_create_payment_intent import ...` | `stripe_create_payment_intent` | Stripe 退款 |
| `_stripe_retrieve_payment_intent.py:7` | `from oprim.stripe_create_payment_intent import ...` | `stripe_create_payment_intent` | Stripe 查询 |
| `_stripe_verify_webhook_signature.py:5` | `from oprim.stripe_create_payment_intent import ...` | `stripe_create_payment_intent` | Stripe webhook 验签 |

---

## 复现

```python
import oprim
oprim.llm_query_expand                 # ModuleNotFoundError: No module named 'oprim.llm_judge_rerank'
import oprim.alipay_refund_order        # 同类报错
import oprim.stripe_refund_payment      # 同类报错
import oprim.detect_volume_spike        # 同类报错
```

文件存在性佐证(目标只有下划线版,无真实模块):

```
llm_judge_rerank             -> 只有 _llm_judge_rerank.py
alipay_create_qr_order       -> 只有 _alipay_create_qr_order.py
limit_status_calc            -> 只有 _limit_status_calc.py
financial_metric_extraction  -> 只有 _financial_metric_extraction.py
volume_ratio                 -> 只有 _volume_ratio.py
stripe_create_payment_intent -> 只有 _stripe_create_payment_intent.py
```

---

## 修复(每处加下划线,指向真实模块)

```python
- from oprim.llm_judge_rerank import LLMCaller
+ from oprim._llm_judge_rerank import LLMCaller
# 其余 9 处同理:oprim.<name> → oprim._<name>
```

---

## 建议(防回归)

1. **CI 冒烟测试**:对 `_ELEMENT_MAP` 里每个元素都 `importlib.import_module` 一遍,任何
   `ModuleNotFoundError` 即失败。
2. **lint 规则**:禁止模块内 `from oprim.<非下划线> import`,内部引用一律走 `oprim._xxx` 真实模块。
3. **已排除误报**:`oprim.types` / `oprim.prompt` / `oprim.policy_event_extraction` /
   `oprim.serialization` 都是真实模块/包,**安全**。

---

## Stratum 侧现状

`llm_query_expand` 已用 Layer-4 兜底绕过(`src/stratum/service/rerank.py` 的 `_inline_expand`),
不阻塞 Stratum。但支付宝 / Stripe / 检测器那几处建议 owner 优先修(支付链路尤其关键)。
