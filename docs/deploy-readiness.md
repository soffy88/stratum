# Phase 14 公网发布 Readiness Checklist

**状态: 🔴 未满足条件 — 等待 Wiki 显式 sign-off**

## 条件清单（全部 ✅ 才可执行 `docker compose --profile public`）

### Wiki 签核（必须）
- [ ] Wiki (soffy88) 明确在 Slack/commit/issue 里说 "可以上线"
- [ ] 隐私政策法律文案已由法律顾问审核并确认
- [ ] 服务条款法律文案已由法律顾问审核并确认

### 外部服务凭证（必须）
- [ ] `SENTRY_DSN` 已获取并填入 `.env.prod`
- [ ] `NEXT_PUBLIC_SENTRY_DSN` 已填入 Next.js `.env.production`
- [ ] Cloudflare Tunnel token 已获取（用于穿透内网）
- [ ] `ADMIN_SECRET` 已生成（>=32 字符随机字符串）并安全存储

### 合规检查（必须）
- [ ] `privacy/page.tsx` 占位符文案已替换为正式法律文本
- [ ] `terms/page.tsx` 占位符文案已替换为正式法律文本
- [ ] robots.txt 已配置（如需屏蔽某些路径）
- [ ] 无 PII 泄露确认：`GET /api/users/by-username/:username` 不返回 email/user_id
- [ ] 无 PII 泄露确认：`GET /share/:token` 不返回 user_id/corpus_id

### 技术门控（必须）
- [ ] `pytest`: 212/212 pass（包括 oskill 相关测试，即 Phase 11B 完成）
  - 当前状态：210/212（2 个 oskill ModuleNotFoundError 预存失败）
- [ ] `vitest`: 90/90 pass ✅
- [ ] `playwright e2e`: 40/40 pass ✅
- [ ] `pnpm type-check`: 0 errors ✅
- [ ] `next build`: 生产构建无错误（尚未验证）
- [ ] Storybook build: ✅

### 基础设施（必须）
- [ ] Cloudflare Tunnel 配置文件已准备
- [ ] `docker compose --profile public` 文件已审查
- [ ] 反向代理/TLS 证书已配置
- [ ] 数据库备份策略已确认

## TECHNICAL_DEBT 汇总（发布前需处理或明确推迟）

| 项目 | 描述 | 优先级 |
|------|------|--------|
| oskill ModuleNotFoundError | Phase 11B 未完成，search/cross-corpus tests 失败 | 高 |
| `datetime.utcnow()` deprecation | 多处 DAO 使用已废弃 API，Python 3.14 警告 | 中 |
| @storybook/nextjs 不兼容 Next.js 16 | 使用 react-vite 替代，router mocks 缺失 | 低 |
| privacy/terms 占位符法律文本 | 需法律顾问确认 | 高（发布前必须） |
| Admin RBAC 缺失 | 仅静态 ADMIN_SECRET，无 role 系统 | 中 |
| @sentry/nextjs 版本 | 8.x 不是最新，需升级至 10.x | 低 |

---

**不执行 `docker compose --profile public` 直到以上所有 ✅ 完成。**
