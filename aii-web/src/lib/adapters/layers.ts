/**
 * Adapter: stratum /api/v1/layers/* and /api/v1/fs/* → Layer Browser
 */

import { apiClient } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LayerId = "L0" | "L1" | "L2";

export interface LayerContent {
  content: string;
  token_count: number;
  [key: string]: unknown;
}

export interface LayerStats {
  total_substrates: number;
  substrates_with_l0: number;
  substrates_with_l1: number;
  substrates_with_l2: number;
  total_kus: number;
  kus_with_layers: number;
  [key: string]: unknown;
}

export interface FsNode {
  uri: string;
  name: string;
  type: "directory" | "substrate" | "ku";
  ref_id?: string;
  children?: FsNode[];
  l0?: string;
  l1?: string;
  [key: string]: unknown;
}

export interface FsTreeResponse {
  uri: string;
  nodes: FsNode[];
  count: number;
}

export interface FsLsResponse {
  uri: string;
  children: FsNode[];
  count: number;
}

// ---------------------------------------------------------------------------
// Layer endpoints
// ---------------------------------------------------------------------------

export async function getSubstrateLayer(
  substrateId: string,
  layer: LayerId,
): Promise<LayerContent | null> {
  try {
    return await apiClient.get<LayerContent>(
      `/api/v1/layers/substrate/${substrateId}?layer=${layer}`,
    );
  } catch {
    return null;
  }
}

export async function getKULayer(
  kuId: string,
  layer: LayerId,
): Promise<LayerContent | null> {
  try {
    return await apiClient.get<LayerContent>(
      `/api/v1/layers/ku/${kuId}?layer=${layer}`,
    );
  } catch {
    return null;
  }
}

export async function getLayerStats(): Promise<LayerStats | null> {
  try {
    return await apiClient.get<LayerStats>("/api/v1/layers/stats");
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Viking filesystem endpoints
// ---------------------------------------------------------------------------

export async function fsLs(
  uri: string,
  depth?: number,
): Promise<FsLsResponse | null> {
  try {
    const params = new URLSearchParams({ uri });
    if (depth !== undefined) params.set("depth", String(depth));
    return await apiClient.get<FsLsResponse>(`/api/v1/fs/ls?${params}`);
  } catch {
    return null;
  }
}

export async function fsTree(
  uri: string,
  depth?: number,
): Promise<FsTreeResponse | null> {
  try {
    const params = new URLSearchParams({ uri });
    if (depth !== undefined) params.set("depth", String(depth));
    return await apiClient.get<FsTreeResponse>(`/api/v1/fs/tree?${params}`);
  } catch {
    return null;
  }
}

export async function fsRead(
  uri: string,
  layer: LayerId,
): Promise<LayerContent | null> {
  try {
    const params = new URLSearchParams({ uri, layer });
    return await apiClient.get<LayerContent>(`/api/v1/fs/read?${params}`);
  } catch {
    return null;
  }
}

export async function fsGrep(
  pattern: string,
  scope?: string,
  layer?: string,
): Promise<unknown | null> {
  try {
    const params = new URLSearchParams({ pattern });
    if (scope) params.set("scope", scope);
    if (layer) params.set("layer", layer);
    return await apiClient.get(`/api/v1/fs/grep?${params}`);
  } catch {
    return null;
  }
}

export async function fsFind(
  q: string,
  mode: "name" | "content" | "semantic",
): Promise<unknown | null> {
  try {
    const params = new URLSearchParams({ q, mode });
    return await apiClient.get(`/api/v1/fs/find?${params}`);
  } catch {
    return null;
  }
}

export async function fsCat(
  uri: string,
  layer?: string,
): Promise<LayerContent | null> {
  try {
    const params = new URLSearchParams({ uri });
    if (layer) params.set("layer", layer);
    return await apiClient.get<LayerContent>(`/api/v1/fs/cat?${params}`);
  } catch {
    return null;
  }
}

export async function fsStat(
  uri: string,
): Promise<Record<string, unknown> | null> {
  try {
    const params = new URLSearchParams({ uri });
    return await apiClient.get<Record<string, unknown>>(
      `/api/v1/fs/stat?${params}`,
    );
  } catch {
    return null;
  }
}

export async function fsStats(): Promise<Record<string, unknown> | null> {
  try {
    return await apiClient.get<Record<string, unknown>>("/api/v1/fs/stats");
  } catch {
    return null;
  }
}
