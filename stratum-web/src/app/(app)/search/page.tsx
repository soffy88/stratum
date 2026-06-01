"use client";

import { useState } from "react";
import { OSemanticSearch } from "@helios/blocks";
import { useStratumSearch } from "@/lib/adapters/search";
import { SearchPanel } from "@/components/SearchPanel";

export default function SearchPage() {
  const onSearch = useStratumSearch();
  const [advanced, setAdvanced] = useState(false);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">搜索</h1>
        <button
          onClick={() => setAdvanced((v) => !v)}
          className="text-sm text-[var(--color-muted)] border border-[var(--color-border)] px-3 py-1 rounded hover:bg-[var(--color-border)] transition"
        >
          {advanced ? "基础搜索" : "高级搜索"}
        </button>
      </div>
      {advanced ? (
        <SearchPanel />
      ) : (
        <OSemanticSearch onSearch={onSearch} placeholder="输入搜索内容..." />
      )}
    </div>
  );
}
