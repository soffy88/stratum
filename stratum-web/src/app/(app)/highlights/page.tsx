"use client";

import Link from "next/link";

export default function HighlightsPage() {
  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">我的高亮</h1>
      <div className="p-4 border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-sm text-[var(--color-muted)] space-y-2">
        <p>高亮按文档/内容关联存储，暂不支持跨文档全局列表。</p>
        <p>
          在{" "}
          <Link href="/documents" className="underline hover:text-[var(--color-primary)]">文档</Link>
          {" "}或{" "}
          <Link href="/search" className="underline hover:text-[var(--color-primary)]">搜索</Link>
          {" "}中打开具体内容，选中文字即可高亮。
        </p>
      </div>
    </div>
  );
}
