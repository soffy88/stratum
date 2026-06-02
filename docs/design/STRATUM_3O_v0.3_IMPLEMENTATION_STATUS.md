# STRATUM 3O v0.3 实施状态核查报告

**核查日期**: 2026-06-02  
**核查方法**: Python hasattr / inspect.getsource / 直接文件检查 / Stratum 路由 import 验证  
**核查范围**: oprim / oskill / omodul / obase Stratum 专属元素  
**权威来源**: PHASE_1_4O_IMPLEMENTATION_INSTRUCTIONS_v0.1.md + STRATUM_ROADMAP_v1.0.md + 实际代码  

---

## 状态符号说明

| 符号 | 含义 |
|------|------|
| ✅ | 已实施可用（真函数 + 通过测试 + 真业务可调） |
| 🟡 | 部分实施（有签名/文件但内部 stub / 未导出 / 缺关键依赖） |
| ❌ | 未实施（函数不存在 或 模块空） |
| ⚠️ | 已实施但 Stratum 端因路径 bug 无法调用 |

---

## 第一部分：oprim Stratum 专属元素

### §1.1 oprim.classifier（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| detect_mime | oprim-c01 | P1 | ✅ 24L，magic bytes 检测，测试覆盖 |
| detect_pdf_features | oprim-c02 | P1 | ✅ pymupdf，page_count/has_cjk/is_scanned/is_two_column |
| detect_image_exif | oprim-c03 | P1 | ✅ Pillow，EXIF+camera_make+is_screenshot_likely |
| extract_text_sample | oprim-c04 | P1 | ✅ 多 MIME 采样，chardet 编码检测 |

### §1.2 oprim.parser（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| parse_pdf（provider 接口） | oprim-p01 | P1 | ✅ 31L，auto dispatch 策略 |
| parse_pdf.pymupdf4llm | oprim-p02 | P1 | ✅ 默认 provider，markdown 输出 |
| parse_pdf.marker | oprim-p03 | P1 | ✅ 扫描件 OCR，降级有 logging |
| parse_pdf.mineru | oprim-p04 | P1 | ✅ 中文 CJK 路径，PaddleOCR 可选 |
| parse_epub | oprim-p05 | P1 | ✅ ebooklib，章节+markdown |
| parse_html | oprim-p06 | P1 | ✅ trafilatura，主文抽取 |

### §1.3 oprim.embedding（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| embed_text（provider 接口） | oprim-e01 | P1 | ✅ 27L，batching+retry |
| embed_text.qwen3_dashscope | oprim-e02 | P1 | ✅ DashScope API，Matryoshka 1024 dim |
| embed_text.bge_m3 | oprim-e03 | P1 | ✅ sentence-transformers，本地备选 |
| embed_text.qwen3_local | oprim-e04 | P1 | ✅ 本地 Ollama 路径 |

### §1.4 oprim.vector_db（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| open_vector_db（provider 接口） | oprim-v01 | P1 | ✅ 14L，LanceDB upsert/search/delete/count |
| VectorRecord / VectorDB Protocol | oprim-v02 | P1 | ✅ schema 完整 |

### §1.5 oprim.fulltext（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| open_fulltext_index（tantivy） | oprim-f01 | P1 | ✅ 11L，BM25，中文分词支持 |
| FulltextDoc / FulltextHit | oprim-f02 | P1 | ✅ |

### §1.6 oprim.meta_db（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| open_meta_db（DuckDB） | oprim-m01 | P1 | ✅ 3L 包装，migrations 就位 |
| MetaDB class | oprim-m02 | P1 | ✅ connect/execute/fetchall/migrate/close |

### §1.7 oprim.llm（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| llm_call | oprim-l01 | P1 | ✅ 28L，LLMResponse，多模型路由 |

### §1.8 oprim.mcp（Phase 1）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| mcp_server / create_mcp_server | oprim-mcp01 | P1 | ✅ 34L，FastMCP wrapper |
| register_tool | oprim-mcp02 | P1 | ✅ |

### §1.9 oprim.storage（Phase 2）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| storage（模块壳） | oprim-s01 | P2 | ❌ 模块存在，0 symbols，Google Drive/Local adapters 未实施 |
| gdrive_adapter | oprim-s02 | P2 | ❌ |
| local_adapter | oprim-s03 | P2 | ❌ |
| upload_file / download_file / delete_file | oprim-s04 | P2 | ❌ |

