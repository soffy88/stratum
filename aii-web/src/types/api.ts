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
