'use client';

/**
 * EpubReader — react-reader + epubjs,cfi 定位高亮。
 * 选中 → 高亮 + 笔记 → 存回 Stratum。重开回显(遍历已有高亮 annotations.highlight)。
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { ReactReader } from 'react-reader';
import type { Rendition } from 'epubjs';
import {
  listHighlightsByDocument, createHighlight, type Highlight, type EpubLocation,
} from '@/lib/highlights';

const COLORS = ['yellow', 'green', 'blue', 'red'];

export function EpubReader({ buffer, documentId, title }: {
  buffer: ArrayBuffer; documentId: string; title: string;
}) {
  const [location, setLocation] = useState<string | number>(0);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [color, setColor] = useState('yellow');
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
    rendition.on('selected', async (cfiRange: string) => {
      let text = '';
      try { text = rendition.getRange(cfiRange).toString(); } catch { /* ignore */ }
      try {
        await createHighlight({
          substrate_id: documentId, color, text,
          location_json: { cfi: cfiRange },
        });
        // 当前会话立即高亮
        rendition.annotations.highlight(cfiRange, {}, () => {}, '', { fill: color });
        reload();
      } catch { /* 保存失败 */ }
    });
  };

  return (
    <div className="flex flex-col gap-2">
      {/* 颜色选择(选中前先选色)*/}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">高亮颜色:</span>
        {COLORS.map(c => (
          <button key={c} onClick={() => setColor(c)} aria-label={c}
            className="w-5 h-5 rounded-full border-2"
            style={{ background: c, borderColor: color === c ? 'var(--foreground)' : 'transparent' }} />
        ))}
      </div>
      <div style={{ height: '75vh' }} className="border border-border rounded-lg overflow-hidden relative">
        <ReactReader
          url={buffer}
          location={location}
          locationChanged={(loc: string) => setLocation(loc)}
          getRendition={onRendition}
          title={title}
        />
      </div>
    </div>
  );
}