### §1.10 oprim.changefeed（Phase 2）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| changefeed_append | oprim-cf01 | P2 | ❌ 模块存在，0 symbols |
| changefeed_read | oprim-cf02 | P2 | ❌ |
| changefeed_compact | oprim-cf03 | P2 | ❌ |
| changefeed_snapshot | oprim-cf04 | P2 | ❌ |

### §1.11 oprim.push（Phase 2）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| push_web（WebPush） | oprim-pu01 | P2 | ❌ 模块存在，0 symbols |
| push_email | oprim-pu02 | P2 | ❌ |

### §1.12 oprim.translate（Phase 10）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| translate_document_async | oprim-tr01 | P10 | 🟡 2L wrapper，TerminologyGlossary 就位，DeepSeek/Claude/Qwen provider 实际配置未验证 |
| TranslationResult / TerminologyGlossary | oprim-tr02 | P10 | ✅ |

### §1.13 oprim.external（Phase 11）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| external（模块壳） | oprim-ex01 | P11 | ❌ 模块存在，0 symbols |
| external/clients/tts_client.py | oprim-ex02 | P11 | 🟡 文件存在（oprim.external.clients），不在 oprim.__init__ 导出 |

### §1.14 oprim 多媒体元素（Phase 11）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| tts_synthesize | oprim-tt01 | P11 | 🟡 oprim/tts_synthesize.py 60L 实现存在，**未在 oprim.__init__.py 导出**，ProviderRegistry 0 providers |
| image_generate | oprim-ig01 | P11 | 🟡 oprim/image_generate.py 存在，**未导出**，ProviderRegistry 0 providers |
| image_understand | oprim-iu01 | P11 | 🟡 oprim/image_understand.py 存在，**未导出** |
| image_to_video | oprim-iv01 | P11 | 🟡 已导出至 oprim.__init__，但 ProviderRegistry.list_providers() = []（wan22 未激活） |

### §1.15 oprim 辅助工具元素（跨 Phase）

| 元素 | v0.3 编号 | Phase | 真状态 |
|------|-----------|-------|--------|
| file_type_detector | oprim-ut01 | P1 | ✅ |
| file_size_limiter | oprim-ut02 | P1 | ✅ |
| file_upload_handler | oprim-ut03 | P1 | ✅ |
| file_parser_pdf / epub / html / markdown / plaintext | oprim-ut04 | P1 | ✅ 全部 5 个 |
| document_structure_extractor | oprim-ut05 | P1 | ✅ |
| migration_runner | oprim-ut06 | P1 | ✅ |
| url_safety_check | oprim-ut07 | P1 | ✅ |
| should_throttle | oprim-ut08 | P1 | ✅ |
| canonical_json | oprim-ut09 | P1 | ✅ |
| sha256_hash / hmac_sha256 | oprim-ut10 | P1 | ✅ |
| compute_dedup_key / compute_event_fingerprint | oprim-ut11 | P1 | ✅ |
| temp_file_manager（TTL=1800s） | oprim-ut12 | P1 | ✅ TTL 值正确，cleanup_expired action 就位，**无定时调度器触发** |

---

**oprim 小计（估算）**：  
✅ 已实施可用：~44 个  
🟡 部分实施：~8 个（translate_document_async / tts_synthesize / image_generate / image_understand / image_to_video / external/tts_client）  
❌ 未实施：~12 个（storage 全部 + changefeed 全部 + push 全部）  

---

## 第二部分：oskill Stratum 专属元素（7 个核心）

