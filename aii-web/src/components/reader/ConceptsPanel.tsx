'use client';

/**
 * 左栏: 该文档关联的 Concepts（按 type 分组）。
 * 点击概念 → 传 onSelect 回调（右栏笔记可关联到该概念）。
 * 注: Concepts 无 chapter_id/position，无法跳转到 PDF 位置；分组用 type 字段代替章节。
 */

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';

interface Concept {
  id: string;
  name: string;
  type: string;
  substrate_refs: string[];
}

const TYPE_LABEL: Record<string, string> = {
  concept_idea: '概念',
  term: '术语',
  person: '人物',
  event: '事件',
  place: '地点',
  theorem: '定理',
  formula: '公式',
  method: '方法',
};

export function ConceptsPanel({
  documentId,
  onSelect,
  selectedId,
}: {
  documentId: string;
  onSelect: (c: Concept | null) => void;
  selectedId: string | null;
}) {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get<Concept[]>('/api/v1/concepts')
      .then(r => {
        const filtered = (r.data ?? []).filter(c =>
          Array.isArray(c.substrate_refs) && c.substrate_refs.includes(documentId)
        );
        setConcepts(filtered);
      })
      .catch(() => setConcepts([]))
      .finally(() => setLoading(false));
  }, [documentId]);

  if (loading) {
    return <div className="p-3 text-xs text-muted-foreground">加载概念…</div>;
  }
  if (concepts.length === 0) {
    return (
      <div className="p-3 text-xs text-muted-foreground">
        <p className="font-medium mb-1">本书暂无关联概念</p>
        <p>在概念页面关联此文档后将显示在此</p>
      </div>
    );
  }

  // 按 type 分组
  const groups: Record<string, Concept[]> = {};
  for (const c of concepts) {
    const key = c.type || 'concept_idea';
    if (!groups[key]) groups[key] = [];
    groups[key].push(c);
  }

  return (
    <div className="text-sm">
      {Object.entries(groups).map(([type, items]) => (
        <div key={type}>
          <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide bg-muted/40 sticky top-0">
            {TYPE_LABEL[type] ?? type}
          </div>
          {items.map(c => (
            <button
              key={c.id}
              onClick={() => onSelect(selectedId === c.id ? null : c)}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-muted/60 transition-colors ${
                selectedId === c.id ? 'bg-primary/10 text-primary font-medium' : ''
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
