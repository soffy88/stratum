/**
 * Adapter: stratum /api/notes/* → OBacklinkPanel + ODocumentReader (note view)
 *
 * Backend BacklinkItem = {id, title, snippet}
 * helios BacklinkItem  = {note: Note, excerpt?, link_text?}
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { BacklinkItem, Note } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import { extractWikilinkTargets } from "@/lib/wikilink";
import type {
  BacklinkItem as BackendBacklinkItem,
  BacklinksResponse,
  NoteRevision,
  TrashNoteItem,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Local NoteDetail type for GET /api/notes/:id (added Wave 10B)
// ---------------------------------------------------------------------------
export interface NoteDetail {
  id: string;
  title: string | null;
  content: string | null;
  wikilinks: string[];
  substrate_id: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Shape adapters
// ---------------------------------------------------------------------------

/** Construct a minimal helios Note from backend backlink row */
function adaptBacklinkNote(item: BackendBacklinkItem): Note {
  return {
    id: item.id,
    title: item.title,
    content: null,
    wikilinks: [],
    substrate_id: null,
    meta_json: {},
    created_at: "",
    updated_at: "",
  };
}

/** Map backend BacklinkItem → helios BacklinkItem */
function adaptBacklink(item: BackendBacklinkItem): BacklinkItem {
  return {
    note: adaptBacklinkNote(item),
    excerpt: item.snippet ?? undefined,
    link_text: undefined,
  };
}

/** Adapt NoteDetail → helios Note (for ODocumentReader) */
export function adaptNoteToHeliosNote(note: NoteDetail): Note {
  return {
    id: note.id,
    title: note.title,
    content: note.content,
    wikilinks: note.wikilinks,
    substrate_id: note.substrate_id,
    meta_json: note.meta_json,
    created_at: note.created_at,
    updated_at: note.updated_at,
  };
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Hook: backlinks for OBacklinkPanel */
export function useBacklinks(noteId: string) {
  const query = useQuery({
    queryKey: ["backlinks", noteId],
    queryFn: () =>
      apiClient.get<BacklinksResponse>(`/api/notes/${noteId}/backlinks`),
    enabled: !!noteId,
  });
  return {
    backlinks: (query.data?.items ?? []).map(adaptBacklink),
    isLoading: query.isLoading,
  };
}

/** Hook: single note detail for ODocumentReader */
export function useNote(noteId: string) {
  const query = useQuery({
    queryKey: ["note", noteId],
    queryFn: () => apiClient.get<NoteDetail>(`/api/notes/${noteId}`),
    enabled: !!noteId,
  });
  return {
    note: query.data ? adaptNoteToHeliosNote(query.data) : null,
    isLoading: query.isLoading,
    error: query.error,
  };
}

// ---------------------------------------------------------------------------
// Mutations for the (app)/notes page (edit content / delete)
// Backend NoteUpdate expects { content_markdown } — see routers/notes.py.
// ---------------------------------------------------------------------------
export async function updateNote(id: string, content: string): Promise<boolean> {
  try {
    await apiClient.put(`/api/v1/notes/${id}`, { content_markdown: content });
    return true;
  } catch {
    return false;
  }
}

export async function deleteNote(id: string): Promise<boolean> {
  try {
    await apiClient.delete(`/api/v1/notes/${id}`);
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// P0-1 版本历史 / P0-2 回收站 / P0-4 出链（AII Notes）
// ---------------------------------------------------------------------------

/** 出链：正文 [[目标]] 解析结果 */
export interface OutgoingLink {
  /** 正文里写出的目标文本 */
  target: string;
  /** 解析到的笔记 id（断链为 null） */
  id: string | null;
  /** 目标笔记标题 */
  title: string | null;
}

/** 把未知 envelope 归一为数组（兼容裸数组 / {items} / {revisions}） */
function asArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    const o = data as { items?: unknown; revisions?: unknown };
    if (Array.isArray(o.items)) return o.items as T[];
    if (Array.isArray(o.revisions)) return o.revisions as T[];
  }
  return [];
}

type NoteListRow = { id: string; title: string | null; updated_at: string };

/**
 * 解析正文 wikilink 出链：目标先按笔记 id 精确匹配，再按标题
 * （大小写不敏感）匹配，与后端 knowledge_lint 的规则对齐。
 */
export function useOutgoingLinks(content: string) {
  const targets = useMemo(() => extractWikilinkTargets(content ?? ""), [content]);
  const query = useQuery({
    queryKey: ["outgoing-links", targets.join(" ")],
    queryFn: async (): Promise<OutgoingLink[]> => {
      const rows = await apiClient.get<NoteListRow[]>("/api/v1/notes");
      const byId = new Map(rows.map((r) => [r.id, r]));
      const byTitle = new Map<string, NoteListRow>();
      for (const r of rows) {
        const key = (r.title ?? "").trim().toLowerCase();
        if (key && !byTitle.has(key)) byTitle.set(key, r);
      }
      return targets.map((target) => {
        const hit = byId.get(target) ?? byTitle.get(target.toLowerCase());
        return hit
          ? { target, id: hit.id, title: hit.title }
          : { target, id: null, title: null };
      });
    },
    enabled: targets.length > 0,
    staleTime: 60_000,
  });
  return {
    links: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
  };
}

/** Hook: 版本历史（version DESC）— GET /api/v1/notes/{id}/revisions */
export function useRevisions(noteId: string) {
  const query = useQuery({
    queryKey: ["note-revisions", noteId],
    queryFn: () => apiClient.get<unknown>(`/api/v1/notes/${noteId}/revisions`),
    enabled: !!noteId,
  });
  return {
    revisions: asArray<NoteRevision>(query.data),
    isLoading: query.isLoading,
    error: query.error,
  };
}

/** 恢复到指定版本（后端写新版本，不覆写历史） */
export async function restoreRevision(noteId: string, version: number): Promise<boolean> {
  try {
    await apiClient.post(`/api/v1/notes/${noteId}/revisions/${version}/restore`, {});
    return true;
  } catch {
    return false;
  }
}

/** Hook: 回收站列表 — GET /api/v1/notes/trash */
export function useTrash() {
  const query = useQuery({
    queryKey: ["notes-trash"],
    queryFn: () => apiClient.get<unknown>("/api/v1/notes/trash"),
  });
  return {
    items: asArray<TrashNoteItem>(query.data),
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/** 从回收站恢复笔记 — POST /api/v1/notes/{id}/restore */
export async function restoreNoteFromTrash(id: string): Promise<boolean> {
  try {
    await apiClient.post(`/api/v1/notes/${id}/restore`, {});
    return true;
  } catch {
    return false;
  }
}