| 元素 | 实际路径 | v0.3 编号 | Phase | 真状态 | 备注 |
|------|----------|-----------|-------|--------|------|
| classify_inbox_file | oskill.knowledge.classify_inbox_file | oskill-01 | P1 | 🟡 Layer 1+2 真实现；Layer 3 `raise NotImplementedError("LLM classification not implemented in Phase 1")` | process_inbox_substrate 强制 use_llm=False |
| ingest_substrate | **oskill.ingest_substrate**（非 oskill.knowledge.ingest_substrate） | oskill-02 | P1 | ✅ 138L，classify→dedup→parse→embed→index 全流程 | **路径 bug**：omodul.knowledge 从 oskill.knowledge.ingest_substrate import（❌）→ 整个 omodul.knowledge 命名空间崩溃 |
| detect_duplicate_substrate | oskill.knowledge.detect_duplicate_substrate | oskill-03 | P1 | ✅ 29L，file_hash + meta_db 查重 |  |
| generate_derivative | oskill.knowledge.generate_derivative | oskill-04 | P1 | ✅ 44L，多 derivative 类型调度 |  |
| hybrid_search | **oskill.hybrid_search**（非 oskill.knowledge.hybrid_search） | oskill-05 | P1.5 | ✅ 100L，vector+fulltext+RRF 融合 | **路径 bug**：omodul.knowledge.start_mcp_server 从 oskill.knowledge.hybrid_search import（❌） |
| lint | oskill.knowledge.lint | oskill-06 | P1 | ✅ LintIssue 完整 |  |
| translate_substrate | **oskill.translate_substrate** | oskill-07 | P10 | 🟡 接口定义 + TranslateResult 就位，实际翻译通过 oprim.translate_document_async，provider 配置依赖运行时环境 |  |

**oskill 附加（Stratum 路由直接使用）**：

| 元素 | 路径 | 真状态 |
|------|------|--------|
| cross_layer_search | oskill.cross_layer_search | ✅ PGVectorMgr + LanceDBMgr + TantivyMgr 融合 |
| recommend_content | oskill.recommend_content | ✅ |
| render_template | oskill.render_template | ✅ Jinja2 wrapper |
| generate_audio_narration | oskill.knowledge.generate_audio_narration | 🟡 87L，HTTP 调用结构完整，但依赖 oprim.tts_synthesize（未导出）→ 运行时 provider 不存在 |
| generate_illustration | oskill.knowledge.generate_illustration | 🟡 85L，HTTP 调用完整，依赖 oprim.image_generate（未导出）→ 运行时 provider 不存在 |
| transcribe_audio_substrate | oskill.knowledge.transcribe_audio_substrate | 🟡 76L，依赖 oprim.external.whisper（空模块）→ 运行时无法真实调用 |
| web_search_augmented | oskill.knowledge.web_search_augmented | 🟡 45L，依赖 searxng external（空模块） |

**oskill.sync（Phase 2）**：

| 元素 | 真状态 |
|------|--------|
| flush_outbox | ❌ `import oskill.sync` 抛 `ModuleNotFoundError: No module named 'oprim.changefeed.schema'` |
| apply_remote_events | ❌ 同上 |
| snapshot_backup | ❌ 同上 |

---

## 第三部分：omodul Stratum 专属元素（28 个）

### 核心 SaaS 工作流（可用）

| 元素 | 路径 | v0.3 编号 | Phase | 真状态 |
|------|------|-----------|-------|--------|
| process_inbox_substrate | omodul.process_inbox_substrate | omodul-01 | P1 | ✅ 213L，入库全流程，auto_classify=True（use_llm=False） |
| daily_digest_workflow | omodul.daily_digest_workflow | omodul-02 | P11 | ✅ 111L |
| weekly_review_workflow | omodul.weekly_review_workflow | omodul-03 | P11 | ✅ 84L |
| reset_password_workflow | omodul.reset_password_workflow | omodul-04 | P1 | ✅ 134L |
| verify_email_workflow | omodul.verify_email_workflow | omodul-05 | P1 | ✅ 43L |
| notification_dispatch_workflow | omodul.notification_dispatch_workflow | omodul-06 | P11 | ✅ 70L |

### omodul.knowledge（整体命名空间崩溃）

**根因**：`omodul/knowledge/__init__.py` → `omodul.knowledge.process_inbox` → `from oskill.knowledge.ingest_substrate import ...` → **ModuleNotFoundError**  
正确路径应为 `from oskill.ingest_substrate import ...`（不含 `.knowledge.`）

所有以下元素代码**文件存在且非 stub**，但因命名空间 import 链断裂，**运行时全部不可达**：

| 元素 | 路径 | v0.3 编号 | Phase | 真状态 |
|------|------|-----------|-------|--------|
| omodul.knowledge.process_inbox | knowledge/process_inbox.py | omodul-10 | P1 | ⚠️ 文件实现完整，import 链断裂（oskill.knowledge.ingest_substrate 路径错误） |
| start_mcp_server | knowledge/start_mcp_server.py | omodul-11 | P1 | ⚠️ 文件存在，import 链断裂（oskill.knowledge.hybrid_search 路径错误） |

