# STRATUM 3O 全量补全需求清单 v1.0

**版本**: v1.0
**日期**: 2026-06-04
**作者**: CC (Stratum advisor, R-4 只读)
**输入源**:
- STRATUM_REALITY_AUDIT_v1.0.md (58 项 gap)
- STRATUM_SPEC_v0.5 + v0.6 PATCH
- STRATUM_3O_v0.3_IMPLEMENTATION_STATUS.md (commit 65e2658d)
- 3O_CATALOG.md (主库权威元素表)
**性质**: Stratum 视角需求反推, 不查重, 不评估, 不修代码, 不启动跨经理人协调

---

## §0 核心原则

1. **覆盖范围**: audit §2 全部 🟡 + ❌ + ⚠️ 项, 共 58 项 gap 全部展开
2. **已 ship 8 项 ✅ 不动** (Wiki 决策)
3. **不查重**: 查重是主库经理人 / 各库 owner 的事
4. **不评估**: 不评"应该做不做"、"新增 vs 已有"、"哪个 Phase"
5. **每元素 6 标签全填**: `元素名 | v0.3编号/已有标识 | 类型 | audit来源行 | Stratum端使用位置 | 跨经理人需求`
6. **3O 边界说明**:
   - `oprim` = 纯函数原子操作 (无 IO 状态, 可独立测试)
   - `oskill` = stateless 组合算法 (多 oprim 组合, 无事务)
   - `omodul` = 有状态业务事务 (DB 读写, 完整 workflow)
   - `obase` = 横切基础设施 (logging, registry, pipeline, auth, pay)
7. **关键前提**: omodul.knowledge 命名空间有 2 行 import bug (已识别 in 65e2658d), 修复后可解锁 ~20 个元素 (agents/scheduler/views/browser_extension). 这 2 行修复属于**主库 omodul 经理人**负责.

---

## §1 反推方法

对 audit §2 每行 🟡/❌/⚠️ 功能:
1. 分析该功能所需的原子能力 → oprim
2. 分析所需的组合算法 → oskill
3. 分析所需的业务事务 → omodul
4. 分析横切需求 → obase
5. 标注 v0.3 已有编号 (如有), 否则标 (新)

---

## §2 分库元素需求清单

---

### == obase 元素清单 ==

横切关注点: 认证/支付/DNS安全/可观测性

| 元素名 | v0.3编号/已有 | 类型 | audit来源 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `obase.oauth2_provider.google` | (新) | 新增 | audit §F Google Drive + §G WeChat | Phase 2 网盘 OAuth 登录, Phase 4 Google 登录 | obase 经理人; ADR-022 |
| `obase.oauth2_provider.microsoft` | (新) | 新增 | audit §F OneDrive | Phase 2 OneDrive OAuth | obase 经理人 |
| `obase.oauth2_provider.dropbox` | (新) | 新增 | audit §F Dropbox | Phase 9 Dropbox OAuth | obase 经理人 |
| `obase.wechat_pay_gateway` | (新) | 新增 | audit §G WeChat Pay | billing.py subscribe endpoint | obase 经理人; ADR-026 |
| `obase.stripe_gateway` | (Helios P9-B3 评估) | 注册到已有/新增 | audit §G Stripe 海外 | billing.py Stripe path | obase 经理人; ADR-026 |
| `obase.dns_pinned_http_transport` | (新) | 新增 | TECHNICAL_DEBT DNS rebinding | oprim.url_fetch_ssrf_safe 修复 TOCTOU | obase 经理人; TECHNICAL_DEBT pre-launch |
| `obase.push_apns_gateway` | (新) | 新增 | audit §A 录音/§F push | iOS push notification (Phase 4/11) | obase 经理人 |
| `obase.push_fcm_gateway` | (新) | 新增 | audit §F push Android | Android push (Phase 4/11) | obase 经理人 |
| `obase.wechat_login_provider` | (新) | 新增 | audit §G WeChat 小程序 | 微信登录 (Phase 4) | obase 经理人; ADR-025 |
| `obase.observability_tracer` | (新) | 新增 | audit §C 4个Agent外挂失败 | 8 Agent 跨服务调用追踪 | obase 经理人 |

**obase 小计**: 10 个新元素 (其中 1 个待确认是否 Helios 已有)

---

### == oprim 元素清单 ==

#### A. 用户输入资料新增需求 (audit §A 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.ingest_progress_tracker` | (新) | 新增 | audit §A 上传文件 🟡 无进度 | inbox_submit 路由; WS 推送进度事件 | oprim 经理人 |
| `oprim.ingest_failure_notifier` | (新) | 新增 | audit §A 上传失败无提示 | inbox 路由失败时 emit WS event | oprim 经理人 |
| `oprim.url_fetch_ssrf_safe` | oprim-ut07 (已有 url_safety_check) | 修订 | audit §A URL抓取 🟡 + TECHNICAL_DEBT TOCTOU | inbox web-clip _fetch_url_html | oprim 经理人; 需整合 obase.dns_pinned_transport |
| `oprim.fetch_rss_feed` | (有 stub, 不可用) | 修订 | audit §A RSS ⚠️ + §B 领域跟踪 ❌ | feed_tracker_agent; domain_monitor_agent | oprim 经理人; fetch_rss stub 需补 feedparser |
| `oprim.parse_atom_feed` | (新) | 新增 | audit §A RSS ⚠️ | Atom/RSS 格式统一解析 | oprim 经理人 |
| `oprim.detect_feed_url_from_homepage` | (新) | 新增 | audit §A RSS ⚠️ | 从网页 URL 自动发现 RSS/Atom feed | oprim 经理人 |
| `oprim.podcast_episode_parser` | (新) | 新增 | audit §A Podcast feed ❌ | podcast medium ingest pipeline | oprim 经理人 |
| `oprim.email_receive_handler` | (新) | 新增 | audit §A 邮件转发 ❌ | 邮件入库入口 (SMTP/IMAP) | oprim 经理人 |
| `oprim.wechat_official_msg_handler` | (新) | 新增 | audit §A 微信图文 ❌ + §K 微信生态 | 公众号文件接收 → 入库 | oprim 经理人; ADR-025 |
| `oprim.wechat_file_receiver` | (新) | 新增 | audit §A 微信文件 ❌ | 公众号/小程序文件接收 | oprim 经理人 |
| `oprim.voice_audio_capture` | (新) | 新增 | audit §A 录音 ❌ | 移动端录音入口 → whisper ASR | oprim 经理人 |

