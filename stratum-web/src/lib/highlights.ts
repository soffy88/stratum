import { apiClient } from './apiClient';

// PDF:页 + 矩形区域;EPUB:cfi 定位
export interface PdfLocation {
  page?: number;
  rects?: { top: number; left: number; width: number; height: number; pageIndex: number }[];
}
export interface EpubLocation {
  cfi: string;
}
export type HighlightLocation = PdfLocation | EpubLocation;

export interface Highlight {
  id: string;
  color: string;          // yellow | blue | green | red
  text: string;
  note?: string;
  substrate_id: string;
  substrate_title?: string;
  location_json?: HighlightLocation;
  created_at: string;
}

export const listHighlights = () =>
  apiClient.get<Highlight[]>('/api/v1/highlights').then(r => r.data);

// 按文档过滤(阅读器回显用)
export const listHighlightsByDocument = (substrateId: string) =>
  apiClient.get<Highlight[]>('/api/v1/highlights', { params: { substrate_id: substrateId } }).then(r => r.data);

export const createHighlight = (body: {
  substrate_id: string;
  color: string;
  text: string;
  note?: string;
  location_json: HighlightLocation;
}) => apiClient.post<Highlight>('/api/v1/highlights', body).then(r => r.data);

export const updateHighlight = (id: string, body: { color?: string; note?: string }) =>
  apiClient.patch<Highlight>(`/api/v1/highlights/${id}`, body).then(r => r.data);

export const deleteHighlight = (id: string) =>
  apiClient.delete(`/api/v1/highlights/${id}`);
