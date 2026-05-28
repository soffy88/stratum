import Link from "next/link";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-border)]">
        <Link href="/" className="font-semibold text-lg tracking-tight">Stratum</Link>
      </header>

      <article className="max-w-2xl mx-auto px-8 py-16 space-y-6">
        <h1 className="text-3xl font-bold">服务条款</h1>
        <p className="text-sm text-[var(--color-muted)]">最后更新：占位符 — 正式法律文案待 Wiki 审核</p>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">使用条件</h2>
          {/* PLACEHOLDER: 法律文案待 Wiki 签核后填入 */}
          <p className="text-[var(--color-muted)]">
            正式服务条款内容正在准备中。
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">免责声明</h2>
          <p className="text-[var(--color-muted)]">
            {/* PLACEHOLDER */}
            正式服务条款内容正在准备中。
          </p>
        </section>
      </article>

      <footer className="border-t border-[var(--color-border)] px-8 py-6 text-xs text-[var(--color-muted)]">
        <Link href="/" className="hover:underline">← 返回首页</Link>
      </footer>
    </main>
  );
}
