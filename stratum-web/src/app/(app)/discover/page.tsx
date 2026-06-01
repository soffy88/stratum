import Link from "next/link";

interface ContentItem {
  id: string;
  title: string;
  author?: string;
  published_at?: string;
  tags?: string[];
  access_tier?: string;
}

async function getFeed(): Promise<{ items: ContentItem[] }> {
  try {
    const res = await fetch(
      `${process.env.STRATUM_API_INTERNAL_URL || "http://localhost:9302"}/api/v1/content/feed`,
      { cache: "no-store" }
    );
    if (!res.ok) return { items: [] };
    return res.json();
  } catch {
    return { items: [] };
  }
}

export default async function DiscoverPage() {
  const data = await getFeed();

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">发现</h1>
      {data.items.length === 0 && (
        <p className="text-[var(--color-muted)]">暂无内容，稍后再来。</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.items.map((item) => (
          <Link
            key={item.id}
            href={`/content/${item.id}`}
            className="p-4 border border-[var(--color-border)] rounded hover:shadow-md transition"
          >
            <h2 className="font-semibold text-lg leading-tight">{item.title}</h2>
            <p className="text-sm text-[var(--color-muted)] mt-1">
              {item.author} · {item.published_at?.slice(0, 10)}
            </p>
            <div className="flex gap-1 mt-2 flex-wrap">
              {(item.tags || []).map((t) => (
                <span
                  key={t}
                  className="text-xs bg-[var(--color-border)] px-2 py-0.5 rounded"
                >
                  {t}
                </span>
              ))}
            </div>
            {item.access_tier && item.access_tier !== "free" && (
              <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded mt-1 inline-block">
                {item.access_tier.toUpperCase()}
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
