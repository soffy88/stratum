import { apiClient } from "@/lib/api-client";

export interface Bookmark {
  id: string;
  content_id: string;
  content_title?: string;
  created_at: string;
}

export async function listBookmarks(): Promise<Bookmark[]> {
  try {
    return (await apiClient.get<Bookmark[]>("/api/v1/bookmarks")) ?? [];
  } catch {
    return [];
  }
}

export async function addBookmark(contentId: string): Promise<boolean> {
  try {
    await apiClient.post(`/api/v1/bookmarks?content_id=${encodeURIComponent(contentId)}`);
    return true;
  } catch {
    return false;
  }
}

export async function removeBookmark(id: string): Promise<boolean> {
  try {
    await apiClient.delete(`/api/v1/bookmarks/${id}`);
    return true;
  } catch {
    return false;
  }
}
