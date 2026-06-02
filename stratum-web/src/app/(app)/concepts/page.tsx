import Link from "next/link";

interface Concept {
  id: string;
  name: string;
  type?: string;
}

async function getConcepts(): Promise<Concept[]> {
  try {
    const res = await fetch(
      `${process.env.STRATUM_API_INTERNAL_URL || "http://localhost:9304"}/api/v1/concepts`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function ConceptsPage() {
  const concepts = await getConcepts();

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">概念</h1>
      {concepts.length === 0 && (
        <p className="text-[var(--color-muted)]">暂无概念。</p>
      )}
      <div className="space-y-2">
        {concepts.map((c) => (
          <Link
            key={c.id}
            href={`/concepts/${c.id}`}
            className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/10 transition"
          >
            <span className="font-medium">{c.name}</span>
            {c.type && (
              <span className="text-xs text-[var(--color-muted)]">{c.type}</span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
