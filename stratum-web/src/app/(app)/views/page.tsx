"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";

type PresetView = { name: string; description?: string };
type UserView = { id: string; name: string; description?: string; is_default?: boolean };
type ViewsData = { presets: Record<string, PresetView>; user_views: UserView[] };

export default function ViewsPage() {
  const [data, setData] = useState<ViewsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient.get<ViewsData>("/api/v1/views")
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, []);

  if (loading) return <p className="p-6 text-[var(--color-muted)] text-sm">加载中...</p>;
  if (error || !data) return <p className="p-6 text-red-500 text-sm">加载失败</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">视图</h1>

      <section className="mb-8">
        <h2 className="text-sm font-medium text-[var(--color-muted)] mb-3">预设视图</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(data.presets).map(([id, v]) => (
            <div key={id} className="p-4 border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
              <h3 className="font-medium text-sm">{v.name}</h3>
              {v.description && (
                <p className="text-xs text-[var(--color-muted)] mt-1">{v.description}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-[var(--color-muted)] mb-3">我的视图</h2>
        {data.user_views.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">
            还没有自定义视图。可在{" "}
            <Link href="/discover" className="underline hover:text-[var(--color-primary)]">发现</Link>
            {" "}页面根据主题筛选并保存为视图。
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.user_views.map((v) => (
              <div key={v.id} className="p-4 border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-sm">{v.name}</h3>
                  {v.is_default && (
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">默认</span>
                  )}
                </div>
                {v.description && (
                  <p className="text-xs text-[var(--color-muted)] mt-1">{v.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