#### B. Stratum 主动找资料新增需求 (audit §B 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.keyword_alert_checker` | (新) | 新增 | audit §B 关键词监控 ❌ | domain_monitor_agent; alert_agent | oprim 经理人 |
| `oprim.feed_subscription_manager` | (新) | 新增 | audit §B 领域跟踪 ❌ + §A RSS | 订阅记录存储 (URL + 用户 + 频率) | oprim 经理人 |
| `oprim.feed_diff_detector` | (新) | 新增 | audit §B 领域跟踪 ❌ | 两次 RSS 抓取 diff → 新增内容 | oprim 经理人 |

#### C. AI 加工新增需求 (audit §C 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.tts_synthesize` (导出修复) | oprim-tt01 🟡 文件存在未导出 | 修订 | audit §C 音频朗读 🟡 | audio_generator Agent; generate_audio_narration | oprim 经理人; 加入 __init__.py 导出 |
| `oprim.tts_synthesize.edge_tts` (provider) | (有文件 edge-tts 待注册) | 注册到已有 | audit §C 音频朗读 🟡 | ProviderRegistry 注册 edge-tts | oprim 经理人 |
| `oprim.tts_synthesize.f5_tts` (provider) | (新, 需 ADR-020) | 新增 | audit §C 音频朗读 🟡 | F5-TTS 外挂 provider 注册 | oprim 经理人; ADR-020 GPU 部署前置 |
| `oprim.tts_synthesize.fish_speech` (provider) | (新, 需 ADR-020) | 新增 | audit §C 音频朗读 🟡 | fish-speech 外挂 provider 注册 | oprim 经理人; ADR-020 |
| `oprim.image_generate` (导出修复) | oprim-ig01 🟡 文件存在未导出 | 修订 | audit §C 插图生成 🟡 | illustration_agent; generate_illustration | oprim 经理人; 加入 __init__.py |
| `oprim.image_generate.comfyui` (provider) | (新, 需 ADR-020) | 新增 | audit §C 插图生成 🟡 | ComfyUI/SD-webui provider 注册 | oprim 经理人; ADR-020 |
| `oprim.image_understand` (导出修复) | oprim-iu01 🟡 文件存在未导出 | 修订 | audit §C 多模态 ⚠️ | image_qa workflow; multi-modal LLM | oprim 经理人 |
| `oprim.image_understand.qwen_vl` (provider) | (新) | 新增 | audit §C 多模态 ⚠️ | Qwen-VL / Claude Vision provider | oprim 经理人 |
| `oprim.concept_extractor` | (新) | 新增 | audit §C 概念自动抽取 ❌ | concept_extractor_agent; knowledge_curator | oprim 经理人 |
| `oprim.ocr_detect_text` | (新) | 新增 | audit §C OCR ❌ | image substrate 文字识别 (parse_pdf.marker 补充) | oprim 经理人 |

#### D. 用户使用新增需求 (audit §D 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.hybrid_search_view_filter` | (修订 oskill-05 hybrid_search) | 修订 | audit §D 视图过滤 ❌ | search 接口 view_id 参数 (SPEC §16.4) | oprim/oskill 经理人 |
| `oprim.citation_formatter` | (新) | 新增 | audit §D 引用 ⚠️ | Agent 输出 + search 结果 citation 字段 (SPEC §10.1) | oprim 经理人 |
| `oprim.platform_content_indexer` | (新) | 新增 | audit §D 跨层检索 ❌ | hevi 平台内容入索引; cross_layer_search | oprim 经理人; Phase 6 依赖 hevi |
| `oprim.user_behavior_aggregator` | (新) | 新增 | audit §D 推荐 ❌ | recommend_content (现 stub); 行为信号汇聚 | oprim 经理人 |
| `oprim.graph_traversal` | (新) | 新增 | audit §D 概念图谱 🟡 | concept graph API (后端有, 前端无图谱组件) | oprim 经理人 |
| `oprim.timeline_aggregator` | (新) | 新增 | audit §D 时间线 ❌ | substrate 按时间分桶展示 | oprim 经理人 |
| `oprim.backlink_resolver` | (新) | 新增 | audit §D 反向链接 🟡 | note→note wikilink 前端展示 | oprim 经理人 |
| `oprim.mcp_server_config` | (新) | 新增 | audit §D MCP 生产 🟡 | omodul.start_mcp_server 生产容器挂载 | oprim 经理人 |

#### E. 用户协作新增需求 (audit §E 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.public_link_generator` | (新) | 新增 | audit §E 公开 substrate ❌ | 公开 share link (无需 token, 可发现) | oprim 经理人 |
| `oprim.access_control_checker` | (新) | 新增 | audit §E 公开/订阅 ❌ | access_tier 控制 (platform content) | oprim 经理人 |
| `oprim.social_subscription_manager` | (新) | 新增 | audit §E 关注作者 ❌ | follow/unfollow 记录存取 | oprim 经理人 |
| `oprim.comment_store` | (新) | 新增 | audit §E 评论 ❌ | substrate/note 评论 CRUD | oprim 经理人 |
| `oprim.email_sender` | (oprim-pu02 push_email 相关) | 注册到已有 | audit §E 评论通知 + §F push | 关注/评论通知邮件 | oprim 经理人 |

