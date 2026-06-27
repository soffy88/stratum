/**
 * AII 后端 6 endpoints 响应类型(契约见 AII-FRONTEND-REQ-001 §一)。
 *
 * 统一响应包络:
 *   { status: "ok" | "error", data?: T, error?: string, warning?: string }
 *
 * 关键 warning:
 *   - "degraded_no_provider":LLM provider 不可用,后端给出降级结果
 *     红线:UI 不能静默展示,必须醒目提示
 */

import type { EpistemicGrade, EpistemicDefeater } from '@helios/blocks';

// ============================================================
// 通用响应包络
// ============================================================

export type ApiEnvelope<T> =
  | {
      status: 'ok';
      data: T;
      warning?: string;
    }
  | {
      status: 'error';
      error: string;
    };

/** 客户端化后的统一结果(apiClient 包后给页面消费) */
export interface ApiResult<T> {
  ok: boolean;
  data?: T;
  error?: string;
  /** warning === "degraded_no_provider" 时为 true */
  degraded: boolean;
  /** 原始 warning(如有) */
  warning?: string;
}

// ============================================================
// Endpoint 1: POST /query — 查询接口
// ============================================================

export interface QueryRequest {
  query: string;
  k?: number;
  filters?: Record<string, unknown>;
}

export interface QueryResultItem {
  id: string;
  title?: string;
  body: string;
  grade: EpistemicGrade;
  defeaters: EpistemicDefeater[];
  source?: string;
  score?: number;
  metadata?: Array<{ label: string; value: string }>;
}

export interface QueryResponse {
  items: QueryResultItem[];
  total: number;
  query_id?: string;
}

// ============================================================
// Endpoint 2: POST /ingest — 摄入接口
// ============================================================

