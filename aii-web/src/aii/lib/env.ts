/**
 * 环境配置 — 集中读取 NEXT_PUBLIC_* env vars
 *
 * 注意:Next.js 只会把 NEXT_PUBLIC_ 前缀的 env 注入到客户端 bundle。
 */

/** AII 后端 base URL(不含尾斜杠) */
export const AII_API_BASE: string =
  process.env.NEXT_PUBLIC_AII_API_BASE ?? '/api/aii';

/** Mock 模式:true 时所有 API 调用走 mock-data,不打后端 */
export const USE_MOCK: boolean =
  (process.env.NEXT_PUBLIC_USE_MOCK ?? 'false').toLowerCase() === 'true';

/** AII 后端 API Key */
export const AII_API_KEY: string = process.env.NEXT_PUBLIC_AII_API_KEY ?? '';

/** 用于在 UI 上显示当前模式(供 Topbar 角标使用) */
export const ENV_BADGE: string = USE_MOCK ? 'MOCK' : AII_API_BASE.replace(/^https?:\/\//, '');
