'use client';

/**
 * EpubReader — react-reader + epubjs，cfi 定位高亮。
 * 选中 → 底部弹窗(颜色+笔记+确认) → 存回 Stratum。重开回显。
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { ReactReader } from 'react-reader';
import type { Rendition } from 'epubjs';
import {
  listHighlightsByDocument, createHighlight, type Highlight, type EpubLocation,
} from '@/lib/highlights';

const COLORS = ['yellow', 'green', 'blue', 'red'];

export function EpubReader({ buffer, documentId, title, fullHeight }: {
  buffer: ArrayBuffer; documentId: string; title: string; fullHeight?: boolean;
}) {
  const [location, setLocation] = useState<string | number>(0);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [pending, setPending] = useState<{ cfi: string; text: string } | null>(null);
  const [pendingColor, setPendingColor] = useState('yellow');
  const [pendingNote, setPendingNote] = useState('');
  const renditionRef = useRef<Rendition | null>(null);

  const reload = useCallback(() => {
    listHighlightsByDocument(documentId).then(setHighlights).catch(() => setHighlights([]));
  }, [documentId]);

  useEffect(() => { reload(); }, [reload]);

  // 回显已有高亮
  useEffect(() => {
    const r = renditionRef.current;
    if (!r) return;
    highlights.forEach(h => {
      const loc = h.location_json as EpubLocation | undefined;
      if (loc?.cfi) {
        try { r.annotations.highlight(loc.cfi, {}, () => {}, '', { fill: h.color }); } catch { /* cfi 无效跳过 */ }
      }
    });
  }, [highlights]);

  const onRendition = (rendition: Rendition) => {
    renditionRef.current = rendition;
    rendition.on('selected', (cfiRange: string) => {
      let text = '';
      try { text = rendition.getRange(cfiRange).toString(); } catch { /* ignore */ }
      setPending({ cfi: cfiRange, text });
      setPendingNote('');
      setPendingColor('yellow');
    });
  };

  const confirmHighlight = async () => {
    if (!pending) return;
    const r = renditionRef.current;
    try {
      await createHighlight({
        substrate_id: documentId,
        color: pendingColor,
        text: pending.text,
        note: pendingNote || undefined,
        location_json: { cfi: pending.cfi },
      });
      if (r) r.annotations.highlight(pending.cfi, {}, () => {}, '', { fill: pendingColor });
      reload();
    } catch { /* 保存失败 */ }
    setPending(null);
  };

  return (
    <div className={fullHeight ? 'h-full' : 'flex flex-col gap-2'}>
      <div style={{ height: fullHeight ? '100%' : '75vh' }} className="border border-border rounded-lg overflow-hidden relative">
        <ReactReader
          url={buffer}
          location={location}
          locationChanged={(loc: string) => setLocation(loc)}
          getRendition={onRendition}
          title={title}
        />
        {pending && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-background border rounded-xl shadow-xl p-3 flex flex-col gap-2 w-72 z-50">
            {pending.text && (
              <p className="text-xs text-muted-foreground line-clamp-2 border-l-2 border-yellow-400 pl-2">
                {pending.text}
              </p>
            )}
            <div className="flex gap-1 items-center">
              <span className="text-xs text-muted-foreground mr-1">颜色:</span>
              {COLORS.map(c => (
                <button key={c} onClick={() => setPendingColor(c)} aria-label={c}
                  className="w-5 h-5 rounded-full border-2 transition-transform hover:scale-110"
                  style={{ background: c, borderColor: pendingColor === c ? 'var(--foreground)' : 'transparent' }} />
              ))}
            </div>
            <textarea
              autoFocus
              value={pendingNote}
              onChange={e => setPendingNote(e.target.value)}
              placeholder="添加笔记（可选）…"
              className="text-xs border rounded p-1.5 resize-none w-full"
              rows={2}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setPending(null)} className="text-xs text-muted-foreground px-2 py-1">取消</button>
              <button onClick={confirmHighlight} className="text-xs bg-primary text-primary-foreground px-3 py-1 rounded">
                保存高亮
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
