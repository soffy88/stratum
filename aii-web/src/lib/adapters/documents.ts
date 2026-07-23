/**
 * Adapter: stratum API → ODocumentTree + ODocumentReader
 *
 * useDocumentTree  → /api/substrates        (stratum-api, legacy)
 * useDocument      → /api/v1/documents/:id  (stratum-sl, new service layer)
 *
 * The split exists because stratum-sl holds the DuckDB write lock; stratum-api
 * cannot open the same file concurrently and returns 500 on per-document queries.
 */

import { useQuery } from "@tanstack/react-query";
import type { Substrate, Derivative, Medium, SourceType } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { SubstrateItem, SubstratesResponse, DerivativeItem } from "@/lib/types";

/** Derivative shape returned by /api/v1/documents/:id/derivatives (stratum-sl). */
interface SlDerivativeItem {
  kind: string;
  content: string | null;
}

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
export function useDocumentTree() {
  const query = useQuery({
    queryKey: ["substrates"],
    queryFn: () => apiClient.get<SubstratesResponse>("/api/substrates"),
  });
  return {
    substrates: (query.data?.items ?? []).map(adaptSubstrate),
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/** Hook: single substrate + derivatives for ODocumentReader (via stratum-sl) */
export function useDocument(id: string) {
  const subQuery = useQuery({
    queryKey: ["substrate", id],
    queryFn: () => apiClient.get<SubstrateItem>(`/api/v1/documents/${id}`),
    enabled: !!id,
  });
  const derQuery = useQuery({
    queryKey: ["derivatives", id],
    queryFn: () =>
      apiClient.get<SlDerivativeItem[]>(`/api/v1/documents/${id}/derivatives`),
    enabled: !!id,
  });
  return {
    substrate: subQuery.data ? adaptSubstrate(subQuery.data) : null,
    derivatives: (derQuery.data ?? []).map((d, i) =>
      adaptDerivative({ id: `${id}-${d.kind}-${i}`, kind: d.kind, seq: i, content: d.content ?? "" }, id)
    ),
    isLoading: subQuery.isLoading || derQuery.isLoading,
  };
}
