"use client";
import { useEffect, useState } from "react";

interface Props {
  onViewChange: (filter: Record<string, unknown>) => void;
}

export function ViewSwitcher({ onViewChange }: Props) {
  const [views, setViews] = useState<Record<string, { name: string; filter?: Record<string, unknown>; default_filter?: Record<string, unknown> }>>({});
  const [selected, setSelected] = useState("all");

  useEffect(() => {
    fetch("/api/v1/views", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const merged: typeof views = { ...(d.presets || {}) };
        for (const v of d.user_views || []) {
          merged[v.id] = v;
        }
        setViews(merged);
      })
      .catch(() => {});
  }, []);

  function handleChange(id: string) {
    setSelected(id);
    const v = views[id];
    onViewChange(v?.default_filter ?? v?.filter ?? {});
  }

  return (
    <select
      value={selected}
      onChange={(e) => handleChange(e.target.value)}
      className="border border-[var(--color-border)] rounded px-2 py-1 text-sm"
    >
      {Object.entries(views).map(([id, v]) => (
        <option key={id} value={id}>
          {v.name}
        </option>
      ))}
    </select>
  );
}
