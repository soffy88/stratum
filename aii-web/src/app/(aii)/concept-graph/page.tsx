/**
 * /concept-graph — B仓知识网络审查 · 视图1:概念判同(AII-BREPO-VIZ-SPEC-001)
 * + God Node 检测(AII-KNOWLEDGE-FIRST-SPEC-001 改进一)。
 *
 * ★这不是展示玩具,是给 Wiki 的审查工具——让他用眼睛审"判同对不对"。
 * 数据:GET /api/graph/concepts(discipline/limit/risk_only 过滤)+ /api/graph/node/{id}(详情)
 * + GET /api/graph/god-nodes(高中心性候选)。
 * 已知限制(如实告知,不假装做到):
 *   - risk_flag 目前只基于 alias_count(≥3),decision_id 链路暂空,"跨discipline判据"
 *     当前 schema 不可计算,详见实施计划。
 *   - "一键回溯 A仓原文"目前只到"看到 a_concept_ids"这一步,没有 A仓原文查询接口。
 *   - ★God Node 只是本性路径B候选提示,不是本性认定——高中心性≠有本性;disciplines
 *     字段依赖的 discipline 原始数据质量差(多为per-book哈希/ULID,只做过粗归一),
 *     跨学科信号仍偏弱,详见后端 graph_god_nodes 函数 docstring。
 */
'use client';

import { useEffect, useState } from 'react';
import { OGridFrame, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi, useApiNoArg } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { OKnowledgeGraph } from '@/aii/components/graph/OKnowledgeGraph';
import type { ConceptNodeDetail, GodNode } from '@/aii/types/api';

