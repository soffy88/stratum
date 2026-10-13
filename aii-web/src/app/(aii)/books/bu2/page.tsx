/**
 * /books/bu2 — BU2 书级理解列表（/api/v1/bu）。
 */
'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { bu2, type Bu2ListItem } from '@/aii/lib/bu2-client';

export default function Bu2ListPage() {
  const [items, setItems] = useState<Bu2ListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    bu2.list().then(setItems).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  };
  useEffect(load, []);

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">BU2 书级理解</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          每条主张都与原文锚定比对；未被原文支持的主张标为“模型推断”，不作为原书陈述呈现。
        </p>
      </header>
      {error && <OErrorState error={error} onRetry={load} />}
      {!error && items === null && <OLoadingState rows={4} />}
      {items && items.length === 0 && <OEmptyState title="暂无 BU2 理解" description="完成一次书籍理解后会出现在这里" />}
      {items && items.length > 0 && (
        <ul className="flex flex-col divide-y divide-[color:var(--border)]">
          {items.map(it => (
            <li key={it.id}>
              <Link href={`/books/bu2/${encodeURIComponent(it.run_id)}`} className="flex items-center justify-between gap-3 py-3 hover:opacity-80">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[15px] font-medium">{it.book_title}</span>
                  <span className="text-xs text-[color:var(--text-secondary)]">{it.summary} · v{it.version}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${it.status === 'VERIFIED' ? 'bg-emerald-500/15 text-emerald-600' : 'bg-amber-500/15 text-amber-600'}`}>
                  {it.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
