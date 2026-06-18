'use client';

/**
 * DocumentViewer — 按 mime 分发到 PdfReader / EpubReader / 其他。
 *
 * file endpoint 需 JWT → fetch 成 blob(带 token)。
 * PDF:blob URL 喂 @react-pdf-viewer。EPUB:ArrayBuffer 喂 react-reader(比 blob URL 稳)。
 * 大文件兜底(§6):>200MB 直接给下载,不内嵌;50-200MB 显示下载进度。
 */

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';
import { PdfReader } from './PdfReader';
import { EpubReader } from './EpubReader';

interface Props {
  documentId: string;
  mime: string;
  medium: string;
  title: string;
  byteSize?: number;
}

const MB = 1024 * 1024;

export default function DocumentViewer({ documentId, mime, medium, title, byteSize }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [buffer, setBuffer] = useState<ArrayBuffer | null>(null);
  const [loading, setLoading] = useState(true);
  const [pct, setPct] = useState(0);
  const [error, setError] = useState(false);

  const isPdf = mime?.includes('pdf') || medium === 'pdf';
  const isEpub = mime?.includes('epub') || medium === 'epub' || medium === 'book';
  const tooLarge = (byteSize ?? 0) > 200 * MB;

  useEffect(() => {
    if (tooLarge) { setLoading(false); return; }
    let url: string | null = null;
    let cancelled = false;
    setLoading(true); setError(false); setPct(0);

    apiClient
      .get(`/api/v1/documents/${documentId}/file`, {
        responseType: 'blob',
        onDownloadProgress: (e: { loaded: number; total?: number }) => {
          if (e.total) setPct(Math.round((e.loaded / e.total) * 100));
        },
      })
      .then(async res => {
        if (cancelled) return;
        const blob = res.data as Blob;
        if (isEpub) {
          setBuffer(await blob.arrayBuffer());
        } else {
          url = URL.createObjectURL(blob);
          setBlobUrl(url);
        }
        setLoading(false);
      })
      .catch(() => { if (!cancelled) { setError(true); setLoading(false); } });

    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [documentId, isEpub, tooLarge]);

  // 大文件兜底
  if (tooLarge) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <p className="mb-3">文件较大（{Math.round((byteSize ?? 0) / MB)}MB），建议下载查看</p>
        <a href={`/api/v1/documents/${documentId}/file`} className="text-primary hover:underline">下载文件</a>
      </div>
    );
  }

  if (loading) {
    const big = (byteSize ?? 0) > 50 * MB;
    return (
      <div className="py-12 text-center text-muted-foreground">
        {big ? '正在加载大文件' : '加载文件中'}…{pct > 0 && ` ${pct}%`}
        {pct > 0 && (
          <div className="max-w-xs mx-auto mt-3 h-1 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        无法加载文件。
        <a href={`/api/v1/documents/${documentId}/file`} className="text-primary ml-1 hover:underline">下载查看</a>
      </div>
    );
  }

  if (isPdf && blobUrl) return <PdfReader blobUrl={blobUrl} documentId={documentId} />;
  if (isEpub && buffer) return <EpubReader buffer={buffer} documentId={documentId} title={title} />;

  // 其他类型
  return (
    <div className="py-8 text-center">
      <p className="text-muted-foreground mb-1">{title}</p>
      <p className="text-sm text-muted-foreground mb-4">此类型暂不支持内嵌预览（{mime}）</p>
      <a href={`/api/v1/documents/${documentId}/file`} className="text-primary text-sm hover:underline">下载文件</a>
    </div>
  );
}
