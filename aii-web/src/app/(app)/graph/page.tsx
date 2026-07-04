'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, { Background, Controls, Handle, Position, type Node, type Edge, type NodeProps } from 'reactflow';
import 'reactflow/dist/style.css';
import { toast } from 'sonner';
import { Search, Share2, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/EmptyState';
import { GraphSkeleton } from '@/components/LoadingSkeleton';
import {
  listEntities, getSubgraph, queryGraph,
  type GraphEntity, type Subgraph, type GraphQueryResult,
} from '@/lib/graph';
import { computeForceLayout } from '@/lib/forceLayout';

const TYPE_COLOR: Record<string, string> = {
  concept: '#3b82f6', // 蓝
  method:  '#22c55e', // 绿
  person:  '#f97316', // 橙
  system:  '#a855f7', // 紫
};

// 自定义节点
function EntityNode({ data }: NodeProps<{ label: string; type: string; description?: string }>) {
  const color = TYPE_COLOR[data.type] ?? '#64748b';
  return (
    <div title={data.description}
      style={{ borderColor: color, color }}
      className="px-3 py-1.5 rounded-lg border-2 bg-background text-xs font-medium shadow-sm">
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      {data.label}
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
}
const nodeTypes = { entityNode: EntityNode };

type MobileTab = 'entities' | 'graph' | 'query';

export default function GraphPage() {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [loadingEntities, setLoadingEntities] = useState(true);
  const [search, setSearch] = useState('');
  const [subgraph, setSubgraph] = useState<Subgraph | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [question, setQuestion] = useState('');
  const [querying, setQuerying] = useState(false);
  const [result, setResult] = useState<GraphQueryResult | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>('entities');

  const loadEntities = useCallback(async (q?: string) => {
    setLoadingEntities(true);
    try {
      const data = await listEntities(q);
      data.sort((a, b) => b.mention_count - a.mention_count);
      setEntities(data);
    } catch { toast.error('加载实体失败'); }
    finally { setLoadingEntities(false); }
  }, []);

  useEffect(() => { loadEntities(); }, [loadEntities]);

  // 搜索防抖
  useEffect(() => {
    const t = setTimeout(() => loadEntities(search || undefined), 300);
    return () => clearTimeout(t);
  }, [search, loadEntities]);

  const selectEntity = async (id: string) => {
    setLoadingGraph(true);
    setMobileTab('graph');
    try { setSubgraph(await getSubgraph(id)); }
    catch { toast.error('加载子图失败'); }
    finally { setLoadingGraph(false); }
  };

  const runQuery = async () => {
    if (!question.trim()) return;
    setQuerying(true);
    setMobileTab('query');
    try { setResult(await queryGraph(question.trim())); }
    catch { toast.error('查询失败'); }
    finally { setQuerying(false); }
  };

  // subgraph → reactflow nodes/edges(力导向布局，d3-force 迭代收敛)
  const { nodes, edges } = useMemo(() => {
    if (!subgraph) return { nodes: [] as Node[], edges: [] as Edge[] };
    const positions = computeForceLayout(
      subgraph.nodes.map(e => ({ id: e.id })),
      subgraph.edges.map(r => ({ source: r.source, target: r.target })),
    );
    const nodes: Node[] = subgraph.nodes.map(e => ({
      id: e.id, type: 'entityNode',
      data: { label: e.name, type: e.type, description: e.description },
      position: positions[e.id] ?? { x: 0, y: 0 },
    }));
    const edges: Edge[] = subgraph.edges.map(r => ({
      id: `${r.source}-${r.target}`, source: r.source, target: r.target,
      label: r.type, animated: false,
      style: { stroke: '#94a3b8' }, labelStyle: { fontSize: 10, fill: '#64748b' },
    }));
    return { nodes, edges };
  }, [subgraph]);

  // ── 三个 panel 内容 ──
  const EntitiesPanel = (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-sm">实体 ({entities.length})</span>
      </div>
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="搜索实体..." className="pl-8 min-h-11" />
      </div>
      <div className="flex-1 overflow-y-auto flex flex-col gap-1">
        {loadingEntities ? (
          <div className="text-sm text-muted-foreground p-4 text-center">加载中…</div>
        ) : entities.length === 0 ? (
          <div className="text-sm text-muted-foreground p-4 text-center">无实体</div>
        ) : entities.map(e => (
          <button key={e.id} onClick={() => selectEntity(e.id)}
            className="text-left p-2 rounded-lg hover:bg-muted flex flex-col gap-0.5 min-h-11">
            <span className="text-sm font-medium">{e.name}</span>
            <span className="flex items-center gap-2 text-xs text-muted-foreground">
              <span style={{ color: TYPE_COLOR[e.type] ?? '#64748b' }}>{e.type}</span>
              <span>×{e.mention_count}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );

  const GraphPanel = (
    <div className="h-full min-h-[400px] border rounded-lg overflow-hidden">
      {loadingGraph ? <GraphSkeleton /> : !subgraph ? (
        <EmptyState icon={<Share2 />} title="选择一个实体" description="点左侧实体查看其知识子图。" />
      ) : (
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
          <Background gap={16} size={1} />
          <Controls />
        </ReactFlow>
      )}
    </div>
  );

  const QueryPanel = (
    <div className="flex flex-col gap-3 h-full">
      <span className="font-semibold text-sm">图谱查询</span>
      <div className="flex flex-col gap-2">
        <Input value={question} onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') runQuery(); }}
          placeholder="输入问题，例如: Cooper pairing 和 GL 有什么关系" className="min-h-11" />
        <Button onClick={runQuery} disabled={querying || !question.trim()} className="min-h-11">
          {querying ? '查询中…' : <><Send className="w-4 h-4 mr-1" /> 查询</>}
        </Button>
      </div>

      {result && (
        <div className="flex flex-col gap-4 overflow-y-auto">
          <div>
            <div className="text-xs font-semibold text-muted-foreground mb-1">答案</div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
          </div>
          {result.entities_used?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-1">涉及实体</div>
              <div className="flex flex-wrap gap-1">
                {result.entities_used.map((e, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded bg-muted">{e}</span>
                ))}
              </div>
            </div>
          )}
          {result.sources?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-1">来源文档</div>
              <ul className="text-sm flex flex-col gap-1">
                {result.sources.map((s, i) => <li key={i} className="text-muted-foreground">· {s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="p-4 sm:p-6 h-[calc(100dvh-3.5rem)] flex flex-col">
      <h1 className="text-xl font-bold mb-4">知识图谱</h1>

      {/* 移动端 Tab 切换 */}
      <div className="flex md:hidden gap-1 mb-3">
        {([['entities', '实体'], ['graph', '图谱'], ['query', '查询']] as [MobileTab, string][]).map(([id, label]) => (
          <button key={id} onClick={() => setMobileTab(id)}
            className={`flex-1 py-2 rounded-lg text-sm min-h-11 ${mobileTab === id ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* 桌面端三栏 */}
      <div className="hidden md:grid grid-cols-[260px_1fr_300px] gap-4 flex-1 min-h-0">
        <div className="overflow-hidden">{EntitiesPanel}</div>
        {GraphPanel}
        <div className="overflow-hidden">{QueryPanel}</div>
      </div>

      {/* 移动端单 panel */}
      <div className="md:hidden flex-1 min-h-0">
        {mobileTab === 'entities' && EntitiesPanel}
        {mobileTab === 'graph' && GraphPanel}
        {mobileTab === 'query' && QueryPanel}
      </div>
    </div>
  );
}
