'use client';

/**
 * DocumentViewer — 内嵌 PDF/EPUB 阅读器(文档详情页「原始文档」Tab)
 *
 * file endpoint 需 JWT,不能直接 iframe src → fetch 成 blob 再喂 viewer(方案 A)。
 * PDF:react-pdf(PDF.js)分批渲染(大文件不一次性全渲染,§6)。
 * EPUB:react-reader(epub.js,本身分章节)。
 * 其他:文件信息 + 下载链接。
 */

import { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ReactReader } from 'react-reader';
import { apiClient } from '@/lib/apiClient';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc =
  `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface Props {
  documentId: string;
  mime: string;
  medium: string;
  title: string;
}

const PDF_BATCH = 5; // 每批渲染页数(懒加载)

export default function DocumentViewer({ documentId, mime, medium, title }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadPct, setDownloadPct] = useState(0);
  const [error, setError] = useState(false);

  const [numPages, setNumPages] = useState(0);
  const [shownPages, setShownPages] = useState(PDF_BATCH);
  const [scale, setScale] = useState(1);
  const [epubLocation, setEpubLocation] = useState<string | number>(0);

  const containerRef = useRef<HTMLDivElement>(null);

  const isPdf = mime?.includes('pdf') || medium === 'pdf';
  const isEpub = mime?.includes('epub') || medium === 'epub' || medium === 'book';

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setLoading(true); setError(false); setDownloadPct(0);

    apiClient
      .get(`/api/v1/documents/${documentId}/file`, {
        responseType: 'blob',
        onDownloadProgress: (e: { loaded: number; total?: number }) => {
          if (e.total) setDownloadPct(Math.round((e.loaded / e.total) * 100));
        },
      })
      .then(res => {
        if (cancelled) return;
        url = URL.createObjectURL(res.data as Blob);
        setBlobUrl(url);
        setLoading(false);
      })
      .catch(() => { if (!cancelled) { setError(true); setLoading(false); } });

    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [documentId]);

  if (loading) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        加载文件中…{downloadPct > 0 && ` ${downloadPct}%`}
        {downloadPct > 0 && (
          <div className="max-w-xs mx-auto mt-3 h-1 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all" style={{ width: `${downloadPct}%` }} />
          </div>
        )}
      </div>
    );
  }

  if (error || !blobUrl) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        无法加载文件。
        <a href={`/api/v1/documents/${documentId}/file`} className="text-primary ml-1 hover:underline">
          下载查看
        </a>
      </div>
    );
  }

  // ── PDF ──
  if (isPdf) {
    return (
      <div className="flex flex-col gap-3">
        {/* 工具栏 */}
        <div className="flex items-center gap-2 justify-end">
          <button className="px-2 min-h-9 rounded border hover:bg-muted text-sm"
            onClick={() => setScale(s => Math.max(0.5, s - 0.2))}>−</button>
          <span className="text-sm text-muted-foreground tabular-nums">{Math.round(scale * 100)}%</span>
          <button className="px-2 min-h-9 rounded border hover:bg-muted text-sm"
            onClick={() => setScale(s => Math.min(2.5, s + 0.2))}>+</button>
        </div>

        <div ref={containerRef} className="border border-border rounded-lg overflow-auto max-h-[80vh] flex flex-col items-center bg-muted/30">
          <Document
            file={blobUrl}
            onLoadSuccess={({ numPages }) => setNumPages(numPages)}
            loading={<div className="py-12 text-muted-foreground">解析 PDF…</div>}
            error={<div className="py-12 text-muted-foreground">PDF 解析失败,
              <a href={`/api/v1/documents/${documentId}/file`} className="text-primary ml-1">下载查看</a></div>}
          >
            {Array.from({ length: Math.min(shownPages, numPages) }, (_, i) => (
              <Page key={i} pageNumber={i + 1} scale={scale} className="mb-2 shadow-sm"
                renderTextLayer renderAnnotationLayer={false} />
            ))}
          </Document>

          {/* 懒加载:加载更多 */}
          {shownPages < numPages && (
            <button
              className="my-4 px-4 min-h-11 rounded-lg border hover:bg-muted text-sm"
              onClick={() => setShownPages(n => Math.min(n + PDF_BATCH, numPages))}>
              加载更多({shownPages}/{numPages} 页)
            </button>
          )}
          {numPages > 0 && shownPages >= numPages && (
            <div className="my-4 text-xs text-muted-foreground">共 {numPages} 页 · 已全部加载</div>
          )}
        </div>
      </div>
    );
  }

  // ── EPUB ──
  if (isEpub) {
    return (
      <div style={{ height: '75vh' }} className="border border-border rounded-lg overflow-hidden">
        <ReactReader
          url={blobUrl}
          location={epubLocation}
          locationChanged={(loc: string) => setEpubLocation(loc)}
          title={title}
        />
      </div>
    );
  }

  // ── 其他类型 ──
  return (
    <div className="py-8 text-center">
      <p className="text-muted-foreground mb-1">{title}</p>
      <p className="text-sm text-muted-foreground mb-4">此类型暂不支持内嵌预览（{mime}）</p>
      <a href={blobUrl} download={title} className="text-primary text-sm hover:underline">下载文件</a>
    </div>
  );
}
