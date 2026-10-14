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
  // 60s: ku/list 在 stratum-sl 忙(folder_watcher/LLM)时可能 >10s，过短会 abort 显示页面错误
  const { method = 'GET', body, timeoutMs = 60_000 } = opts;
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
  CommunitiesRequest,
  CommunitiesResponse,
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

// ── Leiden 社区预览(改进二 · resolution 调参用,现算不落库) ──
export async function getCommunities(req: CommunitiesRequest = {}): Promise<ApiResult<CommunitiesResponse>> {
  if (USE_MOCK) return mock.mockCommunities(req);
  return request<CommunitiesResponse>(
    `/api/graph/communities${qs({ resolution: req.resolution, min_size: req.min_size })}`,
    { method: 'GET' }
  );
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

// ── BU2 Chapter Detail ──
export interface ChapterDetail {
  chapter_id: string;
  title: string;
  role: string;
  summary: string;
  concepts: Array<{ ku_id: string; label: string; grade: string; definition: string }>;
  claims: Array<{ id: string; text: string; grade: string; evidence_ids: string[] }>;
  evidence: Array<{ id: string; quote: string; grade: string; locator: string }>;
  mechanisms: Array<{ id: string; description: string; grade: string }>;
  questions: string[];
  conclusions: string[];
  quality_score: number;
  provenance: Record<string, string[]>;
  created_at: string;
}

export async function getChapterDetail(runId: string, chapterId: string): Promise<ApiResult<ChapterDetail>> {
  return request<ChapterDetail>(`/api/v1/bu/${encodeURIComponent(runId)}/chapters/${encodeURIComponent(chapterId)}`, { method: 'GET' });
}

// ── BU2 Synthesis ──
// The stored synthesis row is the whole artefact (~1.7 MB for an 18-chapter
// textbook), so the endpoint now returns a bounded summary by default and the
// item lists are paged. `view=full` still returns the raw row for callers that
// want it all.
export type SynthesisView = 'summary' | 'concepts' | 'claims' | 'full';

export interface SynthesisConcept {
  concept_id: string;
  label: string;
  role: string;
  final_role?: string | null;
  confidence?: number | null;
  definition?: string;
  chapter_refs: string[];
  prerequisites?: string[];
  related_concepts?: string[];
}

export interface SynthesisClaim {
  claim_id: string;
  claim: string;
  is_supported: boolean | null;
  provenance?: string | null;
  chapter_ids: string[];
  evidence_ids: string[];
  evidence_strengths?: Record<string, string>;
}

export interface BuSynthesis {
  run_id: string;
  book_id: string;
  view: SynthesisView;
  available_views: SynthesisView[];
  /** Bounded: the core thesis statement plus per-section counts. */
  thesis: {
    core_thesis: string;
    core_thesis_provenance?: string | null;
    counts: Record<string, number>;
  };
  problem_definition?: string;
  counts?: {
    concepts: number;
    claims: number;
    mechanisms: number;
    arithmetic_arguments: Record<string, number>;
  };
  /** The evidence-map rollup; deliberately not named `evidence_map`. */
  claims_summary?: Record<string, unknown>;
  chapters?: { chapter_count: number; assignments: Array<Record<string, unknown>> };
  concept_roles?: Record<string, number>;
  unresolved_questions?: { count: number; items: string[] };
  limitations?: { count: number; items: string[] };
  author_model?: Record<string, unknown>;
  contradictions?: Record<string, unknown>;
  /** Core concepts in full: the few a page needs before a second request. */
  core_concepts?: SynthesisConcept[];
  /** Present on the concepts/claims views. */
  concepts?: SynthesisConcept[];
  claims?: SynthesisClaim[];
  total?: number;
  offset?: number;
  limit?: number;
  has_more?: boolean;
}

export interface BuSynthesisPage {
  view?: SynthesisView;
  limit?: number;
  offset?: number;
  chapter?: string;
}

/** The bounded synthesis summary: a few KB, not the ~1.7 MB whole row. */
export async function getBuSynthesis(runId: string): Promise<ApiResult<BuSynthesis>> {
  return request<BuSynthesis>(`/api/v1/bu/${encodeURIComponent(runId)}/synthesis`, { method: 'GET' });
}

/** One page of the synthesis's concepts or claims, optionally per chapter. */
export async function getBuSynthesisPage(
  runId: string,
  page: BuSynthesisPage = {}
): Promise<ApiResult<BuSynthesis>> {
  return request<BuSynthesis>(
    `/api/v1/bu/${encodeURIComponent(runId)}/synthesis${qs({ ...page })}`,
    { method: 'GET' }
  );
}

// ── Cross-Book (P14) ──
export interface CrossBookCollection {
  collection_id: string;
  name: string;
  description: string;
  book_ids: string[];
  created_at: string;
}

export interface CrossBookOverview {
  collection_id: string;
  name: string;
  books: Array<{ book_id: string; title: string }>;
  concept_relations: number;
  thesis_relations: number;
  argument_relations: number;
  mechanism_relations: number;
  evidence_relations: number;
  contradictions: number;
  knowledge_gaps: number;
}

export interface ConceptRelationItem {
  relation_id: string;
  source_book_id: string;
  target_book_id: string;
  source_concept_id: string;
  target_concept_id: string;
  relation: string;
  confidence: number;
  evidence: string[];
}

export interface ThesisRelationItem {
  relation_id: string;
  source_book_id: string;
  target_book_id: string;
  source_thesis: string;
  target_thesis: string;
  relation: string;
  confidence: number;
  evidence: string[];
}

export interface ArgumentRelationItem {
  relation_id: string;
  source_book_id: string;
  target_book_id: string;
  source_argument: string;
  target_argument: string;
  relation: string;
  confidence: number;
  evidence: string[];
}

export interface ContradictionItem {
  contradiction_id: string;
  book_a_id: string;
  book_b_id: string;
  type: string;
  element_a: string;
  element_b: string;
  description: string;
  confidence: number;
  evidence: string[];
}

export interface KnowledgeGapItem {
  gap_id: string;
  type: string;
  description: string;
  affected_books: string[];
  related_concepts: string[];
  confidence: number;
}

export interface PairwiseComparison {
  book_a_id: string;
  book_b_id: string;
  concept_relations: ConceptRelationItem[];
  thesis_relations: ThesisRelationItem[];
  argument_relations: ArgumentRelationItem[];
  contradictions: ContradictionItem[];
}

export interface ExpressionResponse {
  collection_id: string;
  collection_name: string;
  book_count: number;
  concept_summary: string;
  thesis_summary: string;
  argument_summary: string;
  contradiction_summary: string;
  gap_summary: string;
  synthesis: string;
  pairwise_comparisons: string;
  quality: string;
}

export interface CrossBookQueryRequest {
  query_type: string;
  filter?: Record<string, unknown>;
}

export interface CrossBookQueryResponse {
  items: unknown[];
  total: number;
  query: string;
  traceability: Record<string, string[]>;
}

export async function getCrossBookCollections(): Promise<ApiResult<CrossBookCollection[]>> {
  return request<CrossBookCollection[]>('/api/v1/cross-books', { method: 'GET' });
}

export async function createCrossBookCollection(body: { name: string; description: string; book_ids: string[] }): Promise<ApiResult<CrossBookCollection>> {
  return request<CrossBookCollection>('/api/v1/cross-books', { method: 'POST', body });
}

export async function getCrossBookOverview(collectionId: string): Promise<ApiResult<CrossBookOverview>> {
  return request<CrossBookOverview>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}`, { method: 'GET' });
}

export async function runP14(collectionId: string): Promise<ApiResult<{ status: string; understanding_id?: string; stats?: any; failures?: string[] }>> {
  return request(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/run`, { method: 'POST' });
}