function ConceptDetailPanel({
  id,
  godNode,
  onClose,
}: {
  id: number;
  godNode?: GodNode;
  onClose: () => void;
}) {
  const [state, run] = useApi(api.getConceptNode);
  useEffect(() => { void run(id); }, [id, run]);
  const d = state.data as ConceptNodeDetail | null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-md h-full overflow-y-auto bg-[color:var(--card)] border-l border-[color:var(--border)] p-5 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold">概念详情</h2>
          <button onClick={onClose} className="text-[color:var(--text-secondary)] text-sm" aria-label="关闭">✕</button>
        </div>
        {state.loading && <OLoadingState rows={3} />}
        {state.error && <OErrorState error={state.error} onRetry={() => void run(id)} />}
        {d && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-medium">{d.label_zh || d.label}</h3>
              {d.risk_flag && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-500 border border-red-500/40">
                  高风险合并
                </span>
              )}
              {godNode?.invariant_candidate && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 border border-amber-500/40">
                  本性路径B候选(仅提示,非认定)
                </span>
              )}
              <span className="text-xs text-[color:var(--text-secondary)]">{d.discipline}</span>
            </div>

            {godNode && (
              <div>
                <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                  God Node 指标
                </h4>
                <p className="text-sm text-[color:var(--text-secondary)]">
                  中心性 {godNode.centrality.toFixed(4)} · 介数 {godNode.betweenness.toFixed(4)} ·
                  入度 {godNode.in_degree} · 邻居学科:{godNode.disciplines.join(', ') || '(无)'}
                </p>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                归并的别名({d.aliases.length})
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {d.aliases.map((a, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--border)]/40">{a}</span>
                ))}
              </div>
            </div>

            {d.discriminative && Object.keys(d.discriminative).length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">判别维度</h4>
                <ul className="text-sm flex flex-col gap-0.5">
                  {Object.entries(d.discriminative).map(([k, v]) => (
                    <li key={k}><span className="text-[color:var(--text-tertiary,#888)]">{k}:</span> {v}</li>
                  ))}
                </ul>
              </div>
            )}

            {d.decision ? (
              <div>
                <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">判同决策</h4>
                <p className="text-sm text-[color:var(--text-secondary)]">
                  {d.decision.decision_type} · {JSON.stringify(d.decision.verdict)}
                </p>
              </div>
            ) : (
              <p className="text-xs text-[color:var(--text-tertiary,#888)]">
                暂无关联的判同决策记录(decision_id 未回填)。
              </p>
            )}

            {d.sources?.a_concept_ids && (
              <div>
                <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                  回溯 A仓(概念 id,暂无原文查询接口)
                </h4>
                <p className="text-sm">{d.sources.a_concept_ids.join(', ')}</p>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] mb-1">
                关联边({d.edges.length})
              </h4>
              <ul className="text-sm flex flex-col gap-0.5">
                {d.edges.map((e) => (
                  <li key={e.id} className="text-[color:var(--text-secondary)]">
                    {e.relation_type} → concept #{e.source === d.id ? e.target : e.source}
                    <span className="text-xs text-[color:var(--text-tertiary,#888)]"> ({e.grade})</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ConceptGraphPage() {
  const [graphState, runGraph] = useApi(api.getConceptGraph);
  const [godState, runGodNodes] = useApi(api.getGodNodes);
  const [themesState, runThemes] = useApiNoArg(api.getThemes);
  const [commState, runCommunities] = useApi(api.getCommunities);
  const [discipline, setDiscipline] = useState('');
  const [riskOnly, setRiskOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showGodNodes, setShowGodNodes] = useState(true);
  const [crossDiscOnly, setCrossDiscOnly] = useState(false);
  const [colorMode, setColorMode] = useState<'discipline' | 'theme' | 'community'>('discipline');
  // ★resolution 是人工旋钮(SPEC §2.2 红线2:社区好坏无客观裁判 → 留人)。这里只负责
  // 让人拖着看效果, 页面绝不基于任何反馈自动搜索"最优值"。
  const [resolution, setResolution] = useState(1.0);

  useEffect(() => {
    void runGraph({ discipline: discipline || undefined, risk_only: riskOnly, limit: 2000 });
  }, [runGraph, discipline, riskOnly]);

  useEffect(() => {
    void runGodNodes({ cross_disc_only: crossDiscOnly, limit: 200 });
  }, [runGodNodes, crossDiscOnly]);

  useEffect(() => {
    void runThemes();
  }, [runThemes]);

  // 只在真的要看预览时才算——Leiden 现算是有成本的, 别人家看学科染色也跟着跑一遍。
  useEffect(() => {
    if (colorMode !== 'community') return;
    void runCommunities({ resolution, min_size: 3 });
  }, [runCommunities, colorMode, resolution]);

  const godNodeById = new Map((godState.data?.god_nodes ?? []).map((g) => [g.concept_id, g]));

  // 预览社区 → 复用跟固化主题同一套染色入参(概念→组id + 组id顺序)。
  const communityConceptMap: Record<string, number> = {};
  for (const c of commState.data?.communities ?? []) {
    for (const m of c.members) communityConceptMap[String(m.concept_id)] = c.community_id;
  }
  const groupIds =
    colorMode === 'community'
      ? (commState.data?.communities ?? []).map((c) => c.community_id)
      : (themesState.data?.themes ?? []).map((t) => t.kc_id);
  const conceptGroup =
    colorMode === 'community' ? communityConceptMap : themesState.data?.concept_theme;

  const disciplines = Array.from(new Set((graphState.data?.nodes ?? []).map((n) => n.discipline))).sort();
  const filtered = graphState.data
    ? {
        ...graphState.data,
        nodes: search
          ? graphState.data.nodes.filter((n) => (n.label_zh || n.label).toLowerCase().includes(search.toLowerCase()))
          : graphState.data.nodes,
      }
    : null;

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">概念判同审查</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          B仓 Layer1 canonical 概念 + 归并别名。红色描边 = 高风险合并(alias_count 超阈值);
          琥珀色 = God Node 本性路径B候选(仅提示,非认定,见下方说明);
          孤立节点不隐藏——碎片是判同没做好的信号,必须看得见。
        </p>
      </header>

      <OGridFrame cols={{ sm: 1, md: 3 }} gap="sm">
        <select
          value={discipline}
          onChange={(e) => setDiscipline(e.target.value)}
          className="text-sm rounded-md border border-[color:var(--border)] bg-[color:var(--card)] px-2 py-1.5"
        >
          <option value="">全部学科</option>
          {disciplines.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={riskOnly} onChange={(e) => setRiskOnly(e.target.checked)} />
          仅看高风险合并
        </label>
        <input
          type="text"
          placeholder="按概念名搜索(客户端过滤)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="text-sm rounded-md border border-[color:var(--border)] bg-[color:var(--card)] px-2 py-1.5"
        />
      </OGridFrame>

      <OGridFrame cols={{ sm: 1, md: 3 }} gap="sm">
        <select
          value={colorMode}
          onChange={(e) => setColorMode(e.target.value as typeof colorMode)}
          className="text-sm rounded-md border border-[color:var(--border)] bg-[color:var(--card)] px-2 py-1.5"
        >
          <option value="discipline">按学科染色</option>
          <option value="theme">按已固化主题染色</option>
          <option value="community">按 Leiden 社区预览染色(现算,未固化)</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showGodNodes} onChange={(e) => setShowGodNodes(e.target.checked)} />
          标记 God Node(高中心性,本性路径B候选提示)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={crossDiscOnly}
            onChange={(e) => setCrossDiscOnly(e.target.checked)}
            disabled={!showGodNodes}
          />
          只看跨学科候选(信号偏弱,discipline 原始数据质量差)
        </label>
      </OGridFrame>

      {colorMode === 'community' && (
        <div className="flex flex-col gap-1 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-3">
          <label className="flex items-center gap-3 text-sm">
            <span className="whitespace-nowrap">resolution {resolution.toFixed(1)}</span>
            <input
              type="range"
              min={0.2}
              max={3}
              step={0.1}
              value={resolution}
              onChange={(e) => setResolution(Number(e.target.value))}
              className="flex-1"
            />
          </label>
          <p className="text-xs text-[color:var(--text-tertiary,#888)]">
            拖动看社区粒度怎么变(大→更碎更多,小→更粗更少)。★这个旋钮只能人调:社区聚得
            好不好没有客观裁判,接口不会自动优化(SPEC §2.2 红线2)。
          </p>
          <p className="text-xs text-amber-600">
            ⚠ 这是【现算预览】,没命名、没落库、刷新即重算——不是结论。调到满意后跑{' '}
            <code>scripts/build_theme_kc.py --resolution {resolution.toFixed(1)}</code> 才会固化成主题KC。
          </p>
          {commState.data && (
            <p className="text-xs text-[color:var(--text-tertiary,#888)]">
              {commState.data.communities.length} 个社区(size≥3) · 全图{' '}
              {commState.data.total_concepts} 概念 · 单例(孤立){commState.data.singleton_count} 个 ·
              modularity {commState.data.modularity?.toFixed(4) ?? '—'}
              (无监督内部指标,不是"划分对不对"的裁判)
            </p>
          )}
          {commState.loading && (
            <p className="text-xs text-[color:var(--text-tertiary,#888)]">重算中…</p>
          )}
        </div>
      )}

      {graphState.error && <OErrorState error={graphState.error} onRetry={() => void runGraph({ discipline: discipline || undefined, risk_only: riskOnly, limit: 2000 })} />}
      {godState.error && <OErrorState error={godState.error} onRetry={() => void runGodNodes({ cross_disc_only: crossDiscOnly, limit: 200 })} />}
      {themesState.error && colorMode === 'theme' && (
        <OErrorState error={themesState.error} onRetry={() => void runThemes()} />
      )}
      {commState.error && colorMode === 'community' && (
        <OErrorState
          error={commState.error}
          onRetry={() => void runCommunities({ resolution, min_size: 3 })}
        />
      )}

      <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-2">
        <OKnowledgeGraph
          data={filtered}
          loading={graphState.loading}
          error={graphState.error ? new Error(graphState.error) : null}
          empty={!!filtered && filtered.nodes.length === 0}
          godNodes={showGodNodes ? godState.data?.god_nodes : undefined}
          colorMode={colorMode}
          conceptTheme={conceptGroup}
          groupIds={groupIds}
          onSelectNode={setSelectedId}
        />
      </div>

      {showGodNodes && godState.data && (
        <p className="text-xs text-[color:var(--text-tertiary,#888)]">
          God Node 候选 {godState.data.god_nodes.length} 个(全图 {godState.data.graph_size} 概念)
        </p>
      )}

      {colorMode === 'theme' && themesState.data && (
        <div className="flex flex-col gap-1">
          {themesState.data.stale && (
            <p className="text-xs text-amber-600">
              ⚠{' '}
              {themesState.data.stale_reason ??
                '固化结果已不完整——需要重跑 scripts/build_theme_kc.py。'}
            </p>
          )}
          {themesState.data.themes.some((t) => t.grade === 'unverified') && (
            <p className="text-xs text-amber-600">
              ⚠ 主题名由 LLM 自动生成(Leiden 聚类 + 自动命名),未经人工审——预览性质,不是定论。
            </p>
          )}
          <p className="text-xs text-[color:var(--text-tertiary,#888)]">
            已固化主题 {themesState.data.themes.length} 个 · 灰色 = 未归入任何已固化主题(社区太小或孤立)
          </p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {themesState.data.themes.slice(0, 12).map((t) => (
              <span key={t.kc_id} className="text-xs text-[color:var(--text-secondary)]">
                {t.theme_name}({t.size}){t.grade === 'unverified' && <sup>未验证</sup>}
              </span>
            ))}
          </div>
        </div>
      )}

      {colorMode === 'community' && commState.data && (
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {/* 预览社区没有主题名——如实显示编号+规模+前几个概念, 不给它编一个名字充数。 */}
          {commState.data.communities.slice(0, 12).map((c) => (
            <span key={c.community_id} className="text-xs text-[color:var(--text-secondary)]">
              社区#{c.community_id}({c.size}):{' '}
              {c.members.slice(0, 3).map((m) => m.label_zh || m.label).join('、')}
            </span>
          ))}
        </div>
      )}

      {graphState.data && (
        <p className="text-xs text-[color:var(--text-tertiary,#888)]">
          {filtered?.nodes.length ?? 0} 个概念 · {filtered?.edges.length ?? 0} 条边
          {graphState.data.truncated && ' · 结果被 limit 截断'}
        </p>
      )}

      {selectedId !== null && (
        <ConceptDetailPanel
          id={selectedId}
          godNode={godNodeById.get(selectedId)}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
