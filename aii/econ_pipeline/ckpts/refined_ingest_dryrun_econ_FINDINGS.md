# B仓步骤3 · 去重KU灌入 dry-run 首跑发现（经济三书）

> 脚本 `scripts/refined_ingest_dryrun.py`（默认不落库, `--commit` 才插 rf.refined_ku）。
> verdicts 缓存 `ckpts/refined_verdicts_econ.json`（147对, SAME=49, 复跑秒级命中不再判同12min）。

## ✅ 核心机制已验证（裸真相）
- **规模/压缩**: A仓三书 1222 KU → refined_ku 预计 **1182 条**（合并簇 29 + 单条 1153, 省 40）。
- **传递合并(union-find)对**: Consumer Surplus 把 5 条(micro_clean+microecon+mankiw×3)并成**一条** refined_ku, 非两两重复。
- **held_apart 命门生效**: SAME 边 49, 实并 45, **跳过 held_apart 4**（ledger 记录 5, 本轮判同命中 4）。不并签核剔出的对。
- **③整合"越读越厚"忠实**（NIM快时6簇样本均干净英文）:
  - Price Takers = "price taker" + "one-price market" 合一
  - Scarcity / Transaction Costs / Property Rights / Derived Demand 均定义+各侧面整合, 无臆造。
- **向量**: 整合正文 BGE-M3 → **dim=1024** 对齐A仓。
- **sources jsonb**: `[{book_id, raw_ku_id, chapter, contributed}]` 多出处溯源A仓, 正确。
- **翻译**: 三书 natural_text 已英文(仅 24 条混中文需NIM清洗); 翻译路径已加 timeout+回退原文(不丢知识)。

## ⚠️ 真瓶颈 = NIM 免费层吞吐(非逻辑bug)
- llama-3.3-70b 单次 ~37s(实测); 今日重用(判同4跑+整合) 后**退化到 >90s/次甚至超时**, 触发整合回退空/翻译卡。
- `--commit` 经济三书需 **~53 次 NIM 调用**(29整合 + 24翻译; 1153英文单条只embed不调LLM)。当前退化速度 → 30–80min 且可能撞日限。
- **决策点**: ①忍受慢, 后台长跑 ②4个NIM key轮转并发 ③整合/翻译改本地 Ollama(快但质量需校) ④歇一会等NIM免费层恢复。

## 命门守护确认
- 默认不落库; held_apart 不并; 合并失败回退最长成员原文(不丢); 翻译失败回退原文。
- **未落库**: 待经理人核对上述整合样本质量 + 定 NIM 吞吐方案后才 `--commit`。
