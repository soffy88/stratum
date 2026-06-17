import { apiClient } from './apiClient';

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
  sort_by: string;        // created_at | updated_at | title | pin_priority
  sort_order: string;     // asc | desc
  display_mode: string;   // list | grid | compact
  position: number;
  created_at: string;
  updated_at: string;
}

export const listViews = () =>
  apiClient.get<View[]>('/api/v1/views').then(r => r.data);

export const createView = (body: Partial<View>) =>
  apiClient.post<View>('/api/v1/views', body).then(r => r.data);

export const updateView = (id: string, body: Partial<View>) =>
  apiClient.put<View>(`/api/v1/views/${id}`, body).then(r => r.data);

export const deleteView = (id: string) =>
  apiClient.delete(`/api/v1/views/${id}`);
