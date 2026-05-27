import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-border)]">
        <Link href="/" className="font-semibold text-lg tracking-tight">Stratum</Link>
      </header>

      <article className="max-w-2xl mx-auto px-8 py-16 space-y-6">
        <h1 className="text-3xl font-bold">隐私政策</h1>
        <p className="text-sm text-[var(--color-muted)]">最后更新：占位符 — 正式法律文案待 Wiki 审核</p>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">数据收集</h2>
          {/* PLACEHOLDER: 法律文案待 Wiki 签核后填入 */}
          <p className="text-[var(--color-muted)]">
            正式隐私政策内容正在准备中。
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">数据使用</h2>
          <p className="text-[var(--color-muted)]">
            {/* PLACEHOLDER */}
            正式隐私政策内容正在准备中。
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">联系我们</h2>
          <p className="text-[var(--color-muted)]">
            如有疑问，请通过应用内反馈功能联系我们。
          </p>
        </section>
      </article>

      <footer className="border-t border-[var(--color-border)] px-8 py-6 text-xs text-[var(--color-muted)]">
        <Link href="/" className="hover:underline">← 返回首页</Link>
      </footer>
    </main>
  );
}
