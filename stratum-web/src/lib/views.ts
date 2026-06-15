import { apiClient } from './api-client';

export interface ViewFilter {
  medium?: string[];
  tags?: string[];
  tag_exclude?: string[];
  language?: string[];
}

export interface View {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  is_preset: boolean;
  filter_json: ViewFilter;
  sort_by: string;
  sort_order: string;
  display_mode: string;
  position: number;
  created_at: string;
  updated_at: string;
}

export const listViews = () =>
  apiClient.get<View[]>('/api/v1/views');

export const createView = (body: Partial<View>) =>
  apiClient.post<View>('/api/v1/views', body);

export const updateView = (id: string, body: Partial<View>) =>
  apiClient.put<View>(`/api/v1/views/${id}`, body);

export const deleteView = (id: string) =>
  apiClient.delete(`/api/v1/views/${id}`);
