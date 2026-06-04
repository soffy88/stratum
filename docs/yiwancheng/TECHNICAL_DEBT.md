# Stratum Technical Debt

## High Priority
- [ ] hybrid_search path migration left `oskill/knowledge/` placeholder, remove in Phase 11D.
- [ ] oprim stubs for tts, sd, whisper need real implementations or standard mock interface.
- [ ] omodul Wissen knowledge submodules are still in historical path, move to flat omodul in Phase 11D.

## Medium Priority
- [ ] task_dao and template_dao are currently minimal, need full DuckDB/SQLAlchemy implementation.
- [ ] weekly_review_workflow uses very basic prompt, need to enrich with detailed activity context.

### Phase 14 Wave 2 — Corpus Isolation
- [ ] oskill.hybrid_search currently accepts corpus_id but does not filter at the BM25/Vector index level. Stratum service layer implements a post-filter which works but is less efficient for large corpora. Needs physical partition or index-level filtering in oskill/oprim v1.2+.

### Phase 14 Part 2 — Front-end Sign-off Audit (2026-05-26)

引用：`docs/yiwancheng/PHASE_14_PART2_SIGNOFF_REPORT.md`

#### High
- [ ] **@helios/blocks 9 个 Block 全部未集成**：Wave 7 + Wave 8 共 9 个 Block（OSemanticSearch / OAIQAPanel / OAISummaryCard / OCitationCard / OScheduledJobsManager / ODocumentTree / ODocumentReader / OAnnotationLayer / OBacklinkPanel）在 stratum-web/src/ 中 0 个 import，0 个使用。package.json 中无 `@helios/blocks` 依赖。当前为手写朴素 Tailwind UI 替代。修复路径：Part 3 Wave 10A。
- [ ] **share/[token] 端口硬编码生产 bug**：`stratum-web/src/app/share/[token]/page.tsx` 第 20 行 fetch `http://localhost:9305/share/${token}`，但后端实际端口 9302（deploy + 设计书均锁定）。RSC 服务端 fetch 不走 next.config rewrite。后果：生产环境 share 公开页直接 500。修复路径：Part 3 Wave 10B，改为 `process.env.STRATUM_API_URL ?? "http://localhost:9302"` 或类似。
- [ ] **e2e 测试 0 page.goto**：4 个 e2e spec 文件（auth / search-ai / wave8 / share）共 25 个测试，全部使用 `request.post/get/delete` 直打后端 9305，0 个走 `page.goto` 验证前端 UI。等同于无前端 e2e 覆盖。修复路径：Part 3 Wave 10C，废弃当前 e2e 风格（迁至 `tests/contract/`），新增 page.goto 风格 e2e ≥ 15 条。

#### Medium
- [ ] **`/profile/[username]/page.tsx` 缺失**：Wave 9 commit description 声明实现但代码不存在。`stratum-web/src/app/` 下无 profile 目录。修复路径：Part 3 Wave 10B。
- [ ] **`/settings` 缺 sessions list / revoke**：当前仅有 profile 只读 + theme 切换两个 tab。Part 2 §5 暗示应有 sessions 管理。修复路径：Part 3 Wave 10B + 后端新增 endpoint。
- [ ] **后端 `GET /api/users/me/sessions` + `DELETE /api/users/me/sessions/:id` 缺失**：sessions 管理无后端支持。修复路径：Part 3 Wave 10B。
- [ ] **后端 `GET /api/users/by-username/:username` 缺失**（条件性）：若 `/profile/[username]/page.tsx` 按 username 路由需要查询用户公开资料，则需此 endpoint；如 share endpoint 已返回 shared_by_username 足够，则不需要。Part 3 启动时需复核。

#### Low / 保留为后续
- [ ] **`POST /api/agents/:name/run` 真触发 omodul Agent**：当前为 stub 返回 `{status: "pending"}`。CC 在 Part 1 sign-off 声明 R-4 严格（不动 platform/omodul），合理妥协。保留至 Phase 11D omodul 扁平化时一起改。
- [ ] **`(auth)/reset-password/page.tsx` 缺失**：Part 2 §2.1 路由树要求，Wave 6 漏项。优先级取决于是否启用密码重置流程。修复路径：Part 3 Wave 10B 或独立小补丁。
- [ ] **Part 2 §2.1 扩展依赖未拉入**：`@tanstack/react-table` / `@tanstack/react-virtual` / `motion` / `shiki` / `cmdk` / `react-resizable-panels` 等。按 Wave 10A Block 实际需要拉入即可。
