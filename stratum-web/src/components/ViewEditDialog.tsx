"use client";

import { useState } from "react";
import { createView, updateView, type View, type ViewCreate } from "@/lib/views";

const MEDIUMS = ["paper", "book", "epub", "webpage", "markdown_note", "other"];

interface Props {
  view: View | null; // null = creating new
  onClose: () => void;
  onSaved: () => void;
}

export function ViewEditDialog({ view, onClose, onSaved }: Props) {
  const [name, setName] = useState(view?.name ?? "");
  const [desc, setDesc] = useState(view?.description ?? "");
  const [icon, setIcon] = useState(view?.icon ?? "");
  const [mediums, setMediums] = useState<string[]>(
    (view?.filter_json?.medium as string[]) ?? []
  );
  const [tags, setTags] = useState(
    ((view?.filter_json?.tags as string[]) ?? []).join(", ")
  );
  const [sortBy, setSortBy] = useState(view?.sort_by ?? "created_at");
  const [sortOrder, setSortOrder] = useState(view?.sort_order ?? "desc");
  const [saving, setSaving] = useState(false);

  const toggleMedium = (m: string) =>
    setMediums((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    const body: ViewCreate = {
      name: name.trim(),
      description: desc.trim() || undefined,
      icon: icon.trim() || undefined,
      filter_json: {
        ...(mediums.length ? { medium: mediums } : {}),
        ...(tags.trim() ? { tags: tags.split(",").map((t) => t.trim()).filter(Boolean) } : {}),
      },
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    try {
      if (view) await updateView(view.id, body);
      else await createView(body);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-md shadow-xl space-y-4">
        <h2 className="font-semibold text-base">{view ? "编辑视图" : "新建视图"}</h2>

        <div className="space-y-3">
          <div className="flex gap-2">
            <input value={icon} onChange={(e) => setIcon(e.target.value)}
              placeholder="图标 (emoji)"
              className="w-16 text-center text-lg border border-[var(--color-border)] rounded px-2 py-1.5 bg-transparent" />
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="视图名称 *"
              className="flex-1 text-sm border border-[var(--color-border)] rounded px-3 py-1.5 bg-transparent outline-none focus:border-[var(--color-primary)]" />
          </div>

          <input value={desc} onChange={(e) => setDesc(e.target.value)}
            placeholder="说明 (可选)"
            className="w-full text-sm border border-[var(--color-border)] rounded px-3 py-1.5 bg-transparent outline-none focus:border-[var(--color-primary)]" />

          <div>
            <p className="text-xs text-[var(--color-muted)] mb-1.5">文档类型过滤</p>
            <div className="flex flex-wrap gap-1.5">
              {MEDIUMS.map((m) => (
                <button key={m} onClick={() => toggleMedium(m)}
                  className={`text-xs px-2 py-1 rounded border transition ${
                    mediums.includes(m)
                      ? "bg-[var(--color-primary)] text-white border-[var(--color-primary)]"
                      : "border-[var(--color-border)] hover:bg-[var(--color-border)]/40"
                  }`}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          <input value={tags} onChange={(e) => setTags(e.target.value)}
            placeholder="标签过滤，逗号分隔 (如: finance, quant)"
            className="w-full text-sm border border-[var(--color-border)] rounded px-3 py-1.5 bg-transparent outline-none focus:border-[var(--color-primary)]" />

          <div className="flex gap-2">
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
              className="flex-1 text-sm border border-[var(--color-border)] rounded px-2 py-1.5 bg-[var(--color-background)]">
              <option value="created_at">创建时间</option>
              <option value="updated_at">更新时间</option>
              <option value="title">标题</option>
            </select>
            <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}
              className="text-sm border border-[var(--color-border)] rounded px-2 py-1.5 bg-[var(--color-background)]">
              <option value="desc">↓ 降序</option>
              <option value="asc">↑ 升序</option>
            </select>
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button onClick={() => void handleSave()} disabled={saving || !name.trim()}
            className="flex-1 py-2 text-sm bg-[var(--color-primary)] text-white rounded disabled:opacity-50">
            {saving ? "保存中..." : "保存"}
          </button>
          <button onClick={onClose}
            className="px-4 py-2 text-sm border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30">
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
