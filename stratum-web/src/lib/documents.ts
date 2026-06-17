import { apiClient } from './apiClient';

export interface Substrate {
  id: string;
  title: string;
  mime: string;
  medium: string;        // pdf | epub | book | text | webpage
  source: string;        // folder_watch | upload | url | rss
  language: string;
  page_count?: number;
  byte_size?: number;
  created_at: string;
  is_pinned: boolean;
}

export interface DocumentListResult {
  items: Substrate[];
  total: number;
}

export type DerivativeKind = 'markdown' | 'translation' | 'audio' | 'illustration';
export interface Derivative {
  kind: DerivativeKind;
}

export const listDocuments = (params?: {
  view?: string; limit?: number; offset?: number; q?: string; kind?: string;
}) =>
  apiClient.get<DocumentListResult>('/api/v1/documents', { params }).then(r => r.data);

export const getDerivatives = (substrateId: string) =>
  apiClient.get<Derivative[]>(`/api/v1/documents/${substrateId}/derivatives`).then(r => r.data);
