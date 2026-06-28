/**
 * /book — 书级理解 BU(书的入口)。信息架构: 书 → BU(整体) → KC(主题) → KU(讲透)。
 * 命门: BU 是 AII 综合,非原文断言; 中文主显简体,英文原文折叠。
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { MathText } from '@/aii/components/MathText';
import type { BuData, BuFacets, BookInfo } from '@/aii/types/api';

const FACETS: { key: keyof BuFacets; label: string; icon: string }[] = [
  { key: 'soul', label: '一句话灵魂', icon: '◎' },
  { key: 'positioning', label: '背景定位', icon: '⌖' },
  { key: 'question', label: '根本问题', icon: '?' },
  { key: 'skeleton', label: '知识骨架', icon: '⊹' },
  { key: 'thinking', label: '思维方式', icon: '⟳' },
  { key: 'for_whom', label: '适合谁 / 能干什么', icon: '☻' },
  { key: 'boundary', label: '诚实边界 / 不讲什么', icon: '∂' },
];

function Facet({ label, icon, zh, en }: { label: string; icon: string; zh: string; en: string }) {
  const [showEn, setShowEn] = useState(false);
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-[color:var(--accent,#2563eb)] text-base">{icon}</span>
        <h3 className="text-sm font-semibold">{label}</h3>
      </div>
      <MathText text={zh} className="text-sm leading-relaxed" />
      {en && (
        <>
          <button
            onClick={() => setShowEn(v => !v)}
            className="self-start text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--accent,#2563eb)] flex items-center gap-1"
          >
            <span className="inline-block w-3">{showEn ? '▾' : '▸'}</span> 英文原文
          </button>
          {showEn && (
            <MathText text={en} className="text-sm leading-relaxed text-[color:var(--text-secondary)] border-l-2 border-[color:var(--border)] pl-2" />
          )}
        </>
      )}
    </div>
  );
}

export default function BookPage() {
  const [state, run] = useApi(api.getBookBu);
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [substrate, setSubstrate] = useState('microecon_en_full_v2');
  useEffect(() => { api.getBooks().then(r => { if (r.ok && r.data) setBooks(r.data.items); }); }, []);
  useEffect(() => { void run(substrate); }, [run, substrate]);
  const bu = state.data as BuData | null;

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-4xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">书级理解 / Book Understanding</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          先选书 → 看 BU 懂这本书是什么、值不值得读 → 再选 KC 主题 → 读 KU 讲透知识。
          <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-[color:var(--alert-warn-bg,#fef3c7)] text-[color:var(--alert-warn-fg,#78350f)] border border-[color:var(--alert-warn,#d97706)]/40">AII 综合 · 非原文断言</span>
        </p>
        {books.length > 0 && (
          <div className="flex gap-2 mt-1 flex-wrap">
            {books.map(b => (
              <button key={b.substrate_id} onClick={() => setSubstrate(b.substrate_id)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  substrate === b.substrate_id
                    ? 'bg-[color:var(--accent,#2563eb)]/15 text-[color:var(--accent,#2563eb)] border-[color:var(--accent,#2563eb)]/40'
                    : 'border-[color:var(--border)] text-[color:var(--text-secondary)]'}`}>
                {b.title} · {b.ku_count} KU
              </button>
            ))}
          </div>
        )}
      </header>

      {state.loading && <OLoadingState rows={5} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(substrate)} />}

      {bu && (
        <>
          <div className="rounded-lg border border-[color:var(--accent,#2563eb)]/30 bg-[color:var(--accent,#2563eb)]/5 p-4">
            <div className="text-base font-medium leading-relaxed">{bu.facets_zh.soul}</div>
            <div className="flex gap-4 mt-3 text-xs text-[color:var(--text-secondary)]">
              <span>{bu.n_ku} 讲透 KU</span>
              <span>{bu.n_kc_chapter} 章节 KC</span>
              <span>{bu.n_kc_spectral} 谱社区 KC</span>
            </div>
            <div className="flex gap-2 mt-3">
              <Link href={`/clusters?substrate=${substrate}`} className="text-xs px-3 py-1 rounded-full border border-[color:var(--border)] hover:border-[color:var(--accent,#2563eb)]/50">→ 看主题 KC</Link>
              <Link href={`/knowledge?substrate=${substrate}`} className="text-xs px-3 py-1 rounded-full border border-[color:var(--border)] hover:border-[color:var(--accent,#2563eb)]/50">→ 读讲透 KU</Link>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {FACETS.filter(f => f.key !== 'soul').map(f => (
              <Facet key={f.key} label={f.label} icon={f.icon}
                zh={bu.facets_zh[f.key] || ''} en={bu.facets_en?.[f.key] || ''} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
