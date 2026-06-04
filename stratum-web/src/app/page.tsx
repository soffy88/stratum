import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <span className="font-semibold text-lg tracking-tight">Stratum</span>
        <div className="flex gap-3">
          <Link
            href="/login"
            className="text-sm px-4 py-1.5 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30"
          >
            登录
          </Link>
          <Link
            href="/register"
            className="text-sm px-4 py-1.5 bg-[var(--color-primary)] text-white rounded hover:opacity-90"
          >
            免费注册
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 py-20 text-center">
        <h1 className="text-4xl font-bold mb-4 leading-tight">
          把英文资料消化成自己的知识
        </h1>
        <p className="text-lg text-[var(--color-muted)] mb-4 max-w-2xl mx-auto">
          上传 PDF / 抓取网页 / 订阅 RSS → AI 自动翻译、摘要、图谱化，真的读懂，而不只是存档。
        </p>
        <p className="text-sm text-[var(--color-muted)] mb-10">
          Alpha 免费，已有知识入库、搜索、AI Agent 全流程。
        </p>
        <Link
          href="/register"
          className="inline-block px-8 py-3 bg-[var(--color-primary)] text-white rounded-lg text-base font-medium hover:opacity-90"
        >
          立即试用 →
        </Link>
      </section>

      {/* 3 use cases */}
      <section className="max-w-4xl mx-auto px-6 pb-16">
        <h2 className="text-center text-xl font-semibold mb-8 text-[var(--color-muted)]">
          真实场景
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <ScenarioCard
            step="1"
            title="上传论文，10 分钟读懂"
            body="拖入 PDF → AI 翻译全文 → 阅读伙伴回答你的问题。不再对着生词表挣扎。"
          />
          <ScenarioCard
            step="2"
            title="RSS 自动追踪行业动态"
            body="订阅 Hacker News / 量化博客 → 新文章自动抓取入库 → 次日早上 Daily Digest 给你精华。"
          />
          <ScenarioCard
            step="3"
            title="搜你自己的知识库"
            body="你的文档 + 你的笔记 + 专业内容三层融合，一个框搜出来，找到你三个月前存的那篇。"
          />
        </div>
      </section>

      {/* Feature grid */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <h2 className="text-center text-xl font-semibold mb-8 text-[var(--color-muted)]">
          已上线功能
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <FeatureCard icon="📄" title="文件上传" description="PDF / EPUB / Markdown，带进度条" />
          <FeatureCard icon="🌐" title="URL 抓取" description="粘贴链接，服务端抓全文" />
          <FeatureCard icon="📡" title="RSS 订阅" description="自动发现 Feed，周期拉取入库" />
          <FeatureCard icon="🌏" title="AI 翻译" description="英文资料翻译为中文" />
          <FeatureCard icon="📝" title="每日 / 周摘要" description="自动生成你的知识消化报告" />
          <FeatureCard icon="💬" title="阅读伙伴" description="针对你的资料库问答" />
          <FeatureCard icon="🔍" title="三层融合搜索" description="文档 + 笔记 + 专业内容" />
          <FeatureCard icon="🧠" title="概念图谱" description="ReactFlow 可交互可视化" />
          <FeatureCard icon="⏰" title="时光机" description="按月查看历史入库内容" />
        </div>
      </section>

      {/* vs obsidian/notion */}
      <section className="max-w-3xl mx-auto px-6 pb-20">
        <h2 className="text-center text-xl font-semibold mb-8 text-[var(--color-muted)]">
          跟 Obsidian / Notion 真区别
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-[var(--color-muted)] text-xs">
                <th className="text-left py-2 pr-4">功能</th>
                <th className="py-2 px-4 text-center">Obsidian</th>
                <th className="py-2 px-4 text-center">Notion</th>
                <th className="py-2 px-4 text-center font-semibold text-[var(--color-primary)]">Stratum</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["AI 翻译", "❌", "❌", "✅"],
                ["RSS 自动入库", "❌", "❌", "✅"],
                ["三层融合搜索", "❌", "❌", "✅"],
                ["概念图谱", "✅", "🟡", "✅"],
                ["AI 每日摘要", "🟡 插件", "🟡", "✅"],
              ].map(([feat, obs, not, str]) => (
                <tr key={feat} className="border-t border-[var(--color-border)]">
                  <td className="py-2.5 pr-4">{feat}</td>
                  <td className="py-2.5 px-4 text-center text-[var(--color-muted)]">{obs}</td>
                  <td className="py-2.5 px-4 text-center text-[var(--color-muted)]">{not}</td>
                  <td className="py-2.5 px-4 text-center font-medium">{str}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* CTA */}
      <section className="text-center pb-20 px-6">
        <p className="text-[var(--color-muted)] mb-4">alpha 免费，现在就开始积累你的知识库。</p>
        <Link
          href="/register"
          className="inline-block px-8 py-3 bg-[var(--color-primary)] text-white rounded-lg text-base font-medium hover:opacity-90"
        >
          免费注册
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] px-6 py-6 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--color-muted)]">
        <span>© {new Date().getFullYear()} Stratum</span>
        <div className="flex gap-4">
          <Link href="/about" className="hover:underline">关于</Link>
          <Link href="/privacy" className="hover:underline">隐私政策</Link>
          <Link href="/terms" className="hover:underline">服务条款</Link>
        </div>
      </footer>
    </main>
  );
}

function ScenarioCard({ step, title, body }: { step: string; title: string; body: string }) {
  return (
    <div className="p-5 border border-[var(--color-border)] rounded-lg">
      <div className="text-xs text-[var(--color-muted)] mb-2">场景 {step}</div>
      <h3 className="font-semibold mb-2 text-sm">{title}</h3>
      <p className="text-sm text-[var(--color-muted)] leading-relaxed">{body}</p>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="p-4 border border-[var(--color-border)] rounded-lg">
      <div className="text-xl mb-2">{icon}</div>
      <h3 className="font-semibold text-sm mb-1">{title}</h3>
      <p className="text-xs text-[var(--color-muted)]">{description}</p>
    </div>
  );
}
