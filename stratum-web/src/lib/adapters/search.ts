/**
 * Adapter: stratum /api/search → OSemanticSearch
 *
 * OSemanticSearch.onSearch is an async callback that returns
 * helios SearchResult[]. Backend returns SearchResultItem[].
 */

import type { SearchResult } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { SearchResultItem, SearchResponse } from "@/lib/types";

/** Map backend SearchResultItem → helios SearchResult */
function adaptSearchResult(item: SearchResultItem): SearchResult {
  return {
    id: item.id,
    type: item.type as "substrate" | "llm_augmented",
    title: item.title,
    score: item.score,
    highlight: item.highlight ?? null,
    metadata: {
      medium: null,
      source_type: null,
      domain: null,
      created_at: null,
    },
    citation: null,
  };
}

/**
 * Search handler for OSemanticSearch.
 * Pass directly as the `onSearch` prop.
 *
 * @example
 * const searchFn = useStratumSearch();
 * <OSemanticSearch onSearch={searchFn} />
 */
export function useStratumSearch() {
  return async (query: string): Promise<SearchResult[]> => {
    const res = await apiClient.post<SearchResponse>("/api/search", {
      query,
      top_k: 10,
      mode: "augmented",
    });
    return res.results.map(adaptSearchResult);
  };
}
