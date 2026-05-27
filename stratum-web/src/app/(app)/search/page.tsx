"use client";

import { OSemanticSearch } from "@helios/blocks";
import { useStratumSearch } from "@/lib/adapters/search";

export default function SearchPage() {
  const onSearch = useStratumSearch();
  return (
    <div className="max-w-4xl mx-auto">
      <OSemanticSearch
        onSearch={onSearch}
        placeholder="输入搜索内容..."
      />
    </div>
  );
}
