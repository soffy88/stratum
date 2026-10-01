# A P1 DATA INVENTORY — 冻结基线数据清单

TASK=STRATUM_A_REPOSITORY_P1_FREEZE_REAL_BOOK_CHAIN
STATUS=FROZEN
REPRODUCIBLE=YES (deterministic content-derived IDs)

## BookSource

- id: `bs_04a94146a35f`
- title: 利率史（第四版）
- author: [美]悉尼·霍默 理查德·西勒
- translator: 曹建海
- publisher: 中信出版社
- isbn: 9787508617497
- edition: 第四版
- language: zh

## SourceVersion

- id: `sv_f548f51a5df5`
- checksum: `4125ee83a0bebeafab0260123278135d773d525461011295297645002b182449`
- version: PDF-v1
- format: PDF
- page_count: 594
- storage_uri: local://wiki_kb/raw/02_经济学_(NEW)利率史(第4版).md

## ReadingRun

- id: `arr_d0d1473d79fc`
- status: READING
- chapter: 第一章 古代时期的信贷 (pages 1-10)
- stages traversed: CREATED → SNAPSHOTTED → READING

## Evidence

count=17

| evidence key | id | page | section |
|---|---|---|---|
| ev_credit_ancient | ev_22f99d11e192 | 1 | 1.1 |
| ev_credit_neolithic | ev_64e42dfdd616 | 2 | 1.1 |
| ev_hammurabi_date | ev_fc56fbbea715 | 3 | 1.2 |
| ev_hammurabi_grain_rate | ev_2ab2ebf27e55 | 4 | 1.2 |
| ev_hammurabi_silver_rate | ev_2199b1a14392 | 4 | 1.2 |
| ev_hammurabi_written | ev_3a9bdb40cc17 | 5 | 1.2 |
| ev_hammurabi_forfeit | ev_546bfe6edc2c | 5 | 1.2 |
| ev_hammurabi_collateral | ev_c966ece01598 | 5 | 1.2 |
| ev_solon_date | ev_9e49cc45bcdc | 6 | 1.3 |
| ev_solon_crisis | ev_291e662405a9 | 6 | 1.3 |
| ev_solon_no_interest_limit | ev_d862c5f48966 | 7 | 1.3 |
| ev_solon_debt_relief | ev_f03c8447e353 | 7 | 1.3 |
| ev_twelve_tables_date | ev_04a9f8b42bce | 8 | 1.4 |
| ev_rome_rate_cap | ev_0e7498adab57 | 9 | 1.4 |
| ev_rome_penalty | ev_ce7a560ec339 | 9 | 1.4 |
| ev_rome_servitude | ev_612caa66a024 | 9 | 1.4 |
| ev_prehistory_conclusion | ev_dc51899259a5 | 10 | 1.5 |

extractor_version: p1-v1 (all 17)
page coverage: 10/10 = 100%

## KU Candidate

count=17

| candidate key | id | evidence |
|---|---|---|
| kc_credit_predates_coinage | kc_c15a971eec12 | ev_credit_ancient |
| kc_credit_neolithic_origin | kc_110e073407b4 | ev_credit_neolithic |
| kc_hammurabi_code | kc_378111b6120b | ev_hammurabi_date |
| kc_babylon_grain_rate_cap | kc_bb8411224a48 | ev_hammurabi_grain_rate |
| kc_babylon_silver_rate_cap | kc_6adfa0ad6c6a | ev_hammurabi_silver_rate |
| kc_written_contract_required | kc_fbd57326f936 | ev_hammurabi_written |
| kc_usury_principal_forfeit | kc_64d594f1becd | ev_hammurabi_forfeit |
| kc_babylon_collateral_scope | kc_cafe7821cc8a | ev_hammurabi_collateral |
| kc_solon_code_date | kc_da2b189b19b0 | ev_solon_date |
| kc_athens_debt_crisis | kc_464d0499f71f | ev_solon_crisis |
| kc_solon_abolished_rate_cap | kc_8a23c5114f83 | ev_solon_no_interest_limit |
| kc_solon_debt_relief | kc_06b1ca59e5f3 | ev_solon_debt_relief |
| kc_twelve_tables_date | kc_2cd3503a53ce | ev_twelve_tables_date |
| kc_rome_rate_cap | kc_46695208e7ab | ev_rome_rate_cap |
| kc_rome_penalty_fourfold | kc_073e32aa0147 | ev_rome_penalty |
| kc_rome_servitude_allowed | kc_1a6146de6804 | ev_rome_servitude |
| kc_credit_precedes_writing | kc_203c6c912a10 | ev_prehistory_conclusion |

status: EXTRACTED (all 17)
orphan_evidence: 0
orphan_candidates: 0

## Traceability

All object IDs are content-derived (sha256-truncated), so any two
independent executions of `freeze_runner.build_baseline()` produce
byte-identical IDs and counts. Verified across 2 independent runs.

DATA_INVENTORY=PASS