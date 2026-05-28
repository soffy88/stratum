import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-border)]">
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
            注册
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-8 py-24 text-center">
        <h1 className="text-4xl font-bold mb-4 leading-tight">
          你的个人知识基座
        </h1>
        <p className="text-lg text-[var(--color-muted)] mb-10 max-w-xl mx-auto">
          Stratum 将你的文档、笔记和想法连接成可搜索、可推理的知识网络。
        </p>
        <Link
          href="/register"
          className="inline-block px-8 py-3 bg-[var(--color-primary)] text-white rounded-lg text-base font-medium hover:opacity-90"
        >
          免费开始使用
        </Link>
      </section>

      {/* Features */}
      <section className="max-w-4xl mx-auto px-8 pb-24 grid grid-cols-1 md:grid-cols-3 gap-8">
        <FeatureCard
          icon="🔍"
          title="语义搜索"
          description="不只是关键词匹配——理解你的意思，找到你需要的内容。"
        />
        <FeatureCard
          icon="🧠"
          title="AI 问答"
          description="基于你自己的文档生成摘要、回答问题、发现关联。"
        />
        <FeatureCard
          icon="🔗"
          title="反向链接"
          description="自动追踪文档之间的引用关系，构建知识图谱。"
        />
        <FeatureCard
          icon="📂"
          title="多格式支持"
          description="PDF、Markdown、纯文本——统一管理，统一搜索。"
        />
        <FeatureCard
          icon="🔒"
          title="隐私优先"
          description="数据存储在本地或你自己的服务器，不依赖第三方云服务。"
        />
        <FeatureCard
          icon="📤"
          title="一键分享"
          description="生成公开链接，与他人分享你的笔记或文档节选。"
        />
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] px-8 py-6 flex items-center justify-between text-xs text-[var(--color-muted)]">
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

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="p-6 border border-[var(--color-border)] rounded-lg">
      <div className="text-2xl mb-3">{icon}</div>
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm text-[var(--color-muted)]">{description}</p>
    </div>
  );
}
