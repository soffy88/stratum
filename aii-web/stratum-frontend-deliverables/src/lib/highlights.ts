import { apiClient } from './apiClient';

export interface Highlight {
  id: string;
  color: string;          // yellow | blue | green | red
  text: string;           // 高亮原文
  note?: string;          // 用户笔记
  substrate_id: string;
  substrate_title?: string;
  created_at: string;
}

export const listHighlights = () =>
  apiClient.get<Highlight[]>('/api/v1/highlights').then(r => r.data);

export const deleteHighlight = (id: string) =>
  apiClient.delete(`/api/v1/highlights/${id}`);
