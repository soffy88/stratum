# Upgrade acceptance runbook

本 runbook 用于本轮升级的部署验收。代码契约、静态检查和 candidate preparation 已在开发环境完成；
以下命令不会把 candidate、smoke 或无 PostgreSQL 环境伪装成正式通过。

## 1. 本地静态预检

```bash
python scripts/check_architecture.py
python scripts/check_slo_gate.py
python scripts/check_pg_acceptance.py
```

`check_pg_acceptance.py` 在没有 PostgreSQL 时应明确输出 `PG acceptance BLOCKED`；部署 CI 不应使用
`--allow-unavailable`。

## 2. 准备并审核 evaluation data

```bash
python scripts/import_legacy_retrieval_gold.py \
  --input aii/scripts/eval/golden.json \
  --output /tmp/retrieval-gold-candidate.json
python scripts/build_retrieval_review_packet.py \
  --manifest /tmp/retrieval-gold-candidate.json \
  --output /tmp/retrieval-review-packet.json

python scripts/discover_parser_candidates.py \
  --root experiments/02-batch/samples/pdf \
  --output /tmp/parser-candidates.json --limit 20
python scripts/build_parser_review_packet.py \
  --manifest /tmp/parser-candidates.json \
  --output /tmp/parser-review-packet.json
```

人工审核者必须验证 retrieval 的 substrate mapping/rationale，以及 parser 的 layout/language/
structure/markers，并填写真实 `reviewer`。审核决定写入单独 JSON 后，用
`scripts/apply_eval_reviews.py` 生成新 manifest；不要修改 candidate 源文件。

```bash
python scripts/apply_eval_reviews.py --kind retrieval \
  --manifest /tmp/retrieval-gold-candidate.json \
  --reviews retrieval-decisions.json \
  --output retrieval-gold-reviewed.json
python scripts/apply_eval_reviews.py --kind parser \
  --manifest /tmp/parser-candidates.json \
  --reviews parser-decisions.json \
  --output parser-gold-reviewed.json
```

## 3. 检查数据是否够资格跑 benchmark

```bash
python scripts/check_eval_manifest_readiness.py \
  --retrieval-manifest retrieval-gold-reviewed.json \
  --parser-manifest parser-gold-reviewed.json \
  --output eval-manifest-readiness.json
```

期望：retrieval 至少 50 条、parser 至少 20 份、所有记录 reviewed、parser 文件全部存在，且
`ready: true`。当前仓库的 candidate 状态预期为 false：55 retrieval candidate 但 0 reviewed，
5 parser candidate 且不足 20。

## 4. PostgreSQL 部署验收

在部署环境设置真实连接变量后执行：

```bash
python scripts/bootstrap_pg_schema.py
python scripts/check_pg_acceptance.py \
  --http-base-url https://<deployed-api> \
  --report-out pg-acceptance-report.json
```

通过条件包括 019–028 migrations、canonical tables/columns、LearningEvent/import/merge/usage
ledger terminal-transition triggers，以及 OpenAPI 中的关键路径。必须实际执行 migration；离线
marker check 不能替代 catalog inspection。

## 5. 运行正式 evaluation

```bash
python scripts/eval_retrieval.py \
  --golden retrieval-gold-reviewed.json \
  --min-queries 50 --require-provenance \
  --baseline retrieval-baseline.json \
  --report-out retrieval-report.json
python scripts/eval_parser_benchmark.py parser-gold-reviewed.json \
  --min-cases 20 --require-provenance --require-files \
  --baseline parser-baseline.json \
  --report-out parser-report.json
python scripts/check_eval_release_gate.py \
  --retrieval-report retrieval-report.json \
  --parser-report parser-report.json
```

需要真实 baseline（并通过 `--baseline` 传入），且 baseline 必须与当前 reviewed manifest 具有相同
`evaluation_fingerprint`；还需要 retrieval precision/recall/MRR/hit-rate，以及 parser 各维度结果。release gate
还会拒绝缺少有限、位于 `[0,1]` 的四项 retrieval 指标，或缺少非空 `by_dimension` 与每维度
`pass_rate`/`marker_coverage`/`structure_coverage` 的报告。pdftotext text-only smoke、示例
fixture 和未审核 manifest 不能替代正式结果。

## 6. 人工产品验收

- 五入口 Today/Library/Ask/Learn/Map：按真实账户完成端到端路径并记录问题。
- Reader semantic actions、credits/settings、Obsidian 双向同步：用真实挂载和真实账户验证。
- Belief/ContextLink/PersonalState：验证多用户隔离、旧数据映射和 LearningEvent 审计。
- Stripe/WeChat：使用部署商户密钥验证 webhook、tier 变更和 credits 额度变化。

在第 4–6 步完成前，本轮只能报告“代码与本地契约完成、外部验收待执行”，不能报告蓝图
100% 完成。
