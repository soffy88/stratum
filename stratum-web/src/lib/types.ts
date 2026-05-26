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
