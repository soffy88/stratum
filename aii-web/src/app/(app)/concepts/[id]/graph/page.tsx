"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { apiClient } from "@/lib/api-client";
import Link from "next/link";

interface GraphNode {
  id: string;
  type: "concept" | "substrate";
  label?: string;
  title?: string;
}

interface GraphEdge {
  from: string;
  to: string;
  type: string;
}

interface ConceptGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Auto-layout: place center node at origin, radiate others
function buildFlowNodes(nodes: GraphNode[], conceptId: string): Node[] {
  const center = nodes.find((n) => n.id === conceptId);
  const others = nodes.filter((n) => n.id !== conceptId);
  const angleStep = others.length > 0 ? (2 * Math.PI) / others.length : 0;
  const radius = 200;

  const result: Node[] = [];

  if (center) {
    result.push({
      id: center.id,
      position: { x: 0, y: 0 },
      data: { label: center.label ?? center.title ?? center.id },
      style: { background: "var(--color-primary)", color: "#fff", fontWeight: 600 },
    });
  }

  others.forEach((n, i) => {
    const angle = i * angleStep;
    result.push({
      id: n.id,
      position: {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      },
      data: { label: n.label ?? n.title ?? n.id },
      style:
        n.type === "substrate"
          ? { background: "var(--color-surface)", border: "1px solid var(--color-border)" }
          : {},
    });
  });

  return result;
}

function buildFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((e, i) => ({
    id: `e${i}`,
    source: e.from,
    target: e.to,
    label: e.type === "references" ? "关联" : undefined,
    style: { stroke: "var(--color-muted)" },
  }));
}

export default function ConceptGraphPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data, isLoading, error } = useQuery({
    queryKey: ["concept-graph", id],
    queryFn: () => apiClient.get<ConceptGraph>(`/api/v1/concepts/graph/${id}`),
    enabled: !!id,
  });

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--color-muted)]">加载图谱中...</div>;
  }
  if (error || !data) {
    return <div className="p-6 text-sm text-red-600">无法加载图谱</div>;
  }

  const flowNodes = buildFlowNodes(data.nodes, id);
  const flowEdges = buildFlowEdges(data.edges);

  return (
    <div className="flex flex-col h-screen">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)]">
        <Link
          href={`/concepts/${id}`}
          className="text-sm text-[var(--color-muted)] hover:underline"
        >
          ← 返回概念
        </Link>
        <span className="text-sm font-medium">概念图谱</span>
        <span className="text-xs text-[var(--color-muted)]">
          {data.nodes.length} 节点 · {data.edges.length} 关系
        </span>
      </div>
      <div className="flex-1">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          fitView
          attributionPosition="bottom-right"
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </div>
  );
}
