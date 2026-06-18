/**
 * Axios-like API client adaptor for v1.1 deliverables.
 * Wraps api-client.ts, adds { params } support and { data } wrapping.
 */

import { apiClient as _client, type RequestConfig } from './api-client';

type Params = Record<string, string | number | boolean | undefined | null>;

interface MergedConfig extends RequestConfig {
  params?: Params;
}

function buildUrl(path: string, params?: Params): string {
  if (!params) return path;
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null) as [string, string | number | boolean][];
  if (!entries.length) return path;
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
  return `${path}?${qs}`;
}

export const apiClient = {
  get<T>(path: string, config?: MergedConfig) {
    return _client.get<T>(buildUrl(path, config?.params), config).then(data => ({ data }));
  },
  post<T>(path: string, body?: unknown, config?: RequestConfig) {
    return _client.post<T>(path, body, config).then(data => ({ data }));
  },
  put<T>(path: string, body?: unknown, config?: RequestConfig) {
    return _client.put<T>(path, body, config).then(data => ({ data }));
  },
  patch<T>(path: string, body?: unknown, config?: RequestConfig) {
    return _client.patch<T>(path, body, config).then(data => ({ data }));
  },
  delete(path: string, config?: RequestConfig) {
    return _client.delete<unknown>(path, config).then(data => ({ data }));
  },
};
