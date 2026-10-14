/**
 * /books/bu2/[runId] — BU2 详情：质量门 + 六维、章节主张（支持/模型推断）、
 * 重建论证链、证据引文+定位、推理图/论证图、概念演化。
 */
'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { OLoadingState, OErrorState } from '@helios/blocks';
import {
  bu2,
  type Bu2Argument,
  type Bu2ChapterDetail,
  type Bu2Detail,
  type Bu2Evidence,
  type Bu2Evolution,
  type Bu2GuideStep,
  type Bu2Graph,
  type Bu2QualityGates,
  type Bu2Synthesis,
} from '@/aii/lib/bu2-client';

type Tab = 'guide' | 'chapters' | 'arguments' | 'evidence' | 'graph' | 'evolution' | 'synthesis';
const TABS: Array<[Tab, string]> = [
  ['guide', '学习导览'],
  ['chapters', '章节主张'],
  ['arguments', '论证链'],
  ['evidence', '证据'],
  ['graph', '图谱'],
  ['evolution', '概念演化'],
  ['synthesis', '综合'],
];

const DIM_LABEL: Record<string, string> = {
  accuracy: "准确性", coverage: "覆盖", depth: "深度",
  traceability: "可追溯", cross_chapter: "跨章", expression: "表达",
};

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    setError(null);
    setData(null);
    fn().then(setData).catch(e => setError(errMsg(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(load, [load]);
  return { data, error, reload: load };
}

function SupportBadge({ supported }: { supported: boolean | null }) {
  if (supported === false)
    return <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 shrink-0">模型推断</span>;
  if (supported === true)
    return <span className="text-[11px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 shrink-0">原文支持</span>;
  return <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-500/15 text-zinc-500 shrink-0">未校验</span>;
}

function Quote({ ev }: { ev: Bu2Evidence }) {
  return (
    <blockquote className="border-l-2 border-[color:var(--border)] pl-3 flex flex-col gap-1">
      <p className="text-sm leading-relaxed whitespace-pre-wrap line-clamp-6">{ev.quote}</p>
      <span className="text-[11px] text-[color:var(--text-secondary)]">
        定位 {ev.chapter_id ? `${ev.chapter_id} · ` : ''}{ev.locator}
        {ev.strength ? ` · ${ev.strength}` : ''}
        {ev.verified === false ? ' · 未通过校验' : ev.verified ? ' · 已校验' : ''}
      </span>
    </blockquote>
  );
}

function GatesPanel({ g }: { g: Bu2QualityGates }) {
  const six = g.six_dimension;
  const dims = (six?.evidence as { dimensions?: Record<string, number> } | null)?.dimensions;
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">质量门 H1–H7</h2>
        <span className={`text-xs ${g.all_passed ? 'text-emerald-600' : 'text-red-600'}`}>
          {g.all_passed ? '全部通过' : '存在未通过项'}
        </span>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {g.hard_gates.map(h => (
          <li key={h.gate_number} className="flex gap-2 text-xs">
            <span className={h.status === 'PASS' ? 'text-emerald-600' : 'text-red-600'}>{h.status === 'PASS' ? '✓' : '✗'}</span>
            <span className="font-medium shrink-0">H{h.gate_number}</span>
            <span className="text-[color:var(--text-secondary)]">{h.detail}</span>
          </li>
        ))}
      </ul>
      {six && (
        <div className="flex flex-col gap-2 pt-2 border-t border-[color:var(--border)]">
          <span className="text-sm font-semibold">六维评分 {six.score?.toFixed(2)} / 10</span>
          {dims && (
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {Object.entries(dims).map(([k, v]) => (
                <div key={k} className="flex flex-col items-center rounded bg-[color:var(--muted,#f4f4f5)] py-1.5">
                  <span className="text-base font-semibold">{Number(v).toFixed(1)}</span>
                  <span className="text-[11px] text-[color:var(--text-secondary)]">{DIM_LABEL[k] ?? k}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ChaptersTab({ runId, d }: { runId: string; d: Bu2Detail }) {
  const [open, setOpen] = useState<string | null>(null);
  const [ch, setCh] = useState<Bu2ChapterDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    setCh(null);
    setErr(null);
    bu2.chapter(runId, open).then(setCh).catch(e => setErr(errMsg(e)));
  }, [runId, open]);
  return (
    <ul className="flex flex-col divide-y divide-[color:var(--border)]">
      {d.chapters.map(c => (
        <li key={c.chapter_id} className="py-2.5 flex flex-col gap-2">
          <button className="flex items-center justify-between text-left gap-3" onClick={() => setOpen(open === c.chapter_id ? null : c.chapter_id)}>
            <span className="text-[15px]">
              <span className="font-medium mr-2">{c.chapter_id}</span>
              <span className="text-[color:var(--text-secondary)]">{c.chapter_question}</span>
            </span>
            <span className="text-xs text-[color:var(--text-secondary)] shrink-0">
              概念 {c.concepts_introduced} · 论证 {c.arguments_count} · 主张 {c.evidence_count}
            </span>
          </button>
          {open === c.chapter_id && (
            <div className="ml-3 flex flex-col gap-2">
              {err && <OErrorState error={err} />}
              {!err && !ch && <OLoadingState rows={2} />}
              {ch?.chapter_thesis && <p className="text-sm"><span className="font-medium">本章论旨：</span>{ch.chapter_thesis}</p>}
              {ch && (
                <ul className="flex flex-col gap-1.5">
                  {ch.claims.map((cl, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <SupportBadge supported={cl.is_supported} />
                      <span className={cl.is_supported === false ? 'text-[color:var(--text-secondary)] italic' : ''}>{cl.claim}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function ArgumentsTab({ runId }: { runId: string }) {
  const { data, error, reload } = useLoad(() => bu2.arguments(runId), [runId]);
  if (error) return <OErrorState error={error} onRetry={reload} />;
  if (!data) return <OLoadingState rows={4} />;
  return (
    <div className="flex flex-col gap-5">
      <p className="text-xs text-[color:var(--text-secondary)]">共 {data.total} 条重建论证：前提 → 推理步骤 → 结论，附原文引文。</p>
      {data.items.map((a: Bu2Argument) => (
        <article key={a.id} className="flex flex-col gap-2 rounded-lg border border-[color:var(--border)] p-3">
          <div className="flex items-start gap-2">
            <span className="text-[11px] text-[color:var(--text-secondary)] shrink-0 mt-0.5">{a.chapter_id}</span>
            <p className="text-[15px] font-medium flex-1">{a.claim || a.conclusion}</p>
            <SupportBadge supported={a.is_supported} />
          </div>
          {a.premises.length > 0 && (
            <div className="text-sm"><span className="font-medium">前提</span>
              <ul className="list-disc ml-5">{a.premises.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
          )}
          {a.inference_steps.length > 0 && (
            <div className="text-sm"><span className="font-medium">推理</span>
              <ol className="list-decimal ml-5">{a.inference_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            </div>
          )}
          {a.conclusion && <p className="text-sm"><span className="font-medium">结论 </span>{a.conclusion}</p>}
          {a.evidence.map(ev => <Quote key={ev.id} ev={ev} />)}
        </article>
      ))}
    </div>
  );
}

function EvidenceTab({ runId }: { runId: string }) {
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useLoad(() => bu2.evidence(runId, undefined, 50, offset), [runId, offset]);
  if (error) return <OErrorState error={error} onRetry={reload} />;
  if (!data) return <OLoadingState rows={4} />;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-[color:var(--text-secondary)]">共 {data.total} 条持久化证据（引文 + 定位）。</p>
      {data.items.map(ev => <Quote key={ev.id} ev={ev} />)}
      <div className="flex gap-3 text-sm">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))} className="disabled:opacity-40">上一页</button>
        <span className="text-[color:var(--text-secondary)]">{offset + 1}–{Math.min(offset + 50, data.total)}</span>
        <button disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)} className="disabled:opacity-40">下一页</button>
      </div>
    </div>
  );
}

function GraphSummary({ g, title }: { g: Bu2Graph; title: string }) {
  const types: Record<string, number> = {};
  g.nodes.forEach(n => { types[n.node_type] = (types[n.node_type] ?? 0) + 1; });
  const rels: Record<string, number> = {};
  g.edges.forEach(e => { rels[e.relation_type] = (rels[e.relation_type] ?? 0) + 1; });
  const label = new Map(g.nodes.map(n => [n.id, n.label]));
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-[color:var(--border)] p-3">
      <h3 className="text-sm font-semibold">{title}：{g.total_nodes} 节点 / {g.total_edges} 边</h3>
      <p className="text-xs text-[color:var(--text-secondary)]">
        样本节点类型 {Object.entries(types).map(([k, v]) => `${k} ${v}`).join(' · ')}；关系 {Object.entries(rels).map(([k, v]) => `${k} ${v}`).join(' · ')}
      </p>
      <ul className="flex flex-col gap-1 text-xs max-h-72 overflow-y-auto">
        {g.edges.slice(0, 80).map(e => (
          <li key={e.id} className="truncate">
            {label.get(e.source_node_id)} <span className="text-[color:var(--text-secondary)]">—{e.relation_type}→</span> {label.get(e.target_node_id)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function GraphTab({ runId }: { runId: string }) {
  const r = useLoad(() => bu2.graph(runId, 'reasoning'), [runId]);
  const a = useLoad(() => bu2.graph(runId, 'argument'), [runId]);
  return (
    <div className="flex flex-col gap-4">
      {r.error ? <OErrorState error={r.error} onRetry={r.reload} /> : r.data ? <GraphSummary g={r.data} title="推理图" /> : <OLoadingState rows={3} />}
      {a.error ? <OErrorState error={a.error} onRetry={a.reload} /> : a.data ? <GraphSummary g={a.data} title="论证图" /> : <OLoadingState rows={3} />}
    </div>
  );
}

function GuideTab({ runId }: { runId: string }) {
  const { data, error, reload } = useLoad(() => bu2.learningGuide(runId), [runId]);
  if (error) return <OErrorState error={error} onRetry={reload} />;
  if (!data) return <OLoadingState rows={4} />;
  const groups: Array<[string, Bu2GuideStep[]]> = [];
  data.steps.forEach(s => {
    const last = groups[groups.length - 1];
    if (last && last[0] === s.chapter_id) last[1].push(s);
    else groups.push([s.chapter_id, [s]]);
  });
  let n = 0;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-[color:var(--text-secondary)]">
        按依赖排序的学习路径：先学前置概念，再学依赖它们的定理与方法。共 {data.step_count} 步{data.steps.length < data.step_count ? `（显示前 ${data.steps.length} 步）` : ''}。
      </p>
      {data.cycles.length > 0 && <p className="text-xs text-amber-600">{data.cycles.join('；')}</p>}
      {groups.map(([ch, steps], gi) => (
        <section key={`${ch}-${gi}`} className="flex flex-col gap-1.5">
          <h3 className="text-sm font-semibold">{ch}</h3>
          <ol className="flex flex-col gap-1 ml-1">
            {steps.map(s => {
              n += 1;
              return (
                <li key={n} className="flex gap-2 text-sm">
                  <span className="text-[color:var(--text-secondary)] w-10 shrink-0 text-right">{n}.</span>
                  <span className="flex flex-col">
                    <span>
                      <span className={s.kind === 'THEOREM' ? 'font-medium text-indigo-600' : 'font-medium'}>{s.concept}</span>
                      {s.kind === 'THEOREM' && <span className="text-[11px] text-[color:var(--text-secondary)]"> · 定理</span>}
                    </span>
                    {s.requires.length > 0 && (
                      <span className="text-xs text-[color:var(--text-secondary)]">先修：{s.requires.join('、')}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

function EvolutionTab({ runId }: { runId: string }) {
  const { data, error, reload } = useLoad(() => bu2.evolution(runId, 200), [runId]);
  if (error) return <OErrorState error={error} onRetry={reload} />;
  if (!data) return <OLoadingState rows={4} />;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-[color:var(--text-secondary)]">共 {data.total} 条概念引入/重定义记录（显示前 {data.items.length} 条）。</p>
      <ul className="flex flex-col divide-y divide-[color:var(--border)]">
        {data.items.map((e: Bu2Evolution, i) => (
          <li key={i} className="py-2 flex flex-col gap-0.5">
            <span className="text-sm"><span className="font-medium">{e.concept_ref}</span>
              <span className="text-xs text-[color:var(--text-secondary)]"> · {e.chapter_ref} · {e.evolution_type} · v{e.version}</span>
            </span>
            <span className="text-xs text-[color:var(--text-secondary)] line-clamp-2">{e.definition}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SynthesisTab({ runId }: { runId: string }) {
  // The synthesis endpoint returns a bounded summary by default; concepts and
  // claims are paged on demand, one page of 50 at a time.
  const [list, setList] = useState<'concepts' | 'claims' | null>(null);
  const [page, setPage] = useState<Bu2Synthesis | null>(null);
  const [pageErr, setPageErr] = useState<string | null>(null);
  const [loadingPage, setLoadingPage] = useState(false);
  const summary = useLoad(() => bu2.synthesis(runId), [runId]);
  const s = summary.data;

  const loadPage = useCallback(
    (view: 'concepts' | 'claims', offset: number) => {
      setLoadingPage(true);
      setPageErr(null);
      bu2
        .synthesisPage(runId, view, 50, offset)
        .then(setPage)
        .catch((e: unknown) => setPageErr(errMsg(e)))
        .finally(() => setLoadingPage(false));
    },
    [runId],
  );

  if (summary.error) return <OErrorState error={summary.error} onRetry={summary.reload} />;
  if (!s) return <OLoadingState rows={5} />;

  const counts = s.counts;
  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-2 rounded-lg border border-[color:var(--border)] p-4">
        <h2 className="text-sm font-semibold">核心论点</h2>
        <p className="text-sm leading-relaxed">{s.thesis?.core_thesis || '—'}</p>
        {s.thesis?.core_thesis_provenance && (
          <span className="text-[11px] text-[color:var(--text-secondary)]">
            来源 {s.thesis.core_thesis_provenance}
          </span>
        )}
      </section>

      {counts && (
        <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] p-4">
          <h2 className="text-sm font-semibold">规模</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              ['概念', counts.concepts],
              ['主张', counts.claims],
              ['机制', counts.mechanisms],
              ['章节', s.chapters?.chapter_count ?? 0],
            ].map(([k, v]) => (
              <div
                key={String(k)}
                className="flex flex-col items-center rounded bg-[color:var(--muted,#f4f4f5)] py-2"
              >
                <span className="text-lg font-semibold">{String(v)}</span>
                <span className="text-[11px] text-[color:var(--text-secondary)]">{String(k)}</span>
              </div>
            ))}
          </div>
          {s.concept_roles && (
            <div className="flex flex-wrap gap-2 pt-1">
              {Object.entries(s.concept_roles).map(([role, n]) => (
                <span
                  key={role}
                  className="text-[11px] px-2 py-0.5 rounded-full bg-[color:var(--muted,#f4f4f5)]"
                >
                  {role} · {n}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {s.core_concepts && s.core_concepts.length > 0 && (
        <section className="flex flex-col gap-2 rounded-lg border border-[color:var(--border)] p-4">
          <h2 className="text-sm font-semibold">核心概念（{s.core_concepts.length}）</h2>
          <ul className="flex flex-wrap gap-1.5">
            {s.core_concepts.map(c => (
              <li
                key={c.concept_id}
                className="text-xs px-2 py-1 rounded border border-[color:var(--border)]"
                title={c.chapter_refs.join(', ')}
              >
                {c.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] p-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">明细</h2>
          <button
            onClick={() => {
              setList('concepts');
              loadPage('concepts', 0);
            }}
            className={`text-xs px-2 py-1 rounded ${
              list === 'concepts'
                ? 'bg-[color:var(--foreground)] text-[color:var(--background)]'
                : 'border border-[color:var(--border)]'
            }`}
          >
            概念
          </button>
          <button
            onClick={() => {
              setList('claims');
              loadPage('claims', 0);
            }}
            className={`text-xs px-2 py-1 rounded ${
              list === 'claims'
                ? 'bg-[color:var(--foreground)] text-[color:var(--background)]'
                : 'border border-[color:var(--border)]'
            }`}
          >
            主张
          </button>
        </div>
        {pageErr && <p className="text-xs text-red-600">{pageErr}</p>}
        {loadingPage && <OLoadingState rows={3} />}
        {!loadingPage && list && page && (
          <>
            <p className="text-xs text-[color:var(--text-secondary)]">
              共 {page.total ?? 0} 条，第 {(page.offset ?? 0) + 1}–
              {(page.offset ?? 0) +
                (list === 'concepts' ? (page.concepts?.length ?? 0) : (page.claims?.length ?? 0))} 条
            </p>
            {list === 'concepts' &&
              (page.concepts ?? []).map(c => (
                <div
                  key={c.concept_id}
                  className="flex flex-col gap-0.5 py-1.5 border-b border-[color:var(--border)] last:border-0"
                >
                  <span className="text-sm font-medium">
                    {c.label}
                    <span className="text-xs text-[color:var(--text-secondary)]">
                      {' '}
                      · {c.role} · {c.chapter_refs.join(', ')}
                    </span>
                  </span>
                  {c.definition && (
                    <span className="text-xs text-[color:var(--text-secondary)] line-clamp-2">
                      {c.definition}
                    </span>
                  )}
                </div>
              ))}
            {list === 'claims' &&
              (page.claims ?? []).map(c => (
                <div
                  key={c.claim_id}
                  className="flex items-start gap-2 py-1.5 border-b border-[color:var(--border)] last:border-0"
                >
                  <SupportBadge supported={c.is_supported} />
                  <span className="text-sm leading-relaxed">{c.claim}</span>
                </div>
              ))}
            <div className="flex gap-2 pt-1">
              <button
                disabled={(page.offset ?? 0) === 0}
                onClick={() => loadPage(list, (page.offset ?? 0) - 50)}
                className="text-xs px-2 py-1 rounded border border-[color:var(--border)] disabled:opacity-40"
              >
                上一页
              </button>
              <button
                disabled={!page.has_more}
                onClick={() => loadPage(list, (page.offset ?? 0) + 50)}
                className="text-xs px-2 py-1 rounded border border-[color:var(--border)] disabled:opacity-40"
              >
                下一页
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default function Bu2DetailPage() {
  const params = useParams<{ runId: string }>();
  const runId = decodeURIComponent(params.runId);
  const [tab, setTab] = useState<Tab>('guide');
  const detail = useLoad(() => bu2.detail(runId), [runId]);
  const gates = useLoad(() => bu2.gates(runId), [runId]);
  const d = detail.data;

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-5xl mx-auto">
      <Link href="/books/bu2" className="text-sm text-[color:var(--text-secondary)]">← BU2 列表</Link>
      {detail.error && <OErrorState error={detail.error} onRetry={detail.reload} />}
      {!detail.error && !d && <OLoadingState rows={4} />}
      {d && (
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">{d.book_title}</h1>
          <p className="text-sm text-[color:var(--text-secondary)]">
            {d.status} · v{d.version} · {d.chapters.length} 章 · 覆盖 {(d.coverage_score * 100).toFixed(0)}% · 校验 {(d.verification_score * 100).toFixed(0)}%
          </p>
        </header>
      )}
      {gates.data && <GatesPanel g={gates.data} />}
      {gates.error && <p className="text-xs text-red-600">质量门加载失败：{gates.error}</p>}
      <nav className="flex gap-4 border-b border-[color:var(--border)] text-sm">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`pb-2 -mb-px ${tab === k ? 'border-b-2 border-[color:var(--foreground)] font-medium' : 'text-[color:var(--text-secondary)]'}`}>
            {label}
          </button>
        ))}
      </nav>
      {tab === 'guide' && <GuideTab runId={runId} />}
      {tab === 'chapters' && d && <ChaptersTab runId={runId} d={d} />}
      {tab === 'arguments' && <ArgumentsTab runId={runId} />}
      {tab === 'evidence' && <EvidenceTab runId={runId} />}
      {tab === 'graph' && <GraphTab runId={runId} />}
      {tab === 'evolution' && <EvolutionTab runId={runId} />}
      {tab === 'synthesis' && <SynthesisTab runId={runId} />}
    </div>
  );
}