#### F. 同步新增需求 (audit §F 对应, Phase 2 全部缺)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.storage.gdrive_adapter` | oprim-s02 ❌ 空 | 新增 | audit §F Google Drive ❌ | Phase 2 用户网盘 | oprim 经理人; ADR-022; GDrive OAuth 前置 |
| `oprim.storage.onedrive_adapter` | (新) | 新增 | audit §F OneDrive ❌ | Phase 9 OneDrive 支持 | oprim 经理人 |
| `oprim.storage.dropbox_adapter` | (新) | 新增 | audit §F Dropbox ❌ | Phase 9 Dropbox 支持 | oprim 经理人 |
| `oprim.storage.local_adapter` | oprim-s03 ❌ 空 | 新增 | audit §F 本地文件夹 ❌ | Phase 2 本地 adapter | oprim 经理人 |
| `oprim.storage.upload_file` | oprim-s04 ❌ 空 | 新增 | audit §F ❌ | 网盘上传通用接口 | oprim 经理人 |
| `oprim.storage.download_file` | oprim-s04 ❌ 空 | 新增 | audit §F ❌ | 网盘下载 | oprim 经理人 |
| `oprim.storage.delete_file` | oprim-s04 ❌ 空 | 新增 | audit §F ❌ | 网盘删除 | oprim 经理人 |
| `oprim.storage.list_files` | oprim-s04 ❌ 空 | 新增 | audit §F ❌ | 网盘目录列表 | oprim 经理人 |
| `oprim.changefeed_append` | oprim-cf01 ❌ 空 | 新增 | audit §F 同步 ❌ | Phase 2 事件追加 | oprim 经理人 |
| `oprim.changefeed_read` | oprim-cf02 ❌ 空 | 新增 | audit §F 同步 ❌ | oskill.sync.flush_outbox 依赖 | oprim 经理人 |
| `oprim.changefeed_compact` | oprim-cf03 ❌ 空 | 新增 | audit §F 同步 ❌ | 长期运行 compaction | oprim 经理人 |
| `oprim.changefeed_snapshot` | oprim-cf04 ❌ 空 | 新增 | audit §F 同步 ❌ | 网盘 snapshot 备份 | oprim 经理人 |
| `oprim.push_web` | oprim-pu01 ❌ 空 | 新增 | audit §F push ❌ | Scheduled Job 完成通知 | oprim 经理人 |
| `oprim.push_email` | oprim-pu02 ❌ 空 | 新增 | audit §F push ❌ | digest/lint 结果邮件推送 | oprim 经理人 |
| `oprim.push_apns` | (新) | 新增 | audit §F push iOS ❌ | iOS app 推送 (Phase 11) | oprim 经理人; obase.push_apns_gateway 前置 |
| `oprim.push_fcm` | (新) | 新增 | audit §F push Android ❌ | Android 推送 (Phase 11) | oprim 经理人; obase.push_fcm_gateway 前置 |
| `oprim.oauth_token_manager` | (新) | 新增 | audit §F OAuth token 加密 ❌ | 用户网盘 token 加密存储 | oprim 经理人; SPEC §13.2 |
| `oprim.sync_status_checker` | (新) | 新增 | audit §F 多设备 ❌ | sync_status 字段 (SPEC §10.1 response) | oprim 经理人 |
| `oprim.offline_queue` | (新) | 新增 | audit §F 离线模式 ❌ | 离线操作队列 → 联网后 flush | oprim 经理人 |

#### G. 商业新增需求 (audit §G 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.wechat_pay_create_order` | (新) | 新增 | audit §G 微信支付 ❌ | billing.py subscribe wechat path | oprim 经理人; ADR-026; obase.wechat_pay_gateway 前置 |
| `oprim.wechat_pay_verify_callback` | (新) | 新增 | audit §G ❌ | billing.py /callback/wechat | oprim 经理人 |
| `oprim.wechat_pay_refund` | (新) | 新增 | audit §G ❌ | 退款流程 | oprim 经理人 |
| `oprim.stripe_payment_intent` | (新) | 新增 | audit §G Stripe ❌ | billing.py Stripe path | oprim 经理人; ADR-026 |
| `oprim.subscription_tier_check` | (新) | 新增 | audit §G access_tier ❌ | 平台内容 access_tier 控制 (SPEC §15.3) | oprim 经理人 |
| `oprim.quota_manager` | (新) | 新增 | audit §G 配额 ❌ | substrate 数/翻译 token/TTS 时长 (SPEC §9.4) | oprim 经理人 |
| `oprim.invoice_generator` | (新) | 新增 | audit §G ❌ | 支付后发票生成 | oprim 经理人 |
| `oprim.wechat_miniprogram_auth` | (新) | 新增 | audit §G 微信小程序 ❌ | 微信小程序 code → openid | oprim 经理人; ADR-025 |
| `oprim.wechat_login_client` | (新) | 新增 | audit §G 微信登录 ❌ | 微信 OAuth2 登录 | oprim 经理人 |
| `oprim.wechat_subscribe_msg_sender` | (新) | 新增 | audit §G 微信订阅消息 ❌ | 新内容推送 / 订阅成功通知 | oprim 经理人 |

