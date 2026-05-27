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

export interface AgentRun {
  id: string;
  agent_name: string;
  status: string;
  output?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface RunAgentResponse {
  agent_run: AgentRun;
  message: string;
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

export interface ScheduledJobsResponse {
  items: ScheduledJob[];
  total: number;
}

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
