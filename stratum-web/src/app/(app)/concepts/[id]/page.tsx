import Link from "next/link";

interface ConceptNode {
  id: string;
  type: string;
  label?: string;
  title?: string;
}

interface ConceptEdge {
  from: string;
  to: string;
  type: string;
}

interface ConceptDetail {
  id: string;
  name: string;
  type?: string;
  aliases?: string[];
  wikilink?: string;
  platform_view?: Record<string, unknown> | null;
  related_substrates?: { id: string; title: string; medium: string }[];
}

interface ConceptGraph {
  nodes: ConceptNode[];
  edges: ConceptEdge[];
}

async function getConcept(id: string): Promise<ConceptDetail | null> {
  try {
    const res = await fetch(
      `${process.env.STRATUM_API_INTERNAL_URL || "http://localhost:9303"}/api/v1/concepts/${id}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getConceptGraph(id: string): Promise<ConceptGraph | null> {
  try {
    const res = await fetch(
      `${process.env.STRATUM_API_INTERNAL_URL || "http://localhost:9303"}/api/v1/concepts/graph/${id}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function ConceptDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const [concept, graph] = await Promise.all([
    getConcept(params.id),
    getConceptGraph(params.id),
  ]);

  if (!concept) {
    return <p className="p-6 text-[var(--color-muted)]">概念未找到。</p>;
  }

  const relatedConcepts = graph?.nodes.filter(
    (n) => n.type === "concept" && n.id !== params.id
  );
  const relatedSubstrates = graph?.nodes.filter((n) => n.type === "substrate");

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{concept.name}</h1>
        {concept.type && (
          <span className="text-xs text-[var(--color-muted)] bg-[var(--color-border)] px-2 py-0.5 rounded mt-1 inline-block">
            {concept.type}
          </span>
        )}
        {(concept.aliases?.length ?? 0) > 0 && (
          <p className="text-sm text-[var(--color-muted)] mt-2">
            别名：{concept.aliases!.join(" · ")}
          </p>
        )}
        {concept.wikilink && (
          <p className="text-sm mt-2">
            <Link
              href={concept.wikilink}
              className="text-blue-500 hover:underline"
            >
              {concept.wikilink}
            </Link>
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {(concept.related_substrates?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-semibold mb-3">相关资料</h2>
            <div className="space-y-2">
              {concept.related_substrates!.map((s) => (
                <div
                  key={s.id}
                  className="p-2 border border-[var(--color-border)] rounded text-sm"
                >
                  <span className="font-medium">{s.title}</span>
                  <span className="text-[var(--color-muted)] ml-2">
                    {s.medium}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {(relatedConcepts?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-semibold mb-3">相关概念</h2>
            <div className="space-y-2">
              {relatedConcepts!.map((n) => (
                <Link
                  key={n.id}
                  href={`/concepts/${n.id}`}
                  className="block p-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-border)] transition"
                >
                  {n.label}
                </Link>
              ))}
            </div>
          </section>
        )}

        {(relatedSubstrates?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-semibold mb-3">引用此概念的文档</h2>
            <div className="space-y-2">
              {relatedSubstrates!.map((n) => (
                <div
                  key={n.id}
                  className="p-2 border border-[var(--color-border)] rounded text-sm"
                >
                  {n.title}
                </div>
              ))}
            </div>
          </section>
        )}

        {concept.platform_view && (
          <section>
            <h2 className="font-semibold mb-3">平台知识</h2>
            <div className="p-3 bg-[var(--color-border)] rounded text-sm">
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(concept.platform_view, null, 2)}
              </pre>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
