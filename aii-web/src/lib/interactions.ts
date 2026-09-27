import { apiClient } from './apiClient';

export type ReaderAction = 'important' | 'question' | 'contradict';

export interface ReaderActionResponse {
  status: 'recorded';
  action_id: string;
  event_id?: string | null;
}

/** Record a semantic reader action; Claim/Belief creation remains server-owned. */
export const recordReaderAction = (
  contentId: string,
  action: ReaderAction,
  note?: string,
) => apiClient.post<ReaderActionResponse>(
  `/api/v1/interactions/content/${encodeURIComponent(contentId)}/actions`,
  { action, note: note?.trim() || undefined },
).then(result => result.data);
