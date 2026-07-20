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

import { AII_API_BASE, AII_API_KEY, USE_MOCK } from './env';
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
} from '@/aii/types/api';
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

async function request<T>(path: string, opts: RequestOpts = {}): Promise<ApiResult<T>> {
  const { method = 'GET', body, timeoutMs = 10_000 } = opts;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const url = `${AII_API_BASE}${path}`;
    const headers: Record<string, string> = {};
    if (body) headers['Content-Type'] = 'application/json';
    if (AII_API_KEY) headers['X-API-Key'] = AII_API_KEY;
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
  return request<QueryResponse>('/api/query', { method: 'POST', body: req });
}

export async function ingest(req: IngestRequest): Promise<ApiResult<IngestResponse>> {
  if (USE_MOCK) return mock.mockIngest(req);
  return request<IngestResponse>('/api/ingest', { method: 'POST', body: req });
}

export async function getGraphHealth(): Promise<ApiResult<GraphHealthResponse>> {
  if (USE_MOCK) return mock.mockGraphHealth();
  return request<GraphHealthResponse>('/api/health/graph', { method: 'GET' });
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

// ============================================================
// AII-FRONTEND-DISPLAY-001 — 成果展示 endpoints(§六)
//   后端待实现;Mock 模式走 mock-data。真模式打 GET /api/...
// ============================================================

import type {
  StatsOverviewResponse,
  StatsIngestionResponse,
  KuListRequest,
  KuListResponse,
  KuDetail,
  SubgraphRequest,
  SubgraphResponse,
  GraphSearchRequest,
  GraphSearchResponse,
  KcListItem,
  KcDetail,
  BuListItem,
  BuDetail,
  BuData,
  BookInfo,
  ConceptGraphRequest,
  ConceptGraphResponse,
  ConceptNodeDetail,
  GodNodeRequest,
  GodNodeResponse,
  ThemesResponse,
} from '@/aii/types/api';

function qs(params: Record<string, unknown>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : '';
}

export async function getStatsOverview(): Promise<ApiResult<StatsOverviewResponse>> {
  if (USE_MOCK) return mock.mockStatsOverview();
  return request<StatsOverviewResponse>('/api/stats/overview', { method: 'GET' });
}

export async function getStatsIngestion(): Promise<ApiResult<StatsIngestionResponse>> {
  if (USE_MOCK) return mock.mockStatsIngestion();
  return request<StatsIngestionResponse>('/api/stats/ingestion', { method: 'GET' });
}

export async function getKuList(req: KuListRequest): Promise<ApiResult<KuListResponse>> {
  if (USE_MOCK) return mock.mockKuList(req);
  return request<KuListResponse>(`/api/ku/list${qs({ ...req })}`, { method: 'GET' });
}

export async function getKuDetail(id: string): Promise<ApiResult<KuDetail>> {
  if (USE_MOCK) return mock.mockKuDetail(id);
  return request<KuDetail>(`/api/ku/${encodeURIComponent(id)}`, { method: 'GET' });
}

export async function getSubgraph(req: SubgraphRequest): Promise<ApiResult<SubgraphResponse>> {
  if (USE_MOCK) return mock.mockSubgraph(req);
  return request<SubgraphResponse>(
    `/api/graph/subgraph${qs({ ku_id: req.ku_id, hops: req.hops, limit: req.limit })}`,
    { method: 'GET' }
  );
}

export async function graphSearch(req: GraphSearchRequest): Promise<ApiResult<GraphSearchResponse>> {
  if (USE_MOCK) return mock.mockGraphSearch(req);
  return request<GraphSearchResponse>(`/api/graph/search${qs({ q: req.q, limit: req.limit })}`, { method: 'GET' });
}

// ── B仓知识网络审查 · 视图1:概念判同(AII-BREPO-VIZ-SPEC-001) ──
export async function getConceptGraph(req: ConceptGraphRequest = {}): Promise<ApiResult<ConceptGraphResponse>> {
  if (USE_MOCK) return mock.mockConceptGraph(req);
  return request<ConceptGraphResponse>(
    `/api/graph/concepts${qs({ discipline: req.discipline, limit: req.limit, risk_only: req.risk_only })}`,
    { method: 'GET' }
  );
}

export async function getConceptNode(id: number): Promise<ApiResult<ConceptNodeDetail>> {
  if (USE_MOCK) return mock.mockConceptNode(id);
  return request<ConceptNodeDetail>(`/api/graph/node/${id}`, { method: 'GET' });
}

// ── God Node 检测(AII-KNOWLEDGE-FIRST-SPEC-001 改进一) ──
export async function getGodNodes(req: GodNodeRequest = {}): Promise<ApiResult<GodNodeResponse>> {
  if (USE_MOCK) return mock.mockGodNodes(req);
  return request<GodNodeResponse>(
    `/api/graph/god-nodes${qs({
      min_centrality: req.min_centrality,
      cross_disc_only: req.cross_disc_only,
      limit: req.limit,
    })}`,
    { method: 'GET' }
  );
}

// ── 已固化主题染色(AII-KNOWLEDGE-FIRST-SPEC-001 改进二) ──
export async function getThemes(): Promise<ApiResult<ThemesResponse>> {
  if (USE_MOCK) return mock.mockThemes();
  return request<ThemesResponse>('/api/graph/themes', { method: 'GET' });
}

export async function getKcList(
  arg: { view: 'chapter' | 'spectral'; substrate: string } = { view: 'chapter', substrate: 'microecon_en_full_v2' }
): Promise<ApiResult<KcListItem[]>> {
  if (USE_MOCK) return mock.mockKcList();
  return request<KcListItem[]>(`/api/kc/list?view=${arg.view}&substrate=${encodeURIComponent(arg.substrate)}`, { method: 'GET' });
}
export async function getBooks(): Promise<ApiResult<{ items: BookInfo[] }>> {
  return request<{ items: BookInfo[] }>('/api/books', { method: 'GET' });
}
export async function getKcDetail(id: string): Promise<ApiResult<KcDetail>> {
  if (USE_MOCK) return mock.mockKcDetail(id);
  return request<KcDetail>(`/api/kc/${encodeURIComponent(id)}`, { method: 'GET' });
}
export async function getBookBu(substrate: string): Promise<ApiResult<BuData>> {
  return request<BuData>(`/api/book/${encodeURIComponent(substrate)}/bu`, { method: 'GET' });
}

export async function getBuList(): Promise<ApiResult<BuListItem[]>> {
  if (USE_MOCK) return mock.mockBuList();
  return request<BuListItem[]>('/api/bu/list', { method: 'GET' });
}
export async function getBuDetail(id: string): Promise<ApiResult<BuDetail>> {
  if (USE_MOCK) return mock.mockBuDetail(id);
  return request<BuDetail>(`/api/bu/${encodeURIComponent(id)}`, { method: 'GET' });
}
