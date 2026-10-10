/**
 * /cross-books — 跨书分析集合列表页。
 * 消费 GET /api/v1/cross-books。
 */
'use client';

import { useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApiNoArg, useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import Link from 'next/link';

interface CrossBookCollection {
  collection_id: string;
  name: string;
  description: string;
  book_ids: string[];
  created_at: string;
}

interface CreateCollectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function CreateCollectionModal({ isOpen, onClose, onCreated }: CreateCollectionModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [bookIds, setBookIds] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [books, setBooks] = useState<Array<{ substrate_id: string; title: string }>>([]);

  useEffect(() => {
    if (isOpen) {
      api.getBooks().then(res => {
        if (res.ok && res.data?.items) {
          setBooks(res.data.items);
        }
      });
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const ids = bookIds.split(',').map(s => s.trim()).filter(Boolean);
    const res = await api.createCrossBookCollection({ name, description, book_ids: ids });
    setLoading(false);
    if (res.ok) {
      onCreated();
      onClose();
    } else {
      setError(res.error || '创建失败');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md bg-[color:var(--card)] border border-[color:var(--border)] rounded-lg p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold mb-4">创建跨书分析集合</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm text-[color:var(--text-secondary)] mb-1">集合名称</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 rounded border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--foreground)]"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-[color:var(--text-secondary)] mb-1">描述</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full px-3 py-2 rounded border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--foreground)]"
              rows={2}
            />
          </div>
          <div>
            <label className="block text-sm text-[color:var(--text-secondary)] mb-1">书籍 IDs (逗号分隔)</label>
            <input
              type="text"
              value={bookIds}
              onChange={e => setBookIds(e.target.value)}
              className="w-full px-3 py-2 rounded border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--foreground)]"
              placeholder="sub-capital,sub-keynes,sub-spivak"
              required
            />
            <p className="text-xs text-[color:var(--text-tertiary)] mt-1">至少需要 2 本书。可用: {books.map(b => b.substrate_id).join(', ')}</p>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded border border-[color:var(--border)] text-sm" disabled={loading}>
              取消
            </button>
            <button type="submit" className="px-4 py-2 rounded bg-[color:var(--accent)] text-white text-sm" disabled={loading}>
              {loading ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CrossBooksPage() {
  const [state, run] = useApiNoArg(api.getCrossBookCollections);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  useEffect(() => { void run(); }, [run]);
  const items = state.data ?? [];

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-5xl mx-auto">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">跨书分析 / Cross-Book Analysis</h1>
          <p className="text-sm text-[color:var(--text-secondary)]">
            选择多本书运行 P14 跨书智能管线，获得概念对齐、论题比较、矛盾检测、知识缺口。
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 rounded bg-[color:var(--accent)] text-white text-sm font-medium hover:opacity-90"
        >
          新建集合
        </button>
      </header>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run()} />}
      {!state.loading && items.length === 0 && <OEmptyState title="暂无跨书分析集合" description="点击「新建集合」开始" />}

      {items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map(coll => (
            <Link
              key={coll.collection_id}
              href={`/cross-books/${coll.collection_id}`}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5 flex flex-col gap-3 hover:border-[color:var(--accent)]/50 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-[15px] font-medium">{coll.name}</h3>
              </div>
              <p className="text-sm text-[color:var(--text-secondary)] leading-relaxed line-clamp-2">{coll.description || '无描述'}</p>
              <div className="flex flex-wrap gap-1.5">
                {coll.book_ids.slice(0, 5).map(bid => (
                  <span key={bid} className="px-2 py-0.5 text-xs rounded border border-[color:var(--border)] text-[color:var(--text-tertiary)]">
                    {bid}
                  </span>
                ))}
                {coll.book_ids.length > 5 && (
                  <span className="px-2 py-0.5 text-xs text-[color:var(--text-tertiary)]">+{coll.book_ids.length - 5} 更多</span>
                )}
              </div>
              <p className="text-xs text-[color:var(--text-tertiary)]">
                创建: {new Date(coll.created_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}

      <CreateCollectionModal isOpen={showCreate} onClose={() => setShowCreate(false)} onCreated={() => void run()} />
    </div>
  );
}