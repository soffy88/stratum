'use client';

/**
 * OKnowledgeGraph — B仓知识网络审查 · 视图1(概念判同)。AII-BREPO-VIZ-SPEC-001。
 *
 * ★这不是展示玩具,是给 Wiki 的审查工具——审查纪律直接映射成视觉规则(§四,硬性):
 *   - 节点大小 ∝ alias_count(挂了一堆别名的概念一眼可见)。
 *   - risk_flag=true → 固定语义红色描边,不随主题变(风险是信号,不是装饰)。
 *   - grade 可视化铁律:非高置信(proven/high)的边用低饱和度+半透明色区分
 *     (sigma 核心不带虚线边渲染器,用颜色+透明度落地同一条铁律,不额外引入依赖)。
 *   - ★不隐藏孤立节点:degree=0 的概念照常入图,不做任何过滤/移除——碎片是
 *     "宁碎片不错合"的正常产物,是判同没做好的信号,必须看得见。
 *
 * Props 走 OBlockDataProps<T> & OHeavyBlockProps 契约(跟 @helios/blocks 的
 * ONetworkGraph3D 同款——重型/WebGL Block 的标准形状),但组件本身是仓库本地实现
 * (@helios/blocks 是 vendor 进来的预编译包,没法把新组件塞进它内部)。
 *
 * ★God Node(AII-KNOWLEDGE-FIRST-SPEC-001 改进一): godNodes 传入后,高中心性节点
 * 额外加大(在 alias_count 大小基础上叠加), invariant_candidate=true 的用琥珀色
 * 特别标记"本性路径B候选"——但这只是候选提示,不是本性认定(高中心性≠有本性),
 * 优先级低于 risk_flag(红色错合风险信号更紧急,两者都命中时红色赢)。
 *
 * ★主题染色(AII-KNOWLEDGE-FIRST-SPEC-001 改进二,已固化): colorMode='theme' 时,
 * 按 rf.refined_theme_kc 固化的社区(themes/conceptTheme)分配颜色,不再按 discipline
 * 着色——discipline 原始数据质量差(见后端 _normalize_discipline),Leiden 社区是从
 * 概念间实际的边关系算出来的,信号更真实。不属于任何已固化主题的概念(社区太小被
 * min_size 过滤掉,或本身就是孤立概念)保留灰色,不强行归到某个主题——不属于任何
 * 主题不是 bug,是"这批概念确实还没形成够大的可命名聚类"的真实反映。
 * risk_flag 红色描边在任何 colorMode 下都优先(风险信号不该被颜色模式掩盖)。
 */

import { useEffect, useRef, useState } from 'react';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import Sigma from 'sigma';
import {
  useHeliosChartColors,
  resolveBlockState,
  OLoadingState,
  OErrorState,
  OEmptyState,
  type OBlockDataProps,
  type OHeavyBlockProps,
} from '@helios/blocks';
import type { ConceptGraphResponse, ConceptNode, GodNode, Theme } from '@/aii/types/api';

// 风险是语义信号,不是装饰色——固定值,不随主题切换。
const RISK_COLOR = '#dc2626';
// 本性路径B候选——琥珀色,同样固定语义色,跟 risk_flag 的红做视觉区分(不是"错",是"值得看")。
const GOD_NODE_COLOR = '#f59e0b';
// 不属于任何已固化主题的概念——中性灰,不是"错误"色,只是"暂无主题归属"。
const NO_THEME_COLOR = '#9ca3af';
const HIGH_CONFIDENCE_GRADES = new Set(['proven', 'high']);

export interface OKnowledgeGraphProps
  extends OBlockDataProps<ConceptGraphResponse>,
    OHeavyBlockProps {
  height?: string | number;
  /** God Node 检测结果(可选)——为空时组件退化成纯概念判同视图,不影响原有渲染。 */
  godNodes?: GodNode[];
  /** 按学科(默认)或按已固化主题社区染色。 */
  colorMode?: 'discipline' | 'theme';
  /** colorMode='theme' 时用——概念的社区归属(concept_id → kc_id)。 */
  conceptTheme?: Record<string, number>;
  /** colorMode='theme' 时用——主题列表(取 kc_id 顺序分配色板,跟图例保持一致)。 */
  themes?: Theme[];
  /** 点击节点时回调概念 id(用于打开详情面板)。 */
  onSelectNode?: (id: number) => void;
}

/**
 * @helios/blocks 的 useHeliosChartColors() 读的是计算后的 CSS 变量原始值——当前主题
 * 用 lab()/oklch() 定义颜色时,读出来的就是 "lab(35.76% -4.01 -33.73)" 这种字符串。
 * sigma 的 WebGL 颜色解析器只认 hex/rgb(a),塞一个它不认识的格式会静默retreat成黑色
 * ——这正是"节点全黑成一坨"的根因。用 canvas 2D 走一遍颜色解析(getImageData 拿到
 * 浏览器实际算出的 sRGB 分量),把任意 CSS 颜色格式规整成 sigma 认识的 rgba()。
 */
