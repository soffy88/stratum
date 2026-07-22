/**
 * Force-directed layout for ReactFlow graphs, via d3-force.
 *
 * Both graph pages previously hand-computed positions on a fixed circle/radial
 * ring (angle = i/n * 2π) — nodes never overlap-repel, edge length carries no
 * meaning, and dense subgraphs just become an unreadable ring. This runs a
 * real physics simulation to convergence (synchronously, via tickCount manual
 * ticks — no need to animate frame-by-frame for a one-shot subgraph render)
 * and returns final {x, y} positions keyed by node id.
 */
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, type SimulationNodeDatum } from 'd3-force';

export interface ForceLayoutNode { id: string; }
export interface ForceLayoutEdge { source: string; target: string; }

export function computeForceLayout(
  nodes: ForceLayoutNode[],
  edges: ForceLayoutEdge[],
  opts: { width?: number; height?: number; nodeRadius?: number; tickCount?: number; fixedCenterNodeId?: string } = {},
): Record<string, { x: number; y: number }> {
  const width = opts.width ?? 700;
  const height = opts.height ?? 500;
  const nodeRadius = opts.nodeRadius ?? 60;
  const tickCount = opts.tickCount ?? 300;

  if (nodes.length === 0) return {};

  type SimNode = SimulationNodeDatum & { id: string };
  const simNodes: SimNode[] = nodes.map((n) => ({ id: n.id }));
  if (opts.fixedCenterNodeId) {
    const center = simNodes.find((n) => n.id === opts.fixedCenterNodeId);
    if (center) { center.fx = width / 2; center.fy = height / 2; }
  }
  const nodeIds = new Set(simNodes.map((n) => n.id));
  // Drop edges referencing nodes outside this subgraph — d3-force throws on
  // dangling link references instead of silently ignoring them.
  const simLinks = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  const sim = forceSimulation(simNodes)
    .force('charge', forceManyBody().strength(-300))
    .force('link', forceLink(simLinks).id((d: SimulationNodeDatum) => (d as SimNode).id).distance(140))
    .force('center', forceCenter(width / 2, height / 2))
    .force('collide', forceCollide(nodeRadius))
    .stop();

  for (let i = 0; i < tickCount; i++) sim.tick();

  const positions: Record<string, { x: number; y: number }> = {};
  for (const n of simNodes) positions[n.id] = { x: n.x ?? 0, y: n.y ?? 0 };
  return positions;
}
