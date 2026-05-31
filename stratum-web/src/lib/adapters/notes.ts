/**
 * Adapter: stratum /api/notes/* → OBacklinkPanel + ODocumentReader (note view)
 *
 * Backend BacklinkItem = {id, title, snippet}
 * helios BacklinkItem  = {note: Note, excerpt?, link_text?}
 */

import { useQuery } from "@tanstack/react-query";
import type { BacklinkItem, Note } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { BacklinkItem as BackendBacklinkItem, BacklinksResponse } from "@/lib/types";

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
