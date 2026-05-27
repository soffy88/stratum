/**
 * Public share page — no auth required.
 * Server Component: fetches from backend directly.
 */

interface ShareData {
  title: string;
  content: string;
  shared_by_username: string;
  shared_at: string;
}

// Backend URL for server-side fetch (not the browser-facing /api/* proxy).
// STRATUM_API_INTERNAL_URL lets each environment point to the right host:
//   dev        → http://localhost:9305  (default, uvicorn direct)
//   e2e tests  → http://localhost:9311  (set by playwright.browser.config.ts)
//   production → http://stratum-api:9302 (injected by docker-compose / systemd)
const BACKEND = process.env.STRATUM_API_INTERNAL_URL ?? "http://localhost:9305";

export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  const res = await fetch(`${BACKEND}/share/${token}`, {
    cache: "no-store",
  });

  if (res.status === 410) return <ShareExpired />;
  if (res.status === 404) return <ShareNotFound />;
  if (!res.ok) return <ShareError />;

  const data: ShareData = await res.json();

  return (
    <div className="min-h-screen bg-[var(--color-background)]">
      <div className="max-w-3xl mx-auto py-12 px-6">
        <header className="mb-8 pb-4 border-b border-[var(--color-border)]">
          <p className="text-sm text-[var(--color-muted)]">
            由 <span className="font-medium">{data.shared_by_username}</span> 分享
            · {new Date(data.shared_at).toLocaleDateString("zh-CN")}
          </p>
        </header>

        <article>
          <h1 className="text-2xl font-semibold mb-6">{data.title}</h1>
          <div className="prose prose-sm max-w-none whitespace-pre-wrap">
            {data.content}
          </div>
        </article>

        <footer className="mt-12 pt-4 border-t border-[var(--color-border)] text-center text-xs text-[var(--color-muted)]">
          Powered by Stratum · <a href="/register" className="underline">创建你的知识库</a>
        </footer>
      </div>
    </div>
  );
}

function ShareExpired() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-xl font-semibold mb-2">分享已过期</h1>
        <p className="text-[var(--color-muted)]">此链接已失效</p>
      </div>
    </div>
  );
}

function ShareNotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-xl font-semibold mb-2">分享未找到</h1>
        <p className="text-[var(--color-muted)]">链接无效或已被撤销</p>
      </div>
    </div>
  );
}

function ShareError() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-xl font-semibold mb-2">加载失败</h1>
        <p className="text-[var(--color-muted)]">请稍后重试</p>
      </div>
    </div>
  );
}
