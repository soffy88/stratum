/**
 * Ambient type stub for @helios/blocks (private package).
 * Covers shapes used by stratum-web adapter and page files.
 */
declare module '@helios/blocks' {
  import type { ComponentType, ReactNode } from 'react';

  // ── Primitives ──────────────────────────────────────────────────────────────
  export type Medium =
    | 'paper' | 'book' | 'epub' | 'markdown_note' | 'webpage' | 'other' | string;
  export type SourceType = 'inbox_local' | 'url_clip' | 'api' | string;

  // ── Data models ─────────────────────────────────────────────────────────────
  export interface Substrate {
    id: string;
    ulid: string;
    title: string | null;
    mime: string | null;
    source_path: string | null;
    file_hash: string | null;
    byte_size: number | null;
    page_count: number | null;
    parser: string | null;
    language: string | null;
    has_cjk: boolean;
    is_scanned: boolean;
    created_at: string;
    updated_at: string;
    is_pinned: boolean;
    pinned_at: string | null;
    meta_json: {
      medium: Medium;
      source_type: SourceType;
      source: Record<string, unknown>;
      [key: string]: unknown;
    };
  }

  export interface Derivative {
    id: string;
    substrate_id: string;
    kind: 'markdown' | 'summary' | 'embedding' | string;
    seq: number;
    content: string | null;
    embedding_id: string | null;
    embedding_dim: number | null;
    meta_json: Record<string, unknown>;
    created_at: string;
  }

  export interface Citation {
    substrate_id: string;
    title?: string;
    fragment_id?: string | null;
    anchor?: string | null;
    deep_link?: string | null;
    [key: string]: unknown;
  }

  export interface Note {
    id: string;
    title: string | null;
    content: string | null;
    wikilinks: string[];
    substrate_id: string | null;
    meta_json: Record<string, unknown>;
    created_at: string;
    updated_at: string;
  }

  export interface BacklinkItem {
    note: Note;
    excerpt?: string;
    link_text?: string;
  }

  export interface SearchResult {
    id: string;
    type: 'substrate' | 'llm_augmented' | string;
    title: string;
    score: number;
    highlight: string | null;
    metadata: {
      medium: Medium | null;
      source_type: SourceType | null;
      domain: string | null;
      created_at: string | null;
    };
    citation: Citation | null;
  }

  export interface QAResponse {
    answer: string;
    citations: Citation[];
    sources_used?: unknown;
  }

  export interface OAISummaryCardProps {
    summary: string;
    date?: string;
    digestSent: boolean;
    citations: Citation[];
    [key: string]: unknown;
  }

  export type AgentName =
    | 'daily_digest' | 'reading_companion' | 'weekly_review' | 'knowledge_curator' | string;

  export interface ScheduledJobWithStatus {
    id: string;
    user_id: string;
    name: string;
    agent_name: AgentName;
    agent_params: string;
    cron_expression: string;
    timezone: string;
    enabled: boolean;
    notify_on_completion: boolean;
    notify_on_failure: boolean;
    max_runtime_seconds: number;
    created_at: string;
    updated_at: string;
    is_builtin: boolean;
    next_run_at: string | null;
    last_run_at: string | null;
    last_status: string | null;
  }

  // ── React UI components ─────────────────────────────────────────────────────
  export interface OAIQAPanelProps {
    onAsk?: (question: string) => Promise<QAResponse>;
    [key: string]: unknown;
  }
  export const OAIQAPanel: ComponentType<OAIQAPanelProps>;

  export const OAISummaryCard: ComponentType<OAISummaryCardProps>;

  export interface ODocumentReaderProps {
    substrate: Substrate;
    derivatives: Derivative[];
    [key: string]: unknown;
  }
  export const ODocumentReader: ComponentType<ODocumentReaderProps>;

  export interface OAnnotationLayerProps {
    fragments: unknown[];
    emptyText?: string;
    [key: string]: unknown;
  }
  export const OAnnotationLayer: ComponentType<OAnnotationLayerProps>;

  export interface OCitationCardProps {
    citation: Citation;
    compact?: boolean;
    [key: string]: unknown;
  }
  export const OCitationCard: ComponentType<OCitationCardProps>;

  export interface OScheduledJobsManagerProps {
    jobs?: ScheduledJobWithStatus[];
    [key: string]: unknown;
  }
  export const OScheduledJobsManager: ComponentType<OScheduledJobsManagerProps>;

  export interface OSemanticSearchProps {
    onSearch?: (query: string) => Promise<SearchResult[]>;
    [key: string]: unknown;
  }
  export const OSemanticSearch: ComponentType<OSemanticSearchProps>;

  export interface OBacklinkPanelProps {
    backlinks?: BacklinkItem[];
    [key: string]: unknown;
  }
  export const OBacklinkPanel: ComponentType<OBacklinkPanelProps>;
}
