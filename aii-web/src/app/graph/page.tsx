/**
 * /graph — 知识图谱(AII-FRONTEND-DISPLAY-001 §三,核心可视化)。
 *
 * 命门:
 *   - 节点颜色按 grade,大小按 degree
 *   - 边颜色按 relation_type(contradicts 标红)
 *   - rule 边实线 / llm 边虚线 ← 视觉区分可信度(LLM 边是线索)
 * 性能:不画全图(8803 边会卡),默认显示以某 KU 为中心的 N 跳子图。
 *
 * ReactFlow 是重依赖,按 Wiki 指示"项目上再安装"。
 * 这里用动态导入 + 优雅降级:
 *   - 装了 reactflow → 用它渲染(交互拖拽/缩放)
 *   - 没装 → 回退到内置轻量 SVG 力导向布局(只读,但功能完整)
 * 两条路都不阻塞 build。
 */
'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  OSearchBar,
  OEpistemicBadge,
  OFilterChip,
  OLoadingState,
  OErrorState,
  OEmptyState,
  EPISTEMIC_GRADE_LABEL,
  type EpistemicGrade,
  type OFilterChipOption,
} from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import type { SubgraphResponse, GraphNode, GraphEdge, RelationType } from '@/types/api';

// grade → 颜色(命门:可信度色阶)
const GRADE_COLOR: Record<EpistemicGrade, string> = {
  proven:               '#16a34a',
  high:                 '#2563eb',
  moderate:             '#0891b2',
  low:                  '#d97706',
  very_low:             '#a16207',
  unverified:           '#6b7280',
  contradicted:         '#dc2626',
  pending_verification: '#7c3aed',
};
const REL_COLOR: Partial<Record<RelationType, string>> = {
  contradicts: '#dc2626',
  prerequisite_of: '#2563eb',
  special_case_of: '#0891b2',
  supports: '#16a34a',
  references: '#6b7280',
  related_to: '#9ca3af',
};

const REL_OPTS: OFilterChipOption[] = (
  ['references','prerequisite_of','special_case_of','supports','contradicts','related_to'] as RelationType[]
).map(r => ({ value: r, label: r }));

