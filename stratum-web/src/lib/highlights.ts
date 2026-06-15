import { apiClient } from './api-client';

export interface Highlight {
  id: string;
  color: string;
  text: string;
  note?: string;
  substrate_id: string;
  substrate_title?: string;
  created_at: string;
}

export const listHighlights = () =>
  apiClient.get<Highlight[]>('/api/v1/highlights');

export const deleteHighlight = (id: string) =>
  apiClient.delete(`/api/v1/highlights/${id}`);