#### H. 外挂集成新增需求 (audit §H 对应)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.external.whisper_client` | oprim-ex02 🟡 文件有不可达 | 修订/激活 | audit §H whisper ❌ + §A 录音 | transcribe_audio_substrate; 语音入库 | oprim 经理人; ADR-020 whisper 部署 |
| `oprim.external.sd_client` (ComfyUI) | oprim-ex01 ❌ 空 (v0.3 #33) | 新增 | audit §H SD-webui ❌ | generate_illustration; illustration_agent | oprim 经理人; ADR-020 GPU 部署 |
| `oprim.external.searxng_client` | oprim-ex01 ❌ 空 (v0.3 #34) | 新增 | audit §H searxng ❌ + §B | web_search_augmented; researcher_agent | oprim 经理人; searxng Docker 部署 |
| `oprim.external.hevi_client` | oprim-ex01 ❌ 空 (v0.3 #35) | 新增 | audit §H hevi ❌ | platform content 拉取; hevi-content-repo 对接 | oprim 经理人; ADR-021 hevi 协议商定 |
| `oprim.external.screenpipe_reader` | oprim-ex01 ❌ 空 (v0.3 #36) | 新增 | audit §H screenpipe ❌ | screen_event substrate; screenpipe SQLite 读取 | oprim 经理人 |
| `oprim.input.screenpipe_capture` | (新) | 新增 | audit §H screenpipe ❌ | screenpipe 事件写入 substrate | oprim 经理人 |
| `oprim.external.tts_client_f5` | (新) | 新增 | audit §C audio ❌ | F5-TTS MCP/HTTP 调用 | oprim 经理人; ADR-020 |
| `oprim.external.tts_client_fish_speech` | (新) | 新增 | audit §C audio ❌ | fish-speech MCP/HTTP 调用 | oprim 经理人; ADR-020 |
| `oprim.external.tts_client_edge` | (有 tts_client.py 文件存在未导出) | 激活 | audit §C audio 🟡 | edge-tts 免费 TTS; provider 注册 | oprim 经理人 |
| `oprim.llm.vision` | oprim-iu01 🟡 文件未导出 | 修订 | audit §C 多模态 ⚠️ | image_understand provider 注册 | oprim 经理人 |
| `oprim.llm.llm_call.ollama` (provider) | (新 provider) | 注册到已有 | audit §H Ollama ❌ | 本地 LLM 路由 (oprim.llm.llm_call 扩展) | oprim 经理人 |

#### J. 移动端新增需求 (audit §D/§G 隐含)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oprim.apns_push_token_register` | (新) | 新增 | audit §G 手机 App ❌ | iOS app 注册 push token | oprim 经理人; ADR-027 |
| `oprim.fcm_push_token_register` | (新) | 新增 | audit §G ❌ | Android app 注册 push token | oprim 经理人; ADR-027 |
| `oprim.deeplink_handler` | (新) | 新增 | audit §G ❌ | 从 push notification 跳入 App 内 substrate | oprim 经理人 |

---

**oprim 小计**:

| 类别 | 数量 |
|---|---|
| 用户输入 (A) | 11 个 |
| 主动找资料 (B) | 3 个 |
| AI 加工 (C) | 10 个 |
| 用户使用 (D) | 8 个 |
| 协作 (E) | 5 个 |
| 同步 Phase 2 (F) | 19 个 |
| 商业 (G) | 10 个 |
| 外挂 (H) | 11 个 |
| 移动端 (J) | 3 个 |
| **总计** | **80 个** |

---

### == oskill 元素清单 ==

stateless 组合算法 (oprim 的组合, 不含事务)

| 元素名 | v0.3编号/已有 | 类型 | audit来源行 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `oskill.researcher_workflow` | (新) | 新增 | audit §B ResearcherAgent ❌ | researcher_agent 核心; searxng + hybrid_search | oskill 经理人; ADR-024 设计前置 |
| `oskill.domain_monitor_scan` | (新) | 新增 | audit §B 领域跟踪 ❌ | domain_monitor_agent; 定期扫描领域 RSS | oskill 经理人 |
| `oskill.feed_diff` | (新) | 新增 | audit §A RSS ⚠️ + §B ❌ | feed_tracker_agent; 检测 feed 新增条目 | oskill 经理人 |
| `oskill.keyword_alert_scan` | (新) | 新增 | audit §B 关键词监控 ❌ | alert_agent; 在 substrate 检索关键词命中 | oskill 经理人 |
| `oskill.cross_layer_search` 扩展 | (已有 ✅ cross_layer_search) | 修订 | audit §D 跨层检索 ❌ | 加 platform_content 层; 现只查用户 substrate | oskill 经理人; Phase 6 依赖 hevi |
| `oskill.hybrid_search` 扩展 view_id | oskill-05 ✅ hybrid_search | 修订 | audit §D 视图过滤 ❌ | search 接口 view_id 参数 (SPEC §16.4) | oskill 经理人 |
| `oskill.hybrid_search` 扩展 citation | oskill-05 ✅ | 修订 | audit §D 引用 ⚠️ | citation 字段 (SPEC §10.1 v0.6 P3) | oskill 经理人 |
| `oskill.concept_graph_builder` | (新) | 新增 | audit §D 概念图谱 🟡 | concept graph 从多 substrate 中构建 | oskill 经理人 |
| `oskill.extract_concepts_from_substrate` | (新) | 新增 | audit §C 概念抽取 ❌ | concept_extractor_agent; knowledge_curator 增强 | oskill 经理人 |
| `oskill.recommend_content` 修复 | (已有 ✅ recommend_content but stub) | 修订 | audit §D 推荐 ❌ | recommendations 路由 (现返回空列表) | oskill 经理人 |
| `oskill.generate_audio_narration` 修复 | (已有 🟡 文件存在依赖缺) | 修订 | audit §C 音频 🟡 | audio_generator Agent; 依赖 oprim.tts_synthesize 导出 | oskill 经理人; oprim.tts_synthesize 修订后 |
| `oskill.generate_illustration` 修复 | (已有 🟡 文件存在依赖缺) | 修订 | audit §C 插图 🟡 | illustration_agent; 依赖 oprim.image_generate 导出 | oskill 经理人; oprim.image_generate 修订后 |
| `oskill.transcribe_audio_substrate` 修复 | (已有 🟡 依赖 whisper 空) | 修订 | audit §A 录音 ❌ | 音频/播客 ASR → derivative | oskill 经理人; oprim.external.whisper 激活后 |
| `oskill.web_search_augmented` 修复 | (已有 🟡 依赖 searxng 空) | 修订 | audit §B 领域跟踪 + §D | researcher_agent; web context 增强 | oskill 经理人; oprim.external.searxng 激活后 |
| `oskill.classify_inbox_file` Layer 3 | oskill-01 🟡 Layer 3 LLM NotImplementedError | 修订 | audit §C AI 加工 🟡 | Layer 3 LLM 兜底分类器 (知识整理) | oskill 经理人 |
| `oskill.platform_content_ingest` | (新) | 新增 | audit §H hevi ❌ | hevi 内容 → platform_content 流水线 | oskill 经理人; ADR-021 + oprim.external.hevi_client |
| `oskill.platform_concept_extract` | (新) | 新增 | audit §H hevi ❌ | hevi 内容 concept 抽取 → platform_concept 表 | oskill 经理人 |
| `oskill.image_qa` | (新) | 新增 | audit §C 多模态 ⚠️ | 图片问答 skill (oprim.image_understand 上层) | oskill 经理人 |
| `oskill.podcast_ingest` | (新) | 新增 | audit §A Podcast ❌ | podcast episode → substrate pipeline | oskill 经理人 |
| `oskill.sync.flush_outbox` | (已有 ❌ oprim.changefeed.schema 依赖缺) | 修订/解锁 | audit §F 同步 ❌ | omodul.sync.bg_sync 依赖链 | oskill 经理人; oprim.changefeed 实施后 |
| `oskill.sync.apply_remote_events` | (已有 ❌ 同上) | 修订/解锁 | audit §F 同步 ❌ | 多端事件应用 | oskill 经理人; oprim.changefeed 实施后 |
| `oskill.sync.snapshot_backup` | (已有 ❌ 同上) | 修订/解锁 | audit §F 同步 ❌ | 网盘 snapshot 上传 | oskill 经理人; oprim.changefeed + storage 实施后 |
| `oskill.subscription_tier_enforcer` | (新) | 新增 | audit §G 订阅 ❌ | access_tier 检查 + quota 执行 | oskill 经理人 |
| `oskill.screenpipe_event_ingest` | (新) | 新增 | audit §H screenpipe ❌ | screenpipe events → screen_event substrate | oskill 经理人 |
| `oskill.hevi_content_reindex` | (新) | 新增 | audit §H hevi ❌ | hevi 新版本 → reindex platform_content_chunk | oskill 经理人 |

**oskill 小计**: 25 个 (15 新增 + 10 修订/解锁)

---

### == omodul 元素清单 ==

有状态业务事务 (DB 读写, 完整 workflow)

#### 关键前置: 2 行 import bug 修复 (主库 omodul 经理人)

**这 2 行修复可解锁已存在代码的 ~20 个元素, 优先级 P0:**

| Bug | 文件 | 修法 | 影响 |
|---|---|---|---|
| Bug 1 | omodul/knowledge/process_inbox.py L11 | `from oskill.knowledge.ingest_substrate` → `from oskill.ingest_substrate` | 解锁整个 omodul.knowledge 命名空间 |
| Bug 2 | omodul/knowledge/start_mcp_server.py | `from oskill.knowledge.hybrid_search` → `from oskill.hybrid_search` | 解锁 start_mcp_server |

**以下 omodul.knowledge 元素代码完整, import bug 修复后立即可用 (⚠️ → ✅):**

| 元素名 | v0.3编号 | 类型 | audit来源 | Stratum端使用 | 状态 |
|---|---|---|---|---|---|
| `omodul.knowledge.process_inbox` | omodul-10 ⚠️ | 解锁 | audit §A 上传 🟡 | inbox 流水线; knowledge_curator | 2 行 bug fix 后可用 |
| `omodul.knowledge.start_mcp_server` | omodul-11 ⚠️ | 解锁 | audit §D MCP 🟡 | MCP server 生产部署 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.KnowledgeCuratorAgent` | omodul-a01 ⚠️ | 解锁 | audit §C AI加工 ✅ | knowledge_curator 调度 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.DailyDigestAgent` | omodul-a02 ⚠️ | 解锁 | audit §C 摘要 ✅ | daily_digest 调度 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.ReadingCompanionAgent` | omodul-a03 ⚠️ | 解锁 | audit §C 阅读 ✅ | reading_companion 调度 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.TranslationWorkerAgent` | omodul-a04 ⚠️ | 解锁 | audit §C 翻译 ✅ | translation_worker 调度 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.LintBotAgent` | omodul-a05 ⚠️ | 解锁 | audit §C lint ✅ | lint_bot 调度 | 2 行 bug fix 后可用 |
| `omodul.knowledge.agents.AudioGeneratorAgent` | omodul-a06 ⚠️ | 解锁 | audit §C audio 🟡 | audio_generator (外挂部署后) | 2 行 bug fix 后可用 |
| `omodul.knowledge.scheduler.cron_engine` | omodul-s01 ⚠️ | 解锁 | audit §C Scheduled Jobs 🟡 | 定时 Agent 触发 | 2 行 bug fix 后可用 |
| `omodul.knowledge.scheduler.builtin_jobs` | omodul-s02 ⚠️ | 解锁 | audit §C 定时 Job 🟡 | 4 个内置 Job | 2 行 bug fix 后可用 |
| `omodul.knowledge.views.crud` | omodul-v01 ⚠️ | 解锁 | audit §D 视图 🟡 | views CRUD | 2 行 bug fix 后可用 |
| `omodul.knowledge.views.applier` | omodul-v02 ⚠️ | 解锁 | audit §D 视图 🟡 | search 应用 view filter | 2 行 bug fix 后可用 |
| `omodul.knowledge.views.preset_loader` | omodul-v03 ⚠️ | 解锁 | audit §D 视图 🟡 | 5 个预设 view | 2 行 bug fix 后可用 |
| `omodul.knowledge.browser_extension.server` | omodul-b01 ⚠️ | 解锁 | audit §A 浏览器扩展 🟡 | browser extension 服务端 | 2 行 bug fix 后可用 |
| `omodul.knowledge.browser_extension.page_capture` | omodul-b02 ⚠️ | 解锁 | audit §A 浏览器扩展 🟡 | HTML 内容提取 | 2 行 bug fix 后可用 |
| `omodul.knowledge.browser_extension.url_dedup` | omodul-b03 ⚠️ | 解锁 | audit §A 浏览器扩展 🟡 | 网页 URL 去重 | 2 行 bug fix 后可用 |
| `omodul.sync.bg_sync` | omodul-sync01 ⚠️ | 解锁(后) | audit §F 同步 ❌ | 后台同步守护进程 | 需 oprim.changefeed + oskill.sync 先就位 |

**以下是真正的新增 omodul 元素 (代码不存在):**

| 元素名 | v0.3编号/已有 | 类型 | audit来源 | Stratum端使用 | 跨经理人需求 |
|---|---|---|---|---|---|
| `omodul.knowledge.agents.ResearcherAgent` | (新) | 新增 | audit §B ResearcherAgent ❌ | 主动找资料; searxng + hybrid_search | omodul 经理人; ADR-024; oskill.researcher_workflow 前置 |
| `omodul.knowledge.agents.FeedTrackerAgent` | (新) | 新增 | audit §A RSS ⚠️ + §B | RSS/Atom 订阅跟踪; 新内容入库 | omodul 经理人; oprim.fetch_rss + oskill.feed_diff 前置 |
| `omodul.knowledge.agents.DomainMonitorAgent` | (新) | 新增 | audit §B 领域跟踪 ❌ | 关键词/领域定期监控; searxng | omodul 经理人 |
| `omodul.knowledge.agents.ConceptExtractorAgent` | (新) | 新增 | audit §C 概念抽取 ❌ | 从 substrate 自动抽 concept 入库 | omodul 经理人; oprim.concept_extractor 前置 |
| `omodul.knowledge.agents.WeeklyReviewAgent` (扩展) | omodul-03 ✅ | 修订 | audit §C 周复盘 ✅ | UI 结果展示缺失 → findings 结构化 | omodul 经理人 |
| `omodul.knowledge.agents.IllustrationAgent` | (新) | 新增 | audit §C 插图 🟡 | illustration 触发 (SD 部署后) | omodul 经理人; oprim.image_generate + ADR-020 |
| `omodul.sync.gdrive_sync_workflow` | (新) | 新增 | audit §F Google Drive ❌ | 用户网盘 substrate 双向同步 | omodul 经理人; Phase 2 整体 |
| `omodul.sync.snapshot_restore_workflow` | (新) | 新增 | audit §F 同步 ❌ | 从网盘 snapshot 恢复用户数据 | omodul 经理人 |
| `omodul.platform.content_ingest_workflow` | (新) | 新增 | audit §H hevi ❌ | hevi 内容 → platform_content 入库 | omodul 经理人; ADR-021 协议商定前置 |
| `omodul.platform.content_reindex_workflow` | (新) | 新增 | audit §H hevi ❌ | hevi 内容更新 → version 增量 reindex | omodul 经理人 |
| `omodul.platform.tts_pipeline_workflow` | (新) | 新增 | audit §C audio ❌ | hevi 文章 → TTS 音频 CDN (Phase 8) | omodul 经理人; ADR-020 TTS 前置 |
| `omodul.subscription.change_tier_workflow` | (新) | 新增 | audit §G 订阅 ❌ | 支付成功 → subscription 生效 → push | omodul 经理人; oprim.wechat_pay 前置 |
| `omodul.subscription.cancel_workflow` | (新) | 新增 | audit §G ❌ | 取消订阅 → platform_cache 清空 | omodul 经理人 |
| `omodul.social.follow_workflow` | (新) | 新增 | audit §E 关注 ❌ | follow/unfollow + 通知 | omodul 经理人 |
| `omodul.social.comment_workflow` | (新) | 新增 | audit §E 评论 ❌ | 评论 CRUD + 通知 | omodul 经理人 |
| `omodul.email_ingest_workflow` | (新) | 新增 | audit §A 邮件转发 ❌ | 邮件附件/正文 → inbox substrate | omodul 经理人; oprim.email_receive_handler 前置 |
| `omodul.screenpipe_ingest_workflow` | (新) | 新增 | audit §H screenpipe ❌ | screenpipe 事件批量入库 | omodul 经理人; Phase 12 |
| `omodul.wechat.file_ingest_workflow` | (新) | 新增 | audit §A 微信文件 ❌ | 公众号文件 → inbox substrate | omodul 经理人; ADR-025 |

**omodul 小计**:
- 17 个已存在但被 import bug 锁定 (2 行修复可解锁)
- 18 个真正新增

---

## §3 每元素 6 标签格式说明

每行完整格式:
```
[元素名] | [v0.3编号/已有标识] | [类型: 新增/修订/注册到已有/解锁/激活] | [audit来源行] | [Stratum端使用位置] | [跨经理人需求: 哪个库owner/SPEC升级/ADR需要]
```

§2 中所有表格均已按此格式填写全部 6 个字段。

---

## §4 跨经理人协调矩阵

### oprim 经理人需做

| 优先级 | 工作项 | 依赖 | 估工程量 |
|---|---|---|---|
| **P0 立即** | changefeed 全部实施 (4 元素) | 无 | 2-3 周 |
| **P0 立即** | storage adapter 全部 (8 元素: gdrive/local/onedrive/dropbox + CRUD) | GDrive OAuth 申请 | 4-6 周 |
| **P0 立即** | push_web + push_email (2 元素) | 无 | 1-2 周 |
| **P0 立即** | tts_synthesize + image_generate 导出修复 + edge-tts provider 注册 (3 步) | 无 | 2-3 天 |
| **P0 引流前** | url_fetch_ssrf_safe TOCTOU 修复 (整合 obase.dns_pinned_transport) | obase.dns_pinned_transport | 1 周 |
| **P1 近期** | external.whisper_client 激活 | ADR-020 部署 | 1-2 周 |
| **P1 近期** | external.searxng_client 实施 | searxng Docker | 1-2 周 |
| **P1 近期** | tts_synthesize.f5_tts + fish_speech providers | ADR-020 GPU | 2-3 周 |
| **P1 近期** | image_generate.comfyui provider | ADR-020 SD | 2-3 周 |
| **P1 近期** | concept_extractor (新元素) | 无 | 1-2 周 |
| **P1 近期** | fetch_rss_feed 修复 + parse_atom_feed + detect_feed_url | 无 | 1-2 周 |
| **P1 近期** | oauth_token_manager + sync_status_checker | 无 | 1-2 周 |
| **P2 后续** | wechat_pay / stripe_payment_intent | ADR-026; obase gateway | 3-4 周 |
| **P2 后续** | push_apns + push_fcm | ADR-027; obase gateway | 2-3 周 |
| **P2 后续** | external.hevi_client | ADR-021 协议商定 | 2-3 周 |
| **P2 后续** | screenpipe_reader | Phase 12 | 2 周 |
| **P2 后续** | image_understand 导出 + vision providers | 无 | 1-2 周 |
| **P2 后续** | 微信生态全套 (miniprogram_auth/login/msg_handler) | ADR-025 | 3-4 周 |
| **P2 后续** | 商业元素 (quota/invoice/subscription_tier_check) | ADR-026 | 2-3 周 |
| **P2 后续** | 移动端 (apns/fcm/deeplink) | ADR-027 | 1-2 周 |

**oprim 经理人总计**: 约 80 个元素, 其中 P0 约 20 个, P1 约 30 个, P2 约 30 个. **估总工程量 ~20-30 周** (含 P0 + P1).

---

### oskill 经理人需做

| 优先级 | 工作项 | 依赖 | 估工程量 |
|---|---|---|---|
| **P0 立即** | hybrid_search 加 view_id + citation 参数 | 无 | 1 周 |
| **P0 立即** | recommend_content 真实现 (现返回空) | oprim.user_behavior_aggregator | 2-3 周 |
| **P1 近期** | generate_audio_narration 修复 (provider 已注册后) | oprim.tts_synthesize | 当天 |
| **P1 近期** | generate_illustration 修复 (provider 已注册后) | oprim.image_generate | 当天 |
| **P1 近期** | transcribe_audio_substrate 修复 | oprim.external.whisper | 当天 |
| **P1 近期** | web_search_augmented 修复 | oprim.external.searxng | 当天 |
| **P1 近期** | classify_inbox_file Layer 3 LLM 兜底 | 无 | 1 周 |
| **P1 近期** | concept_graph_builder (新) | oprim.graph_traversal | 2-3 周 |
| **P1 近期** | extract_concepts_from_substrate (新) | oprim.concept_extractor | 1-2 周 |
| **P1 近期** | researcher_workflow (新) | oprim.external.searxng | 2-3 周 |
| **P1 近期** | feed_diff (新) | oprim.fetch_rss_feed 修复 | 1 周 |
| **P2 后续** | sync.flush_outbox + apply_remote + snapshot 解锁 | oprim.changefeed 全部 | 2-3 周 |
| **P2 后续** | platform_content_ingest (新) | oprim.external.hevi_client; ADR-021 | 3-4 周 |
| **P2 后续** | cross_layer_search 扩展 platform 层 | oskill.platform_content_ingest | 2 周 |
| **P2 后续** | 其他新增 (domain_monitor/keyword_alert/podcast 等) | 上游 oprim 就位 | 1-2 周/个 |

**oskill 经理人总计**: 约 25 个元素 (8 修订解锁, 17 新增). **估总工程量 ~10-15 周** (P0-P2).

---

### omodul 经理人需做

| 优先级 | 工作项 | 依赖 | 估工程量 |
|---|---|---|---|
| **P0 立即** | **Bug 1 修复**: process_inbox.py 1 行 import 路径 | 无 | 30 分钟 |
| **P0 立即** | **Bug 2 修复**: start_mcp_server.py 1 行 import 路径 | 无 | 10 分钟 |
| **P0 立即后** | 验证 17 个 ⚠️ 元素真实解锁 (agents/scheduler/views/browser_ext) | Bug 1+2 修复 | 1-2 天测试 |
| **P1 近期** | IllustrationAgent (新) | oprim.image_generate + ADR-020 | 1-2 周 |
| **P1 近期** | ConceptExtractorAgent (新) | oskill.extract_concepts_from_substrate | 1-2 周 |
| **P1 近期** | ResearcherAgent (新) | ADR-024; oskill.researcher_workflow | 2-3 週 |
| **P1 近期** | FeedTrackerAgent (新) | oprim.fetch_rss + oskill.feed_diff | 1-2 週 |
| **P2 后续** | gdrive_sync_workflow (新) | oprim.storage + oskill.sync 全套 | 3-4 周 |
| **P2 后续** | platform.content_ingest_workflow (新) | ADR-021 + oprim.hevi_client | 2-3 周 |
| **P2 后续** | subscription.change_tier_workflow (新) | oprim.wechat_pay | 2 周 |
| **P2 后续** | social.follow/comment_workflow (新) | 无 | 2-3 周 |
| **P2 后续** | 其他新增 workflow (screenpipe/wechat/email 各 1-2 周) | 上游 oprim/oskill | 各 1-2 周 |

**omodul 经理人总计**: 17 个解锁 (2 行修复) + 18 个新增. **P0 最关键: 2 行 bug fix = 解锁 17 个已存在元素.** **估总工程量 ~15-20 周** (含 P1+P2 全部新增).

---

### obase 经理人需做

| 优先级 | 工作项 | 依赖 | 估工程量 |
|---|---|---|---|
| **P0 引流前** | dns_pinned_http_transport (TECHNICAL_DEBT) | 无 | 1-2 周 |
| **P1 近期** | oauth2_provider.google (GDrive/login) | GDrive OAuth 申请 | 1-2 周 |
| **P1 近期** | oauth2_provider.microsoft (OneDrive) | 无 | 1 周 |
| **P2 后续** | wechat_pay_gateway | ADR-026; 微信商户号 | 2-3 周 |
| **P2 后续** | stripe_gateway | ADR-026 | 2 周 |
| **P2 后续** | push_apns_gateway + push_fcm_gateway | ADR-027 | 2-3 周 |
| **P2 后续** | wechat_login_provider | ADR-025 | 1 周 |
| **P2 后续** | observability_tracer | 无 | 1-2 周 |

**obase 经理人总计**: 10 个新元素. **估总工程量 ~10-15 周** (含 P0-P2).

---

## §5 SPEC / ADR 待修订清单

### SPEC v0.6 → v0.7 升级清单

| 章节 | 升级内容 | 来源 |
|---|---|---|
| §14.2 Agent 清单 | 新增 ResearcherAgent (7th Agent) | audit §B + ADR-024 |
| 新增 §14.x FeedTrackerAgent | RSS/Atom 订阅跟踪 Agent | audit §A RSS |
| 新增 §14.x DomainMonitorAgent | 关键词/领域监控 Agent | audit §B |
| 新增 §14.x ConceptExtractorAgent | 自动概念抽取 Agent | audit §C |
| 新增 §X RSS/Feed 章节 | feed 订阅数据模型 + 接口 | audit §A |
| 新增 §X 领域跟踪章节 | 主动信息获取设计 | audit §B |
| §6.1 数据架构 修订 | 解决"服务器不持有 substrate"违反: 明确双轨 (SaaS 服务器存储 + 可选用户网盘同步) | REALITY_AUDIT §8.7 + ADR-022 |
| §7 网盘适配层 补充 | 加 OneDrive P0 (已从 SPEC 知道); 阿里云盘状态更新 | audit §F |
| §A 用户输入来源 | 补充邮件转发/Podcast feed | audit §A |
| §13.8 平台推送 | 加 APNS/FCM | audit §F |
| §15.1 订阅档位 | 明确买断选项是否支持 | audit §G; ADR-026 |
| §17.4 浏览器扩展 | 更新为 v0.3 已有代码状态 | audit §A |
| 新增 §X 概念百科 wiki 设计 | platform_concept 真实接入路径 | audit §D 概念图谱 |

### ADR 待做清单

| ADR 编号 | 标题 | 阻塞项 | 紧迫度 |
|---|---|---|---|
| **ADR-020** | 跨机部署拓扑 (TTS/SD GPU + 主力机 + VPS) | audio_generator / illustration_agent 外挂; Phase 11 | 🔴 已逾期 1 个月 |
| **ADR-021** | hevi-content-repo 协议 (meta.yaml schema + git 对接) | platform content 流水线; Phase 3/6 | 🔴 Phase 3 前置 |
| **ADR-022** | 用户数据架构: SaaS 服务器存储 vs 用户网盘 (架构根本决策) | SPEC §6.1 违反; Phase 2 or 不做 | 🔴 引流前必决 |
| **ADR-023** | RSS/Feed 跟踪机制 (数据模型 + 调度频率 + 存储位置) | FeedTrackerAgent; oprim.fetch_rss | 🟡 本月 |
| **ADR-024** | ResearcherAgent 设计 (searxng + hybrid_search 组合策略) | ResearcherAgent 实施 | 🟡 Phase 11 补充 |
| **ADR-025** | 微信生态接入策略 (小程序审核 / 备案 / 公众号 + ICP) | Phase 4 全部 | 🟡 Phase 4 前 |
| **ADR-026** | 付费系统 (微信支付 vs Stripe vs 买断 + 档位确认) | billing 真实上线 | 🟡 引流后立即 |
| **ADR-027** | 移动端策略 (Native vs PWA vs React Native vs 不做) | iOS/Android app | 🟢 Phase 11 后 |

---

## §6 工作量汇总估算

| 经理人 | P0 元素数 | P1 元素数 | P2 元素数 | 总计 | 估 P0+P1 工程量 |
|---|---|---|---|---|---|
| **obase** | 1 (dns_pinned) | 2 (oauth google/ms) | 7 | 10 | ~3-4 周 |
| **oprim** | ~20 | ~30 | ~30 | ~80 | ~12-16 周 |
| **oskill** | 2 (hybrid_search扩展 + recommend) | 10 | 13 | 25 | ~6-8 周 |
| **omodul** | 2 行 bug fix + 验证 | 4 新增Agent | 12 新增workflow | 35 (17解锁+18新增) | ~4-6 周 |
| **ADR** | 3 (020/021/022) | 2 (023/024) | 3 | 8 ADR | Wiki 决策 |
| **总计跨经理人** | | | | **~150 元素** | **~25-34 周 (P0+P1 = ~6-9 个月)** |

**关键路径**:
```
ADR-022 (数据架构决策)
  → oprim.changefeed (4 个)
  → oprim.storage.gdrive_adapter
  → oskill.sync 解锁 (3 个)
  → omodul.sync.bg_sync 解锁
  → 多设备同步 真可用

omodul Bug 1+2 修复 (2 行, 立即)
  → omodul.knowledge 17 个元素解锁
  → 6 Agent + scheduler + views + browser_extension 可用

ADR-020 (GPU 部署决策)
  → oprim.tts_synthesize providers
  → oprim.external.whisper_client
  → oprim.image_generate providers
  → audio_generator / illustration_agent 真可用
```

**最短引流路径 (Phase 17 全通后, 不做 Phase 2 同步)**:
```
1. omodul Bug 1+2 修复 (30分钟) → 解锁 17 个元素
2. oprim.tts_synthesize edge-tts provider 注册 (1天) → audio_generator 可用
3. obase.dns_pinned_transport (1-2周) → 修复 SSRF TOCTOU
4. oprim.ingest_progress_tracker (1周) → 上传进度反馈
5. 以上完成 → 引流条件勉强满足
```

---

## 附录: Audit Gap → 3O 对应快速查表

| audit §2 行 | 状态 | 主要 3O 阻塞 |
|---|---|---|
| 上传文件 | 🟡 | oprim.ingest_progress_tracker (新) |
| URL 抓取 | 🟡 | oprim.url_fetch_ssrf_safe 修订 + TOCTOU fix |
| 浏览器扩展 | 🟡 | omodul Bug 1+2 (2行), omodul.browser_extension 解锁 |
| RSS feed | ⚠️ | oprim.fetch_rss_feed 修复, oprim.parse_atom_feed, oskill.feed_diff |
| 邮件转发 | ❌ | oprim.email_receive_handler, omodul.email_ingest_workflow |
| 微信文件 | ❌ | oprim.wechat_official_msg_handler, ADR-025 |
| Podcast feed | ❌ | oprim.podcast_episode_parser, oskill.podcast_ingest |
| screenpipe | ⚠️ | oprim.external.screenpipe_reader, omodul.screenpipe_ingest_workflow |
| 录音 | ❌ | oprim.voice_audio_capture, oprim.external.whisper_client |
| ResearcherAgent | ❌ | omodul.ResearcherAgent (新), ADR-024, searxng |
| 领域跟踪 | ❌ | omodul.DomainMonitorAgent (新), oprim.feed_diff_detector |
| 关键词监控 | ❌ | oprim.keyword_alert_checker, omodul.agents (new) |
| searxng | ⚠️ | oprim.external.searxng_client (v0.3空) |
| 翻译 | ✅ | — |
| 摘要/周复盘 | ✅ | omodul Bug 1+2 修复后 UI findings 展示 |
| 音频朗读 | 🟡 | oprim.tts_synthesize 导出+providers, ADR-020 |
| 插图生成 | 🟡 | oprim.image_generate 导出+providers, ADR-020 |
| 概念抽取 | ❌ | oprim.concept_extractor, omodul.ConceptExtractorAgent |
| 多模态 | ⚠️ | oprim.image_understand 导出+providers |
| OCR | ❌ | oprim.ocr_detect_text |
| 搜索 | 🟡 | oskill.hybrid_search 扩展 (view_id + citation) |
| 跨层检索 | ❌ | oskill.cross_layer_search 扩展 + hevi 前置 |
| 推荐 | ❌ | oskill.recommend_content 修复, oprim.user_behavior_aggregator |
| 视图过滤 | ❌ | oskill.hybrid_search view_id 扩展 |
| 引用 | ⚠️ | oprim.citation_formatter |
| 概念图谱前端 | 🟡 | oskill.concept_graph_builder (前端可视化另算) |
| MCP 生产 | 🟡 | omodul Bug 1+2 修复, 部署配置 |
| 分享 | 🟡 | 前端 UI 问题, 无 3O 缺失 |
| 公开 substrate | ❌ | oprim.public_link_generator, oprim.access_control_checker |
| 关注作者 | ❌ | oprim.social_subscription_manager, omodul.social.follow_workflow |
| 评论 | ❌ | oprim.comment_store, omodul.social.comment_workflow |
| hevi 发现 | ❌ | oprim.external.hevi_client (v0.3空), ADR-021 |
| Google Drive | ❌ | oprim.storage.gdrive_adapter + changefeed 全套 |
| OneDrive | ❌ | oprim.storage.onedrive_adapter |
| Dropbox | ❌ | oprim.storage.dropbox_adapter |
| 多设备同步 | ❌ | 全套 Phase 2: storage+changefeed+oskill.sync+omodul.bg_sync |
| 离线模式 | ❌ | oprim.offline_queue + 前端 Service Worker |
| WS changefeed | 🟡 | 后端 /ws 路由验证 |
| OAuth 加密 | ❌ | oprim.oauth_token_manager |
| Push Web | ❌ | oprim.push_web (v0.3空) |
| Push Email | ❌ | oprim.push_email (v0.3空) |
| Push APNS/FCM | ❌ | oprim.push_apns + push_fcm (新) |
| 微信支付 | ❌ | oprim.wechat_pay 全套, ADR-026, obase.wechat_pay_gateway |
| Stripe | ❌ | oprim.stripe_payment_intent, ADR-026 |
| 订阅 tier | ❌ | oprim.subscription_tier_check, oskill.subscription_tier_enforcer |
| 配额 | ❌ | oprim.quota_manager |
| 微信小程序 | ❌ | oprim.wechat_miniprogram_auth, ADR-025 |
| 微信公众号 | ❌ | oprim.wechat_official_msg_handler |
| 微信登录 | ❌ | oprim.wechat_login_client, obase.wechat_login_provider |
| hevi 外挂 | ❌ | oprim.external.hevi_client (v0.3空), ADR-021 |
| screenpipe 外挂 | ❌ | oprim.external.screenpipe_reader (v0.3空) |
| whisper ASR | ❌ | oprim.external.whisper_client (激活) |
| F5-TTS | ❌ | oprim.external.tts_client_f5 (新), ADR-020 |
| SD-webui | ❌ | oprim.external.sd_client (v0.3空, ComfyUI) |
| Ollama | ❌ | oprim.llm.llm_call.ollama provider |
| SSRF TOCTOU | TECHNICAL_DEBT | obase.dns_pinned_transport + oprim.url_fetch_ssrf_safe |

---

**End of STRATUM_3O_FULL_COMPLETION_REQUEST_v1.0.md**

*生成: CC Phase 17 技术债 + 真实现状审计 → 3O 反推需求清单, 2026-06-04*
*来源: STRATUM_REALITY_AUDIT_v1.0 + SPEC v0.5/v0.6 + 3O_IMPLEMENTATION_STATUS (65e2658d) + 3O_CATALOG.md*
*R-4 严守: 纯需求列举, 无代码修改, 无跨经理人协调启动*
