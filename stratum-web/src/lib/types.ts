export interface SearchResultItem {
  id: string;
  type: string;
  title: string;
  score: number;
  highlight?: string | null;
}

export interface SearchResponse {
  results: SearchResultItem[];
  query_used: string;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  mode?: "strict" | "augmented";
  rerank?: boolean;
  expand?: boolean;
}

/** Row from agent_runs table (GET /api/v1/agents/runs) */
export interface AgentRun {
  id: string;
  agent_name: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  trace?: unknown | null;
  citations?: unknown[] | null;
  files_generated?: unknown[] | null;
}

/** Full detail from GET /api/v1/agents/runs/{run_id} */
export interface AgentRunDetail extends AgentRun {
  user_id?: string;
  params?: unknown;
  total_input_tokens?: number;
  total_output_tokens?: number;
  cost_usd?: number;
}

/** Response from POST /api/v1/agents/{name}/run */
export interface RunAgentResponse {
  run_id: string;
  agent_name: string;
  status: string;
  findings?: unknown | null;
  report_fingerprint?: string | null;
  citations?: unknown[] | null;
  error?: string | null;
}

export interface AgentRunsResponse {
  items: AgentRun[];
  total: number;
}

export interface ScheduledJob {
  id: string;
  name: string;
  agent_name: string;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  created_at?: string | null;
}

/** /api/v1/scheduled-jobs GET returns a plain array */
export type ScheduledJobsResponse = ScheduledJob[];

export interface SubstrateItem {
  id: string;
  title: string;
  mime?: string | null;
  language?: string | null;
  page_count?: number | null;
  created_at?: string | null;
}

export interface SubstratesResponse {
  items: SubstrateItem[];
  total: number;
}

export interface DerivativeItem {
  id: string;
  kind: string;
  seq: number;
  content: string;
}

export interface BacklinkItem {
  id: string;
  title: string;
  snippet?: string | null;
}

export interface BacklinksResponse {
  items: BacklinkItem[];
  total: number;
}

export interface UserProfilePublic {
  username: string;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface SessionItem {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  items: SessionItem[];
}
