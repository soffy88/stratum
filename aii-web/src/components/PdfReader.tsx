'use client';

/**
 * PdfReader — @react-pdf-viewer 按需渲染 + 高亮/笔记。
 *
 * 选中文字 → 颜色选择 + 原处笔记输入 → 存回 Stratum highlights。
 * 点击已有高亮 → 编辑笔记弹窗。重开回显已有高亮。
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
  listHighlightsByDocument, createHighlight, updateHighlight, type Highlight, type PdfLocation,
} from '@/lib/highlights';

const COLORS = ['yellow', 'green', 'blue', 'red'];

function HighlightTargetPopup({ props, onSave }: {
  props: RenderHighlightTargetProps;
  onSave: (p: RenderHighlightTargetProps, color: string, note: string) => void;
}) {
  const [note, setNote] = useState('');
  return (
    <div
      className="flex flex-col gap-2 p-2 rounded-lg shadow-lg bg-background border min-w-44"
      style={{
        position: 'absolute',
        left: `${props.selectionRegion.left}%`,
        top: `${props.selectionRegion.top + props.selectionRegion.height}%`,
        zIndex: 10,
      }}
    >
      <div className="flex gap-1 justify-center">
        {COLORS.map(c => (
          <button key={c} onClick={() => onSave(props, c, note)} aria-label={`高亮 ${c}`}
            className="w-6 h-6 rounded-full border hover:scale-110 transition-transform"
            style={{ background: c }} />
        ))}
      </div>
      <textarea
        value={note}
        onChange={e => setNote(e.target.value)}
        placeholder="添加笔记（可选）…"
        className="text-xs border rounded p-1 resize-none w-full"
        rows={2}
        onMouseDown={e => e.stopPropagation()}
      />
    </div>
  );
}

function HighlightNotePopover({ highlight, onClose, onSave }: {
  highlight: Highlight;
  onClose: () => void;
  onSave: (note: string) => void;
}) {
  const [note, setNote] = useState(highlight.note ?? '');
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div className="bg-background border rounded-lg p-4 shadow-xl w-72 flex flex-col gap-3" onClick={e => e.stopPropagation()}>
        {highlight.text && (
          <p className="text-xs text-muted-foreground line-clamp-3 border-l-2 pl-2" style={{ borderColor: highlight.color }}>
            {highlight.text}
          </p>
        )}
        <textarea
          autoFocus
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="添加笔记…"
          className="text-sm border rounded p-2 resize-none w-full"
          rows={3}
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="text-sm text-muted-foreground px-3 py-1">取消</button>
          <button
            onClick={() => onSave(note)}
            className="text-sm bg-primary text-primary-foreground px-3 py-1 rounded"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

export function PdfReader({ blobUrl, documentId, fullHeight }: { blobUrl: string; documentId: string; fullHeight?: boolean }) {
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [editingHighlight, setEditingHighlight] = useState<Highlight | null>(null);

  const reload = useCallback(() => {
    listHighlightsByDocument(documentId).then(setHighlights).catch(() => setHighlights([]));
  }, [documentId]);

  useEffect(() => { reload(); }, [reload]);

  const save = async (props: RenderHighlightTargetProps, color: string, note: string) => {
    const loc: PdfLocation = {
      page: props.highlightAreas[0]?.pageIndex,
      rects: props.highlightAreas.map(a => ({
        top: a.top, left: a.left, width: a.width, height: a.height, pageIndex: a.pageIndex,
      })),
    };
    try {
      await createHighlight({
        substrate_id: documentId, color, text: props.selectedText,
        note: note || undefined, location_json: loc,
      });
      props.cancel();
      reload();
    } catch { /* 保存失败保持选区 */ }
  };

  const saveNoteEdit = async (note: string) => {
    if (!editingHighlight) return;
    try {
      await updateHighlight(editingHighlight.id, { note });
      setEditingHighlight(null);
      reload();
    } catch { /* ignore */ }
  };

  const highlightPluginInstance = highlightPlugin({
    renderHighlightTarget: (props: RenderHighlightTargetProps) => (
      <HighlightTargetPopup props={props} onSave={save} />
    ),
    renderHighlights: (props: RenderHighlightsProps) => (
      <>
        {highlights.flatMap(h => {
          const loc = h.location_json as PdfLocation | undefined;
          if (!loc?.rects) return [];
          return loc.rects
            .filter(r => r.pageIndex === props.pageIndex)
            .map((rect, i) => (
              <div
                key={`${h.id}-${i}`}
                title={h.note ?? h.text}
                onClick={() => setEditingHighlight(h)}
                style={{
                  ...props.getCssProperties(rect as HighlightArea, props.rotation),
                  background: h.color, opacity: 0.4, cursor: 'pointer',
                }}
              />
            ));
        })}
      </>
    ),
  });

  const defaultLayoutPluginInstance = defaultLayoutPlugin();

  return (
    <div className="border border-border rounded-lg overflow-hidden" style={{ height: fullHeight ? '100%' : '80vh' }}>
      <Worker workerUrl="/pdf.worker.min.js">
        <Viewer fileUrl={blobUrl} plugins={[defaultLayoutPluginInstance, highlightPluginInstance]} />
      </Worker>
      {editingHighlight && (
        <HighlightNotePopover
          highlight={editingHighlight}
          onClose={() => setEditingHighlight(null)}
          onSave={saveNoteEdit}
        />
      )}
    </div>
  );
}
