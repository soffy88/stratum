/**
 * Axios-like API client adaptor for v1.1 deliverables.
 * Wraps api-client.ts, adds { params } support and { data } wrapping.
 */

import { apiClient as _client } from './api-client';

type Params = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, params?: Params): string {
  if (!params) return path;
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null) as [string, string | number | boolean][];
  if (!entries.length) return path;
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
  return `${path}?${qs}`;
}

export const apiClient = {
  get<T>(path: string, config?: { params?: Params }) {
    return _client.get<T>(buildUrl(path, config?.params)).then(data => ({ data }));
  },
  post<T>(path: string, body?: unknown) {
    return _client.post<T>(path, body).then(data => ({ data }));
  },
  put<T>(path: string, body?: unknown) {
    return _client.put<T>(path, body).then(data => ({ data }));
  },
  patch<T>(path: string, body?: unknown) {
    return _client.patch<T>(path, body).then(data => ({ data }));
  },
  delete(path: string) {
    return _client.delete<unknown>(path).then(data => ({ data }));
  },
};
