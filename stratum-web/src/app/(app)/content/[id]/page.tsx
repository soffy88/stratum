import sanitizeHtml from "sanitize-html";

const SAFE_HTML_OPTIONS: sanitizeHtml.IOptions = {
  allowedTags: sanitizeHtml.defaults.allowedTags.concat(["img", "figure", "figcaption"]),
  allowedAttributes: {
    ...sanitizeHtml.defaults.allowedAttributes,
    img: ["src", "alt", "width", "height"],
    a: ["href", "title", "rel"],
  },
  allowedSchemes: ["https", "http", "mailto"],
};

interface ContentDetail {
  id: string;
  title: string;
  author?: string;
  type?: string;
  body_markdown?: string;
  body_html?: string;
  audio_url?: string;
  published_at?: string;
  domain?: string[];
  tags?: string[];
  access_tier?: string;
  related_user_substrate?: { id: string; title: string; relevance: number }[];
  related_user_notes?: { id: string; title: string }[];
}

async function getContent(id: string): Promise<ContentDetail | null> {
  try {
    const res = await fetch(
      `${process.env.STRATUM_API_INTERNAL_URL || "http://localhost:9302"}/api/v1/content/${id}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function ArticlePage({
  params,
}: {
  params: { id: string };
}) {
  const content = await getContent(params.id);
  if (!content) {
    return <p className="p-6 text-[var(--color-muted)]">内容未找到。</p>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      <main>
        <h1 className="text-2xl font-bold mb-2">{content.title}</h1>
        <p className="text-sm text-[var(--color-muted)] mb-4">
          {content.author} · {content.published_at?.slice(0, 10)}
        </p>
        {content.audio_url && (
          <audio controls src={content.audio_url} className="w-full mb-4" />
        )}
        <div
          className="prose max-w-none"
          dangerouslySetInnerHTML={{
            __html: sanitizeHtml(
              content.body_html || content.body_markdown || "",
              SAFE_HTML_OPTIONS
            ),
          }}
        />
      </main>

      <aside className="space-y-4">
        {(content.related_user_substrate?.length ?? 0) > 0 && (
          <div className="p-3 border border-[var(--color-border)] rounded">
            <h3 className="font-medium text-sm mb-2">你的相关资料</h3>
            {content.related_user_substrate!.map((s) => (
              <p key={s.id} className="text-sm mt-1">
                {s.title}{" "}
                <span className="text-[var(--color-muted)]">
                  ({s.relevance})
                </span>
              </p>
            ))}
          </div>
        )}
        {(content.related_user_notes?.length ?? 0) > 0 && (
          <div className="p-3 border border-[var(--color-border)] rounded">
            <h3 className="font-medium text-sm mb-2">你的笔记</h3>
            {content.related_user_notes!.map((n) => (
              <p key={n.id} className="text-sm mt-1">
                {n.title}
              </p>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