export async function getConceptRelations(collectionId: string, relation?: string): Promise<ApiResult<ConceptRelationItem[]>> {
  return request<ConceptRelationItem[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/concepts${relation ? `?relation=${relation}` : ''}`, { method: 'GET' });
}

export async function getThesisRelations(collectionId: string, relation?: string): Promise<ApiResult<ThesisRelationItem[]>> {
  return request<ThesisRelationItem[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/theses${relation ? `?relation=${relation}` : ''}`, { method: 'GET' });
}

export async function getArgumentRelations(collectionId: string, relation?: string): Promise<ApiResult<ArgumentRelationItem[]>> {
  return request<ArgumentRelationItem[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/arguments${relation ? `?relation=${relation}` : ''}`, { method: 'GET' });
}

export async function getContradictions(collectionId: string, type?: string): Promise<ApiResult<ContradictionItem[]>> {
  return request<ContradictionItem[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/contradictions${type ? `?type=${type}` : ''}`, { method: 'GET' });
}

export async function getKnowledgeGaps(collectionId: string, type?: string): Promise<ApiResult<KnowledgeGapItem[]>> {
  return request<KnowledgeGapItem[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/gaps${type ? `?type=${type}` : ''}`, { method: 'GET' });
}

export async function getCrossBookSynthesis(collectionId: string): Promise<ApiResult<any>> {
  return request(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/synthesis`, { method: 'GET' });
}

export async function getCrossBookExpression(collectionId: string): Promise<ApiResult<ExpressionResponse>> {
  return request<ExpressionResponse>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/expression`, { method: 'GET' });
}

export async function getPairwiseComparisons(collectionId: string): Promise<ApiResult<PairwiseComparison[]>> {
  return request<PairwiseComparison[]>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/pairwise`, { method: 'GET' });
}

export async function queryCrossBook(collectionId: string, body: CrossBookQueryRequest): Promise<ApiResult<CrossBookQueryResponse>> {
  return request<CrossBookQueryResponse>(`/api/v1/cross-books/${encodeURIComponent(collectionId)}/query`, { method: 'POST', body });
}
