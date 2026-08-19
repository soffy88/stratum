/**
 * Adapter: /api/v1/cornell — 机器康奈尔 + 人类康奈尔
 */

import { apiClient } from "@/lib/api-client";

export interface CornellCue {
  id: string;
  mod: string;
  text: string;
  hint?: string;
}

export interface CornellModule {
  id: string;
  title: string;
  body: string;
  kind?: string;
}

export interface CornellDrill {
  id: string;
  kind: string;
  prompt: string;
  answer: string;
  mod?: string | null;
}

export interface CornellContent {
  version: number;
  topicId: string;
  title: string;
  subject?: string;
  date?: string;
  cues: CornellCue[];
  modules: CornellModule[];
  summary: string;
  oneLiner: string;
  drills?: CornellDrill[];
  meta?: Record<string, unknown>;
}

export interface CornellProgressState {
  topicId: string;
  version: number;
  mastered: Record<string, boolean>;
  collapsed: Record<string, boolean>;
  drills?: Record<string, boolean>;
  selfTest: boolean;
  showAnswers: boolean;
  updatedAt: string;
}

export interface CornellNote {
  id: string;
  topic_id: string;
  title: string;
  subject: string | null;
  source: "machine" | "human";
  refined_ku_ids?: string[];
  refined_concept_ids?: number[];
  content: CornellContent;
  user_id: string | null;
  created_at: string;
  updated_at: string;
  kind?: string;
  content_preview?: string;
  cue_count?: number;
  module_count?: number;
}

export async function listCornell(params?: {
  source?: "machine" | "human" | "all";
  subject?: string;
  limit?: number;
}): Promise<CornellNote[]> {
  const q = new URLSearchParams();
  if (params?.source) q.set("source", params.source);
  if (params?.subject) q.set("subject", params.subject);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiClient.get<CornellNote[]>(`/api/v1/cornell${qs ? `?${qs}` : ""}`);
}

export async function getCornell(id: string): Promise<CornellNote> {
  return apiClient.get<CornellNote>(`/api/v1/cornell/${id}`);
}

export async function generateCornell(body: {
  concept_id?: number;
  concept_ids?: number[];
  discipline?: string;
  limit?: number;
  polish?: boolean;
}): Promise<{ n_created: number; n_updated: number; n_skipped: number }> {
  return apiClient.post(`/api/v1/cornell/generate`, body);
}

export async function polishCornell(body?: {
  note_ids?: string[];
  limit?: number;
}): Promise<{ n_ok: number; n_fail: number }> {
  return apiClient.post(`/api/v1/cornell/polish`, body ?? { limit: 10 });
}

/** 云端进度 pull */
export async function pullCornellProgress(
  topicId: string
): Promise<{ state: CornellProgressState | null }> {
  return apiClient.get(`/api/v1/cornell/progress/${encodeURIComponent(topicId)}`);
}

/** 云端进度 push(服务端并集合并) */
export async function pushCornellProgress(
  topicId: string,
  state: CornellProgressState,
  noteId?: string
): Promise<{ state: CornellProgressState }> {
  return apiClient.put(`/api/v1/cornell/progress/${encodeURIComponent(topicId)}`, {
    topic_id: topicId,
    note_id: noteId ?? null,
    state,
  });
}

/**
 * CloudSyncAdapter — 预留云端同步。
 * autoPush=true 时每次 local 保存会 debounce 推送。
 */
export const CloudSyncAdapter = {
  autoPush: true as boolean,
  async push(state: CornellProgressState, noteId?: string) {
    if (!state.topicId) return null;
    try {
      const res = await pushCornellProgress(state.topicId, state, noteId);
      return res.state;
    } catch {
      return null;
    }
  },
  async pull(topicId: string) {
    try {
      const res = await pullCornellProgress(topicId);
      return res.state;
    } catch {
      return null;
    }
  },
};