export interface IngestRequest {
  source: string;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface IngestResponse {
  ingested_count: number;
  fragment_ids: string[];
  rejected?: Array<{ reason: string; preview?: string }>;
}

// ============================================================
// Endpoint 3: GET /graph/health — 图健康度
// ============================================================

export interface GraphHealthResponse {
  total_nodes: number;
  total_edges: number;
  grade_distribution: Partial<Record<EpistemicGrade, number>>;
  defeater_count: number;
  last_audit_at?: string;
  health_score?: number; // 0-1
}

// ============================================================
// Endpoint 4: POST /diagnose — 诊断
// ============================================================

export interface DiagnoseRequest {
  fragment_id?: string;
  scope?: 'fragment' | 'cluster' | 'global';
}

export interface DiagnoseAxis {
  axis: string;
  value: number;
}

export interface DiagnoseResponse {
  axes: DiagnoseAxis[];
  series: Array<{ name: string; values: number[] }>;
  notes?: string[];
}

// ============================================================
// Endpoint 5: POST /evolution/propose — 进化提案
// ============================================================

export interface EvolutionEvent {
  id: string;
  time: string; // ISO
  kind: 'proposed' | 'accepted' | 'rejected' | 'rolled_back';
  title: string;
  body?: string;
  actor?: string;
  status?: 'success' | 'failure' | 'pending';
}

export interface EvolutionResponse {
  history: EvolutionEvent[];
  pending: EvolutionEvent[];
}

// ============================================================
// Endpoint 6: POST /governance/action — 治理操作
// ============================================================

export interface GovernanceActionRequest {
  action: 'quarantine' | 'promote' | 'rollback' | 'delete';
  target_id: string;
  reason?: string;
}

export interface GovernanceActionResponse {
  applied: boolean;
  audit_log_id: string;
}

// ============================================================
// Endpoint 7: POST /api/chat — 对话综合(REQ-003)
//
// 后端 SynthesisEngine 输出。AII 灵魂:每个回答必显示可信度 + 依据 + mode。
// ============================================================

/** 回答模式 — 视觉必须区分 */
export type ChatMode =
  /** 基于确证知识库,有 citations,完整可信度 */
  | 'grounded'
  /** 闲聊,无知识库背书 — UI 必须标注 */
  | 'chitchat'
  /** 知识库未覆盖此问题 — UI 必须醒目 */
  | 'no_knowledge';

export interface ChatCitation {
  ku_id: string;
  grade: EpistemicGrade;
  snippet: string;
}

export interface ChatRequest {
  /** 用户的提问 */
  message: string;
  /** 可选:期望返回的 citations 数量 */
  k?: number;
}

export interface ChatResponse {
  mode: ChatMode;
  answer: string;
  /** 0-1,AII 自算(非 LLM 自评)— UI 一等公民 */
  epistemic_confidence: number;
  /** 可信度的人话依据(如 "基于 5 条 KU:1 proven, 4 unverified") */
  confidence_basis: string;
  /** grounded 模式非空 */
  citations: ChatCitation[];
  /** 免责/标注(金融场景必有) */
  disclaimer?: string;
}

// ============================================================
// REQ AII-FRONTEND-DISPLAY-001 — 成果展示视图类型
//   契约见文档 §六。后端待实现(AII 经理人推进 CC)。
//   注意:grade 枚举用 blocks 真实 EpistemicGrade(moderate 非 medium)。
// ============================================================

/** 关系类型(aii.edge.relation_type)。contradicts 为诚实亮点,UI 标红。 */
export type RelationType =
  | 'references'
  | 'special_case_of'
  | 'prerequisite_of'
  | 'contradicts'
  | 'supports'
  | 'derived_from'
  | 'related_to';

/** 抽取方式 — rule(规则边,实线)/ llm(线索边,虚线)。命门:视觉区分可信度。 */
export type ExtractionMethod = 'rule' | 'llm';

/** 摄取介质 */
export type Medium = 'book' | 'paper' | 'video';

/** 知识类型 */
export type KnowledgeType =
  | 'theorem' | 'definition' | 'lemma' | 'proposition'
  | 'concept' | 'claim' | 'method' | 'example' | 'observation';

// ── 视图1:概览仪表盘 GET /api/stats/overview ──
export interface StatsOverviewResponse {
  ku_count: number;
  edge_count: number;
  kc_count: number;
  bu_count: number;
  /** grade 分布(命门:诚实呈现"大部分未确证")。 */
  grade_dist: Partial<Record<EpistemicGrade, number>>;
  /** 合并过的 KU 数(merge_count>1)。 */
  merge_count: number;
  /** 查重节省条数(去重析出内核)。 */
  dedup_saved: number;
  /** 关系类型分布。 */
  relation_type_dist: Partial<Record<RelationType, number>>;
}

// ── 视图1:摄取进度 GET /api/stats/ingestion ──
export interface StatsIngestionResponse {
  total_files: number;
  ingested: number;
  by_medium: Partial<Record<Medium, { total: number; ingested: number }>>;
  /** 完整深度理解(BU)已生成数。 */
  deep_understood: number;
}

// ── 书清单 GET /api/books ──
export interface BookInfo {
  substrate_id: string;
  title: string;
  subject?: string;
  ku_count: number;
}

// ── BU 书级理解 GET /api/book/{substrate}/bu ──
export interface BuFacets {
  soul: string; positioning: string; question: string;
  skeleton: string; thinking: string; for_whom: string; boundary: string;
}
export interface BuData {
  substrate_id: string;
  facets_zh: BuFacets;
  facets_en: BuFacets;
  grade: EpistemicGrade;
  synthesis_marker: string;
  n_ku: number;
  n_kc_chapter: number;
  n_kc_spectral: number;
}

// ── 视图2:KU 浏览 GET /api/ku/list ──
export interface KuListItem {
  id: string;
  natural_text: string;
  /** 中文译(简体)。中文主显,英文 natural_text 折叠。 */
  natural_text_zh?: string | null;
  grade: EpistemicGrade;
  knowledge_type: KnowledgeType;
  /** 来源 substrate(书名)。 */
  substrate_id: string;
  substrate_title: string;
  /** >1 表示多书共有,UI 标"多书共有"。 */
  merge_count: number;
  defeater_count: number;
}

export interface KuListRequest {
  grade?: EpistemicGrade;
  type?: KnowledgeType;
  substrate?: string;
  /** 是否只看合并过的(merge_count>1)。 */
  merged_only?: boolean;
  page?: number;
  page_size?: number;
}

export interface KuListResponse {
  items: KuListItem[];
  total: number;
  page: number;
  page_size: number;
  /** 可选的筛选 facet(供筛选器渲染 count)。 */
  facets?: {
    grades?: Partial<Record<EpistemicGrade, number>>;
    types?: Partial<Record<KnowledgeType, number>>;
    substrates?: Array<{ id: string; title: string; count: number }>;
  };
}

/** KU 详情(含 sources 多表述) */
export interface KuSource {
  substrate_id: string;
  substrate_title: string;
  /** 该书里的原始表述(多书共有时会有多条)。 */
  text: string;
  locator?: string;
}
export interface KuDetail extends KuListItem {
  sources: KuSource[];
  defeaters: EpistemicDefeater[];
  /** 关联边(去重后) */
  edges: Array<{
    target_id: string;
    target_text: string;
    relation_type: RelationType;
    extraction_method: ExtractionMethod;
    grade: EpistemicGrade;
  }>;
}

// ── 视图3:知识图谱 GET /api/graph/subgraph ──
export interface GraphNode {
  id: string;
  label: string;
  grade: EpistemicGrade;
  knowledge_type: KnowledgeType;
  /** 连接数(决定节点大小)。 */
  degree: number;
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: RelationType;
  /** rule=实线 / llm=虚线(命门)。 */
  extraction_method: ExtractionMethod;
  grade: EpistemicGrade;
}
export interface SubgraphRequest {
  ku_id: string;
  hops?: number;
  limit?: number;
  /** 可选:按 relation_type 过滤。 */
  relation_types?: RelationType[];
}
export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** 中心节点 id。 */
  center_id: string;
  /** 是否被 limit 截断。 */
  truncated: boolean;
}
export interface GraphSearchRequest { q: string; limit?: number; }
export interface GraphSearchResponse {
  matches: Array<{ id: string; label: string; grade: EpistemicGrade }>;
}

