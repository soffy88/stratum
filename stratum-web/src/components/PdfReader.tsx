'use client';

/**
 * PdfReader — @react-pdf-viewer 按需渲染(解决全量渲染的慢)+ 高亮/笔记。
 *
 * 选中文字 → 多色高亮 + 笔记 → 存回 Stratum highlights(跟 /highlights 同源)。
 * 重开回显已有高亮。
 */

import { useState, useEffect, useCallback } from 'react';
import { Viewer, Worker } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import {
  highlightPlugin, type RenderHighlightTargetProps, type RenderHighlightsProps, type HighlightArea,
} from '@react-pdf-viewer/highlight';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/highlight/lib/styles/index.css';
import {
  listHighlightsByDocument, createHighlight, type Highlight, type PdfLocation,
} from '@/lib/highlights';

const COLORS = ['yellow', 'green', 'blue', 'red'];

export function PdfReader({ blobUrl, documentId }: { blobUrl: string; documentId: string }) {
  const [highlights, setHighlights] = useState<Highlight[]>([]);

  const reload = useCallback(() => {
    listHighlightsByDocument(documentId).then(setHighlights).catch(() => setHighlights([]));
  }, [documentId]);

  useEffect(() => { reload(); }, [reload]);

  const save = async (props: RenderHighlightTargetProps, color: string) => {
    const loc: PdfLocation = {
      page: props.highlightAreas[0]?.pageIndex,
      rects: props.highlightAreas.map(a => ({
        top: a.top, left: a.left, width: a.width, height: a.height, pageIndex: a.pageIndex,
      })),
    };
    try {
      await createHighlight({ substrate_id: documentId, color, text: props.selectedText, location_json: loc });
      props.cancel();
      reload();
    } catch { /* 保存失败保持选区 */ }
  };

  const highlightPluginInstance = highlightPlugin({
    renderHighlightTarget: (props: RenderHighlightTargetProps) => (
      <div
        className="flex gap-1 items-center p-1.5 rounded-lg shadow-lg bg-background border"
        style={{
          position: 'absolute',
          left: `${props.selectionRegion.left}%`,
          top: `${props.selectionRegion.top + props.selectionRegion.height}%`,
          zIndex: 10,
        }}
      >
        {COLORS.map(c => (
          <button key={c} onClick={() => save(props, c)} aria-label={`高亮 ${c}`}
            className="w-6 h-6 rounded-full border" style={{ background: c }} />
        ))}
      </div>
    ),
    renderHighlights: (props: RenderHighlightsProps) => (
      <>
        {highlights.flatMap(h => {
          const loc = h.location_json as PdfLocation | undefined;
          if (!loc?.rects) return [];
          return loc.rects
            .filter(r => r.pageIndex === props.pageIndex)
            .map((rect, i) => (
              <div key={`${h.id}-${i}`}
                title={h.note ?? h.text}
                style={{
                  ...props.getCssProperties(rect as HighlightArea, props.rotation),
                  background: h.color, opacity: 0.4, cursor: 'pointer',
                }} />
            ));
        })}
      </>
    ),
  });

  const defaultLayoutPluginInstance = defaultLayoutPlugin();

  return (
    <div className="border border-border rounded-lg overflow-hidden" style={{ height: '80vh' }}>
      <Worker workerUrl="/pdf.worker.min.js">
        <Viewer fileUrl={blobUrl} plugins={[defaultLayoutPluginInstance, highlightPluginInstance]} />
      </Worker>
    </div>
  );
}
