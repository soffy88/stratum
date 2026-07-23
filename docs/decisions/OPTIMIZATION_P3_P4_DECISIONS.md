# P3 前端 / P4 部署统一 — 决策记录（2026-07-01）

审查后按三原则（长期主义 / 质量为王 / 功能至上）对 item15(P3架构) 与 item16(P4部署) 的定案。
这两项涉及**不可逆的 live 服务退役 / 前端重构**，故本文件给出**决策 + 分阶段可回滚方案**，
而非盲目执行切换（质量为王：不打破当前已 200 的站点）。

---

## item15 — P3 前端架构决策

### 裸真相（实查 2026-07-01）
- 部署到 `aii.kanpan.co` 的 `aii-web` 容器，镜像 `deploy/Dockerfile.aii-web` 实际烤的是
  **`stratum-web/.next/standalone`（基座）**，靠 Next 服务端 `rewrites` 把 `/api/v1/*`→stratum-sl、
  `/api/*`→stratum-api。实证：`https://aii.kanpan.co/api/v1/health` → 200。
- `stratum-web` 基座里 `@helios/blocks` 是**桩**（next.config resolveAlias → `src/stubs`）。
- `aii/aii-web/`（14 页、真 `@helios` tarball、`env.ts` 读 `NEXT_PUBLIC_AII_API_BASE`）是**另一套源**，
  当前**未部署**（部署的是 stratum-web 基座）。
- 因此"P3=把 AII 页移植进 stratum-web 基座"在**部署层已事实发生**（跑的是基座），
  但 stratum-web 基座里并没有真正接 `@helios` 设计系统，AII 的 14 页 UI 也未并入基座。

### 决策
**以 stratum-web 为唯一前端基座（承认现状），aii/aii-web 降级为"AII 专属页的源仓"，逐页并入基座。**
理由：部署已在跑基座且 200 可用；维护两套 Next app 违背长期主义；基座 30 页 > aii-web 14 页。

### 落地清单（后续执行，非本次）
1. **修 `NEXT_PUBLIC_AII_API_BASE` 断链**（唯一功能性缺口）：`NEXT_PUBLIC_*` 在 `next build` 时烤死，
   须在**构建期**注入。做法：在前端 build 前 `export NEXT_PUBLIC_AII_API_BASE=https://aii-api.kanpan.co`
   （该域名本次已接通，实证 200），再 `pnpm build` → 重烤 `aii-web:latest` → recreate。
   `deploy/Dockerfile.aii-web` 因只 COPY 预构建 standalone，须在 build 脚本层注入而非 Dockerfile ARG。
   ⚠️ 盲目重构建有打破当前 200 站点风险，须在 staging 验证浏览器端 API 调用成功后再切。
2. 若要 AII 设计系统：把 stratum-web 的 `@helios/blocks` 桩换成真 tarball（`aii/aii-web/vendor` 里有 2.8.0）。
3. 逐页把 aii-web 的 14 页（chat/query/graph/books/clusters/knowledge/dashboard/governance/
   evolution/ingest/diagnose/book/health）并入 stratum-web 的 app 路由，接真实后端替换 mock。
4. 全部并入并验证后，退役 `aii/aii-web` 源与其独立部署路径。

---

## item16 — P4 部署统一决策

### 裸真相
- `deploy/docker-compose.yml` 仍是 stratum-sl(9304) + stratum-api(9309→9302) + stratum-web + aii-web 并存。
- `aii` 后端是**宿主裸 uvicorn 进程**（:8101，无 compose、无 restart 策略，reboot 即死）。
- `aii-postgres`(5435) / `aii-refined-postgres`(5436) / `aii-cloudflared` 各自独立 compose（游离）。
- `~/shared/{stratum-to-aii, aii-to-stratum, textbook-to-aii}` 三个文件中转卷仍挂在 stratum-sl（未退役）。

### 决策
**分两阶段，先"收编纳管"（低风险、可回滚），再"退役旧件"（高风险，需逐一验证）。本次只做阶段一的准备与文档，不执行阶段二的 live 退役。**
理由：stratum-sl/stratum-api 正在 live 服务，盲目退役不可逆（质量为王）；而把游离服务纳入单一 compose 是纯增量、可回滚。

### 阶段一（可安全执行，建议下一步做）
1. 把 `aii` 后端做成 compose service（host venv 不可容器化=需 BGE-M3，故用 `network_mode: host` +
   在 compose 里以 `command` 拉起宿主 venv 不可行→改为**给它写 systemd/supervisor 单元或纳入 compose 用宿主镜像**；
   最小可行：先写一个 `aii/aii-backend.service`(systemd user unit) 让它 reboot 自启，解决"reboot即死")。
2. 把 `docker-compose.aii-pg.yml` / `aii-refined-pg.yml` / `aii-cloudflared.yml` 用 compose `include:`
   合进单一入口，或写一个 `deploy/compose.all.yml` 顶层 include，统一 `up`（各自 project 名保留防误删）。
3. aii-cloudflared 的 `--env-file` 依赖已在其 compose 注释说明（本次 item4 修复）。

### 阶段二（高风险，需逐一 REDLINE 验证后再做）
4. 确认 stratum-web 基座 + rewrites 完全覆盖 stratum-api 的 28 端点后，退役 stratum-api（先 stop 观察，再删）。
5. 确认无代码走 `~/shared` 文件中转（改进程内/HTTP 调用）后，退役三个 shared 卷。
6. 全绿后收敛为单一 `deploy/docker-compose.yml`。

### 回滚
任何阶段：`docker compose up -d` 旧定义即回滚；stratum-sl/api 的 DuckDB 留底（meta.duckdb.bak）仍在。
