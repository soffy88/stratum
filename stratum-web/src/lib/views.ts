import { apiClient } from "@/lib/api-client";

export interface View {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  icon?: string;
  is_preset: boolean;
  filter_json: Record<string, unknown>;
  sort_by: string;
  sort_order: string;
  display_mode: string;
  position: number;
  created_at: string;
  updated_at: string;
}

export type ViewCreate = Pick<View, "name"> &
  Partial<Pick<View, "description" | "icon" | "filter_json" | "sort_by" | "sort_order" | "display_mode" | "position">>;

export const listViews = () => apiClient.get<View[]>("/api/v1/views");
export const createView = (body: ViewCreate) => apiClient.post<View>("/api/v1/views", body);
export const updateView = (id: string, body: Partial<ViewCreate>) =>
  apiClient.put<View>(`/api/v1/views/${id}`, body);
export const deleteView = (id: string) => apiClient.delete<void>(`/api/v1/views/${id}`);