// ── 视图4:知识簇 KC GET /api/kc/list, /api/kc/{id} ──
export interface KcListItem {
  id: string;
  community_label: string;
  /** 簇摘要(AII 综合,非原文断言)。 */
  summary: string;
  /** ≤ 源 KU,永不 proven。 */
  grade: EpistemicGrade;
  community_size: number;
}
export interface KcDetail extends KcListItem {
  summary_en?: string;
  /** chapter=按章(书内固定) | spectral=谱社区(跨书增长) */
  kind?: 'chapter' | 'spectral';
  source_ku_ids: string[];
  members: Array<{
    id: string;
    title?: string;
    natural_text: string;
    natural_text_zh?: string;
    natural_text_en?: string;
    grade: EpistemicGrade;
    source_book?: string;
  }>;
}

// ── 视图5:书级理解 BU GET /api/bu/list, /api/bu/{id} ──
export interface BuListItem {
  id: string;
  substrate_id: string;
  book_title: string;
  /** AII 综合摘要。 */
  summary: string;
  grade: EpistemicGrade;
  main_claim_count: number;
}
/** 主要论断 — 带 stance_marker("X书主张")+ 独立 grade。命门:论断≠真理。 */
export interface MainClaim {
  id: string;
  text: string;
  /** 立场标记,如 "《资本论》主张"。 */
  stance_marker: string;
  claim_grade: EpistemicGrade;
}
/** 论点→论据,论据 grade 独立(哪些论据强/弱)。 */
export interface ArgumentNode {
  id: string;
  /** 论点 */
  thesis: string;
  thesis_grade: EpistemicGrade;
  /** 论据列表,每条 grade 独立 */
  evidence: Array<{ text: string; grade: EpistemicGrade }>;
}
export interface BuStructureSection {
  title: string;
  children?: BuStructureSection[];
}
export interface BuDetail extends BuListItem {
  main_claims: MainClaim[];
  argument_structure: ArgumentNode[];
  structure: BuStructureSection[];
  /** 核心概念 KU(链到 /knowledge)。 */
  key_concepts: Array<{ ku_id: string; label: string; grade: EpistemicGrade }>;
}