// ── 内置 SVG 降级渲染(无 reactflow 时)──
function SvgGraph({ data, onNodeClick, relFilter }: {
  data: SubgraphResponse;
  onNodeClick: (id: string) => void;
  relFilter: string[];
}) {
  const W = 720, H = 480, cx = W / 2, cy = H / 2;
  const edges = relFilter.length ? data.edges.filter(e => relFilter.includes(e.relation_type)) : data.edges;
  // 放射状布局:中心节点居中,其余环绕(轻量,确定性,不卡)
  const others = data.nodes.filter(n => n.id !== data.center_id);
  const pos: Record<string, { x: number; y: number }> = { [data.center_id]: { x: cx, y: cy } };
  others.forEach((n, i) => {
    const angle = (i / others.length) * Math.PI * 2;
    const r = 170 + (i % 3) * 28;
    pos[n.id] = { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
  });
  const nodeR = (n: GraphNode) => Math.min(22, 7 + n.degree * 1.6);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto rounded-lg border border-[color:var(--border)] bg-[color:var(--card)]" role="img" aria-label="知识子图">
      {/* 边 */}
      {edges.map(e => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return null;
        const color = REL_COLOR[e.relation_type] ?? '#9ca3af';
        return (
          <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={color}
            strokeWidth={e.relation_type === 'contradicts' ? 2 : 1.2}
            strokeDasharray={e.extraction_method === 'llm' ? '4 3' : undefined}
            opacity={0.65}
          />
        );
      })}
      {/* 节点 */}
      {data.nodes.map(n => {
        const p = pos[n.id]; if (!p) return null;
        const isCenter = n.id === data.center_id;
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} style={{ cursor: 'pointer' }} onClick={() => onNodeClick(n.id)}>
            <circle r={nodeR(n)} fill={GRADE_COLOR[n.grade]} opacity={0.9}
              stroke={isCenter ? '#fff' : 'none'} strokeWidth={isCenter ? 2 : 0} />
            <text y={nodeR(n) + 11} textAnchor="middle" fontSize="9" fill="var(--text-secondary,#aaa)">
              {n.label.slice(0, 10)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── ReactFlow 渲染(装了才用,动态导入)──
function ReactFlowGraph({ data, onNodeClick, relFilter, mod }: {
  data: SubgraphResponse; onNodeClick: (id: string) => void; relFilter: string[]; mod: any;
}) {
  const { ReactFlow, Background, Controls } = mod;
  const others = data.nodes.filter(n => n.id !== data.center_id);
  const rfNodes = data.nodes.map((n, i) => {
    const isCenter = n.id === data.center_id;
    const angle = (i / Math.max(1, others.length)) * Math.PI * 2;
    const r = isCenter ? 0 : 220;
    return {
      id: n.id,
      position: { x: 360 + Math.cos(angle) * r, y: 240 + Math.sin(angle) * r },
      data: { label: n.label.slice(0, 14) },
      style: {
        background: GRADE_COLOR[n.grade], color: '#fff', border: isCenter ? '2px solid #fff' : 'none',
        borderRadius: 8, fontSize: 11, width: Math.min(120, 50 + n.degree * 6),
      },
    };
  });
  const edges = relFilter.length ? data.edges.filter(e => relFilter.includes(e.relation_type)) : data.edges;
  const rfEdges = edges.map(e => ({
    id: e.id, source: e.source, target: e.target,
    animated: e.relation_type === 'contradicts',
    style: {
      stroke: REL_COLOR[e.relation_type] ?? '#9ca3af',
      strokeWidth: e.relation_type === 'contradicts' ? 2 : 1.2,
      strokeDasharray: e.extraction_method === 'llm' ? '4 3' : undefined,  // 命门:llm 虚线
    },
  }));
  return (
    <div style={{ height: 480 }} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)]">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView onNodeClick={(_: unknown, n: { id: string }) => onNodeClick(n.id)}>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default function GraphPage() {
  const [state, run] = useApi(api.getSubgraph);
  const [centerId, setCenterId] = useState('');
  const [hops, setHops] = useState(1);
  const [relFilter, setRelFilter] = useState<string[]>([]);
  const [q, setQ] = useState('');
  const [rfMod, setRfMod] = useState<any>(null);
  const [rfTried, setRfTried] = useState(false);
  const [searchState, runSearch] = useApi(api.graphSearch);

  // 启动时取第一个真实 KU 作为初始中心节点(取代硬编码假 ID)
  useEffect(() => {
    api.getKuList({ page_size: 1 }).then(res => {
      if (res.ok && res.data?.items?.length) {
        setCenterId(res.data.items[0].id);
      }
    });
  }, []);

  // 尝试动态加载 reactflow(没装就降级,不报错)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        // @ts-expect-error 可选依赖,项目侧安装后才存在
        const mod = await import('reactflow');
        // reactflow 需要其样式;消费项目装了会自带,这里容错
        if (alive) setRfMod(mod);
      } catch {
        if (alive) setRfMod(null);
      } finally {
        if (alive) setRfTried(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  const load = useCallback(() => {
    if (!centerId) return;
    void run({ ku_id: centerId, hops, limit: 24 });
  }, [centerId, hops, run]);
  useEffect(() => { load(); }, [load]);

  const data = state.data as SubgraphResponse | null;

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">知识图谱 / Knowledge Graph</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          以某 KU 为中心的子图(不画全图,8803 边会卡)。<strong>节点色=可信度,实线=规则边,虚线=LLM 线索边</strong>。
        </p>
      </header>

      {/* 搜索定位中心节点 */}
      <div className="flex gap-2 items-stretch">
        <div className="flex-1">
          <OSearchBar value={q} onChange={setQ} placeholder="搜索 KU 作为图谱中心…" debounceMs={300} />
        </div>
        <button onClick={() => void runSearch({ q, limit: 8 })} className="px-4 py-2 rounded bg-[color:var(--accent,#2563eb)] text-white text-sm font-medium">搜索</button>
      </div>
      {searchState.data && (searchState.data as any).matches?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {(searchState.data as any).matches.map((m: { id: string; label: string; grade: EpistemicGrade }) => (
            <button key={m.id} onClick={() => { setCenterId(m.id); }}
              className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border border-[color:var(--border)] hover:border-[color:var(--accent,#2563eb)]/50">
              <OEpistemicBadge grade={m.grade} compact /> {m.label}
            </button>
          ))}
        </div>
      )}

      {/* 控制:hops + 关系类型筛选 */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-[color:var(--text-secondary)]">展开跳数</span>
          {[1, 2, 3].map(h => (
            <button key={h} onClick={() => setHops(h)}
              className={`px-2.5 py-1 rounded border text-sm ${hops === h ? 'border-[color:var(--accent,#2563eb)] text-[color:var(--accent,#2563eb)]' : 'border-[color:var(--border)]'}`}>
              {h} 跳
            </button>
          ))}
          <span className="text-xs text-[color:var(--text-tertiary,#888)] ml-2">中心:{centerId}</span>
        </div>
        <OFilterChip label="关系类型" options={REL_OPTS} selected={relFilter} onChange={setRelFilter} showAll />
      </div>

      {/* 图例 */}
      <div className="flex flex-wrap gap-3 text-xs text-[color:var(--text-secondary)]">
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#6b7280" strokeWidth="1.5" /></svg> 规则边(可信)</span>
        <span className="flex items-center gap-1"><svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4 3" /></svg> LLM 边(线索)</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#dc2626' }} /> contradicts / contradicted</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full" style={{ background: '#6b7280' }} /> unverified</span>
      </div>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={load} />}
      {!state.loading && data && data.nodes.length === 0 && <OEmptyState title="子图为空" description="换一个中心 KU" />}

      {data && data.nodes.length > 0 && (
        <>
          {rfMod
            ? <ReactFlowGraph data={data} onNodeClick={setCenterId} relFilter={relFilter} mod={rfMod} />
            : <SvgGraph data={data} onNodeClick={setCenterId} relFilter={relFilter} />}
          <p className="text-xs text-[color:var(--text-tertiary,#888)]">
            {rfTried && !rfMod && '提示:未检测到 reactflow,使用内置 SVG 降级渲染(只读)。装 reactflow 后自动启用拖拽/缩放。'}
            {data.truncated && ' 子图已按 limit 截断,点节点可重新以它为中心展开。'}
          </p>
        </>
      )}
    </div>
  );
}
