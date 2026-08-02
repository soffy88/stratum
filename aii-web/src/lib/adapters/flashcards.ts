/**
 * Adapter: stratum /api/v1/flashcards (闪卡 + 间隔复习)
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface Flashcard {
  id: string;
  user_id: string;
  source_kind: "substrate" | "note";
  source_id: string;
  source_title: string | null;
  front: string;
  back: string;
  tags: string[];
  repetitions: number;
  easiness: number;
  interval_days: number;
  due_at: string;
  created_at: string;
  updated_at: string;
}

export type Rating = "again" | "hard" | "good" | "easy";

export const RATING_LABELS: Record<Rating, string> = {
  again: "忘记",
  hard: "困难",
  good: "记得",
  easy: "简单",
};

export function useFlashcards(dueOnly = true, limit = 50) {
  return useQuery({
    queryKey: ["flashcards", dueOnly, limit],
    queryFn: () =>
      apiClient.get<Flashcard[]>("/api/v1/flashcards", {
        due_only: dueOnly,
        limit,
      }),
  });
}

export function useDueStats() {
  return useQuery({
    queryKey: ["flashcards-due"],
    queryFn: () => apiClient.get<{ due_count: number; next_due: string | null }>("/api/v1/flashcards/due"),
  });
}

export function useGenerateCards() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { source_kind: string; source_id: string; max_cards?: number }) =>
      apiClient.post<{ generated: number; cards: Flashcard[] }>("/api/v1/flashcards/generate", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flashcards"] });
      qc.invalidateQueries({ queryKey: ["flashcards-due"] });
    },
  });
}

export function useReviewCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: Rating }) =>
      apiClient.post<Flashcard>(`/api/v1/flashcards/${id}/review`, { rating }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flashcards"] });
      qc.invalidateQueries({ queryKey: ["flashcards-due"] });
    },
  });
}

export function useDeleteCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/flashcards/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flashcards"] });
      qc.invalidateQueries({ queryKey: ["flashcards-due"] });
    },
  });
}