### omodul.knowledge.agents（6 builtin agents）

| 元素 | 文件 | v0.3 编号 | Phase | 文件状态 | 运行时状态 |
|------|------|-----------|-------|----------|-----------|
| KnowledgeCuratorAgent | agents/builtin/knowledge_curator.py | omodul-a01 | P11 | ✅ 83L 无 stub | ⚠️ omodul.knowledge import 崩溃，不可达 |
| DailyDigestAgent | agents/builtin/daily_digest.py | omodul-a02 | P11 | ✅ 168L 无 stub | ⚠️ 同上 |
| ReadingCompanionAgent | agents/builtin/reading_companion.py | omodul-a03 | P11 | ✅ 113L 无 stub | ⚠️ 同上 |
| TranslationWorkerAgent | agents/builtin/translation_worker.py | omodul-a04 | P11 | ✅ 112L 无 stub | ⚠️ 同上 |
| LintBotAgent | agents/builtin/lint_bot.py | omodul-a05 | P11 | ✅ 103L 无 stub | ⚠️ 同上 |
| AudioGeneratorAgent | agents/builtin/audio_generator.py | omodul-a06 | P11 | ✅ 64L 无 stub | ⚠️ 同上 |
| agents/base.py（AgentContext） | agents/base.py | omodul-a07 | P11 | ✅ 73L | ⚠️ 同上 |
| agents/registry.py | agents/registry.py | omodul-a08 | P11 | ✅ 52L | ⚠️ 同上 |
| agents/runner.py | agents/runner.py | omodul-a09 | P11 | ✅ 108L | ⚠️ 同上 |

### omodul.knowledge.scheduler（Phase 11）

