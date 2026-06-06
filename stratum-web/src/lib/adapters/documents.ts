/**
 * Adapter: stratum /api/substrates/* → ODocumentTree + ODocumentReader
 *
 * Backend SubstrateItem and DerivativeItem have fewer fields than
 * the helios Substrate and Derivative types. Missing fields are filled
 * with safe defaults per helios type definitions.
 */

import { useQuery } from "@tanstack/react-query";
import type { Substrate, Derivative, Medium, SourceType } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { SubstrateItem, SubstratesResponse, DerivativeItem } from "@/lib/types";

// ---------------------------------------------------------------------------
// Shape adapters
// ---------------------------------------------------------------------------

/** Infer helios Medium from MIME type string */
function inferMedium(mime: string | null | undefined): Medium {
  if (!mime) return "other";
  if (mime.includes("pdf")) return "paper";
  if (mime.includes("markdown") || mime.includes("text/plain")) return "markdown_note";
  if (mime.includes("text/html") || mime.includes("webpage")) return "webpage";
  return "other";
}

/** Map backend SubstrateItem → helios Substrate */
export function adaptSubstrate(item: SubstrateItem): Substrate {
  return {
    id: item.id,
    ulid: item.id,
    title: item.title ?? null,
    mime: item.mime ?? null,
    source_path: null,
    file_hash: null,
    byte_size: null,
    page_count: item.page_count ?? null,
    parser: null,
    language: item.language ?? null,
    has_cjk: false,
    is_scanned: false,
    created_at: item.created_at ?? new Date().toISOString(),
    updated_at: item.created_at ?? new Date().toISOString(),
    is_pinned: false,
    pinned_at: null,
    meta_json: {
      medium: inferMedium(item.mime),
      source_type: "inbox_local" as SourceType,
      source: {},
    },
  };
}

/** Map backend DerivativeItem → helios Derivative */
export function adaptDerivative(item: DerivativeItem, substrateId: string): Derivative {
  return {
    id: item.id,
    substrate_id: substrateId,
    kind: item.kind as Derivative["kind"],
    seq: item.seq,
    content: item.content ?? null,
    embedding_id: null,
    embedding_dim: null,
    meta_json: {},
    created_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Hook: list all substrates for ODocumentTree */
export function useDocumentTree(viewId?: string | null) {
  const url = viewId ? `/api/substrates?view_id=${viewId}` : "/api/substrates";
  const query = useQuery({
    queryKey: ["substrates", viewId ?? "all"],
    queryFn: () => apiClient.get<SubstratesResponse>(url),
  });
  return {
    substrates: (query.data?.items ?? []).map(adaptSubstrate),
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/** Hook: single substrate for ODocumentReader */
export function useDocument(id: string) {
  const subQuery = useQuery({
    queryKey: ["substrate", id],
    queryFn: () => apiClient.get<SubstrateItem>(`/api/substrates/${id}`),
    enabled: !!id,
  });
  const derQuery = useQuery({
    queryKey: ["derivatives", id],
    queryFn: () =>
      apiClient.get<{ items: DerivativeItem[] }>(`/api/substrates/${id}/derivatives`),
    enabled: !!id,
  });
  return {
    substrate: subQuery.data ? adaptSubstrate(subQuery.data) : null,
    derivatives: (derQuery.data?.items ?? []).map((d) => adaptDerivative(d, id)),
    isLoading: subQuery.isLoading || derQuery.isLoading,
  };
}
