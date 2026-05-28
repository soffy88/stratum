"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { SearchRequest, SearchResponse, SearchResultItem } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");

  const searchMutation = useMutation({
    mutationFn: (req: SearchRequest) =>
      apiClient.post<SearchResponse>("/api/search", req),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate({ query, top_k: 10, mode: "augmented" });
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">搜索</h1>

      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入搜索内容..."
          className="flex-1 border border-[var(--color-border)] rounded px-3 py-2"
        />
        <button
          type="submit"
          disabled={searchMutation.isPending}
          className="px-4 py-2 bg-[var(--color-primary)] text-white rounded disabled:opacity-50"
        >
          {searchMutation.isPending ? "搜索中..." : "搜索"}
        </button>
      </form>

      {searchMutation.error && (
        <p className="text-red-600 mb-4">搜索失败: {searchMutation.error.message}</p>
      )}

      {searchMutation.data && (
        <div className="space-y-3">
          <p className="text-sm text-[var(--color-muted)]">
            找到 {searchMutation.data.results.length} 条结果
          </p>
          {searchMutation.data.results.map((item: SearchResultItem) => (
            <SearchResult key={item.id} item={item} />
          ))}
          {searchMutation.data.results.length === 0 && (
            <p className="text-[var(--color-muted)]">无结果</p>
          )}
        </div>
      )}
    </div>
  );
}

function SearchResult({ item }: { item: SearchResultItem }) {
  return (
    <a
      href={`/documents/${item.id}`}
      className="block p-4 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30"
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs px-1.5 py-0.5 bg-[var(--color-border)] rounded">{item.type}</span>
        <span className="text-xs text-[var(--color-muted)]">
          {(item.score * 100).toFixed(0)}%
        </span>
      </div>
      <h3 className="font-medium">{item.title}</h3>
      {item.highlight && (
        <p className="text-sm text-[var(--color-muted)] mt-1">{item.highlight}</p>
      )}
    </a>
  );
}