function resolveCssColor(cssColor: string, alpha = 1): string {
  if (typeof document === 'undefined') return cssColor;
  const canvas = document.createElement('canvas');
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext('2d');
  if (!ctx) return cssColor;
  ctx.fillStyle = cssColor;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function buildGraph(
  data: ConceptGraphResponse,
  colors: ReturnType<typeof useHeliosChartColors>,
  godNodeMap: Map<number, GodNode>,
  colorMode: 'discipline' | 'theme',
  conceptTheme: Record<string, number>,
  themes: Theme[]
) {
  const graph = new Graph({ multi: true, type: 'directed' });
  const maxAlias = Math.max(1, ...data.nodes.map((n) => n.alias_count));
  const maxCentrality = Math.max(0.0001, ...Array.from(godNodeMap.values(), (g) => g.centrality));

  const disciplines = Array.from(new Set(data.nodes.map((n) => n.discipline)));
  const disciplineColor = (d: string) =>
    resolveCssColor(colors.series[disciplines.indexOf(d) % colors.series.length]);
  // 主题色板按 kc_id 在 themes 列表里的顺序取,跟图例(themes 列表本身)保持一一对应。
  const themeIds = themes.map((t) => t.kc_id);
  const themeColor = (kcId: number) =>
    resolveCssColor(colors.series[themeIds.indexOf(kcId) % colors.series.length]);
  const noThemeColor = resolveCssColor(NO_THEME_COLOR);
  const riskColor = resolveCssColor(RISK_COLOR);
  const godColor = resolveCssColor(GOD_NODE_COLOR);
  const highConfidenceColor = resolveCssColor(colors.foreground);
  const lowConfidenceColor = resolveCssColor(colors.mutedForeground, 0.4);

  for (const n of data.nodes) {
    const god = godNodeMap.get(n.id);
    const kcId = conceptTheme[String(n.id)];
    // God Node 在 alias_count 大小基础上叠加中心性带来的加成,两个信号不互相掩盖。
    const godBoost = god ? 4 + (god.centrality / maxCentrality) * 10 : 0;
    const baseColor =
      colorMode === 'theme'
        ? kcId !== undefined
          ? themeColor(kcId)
          : noThemeColor
        : god?.invariant_candidate
          ? godColor
          : disciplineColor(n.discipline);
    graph.addNode(String(n.id), {
      label: n.label_zh || n.label,
      // 节点大小 ∝ alias_count("挂了一堆别名"错合信号) + God Node 中心性加成。
      size: 4 + (n.alias_count / maxAlias) * 12 + godBoost,
      // 优先级: risk_flag(红,错合风险) 恒赢; 其余按 colorMode 分派(见上方 baseColor)。
      color: n.risk_flag ? riskColor : baseColor,
      x: Math.random(),
      y: Math.random(),
      concept: n,
      godNode: god ?? null,
    });
  }

  for (const e of data.edges) {
    const s = String(e.source);
    const t = String(e.target);
    if (s === t || !graph.hasNode(s) || !graph.hasNode(t)) continue;
    const highConfidence = HIGH_CONFIDENCE_GRADES.has(e.grade);
    graph.addEdge(s, t, {
      size: 0.5 + e.strength * 2,
      // grade 铁律:非高置信 = 半透明,不能看起来跟 confirmed 一样实在。
      color: highConfidence ? highConfidenceColor : lowConfidenceColor,
    });
  }

  return graph;
}

function FallbackNodeList({ data }: { data: ConceptGraphResponse }) {
  return (
    <ul className="max-h-[560px] overflow-y-auto text-sm flex flex-col gap-1 p-2">
      {data.nodes.map((n) => (
        <li
          key={n.id}
          className={`px-2 py-1 rounded ${n.risk_flag ? 'border border-red-500/60 text-red-500' : ''}`}
        >
          {n.label_zh || n.label}
          <span className="ml-2 text-xs text-[color:var(--text-tertiary,#888)]">
            ({n.discipline}, {n.alias_count} 别名)
          </span>
        </li>
      ))}
    </ul>
  );
}

export function OKnowledgeGraph({
  data,
  loading,
  error,
  empty,
  height = 560,
  fallback,
  godNodes,
  colorMode = 'discipline',
  conceptTheme,
  themes,
  onSelectNode,
  className,
}: OKnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const colors = useHeliosChartColors(containerRef.current);
  const [renderFailed, setRenderFailed] = useState(false);

  const state = resolveBlockState({ data, loading, error, empty });

  useEffect(() => {
    if (state !== 'ready' || !data || !containerRef.current) return;
    setRenderFailed(false);

    let renderer: Sigma | null = null;
    try {
      const godNodeMap = new Map((godNodes ?? []).map((g) => [g.concept_id, g]));
      const graph = buildGraph(data, colors, godNodeMap, colorMode, conceptTheme ?? {}, themes ?? []);
      forceAtlas2.assign(graph, { iterations: 100 });
      renderer = new Sigma(graph, containerRef.current, {
        renderLabels: true,
        labelRenderedSizeThreshold: 6,
      });
      sigmaRef.current = renderer;
      if (onSelectNode) {
        renderer.on('clickNode', ({ node }) => {
          const concept = graph.getNodeAttributes(node).concept as ConceptNode;
          onSelectNode(concept.id);
        });
      }
    } catch {
      // WebGL 不可用等重型渲染失败场景 → 走 fallback(OHeavyBlockProps 契约)。
      setRenderFailed(true);
    }

    return () => {
      renderer?.kill();
      sigmaRef.current = null;
    };
    // colors 随主题切换变化时需要重建(节点/边颜色要跟着换),data/godNodes/onSelectNode 变化同理。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, data, colors, godNodes, colorMode, conceptTheme, themes]);

  if (state === 'loading') return <OLoadingState rows={8} />;
  if (state === 'error') return <OErrorState error={error!} />;
  if (state === 'empty') return <OEmptyState title="没有概念数据" />;

  if (renderFailed) return <>{fallback ?? (data && <FallbackNodeList data={data} />)}</>;

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height, width: '100%' }}
      data-testid="o-knowledge-graph"
    />
  );
}
