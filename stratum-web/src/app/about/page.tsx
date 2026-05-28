import Link from "next/link";

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-border)]">
        <Link href="/" className="font-semibold text-lg tracking-tight">Stratum</Link>
      </header>

      <article className="max-w-2xl mx-auto px-8 py-16 space-y-6">
        <h1 className="text-3xl font-bold">关于 Stratum</h1>
        <p className="text-[var(--color-muted)]">
          Stratum 是一款本地优先的个人知识管理工具，帮助你整理、搜索和推理你的文档与笔记。
        </p>
        <p className="text-[var(--color-muted)]">
          {/* PLACEHOLDER: 详细的产品介绍内容将在正式发布前补充 */}
          更多内容即将上线。
        </p>
      </article>

      <footer className="border-t border-[var(--color-border)] px-8 py-6 text-xs text-[var(--color-muted)]">
        <Link href="/" className="hover:underline">← 返回首页</Link>
      </footer>
    </main>
  );
}