| 元素 | 文件 | v0.3 编号 | Phase | 文件状态 | 运行时状态 |
|------|------|-----------|-------|----------|-----------|
| cron_engine | scheduler/cron_engine.py | omodul-s01 | P11 | ✅ 94L | ⚠️ omodul.knowledge import 崩溃 |
| builtin_jobs | scheduler/builtin_jobs.py | omodul-s02 | P11 | ✅ 84L（4 builtin jobs） | ⚠️ 同上 |
| job_store / run_lock / notifier / runner | scheduler/*.py | omodul-s03 | P11 | ✅ 各文件存在 | ⚠️ 同上 |

### omodul.knowledge.views（Phase 13）

| 元素 | 文件 | v0.3 编号 | Phase | 文件状态 | 运行时状态 |
|------|------|-----------|-------|----------|-----------|
| views/crud.py | views/crud.py | omodul-v01 | P13 | ✅ 133L | ⚠️ omodul.knowledge import 崩溃 |
| views/applier.py | views/applier.py | omodul-v02 | P13 | ✅ 52L | ⚠️ 同上 |
| views/preset_loader.py | views/preset_loader.py | omodul-v03 | P13 | ✅ 30L | ⚠️ 同上 |

### omodul.knowledge.browser_extension（Phase 4）

| 元素 | 文件 | v0.3 编号 | Phase | 文件状态 | 运行时状态 |
|------|------|-----------|-------|----------|-----------|
| browser_extension/server.py | knowledge/browser_ext/server.py | omodul-b01 | P4 | ✅ 225L | ⚠️ 同上 |
| browser_extension/page_capture.py | knowledge/browser_ext/page_capture.py | omodul-b02 | P4 | ✅ 32L | ⚠️ 同上 |
| browser_extension/url_dedup.py | knowledge/browser_ext/url_dedup.py | omodul-b03 | P4 | ✅ 69L | ⚠️ 同上 |

### omodul.sync（Phase 2）

| 元素 | 文件 | v0.3 编号 | Phase | 文件状态 | 运行时状态 |
|------|------|-----------|-------|----------|-----------|
| sync/bg_sync.py | sync/bg_sync.py | omodul-sync01 | P2 | ✅ 215L | ⚠️ 依赖 oskill.sync → oprim.changefeed（空模块）崩溃 |

---

## 第四部分：obase Stratum 专属元素（6 个）

| 元素 | 路径 | v0.3 编号 | Phase | 真状态 |
|------|------|-----------|-------|--------|
| config | obase.config | obase-01 | P1 | ✅ 模块完整，config_loader 就位 |
| logging（实为 obase._logging / structlog） | oprim._logging（内部使用） | obase-02 | P1 | 🟡 obase 顶层无 logging 属性；oprim 通过 oprim._logging 内部使用；外部直接调用 obase.logging 会 AttributeError |
| errors（实为 obase.exceptions） | obase.exceptions | obase-03 | P1 | 🟡 obase.errors 不存在；实际错误类通过 obase.OBaseError 等直接导出 |
| cost_tracker | obase.cost_tracker | obase-04 | P1 | ✅ CostTracker 类完整 |
| bootstrap | obase.bootstrap | obase-05 | P1 | ✅ 函数存在，初始化 workspace 目录 + logging/config |
| ProviderRegistry | obase.ProviderRegistry | obase-06 | P1 | 🟡 类存在，auto_discover() 后 list_providers() = []（0 providers 注册） |

---

## 第五部分：按 Phase 分组的"可立即用 vs 必等底层补"汇总

### Phase 1（oprim 基础）→ ✅ 绝大多数可用

| 子系统 | 状态 | 说明 |
|--------|------|------|
| classifier（4 elements） | ✅ 全部可用 | detect_mime/pdf/exif/text_sample |
| parser（6 elements） | ✅ 全部可用 | parse_pdf 3 providers + epub + html |
| embedding（4 elements） | ✅ 全部可用 | qwen3/bge-m3/local 3 providers |
| vector_db（lancedb） | ✅ 可用 | upsert/search/delete 正常 |
| fulltext（tantivy） | ✅ 可用 | |
| meta_db（DuckDB） | ✅ 可用 | |
| llm（llm_call） | ✅ 可用 | |
| mcp（server + register_tool） | ✅ 可用 | |
| utility（18 elements） | ✅ 全部可用 | file_*，migration_runner，dedup，etc. |
| temp_file_manager（TTL=1800s） | ✅ 可用（但无调度器触发清理） | |

### Phase 2（网盘 + 同步）→ ❌ 全部阻塞

| 子系统 | 状态 | 阻塞原因 |
|--------|------|----------|
| oprim.storage | ❌ 空模块 | GDrive/Local adapters 未实施 |
| oprim.changefeed | ❌ 空模块 | changefeed_append/read/compact 未实施 |
| oprim.push | ❌ 空模块 | web push / email 未实施 |
| oskill.sync（flush_outbox 等） | ❌ import 崩溃 | 依赖 oprim.changefeed.schema（不存在） |
| omodul.sync.bg_sync | ⚠️ 文件存在 | 依赖 oskill.sync → 链式崩溃 |

### Phase 4（浏览器扩展）→ ⚠️ 代码存在，命名空间崩溃

omodul.knowledge.browser_extension 代码完整（225L server.py），但 omodul.knowledge import 链断裂 → 不可达。

### Phase 10（Translation）→ 🟡 框架就位，provider 配置依赖环境

- oprim.translate_document_async：2L wrapper ✅  
- oskill.translate_substrate：接口就位 🟡  
- Stratum translate 路由→依赖 omodul.knowledge.agents.TranslationWorkerAgent → omodul.knowledge import 崩溃 → **路由运行时 500**

### Phase 11（Agents + Scheduler + 外挂）→ ⚠️ 代码齐全，全部被 import 崩溃封锁

6 个 builtin agents（83-168L 无 stub）+ scheduler cron_engine + builtin_jobs **全部代码完整**，但因 `omodul.knowledge` 命名空间崩溃，**一个都不可达**。

外挂依赖（TTS / SD / whisper）：
- oprim.tts_synthesize：文件存在，未导出，无 provider
- oprim.image_generate：文件存在，未导出，无 provider  
- oprim.external：空模块

### Phase 12（hevi + screenpipe）→ ❌ 未实施

oprim.external.hevi_client / oprim.input.screenpipe：均未实施。

### Phase 13（Views）→ ⚠️ 代码存在，被 import 崩溃封锁

views/crud.py（133L）+ applier.py + preset_loader.py 全部实现，但 omodul.knowledge import 链断裂，不可达。

---

## 第六部分：Stratum SaaS 路由真实阻塞清单

### 路由层实际 3O import 路径

| 路由文件 | 导入语句 | 状态 |
|----------|----------|------|
| routers/inbox.py | `from omodul.process_inbox_substrate import process_inbox_substrate` | ✅ **可用**（直接路径，绕过 omodul.knowledge） |
| service/search.py | `from oskill.hybrid_search import hybrid_search` | ✅ **可用** |
| api/mcp.py | `from oskill.cross_layer_search import cross_layer_search` | ✅ **可用** |
| routers/search.py | `from oskill.cross_layer_search import cross_layer_search` | ✅ **可用** |
| routers/content.py | `from oskill.cross_layer_search import cross_layer_search` | ✅ **可用** |
| routers/recommendations.py | `from oskill.recommend_content import recommend_content` | ✅ **可用** |
| mcp_server/routes/review.py | `from omodul.weekly_review_workflow import ...` | ✅ **可用** |
| mcp_server/routes/templates.py | `from oskill.render_template import render_template` | ✅ **可用** |
| scheduler/builtin_jobs.py | `from omodul import daily_digest_workflow, weekly_review_workflow, notification_dispatch_workflow` | ✅ **可用** |
| api/main.py | `from oprim.llm.llm_call import llm_call` | ✅ **可用** |
| **routers/translate.py** | `from omodul.knowledge.agents.builtin.translation_worker import TranslationWorkerAgent` | **❌ 崩溃**：`ModuleNotFoundError: No module named 'oskill.knowledge.ingest_substrate'` |
| **routers/agents.py** | `from omodul import ...`（agents 相关） | **❌ 崩溃**：同上 |

### 根因：2 个命名空间 import 路径 bug

**Bug 1（最严重）**:
```
omodul/knowledge/__init__.py
  → omodul/knowledge/process_inbox.py
    → from oskill.knowledge.ingest_substrate import ...  # ❌ WRONG
    # 应为：from oskill.ingest_substrate import ...      # ✅ 正确路径
```
影响：`omodul.knowledge.*` **整个命名空间** 全部不可达（6 agents + scheduler + views + browser_extension + process_inbox + start_mcp_server）

**Bug 2**:
```
omodul/knowledge/start_mcp_server.py
  → from oskill.knowledge.hybrid_search import ...  # ❌ WRONG
  # 应为：from oskill.hybrid_search import ...       # ✅ 正确路径
```
影响：`start_mcp_server` 单独不可达（已被 Bug 1 级联覆盖）

**Bug 3**:
```
oskill/sync/__init__.py
  → from oprim.changefeed.schema import ...  # ❌ WRONG（schema 子模块不存在）
  # oprim.changefeed 整个模块是空的
```
影响：`oskill.sync.*` 全部不可达，`omodul.sync.bg_sync` 链式崩溃

### 修复成本估算

| Bug | 修复方法 | 行数 | 风险 |
|-----|----------|------|------|
| Bug 1 | `omodul/knowledge/process_inbox.py` 第 11 行：改 import 路径 | 1 行 | 低（无逻辑变更） |
| Bug 2 | `omodul/knowledge/start_mcp_server.py`：改 hybrid_search import 路径 | 1 行 | 低 |
| Bug 3 | oprim.changefeed 需先实施（Phase 2），或 oskill.sync 改为不依赖 changefeed.schema | 大 | Phase 2 工程量 |

**Bug 1 + Bug 2 合计 2 行改动，可解锁整个 omodul.knowledge 命名空间（6 agents + scheduler + views + browser_extension）。**

---

## 附：核查时执行的关键验证命令

```python
# 1. 命名空间崩溃验证
python3 -c "from omodul.knowledge.agents.base import AgentContext"
# → ModuleNotFoundError: No module named 'oskill.knowledge.ingest_substrate'

# 2. 正确路径验证
python3 -c "from oskill.ingest_substrate import ingest_substrate; print('OK')"
# → OK

# 3. hybrid_search 路径验证
python3 -c "from oskill.hybrid_search import hybrid_search; print('OK')"  
# → OK

# 4. oskill.sync 崩溃验证
python3 -c "import oskill.sync"
# → ModuleNotFoundError: No module named 'oprim.changefeed.schema'

# 5. process_inbox_substrate 可用验证（绕开 omodul.knowledge）
python3 -c "from omodul.process_inbox_substrate import process_inbox_substrate; print('OK')"
# → OK

# 6. tts_synthesize 未导出验证
python3 -c "import oprim; print(hasattr(oprim, 'tts_synthesize'))"
# → False（文件存在但未在 __init__.py 导出）
```

---

*生成时间: 2026-06-02 | 核查执行: Claude Code (claude-sonnet-4-6)*
