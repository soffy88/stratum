'use client';

/**
 * 右栏: 笔记面板。
 * - 新建笔记: 自动关联当前文档(substrate_refs) + 当前选中概念(concept_refs)
 * - 最近笔记列表(全局, API无法按文档过滤)
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';

interface NoteItem {
  id: string;
  title: string;
  updated_at: string;
}

interface SelectedConcept {
  id: string;
  name: string;
}

export function NotesPanel({
  documentId,
  selectedConcept,
}: {
  documentId: string;
  selectedConcept: SelectedConcept | null;
}) {
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadNotes = useCallback(() => {
    apiClient
      .get<NoteItem[]>('/api/v1/notes')
      .then(r => setNotes((r.data ?? []).slice(0, 10)))
      .catch(() => {});
  }, []);

  useEffect(() => { loadNotes(); }, [loadNotes]);

  // 选中概念变化时预填标题
  useEffect(() => {
    if (selectedConcept && !title) {
      setTitle(`关于「${selectedConcept.name}」的笔记`);
    }
  }, [selectedConcept]);  // 只在选中概念变化时触发，不跟踪title

  const submit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await apiClient.post('/api/v1/notes', {
        title: title.trim(),
        content_markdown: content,
        substrate_refs: [documentId],
        concept_refs: selectedConcept ? [selectedConcept.id] : [],
      });
      setTitle('');
      setContent('');
      setCreating(false);
      loadNotes();
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full text-sm">
      {/* 新建按钮 / 表单 */}
      <div className="p-3 border-b shrink-0">
        {!creating ? (
          <button
            onClick={() => setCreating(true)}
            className="w-full py-2 px-3 border-2 border-dashed rounded-lg text-muted-foreground hover:border-primary hover:text-primary transition-colors text-sm"
          >
            + 新建笔记
          </button>
        ) : (
          <div className="flex flex-col gap-2">
            {selectedConcept && (
              <div className="text-xs text-primary bg-primary/10 rounded px-2 py-1">
                将关联概念: {selectedConcept.name}
              </div>
            )}
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="笔记标题…"
              className="w-full border rounded px-2 py-1.5 text-sm"
            />
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="内容（Markdown）…"
              className="w-full border rounded px-2 py-1.5 text-sm resize-none"
              rows={4}
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setCreating(false); setTitle(''); setContent(''); }}
                className="text-xs text-muted-foreground px-2 py-1"
              >
                取消
              </button>
              <button
                onClick={submit}
                disabled={saving || !title.trim()}
                className="text-xs bg-primary text-primary-foreground px-3 py-1 rounded disabled:opacity-50"
              >
                {saving ? '保存…' : '保存'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 最近笔记 */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide bg-muted/40 sticky top-0">
          最近笔记
        </div>
        {notes.length === 0 ? (
          <p className="px-3 py-3 text-xs text-muted-foreground">暂无笔记</p>
        ) : (
          notes.map(n => (
            <a
              key={n.id}
              href={`/notes/${n.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block px-3 py-2 hover:bg-muted/60 transition-colors border-b border-border/40"
            >
              <p className="text-sm font-medium truncate">{n.title}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(n.updated_at).toLocaleDateString('zh-CN')}
              </p>
            </a>
          ))
        )}
      </div>
    </div>
  );
}
