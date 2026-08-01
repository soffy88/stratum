"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getLayerStats,
  fsTree,
  fsRead,
  fsFind,
  type LayerId,
  type LayerStats,
  type FsNode,
  type LayerContent,
} from "@/lib/adapters/layers";

// ---------------------------------------------------------------------------
// Tree node component (recursive)
// ---------------------------------------------------------------------------

function TreeNode({
  node,
  depth,
  expanded,
  selected,
  onToggle,
  onSelect,
}: {
  node: FsNode;
  depth: number;
  expanded: Set<string>;
  selected: string | null;
  onToggle: (uri: string) => void;
  onSelect: (node: FsNode) => void;
}) {
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expanded.has(node.uri);
  const isSelected = selected === node.uri;

  const icon =
    node.type === "directory"
      ? isExpanded
        ? "📂"
        : "📁"
      : node.type === "ku"
        ? "🧠"
        : "📄";

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) onToggle(node.uri);
          onSelect(node);
        }}
        className={`w-full text-left flex items-center gap-1.5 py-1 px-2 rounded text-sm hover:bg-[var(--color-border)]/40 transition ${
          isSelected ? "bg-[var(--color-border)]/60 font-medium" : ""
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        title={node.uri}
      >
        {hasChildren && (
          <span className="text-[10px] text-[var(--color-muted)] w-3 shrink-0">
            {isExpanded ? "▼" : "▶"}
          </span>
        )}
        {!hasChildren && <span className="w-3 shrink-0" />}
        <span className="shrink-0">{icon}</span>
        <span className="truncate">{node.name}</span>
        {node.ref_id && (
          <span className="text-[10px] text-[var(--color-muted)] ml-auto shrink-0">
            {node.ref_id.slice(0, 8)}
          </span>
        )}
      </button>
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.uri}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              selected={selected}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function LayersPage() {
  // Stats
  const [stats, setStats] = useState<LayerStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Tree
  const [treeNodes, setTreeNodes] = useState<FsNode[]>([]);
  const [treeLoading, setTreeLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<FsNode | null>(null);

  // Content viewer
  const [activeLayer, setActiveLayer] = useState<LayerId>("L0");
  const [content, setContent] = useState<LayerContent | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"name" | "content" | "semantic">("name");
  const [searchResults, setSearchResults] = useState<FsNode[] | null>(null);
  const [searching, setSearching] = useState(false);

  // ---------------------------------------------------------------------------
  // Load stats + tree on mount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    setStatsLoading(true);
    getLayerStats().then((s) => {
      setStats(s);
      setStatsLoading(false);
    });

    setTreeLoading(true);
    fsTree("viking://resources/", 2).then((res) => {
      setTreeNodes(res?.nodes ?? []);
      setTreeLoading(false);
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Load content when selection or layer changes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!selected?.ref_id) {
      setContent(null);
      return;
    }
    if (selected.type === "directory") {
      setContent(null);
      return;
    }

    setContentLoading(true);
    const layer = activeLayer;

    fsRead(selected.uri, layer).then((c) => {
      setContent(c);
      setContentLoading(false);
    });
  }, [selected, activeLayer]);

  // ---------------------------------------------------------------------------
  // Tree interaction
  // ---------------------------------------------------------------------------

  const toggleExpand = useCallback((uri: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  }, []);

  const handleSelect = useCallback((node: FsNode) => {
    setSelected(node);
    setActiveLayer("L0");
  }, []);

  // ---------------------------------------------------------------------------
  // Search
  // ---------------------------------------------------------------------------

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    const res = await fsFind(searchQuery.trim(), searchMode);
    // fsFind returns unknown; try to interpret as array of nodes
    if (Array.isArray(res)) {
      setSearchResults(res as FsNode[]);
    } else if (res && typeof res === "object" && "results" in (res as Record<string, unknown>)) {
      setSearchResults((res as Record<string, unknown>).results as FsNode[]);
    } else {
      setSearchResults([]);
    }
    setSearching(false);
  }, [searchQuery, searchMode]);

  // ---------------------------------------------------------------------------
  // Coverage helpers
  // ---------------------------------------------------------------------------

  const pct = (n: number, d: number) =>
    d > 0 ? `${Math.round((n / d) * 100)}%` : "—";

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const LAYERS: LayerId[] = ["L0", "L1", "L2"];

  return (
    <div className="p-6 h-full flex flex-col gap-4 overflow-hidden">
      <h1 className="text-2xl font-bold shrink-0">层浏览</h1>

      {/* ----- Stats cards ----- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        {[
          {
            label: "基底总数",
            value: statsLoading ? "…" : stats?.total_substrates ?? "—",
          },
          {
            label: "L0 覆盖率",
            value: statsLoading
              ? "…"
              : stats
                ? pct(stats.substrates_with_l0, stats.total_substrates)
                : "—",
          },
          {
            label: "L1 覆盖率",
            value: statsLoading
              ? "…"
              : stats
                ? pct(stats.substrates_with_l1, stats.total_substrates)
                : "—",
          },
          {
            label: "KU 层数",
            value: statsLoading ? "…" : stats?.kus_with_layers ?? "—",
          },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4"
          >
            <div className="text-xs text-[var(--color-muted)] mb-1">
              {card.label}
            </div>
            <div className="text-2xl font-semibold">{card.value}</div>
          </div>
        ))}
      </div>

      {/* ----- Main split pane ----- */}
      <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">
        {/* Left pane: tree browser */}
        <div className="w-2/5 flex flex-col gap-2 min-h-0">
          {/* Search bar */}
          <div className="flex gap-2 shrink-0">
            <select
              value={searchMode}
              onChange={(e) =>
                setSearchMode(e.target.value as "name" | "content" | "semantic")
              }
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1.5 text-xs text-[var(--color-foreground)] shrink-0"
            >
              <option value="name">名称</option>
              <option value="content">内容</option>
              <option value="semantic">语义</option>
            </select>
            <input
              type="text"
              placeholder="搜索节点…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] outline-none focus:border-[var(--color-primary)]"
            />
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-border)]/40 disabled:opacity-40 shrink-0"
            >
              {searching ? "…" : "搜索"}
            </button>
          </div>

          {/* Tree */}
          <div className="flex-1 overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-2">
            {treeLoading && (
              <p className="text-sm text-[var(--color-muted)] p-2">
                加载中…
              </p>
            )}
            {!treeLoading && treeNodes.length === 0 && (
              <p className="text-sm text-[var(--color-muted)] p-2">
                无数据
              </p>
            )}
            {searchResults !== null ? (
              searchResults.length === 0 ? (
                <p className="text-sm text-[var(--color-muted)] p-2">
                  无匹配结果
                </p>
              ) : (
                searchResults.map((node) => (
                  <button
                    key={node.uri}
                    onClick={() => handleSelect(node)}
                    className={`w-full text-left flex items-center gap-1.5 py-1 px-2 rounded text-sm hover:bg-[var(--color-border)]/40 transition ${
                      selected?.uri === node.uri
                        ? "bg-[var(--color-border)]/60 font-medium"
                        : ""
                    }`}
                  >
                    <span className="shrink-0">
                      {node.type === "directory"
                        ? "📁"
                        : node.type === "ku"
                          ? "🧠"
                          : "📄"}
                    </span>
                    <span className="truncate">{node.name}</span>
                    <span className="text-[10px] text-[var(--color-muted)] ml-auto shrink-0 truncate max-w-[120px]">
                      {node.uri}
                    </span>
                  </button>
                ))
              )
            ) : (
              treeNodes.map((node) => (
                <TreeNode
                  key={node.uri}
                  node={node}
                  depth={0}
                  expanded={expanded}
                  selected={selected?.uri ?? null}
                  onToggle={toggleExpand}
                  onSelect={handleSelect}
                />
              ))
            )}
          </div>
        </div>

        {/* Right pane: content viewer */}
        <div className="w-3/5 flex flex-col gap-2 min-h-0">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
              <p className="text-[var(--color-muted)] text-sm">
                ← 选择左侧节点查看层内容
              </p>
            </div>
          ) : (
            <>
              {/* Node info */}
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3 shrink-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">{selected.name}</span>
                  <span className="text-xs text-[var(--color-muted)]">
                    {selected.type}
                  </span>
                  {selected.ref_id && (
                    <span className="text-xs text-[var(--color-muted)] font-mono">
                      {selected.ref_id}
                    </span>
                  )}
                </div>
                <div className="text-xs text-[var(--color-muted)] mt-0.5 font-mono truncate">
                  {selected.uri}
                </div>
              </div>

              {/* Layer tabs */}
              <div className="flex gap-1 shrink-0">
                {LAYERS.map((l) => (
                  <button
                    key={l}
                    onClick={() => setActiveLayer(l)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                      activeLayer === l
                        ? "bg-[var(--color-primary)] text-white"
                        : "border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)] hover:bg-[var(--color-border)]/40"
                    }`}
                  >
                    {l}
                  </button>
                ))}
                {content?.token_count != null && (
                  <span className="ml-auto text-xs text-[var(--color-muted)] self-center shrink-0">
                    {content.token_count.toLocaleString()} tokens
                  </span>
                )}
              </div>

              {/* Content area */}
              <div className="flex-1 min-h-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 overflow-y-auto">
                {contentLoading && (
                  <p className="text-sm text-[var(--color-muted)]">
                    加载中…
                  </p>
                )}
                {!contentLoading && !content && selected.type !== "directory" && (
                  <p className="text-sm text-[var(--color-muted)]">
                    该层暂无内容
                  </p>
                )}
                {!contentLoading && selected.type === "directory" && (
                  <p className="text-sm text-[var(--color-muted)]">
                    目录节点无层内容，请选择基底或 KU 节点。
                  </p>
                )}
                {!contentLoading && content && (
                  <pre
                    className={`text-sm whitespace-pre-wrap break-words ${
                      activeLayer === "L0" ? "font-mono" : "font-sans"
                    }`}
                  >
                    {content.content}
                  </pre>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
