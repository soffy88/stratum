'use client';

/**
 * UploadDialog — 上传文件,含 AI 处理选项(§2.3)
 * 提交带 generate_derivatives(JSON string)。
 */

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AIProcessingOptions } from './AIProcessingOptions';
import { apiClient } from '@/lib/apiClient';

export function UploadDialog({ open, onClose, onUploaded }: {
  open: boolean; onClose: () => void; onUploaded?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [derivatives, setDerivatives] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  const submit = async () => {
    if (!file) { toast.error('请先选择文件'); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('generate_derivatives', JSON.stringify(derivatives));
      await apiClient.post('/api/v1/inbox/submit', fd);
      toast.success('已提交入库');
      onUploaded?.(); onClose();
    } catch { toast.error('上传失败'); }
    finally { setUploading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>上传文件</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-4 py-2">
          <label className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary min-h-24 flex flex-col items-center justify-center gap-1">
            <input type="file" accept=".pdf,.epub,.md,.txt" className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
            <span className="text-sm">{file ? file.name : '拖拽或点击选择文件'}</span>
            <span className="text-xs text-muted-foreground">支持 PDF / EPUB / MD / TXT</span>
          </label>
          <AIProcessingOptions value={derivatives} onChange={setDerivatives} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
          <Button onClick={submit} disabled={uploading || !file} className="min-h-11">
            {uploading ? '上传中…' : '上传'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
