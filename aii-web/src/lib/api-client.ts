/**
 * AII API client — 统一处理响应包络 + degraded 检测。
 *
 * 红线 #6 实现:
 *   warning === "degraded_no_provider" 时,result.degraded = true
 *   Page 必须基于 result.degraded 渲染醒目降级提示(<DegradedBanner /> 已经默认在 layout 里 watch hook 结果)
 *
 * 设计原则:
 *   - 永不抛网络错误(都包成 ApiResult{ok:false, error:...}),Page 不需要 try-catch
 *   - Mock 模式下 fetch 走 mock-data 模块,签名不变
 *   - 默认 10s timeout(AbortController)
 */

import { AII_API_BASE, USE_MOCK } from './env';
import type {
  ApiEnvelope,
  ApiResult,
  QueryRequest,
  QueryResponse,
  IngestRequest,
  IngestResponse,
  GraphHealthResponse,
  DiagnoseRequest,
  DiagnoseResponse,
  EvolutionResponse,
  GovernanceActionRequest,
  GovernanceActionResponse,
  ChatRequest,
  ChatResponse,
} from '@/types/api';
import * as mock from './mock-data';

// ============================================================
// 底层 fetch 包装
// ============================================================

interface RequestOpts {
  method?: 'GET' | 'POST';
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
}

const _API_KEY = process.env.NEXT_PUBLIC_AII_API_KEY ?? '';

async function request<T>(path: string, opts: RequestOpts = {}): Promise<ApiResult<T>> {
  const { method = 'GET', body, timeoutMs = 30_000 } = opts;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const url = `${AII_API_BASE}${path}`;
    const headers: Record<string, string> = {};
    if (body) headers['Content-Type'] = 'application/json';
    if (_API_KEY) headers['X-API-Key'] = _API_KEY;
    const init: RequestInit = {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: opts.signal ?? ctrl.signal,
    };
    const res = await fetch(url, init);
    if (!res.ok) {
      return {
        ok: false,
        error: `HTTP ${res.status}: ${res.statusText}`,
        degraded: false,
      };
    }
    const env = (await res.json()) as ApiEnvelope<T>;
    if (env.status === 'error') {
      return { ok: false, error: env.error, degraded: false };
    }
    const warning = env.warning;
    return {
      ok: true,
      data: env.data,
      warning,
      degraded: warning === 'degraded_no_provider',
    };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg, degraded: false };
  } finally {
    clearTimeout(timer);
  }
}

// ============================================================
// 6 个高阶 API(REQ-001 §一)
//   Mock 模式下走 mock-data;真模式打后端
// ============================================================

export async function query(req: QueryRequest): Promise<ApiResult<QueryResponse>> {
  if (USE_MOCK) return mock.mockQuery(req);
  return request<QueryResponse>('/query', { method: 'POST', body: req });
}

export async function ingest(req: IngestRequest): Promise<ApiResult<IngestResponse>> {
  if (USE_MOCK) return mock.mockIngest(req);
  return request<IngestResponse>('/ingest', { method: 'POST', body: req });
}

export async function getGraphHealth(): Promise<ApiResult<GraphHealthResponse>> {
  if (USE_MOCK) return mock.mockGraphHealth();
  return request<GraphHealthResponse>('/graph/health', { method: 'GET' });
}

export async function diagnose(req: DiagnoseRequest): Promise<ApiResult<DiagnoseResponse>> {
  if (USE_MOCK) return mock.mockDiagnose(req);
  return request<DiagnoseResponse>('/diagnose', { method: 'POST', body: req });
}

export async function getEvolution(): Promise<ApiResult<EvolutionResponse>> {
  if (USE_MOCK) return mock.mockEvolution();
  return request<EvolutionResponse>('/evolution/propose', { method: 'POST', body: {} });
}

export async function governanceAction(
  req: GovernanceActionRequest
): Promise<ApiResult<GovernanceActionResponse>> {
  if (USE_MOCK) return mock.mockGovernanceAction(req);
  return request<GovernanceActionResponse>('/governance/action', { method: 'POST', body: req });
}

// ============================================================
// REQ-003 chat — 注意路径 `/api/chat`(跟 REQ-001 的 6 endpoints 无 /api/ 前缀)
// 如果 6 endpoints 也应该是 /api/ 前缀,告诉我我顺手把上面的都改了
// ============================================================

export async function chat(req: ChatRequest): Promise<ApiResult<ChatResponse>> {
  if (USE_MOCK) return mock.mockChat(req);
  return request<ChatResponse>('/api/chat', { method: 'POST', body: req });
}
