# Phase 14 公网发布 Readiness Checklist

**状态: 🟡 半就绪 — 代码侧已达标；剩余为外部凭证 / 人工签核项**

## 条件清单（全部 ✅ 才可执行 `docker compose --profile public`）

### Wiki 签核（必须，人工）
- [ ] Wiki (soffy88) 明确在 Slack/commit/issue 里说 "可以上线"
- [ ] 隐私政策法律文案已由法律顾问审核并确认
- [ ] 服务条款法律文案已由法律顾问审核并确认

### 外部服务凭证（必须，人工）
- [ ] `SENTRY_DSN` 已获取并填入 `.env.prod` / `NEXT_PUBLIC_SENTRY_DSN`
- [ ] `DASHSCOPE_API_KEY` 有效值（当前 `.env` 为 REPLACE_ME 占位符；NVIDIA NIM 键已失效 401）
- [ ] Cloudflare Tunnel token 已获取
- [ ] `ADMIN_SECRET` 已生成（>=32 字符随机字符串）并安全存储

### 公网入口
- [ ] **aiinote.com DNS**：Cloudflare 手动加 CNAME（@ + www → `3ea896f2-5be2-448e-ad27-338cdf3da4b1.cfargotunnel.com`）
     或提供 Zone.DNS 权限 token 后跑 `python3 scripts/setup_aiinote_dns.py`
- [ ] `https://aii.kanpan.co` 已作为临时入口公网验证 200（隧道 ingress + Caddy 链路已通）

### 合规检查（代码侧已满足，剩余人工）
- [ ] privacy/terms 占位符 → 正式法律文本（人工）
- [ ] robots.txt 已配置
- [x] 无 PII：`GET /api/users/by-username/:username` / `GET /share/:token` 已确认不泄 email/user_id

### 技术门控（当前实证，2026-08-02）
- [x] `pytest`: **367 passed / 17 skipped**（17 skipped = 平台包 oskill/omodul 依赖，镜像内有）
- [x] 主链路 E2E：`scripts/e2e_mvp_chain.py` 线上全 PASS
     注册→剪藏/PDF→翻译→问答(sources)→概念追加→检索→导出(vault)→vault同步→Lint→日报→真删→收敛
- [x] docling 已进 stratum-sl 镜像（v2.117.0，PDF 链实测）
- [x] 入库管线三处根因已修：ntfs3 索引→ext4（STRATUM_HOME）、changefeed seq setval、
     embedding provider aii_remote（本地 BGE-M3 172.19.0.1:8102）
- [x] 本地 LLM 兜底：agents 默认 `ollama`（qwen3-8b，think=False 防空响应）
- [x] 音视频转写链：yt-dlp→faster-whisper→结构化→入库（sing-box 代理）
- [x] CI：`.github/workflows/ci.yml`（backend pytest + frontend vitest/build）
- [~] 前端 `next build` 通过（`ignoreBuildErrors: true` 容忍 95 个 @helios/blocks tsc 错，预存）
- [ ] Cloudflare Tunnel 配置 + TLS 证书终审（隧道已配好 ingress，发布前复核一次）

### 基础设施（必须）
- [ ] Cloudflare Tunnel 配置文件已审查
- [ ] `docker compose --profile public` 文件已审查
- [ ] 数据库备份策略已确认（PG aii-postgres 需纳入备份计划）

## TECHNICAL_DEBT（发布后清单）

| 项目 | 描述 | 优先级 |
|------|------|--------|
| /api/v1/retrieve 旧 pgvector 路径 | Ollama 网关死 → 0 命中；/api/v1/search（lance+tantivy+BGE-M3）正常；retrieve 需把 get_embedding 切到 172.19.0.1:8102 | 高 |
| 平台包不可复现 | omodul/oprim/oskill 不随仓发布，17 测试镜像外 skip | 高 |
| @helios/blocks tsc 错 | 私有设计系统未开源，95 错被 ignoreBuildErrors 掩盖 | 中 |
| 无 E2EE / PgBouncer | psycopg2 直连池，无连接治理 | 中 |
| SEARXNG_URL 占位符 | 问答 web 检索未接线 | 中 |
| 锚点前端闭环 | sources[] 已有锚点数据，前端跳段未做 | 中 |

---

**最后更新: 2026-08-02 — 代码侧 E2E 全链绿灯；剩余 = DNS/凭证/法律文本（人工）。**
