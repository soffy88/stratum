"use client";

import { useState } from "react";
import {
  RATING_LABELS,
  type Flashcard,
  type Rating,
  useDeleteCard,
  useDueStats,
  useFlashcards,
  useGenerateCards,
  useReviewCard,
} from "@/lib/adapters/flashcards";

export default function FlashcardsPage() {
  const [dueOnly, setDueOnly] = useState(true);
  const [showAnswer, setShowAnswer] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);

  const { data: cards = [], isLoading } = useFlashcards(dueOnly);
  const { data: due } = useDueStats();
  const review = useReviewCard();
  const remove = useDeleteCard();
  const generate = useGenerateCards();

  const [genSource, setGenSource] = useState({ kind: "note", id: "" });
  const [genMsg, setGenMsg] = useState("");

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  const dueCount = due?.due_count ?? 0;
  const card = cards[current];

  const handleRating = (rating: Rating) => {
    if (!card) return;
    review.mutate({ id: card.id, rating });
    setShowAnswer(null);
    setCurrent((i) => Math.min(i + 1, Math.max(cards.length - 1, 0)));
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">闪卡复习</h1>
        <span className="text-sm text-[var(--color-muted)]">
          今日到期 <b className="text-[var(--color-primary)]">{dueCount}</b> 张
        </span>
      </div>

      {/* 生成 */}
      <div className="p-4 border border-[var(--color-border)] rounded space-y-3">
        <p className="text-sm font-medium">从笔记 / 文档生成闪卡</p>
        <div className="flex gap-2">
          <select
            value={genSource.kind}
            onChange={(e) => setGenSource({ ...genSource, kind: e.target.value })}
            className="border border-[var(--color-border)] rounded px-2 py-1.5 text-sm"
          >
            <option value="note">笔记 (ID)</option>
            <option value="substrate">文档 (ID)</option>
          </select>
          <input
            value={genSource.id}
            onChange={(e) => setGenSource({ ...genSource, id: e.target.value })}
            placeholder="来源 ID"
            className="flex-1 border border-[var(--color-border)] rounded px-3 py-1.5 text-sm"
          />
          <button
            onClick={() => {
              if (!genSource.id.trim()) return;
              setGenMsg("生成中...");
              generate.mutate(
                { source_kind: genSource.kind, source_id: genSource.id.trim() },
                {
                  onSuccess: (r) => setGenMsg(`已生成 ${r.generated} 张卡片`),
                  onError: () => setGenMsg("生成失败"),
                },
              );
            }}
            className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm"
          >
            生成
          </button>
        </div>
        {genMsg && <p className="text-xs text-[var(--color-muted)]">{genMsg}</p>}
      </div>

      {/* 复习区 */}
      {cards.length === 0 ? (
        <p className="text-center text-[var(--color-muted)] py-12">
          {dueOnly ? "没有到期卡片。可切换查看全部。" : "还没有闪卡。"}
        </p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-[var(--color-muted)]">
            <span>
              {current + 1} / {cards.length}
              {card?.source_title ? ` · ${card.source_title}` : ""}
            </span>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={dueOnly} onChange={(e) => { setDueOnly(e.target.checked); setCurrent(0); }} />
              仅到期
            </label>
          </div>

          <div className="p-6 border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
            <p className="text-lg font-medium">{card.front}</p>
            {showAnswer === card.id && (
              <p className="mt-4 pt-4 border-t border-[var(--color-border)] text-[var(--color-text)]">
                {card.back}
              </p>
            )}
          </div>

          {showAnswer === card.id ? (
            <div className="flex gap-2 justify-center">
              {(["again", "hard", "good", "easy"] as Rating[]).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  className="px-4 py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-primary)] hover:text-white"
                >
                  {RATING_LABELS[r]}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex gap-2 justify-center">
              <button
                onClick={() => setShowAnswer(card.id)}
                className="px-6 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
              >
                显示答案
              </button>
              <button
                onClick={() => remove.mutate(card.id)}
                className="px-4 py-2 border border-[var(--color-border)] rounded text-sm text-[var(--color-muted)]"
              >
                删除
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
