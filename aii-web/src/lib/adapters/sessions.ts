import { apiClient } from "@/lib/api-client";

// ── Interfaces ──────────────────────────────────────────────

export interface Session {
  id: string;
  user_id: string;
  title: string;
  status: "active" | "committed" | "archived";
  token_count: number;
  pending_tokens: number;
  message_count: number;
  commit_count: number;
  auto_commit: string;
  created_at: string;
  updated_at: string;
}

export interface SessionMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number;
  created_at: string;
}

export interface SessionDetail {
  session: Session;
  messages: SessionMessage[];
}

export interface WorkingMemory {
  sections: unknown[];
  total_tokens: number;
}

export interface LongTermMemory {
  id: string;
  content: string;
  relevance: number;
}

export interface RetrievalResult {
  substrate_id: string;
  score: number;
  l0_summary: string;
}

export interface SessionContext {
  working_memory: WorkingMemory;
  long_term_memories: LongTermMemory[];
  retrieval_results: RetrievalResult[];
  conversation_summary: string;
  total_tokens: number;
}

export interface SessionMemoryItem {
  id: string;
  session_id: string;
  content: string;
  memory_type: string;
  created_at: string;
}

export interface SessionMemories {
  memories: SessionMemoryItem[];
}

// ── Adapter functions ───────────────────────────────────────

export async function listSessions(
  limit: number = 50,
  offset: number = 0
): Promise<Session[] | null> {
  try {
    return await apiClient.get<Session[]>(
      `/api/v1/sessions/?limit=${limit}&offset=${offset}`
    );
  } catch {
    return null;
  }
}

export async function getSession(id: string): Promise<SessionDetail | null> {
  try {
    return await apiClient.get<SessionDetail>(`/api/v1/sessions/${id}`);
  } catch {
    return null;
  }
}

export async function createSession(title?: string): Promise<Session | null> {
  try {
    return await apiClient.post<Session>(
      "/api/v1/sessions",
      title ? { title } : undefined
    );
  } catch {
    return null;
  }
}

export async function deleteSession(id: string): Promise<boolean> {
  try {
    await apiClient.delete(`/api/v1/sessions/${id}`);
    return true;
  } catch {
    return false;
  }
}

export async function addMessage(
  sessionId: string,
  role: "user" | "assistant" | "system",
  content: string
): Promise<SessionMessage | null> {
  try {
    return await apiClient.post<SessionMessage>(
      `/api/v1/sessions/${sessionId}/messages`,
      { role, content }
    );
  } catch {
    return null;
  }
}

export async function getSessionContext(
  sessionId: string,
  query?: string
): Promise<SessionContext | null> {
  try {
    const qs = query ? `?query=${encodeURIComponent(query)}` : "";
    return await apiClient.get<SessionContext>(
      `/api/v1/sessions/${sessionId}/context${qs}`
    );
  } catch {
    return null;
  }
}

export async function commitSession(
  sessionId: string
): Promise<boolean> {
  try {
    await apiClient.post(`/api/v1/sessions/${sessionId}/commit`);
    return true;
  } catch {
    return false;
  }
}

export async function getSessionMemories(
  sessionId: string
): Promise<SessionMemories | null> {
  try {
    return await apiClient.get<SessionMemories>(
      `/api/v1/sessions/${sessionId}/memories`
    );
  } catch {
    return null;
  }
}
