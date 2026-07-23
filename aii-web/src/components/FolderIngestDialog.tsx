'use client';

/**
 * FolderIngestDialog — 文件夹监听,含 AI 处理选项(§2.5)
 * 创建时带 generate_derivatives,后续每次入库应用同样配置。
 */

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AIProcessingOptions } from './AIProcessingOptions';
import { apiClient } from '@/lib/apiClient';

export function FolderIngestDialog({ open, onClose, onCreated }: {
  open: boolean; onClose: () => void; onCreated?: () => void;
}) {
  const [path, setPath] = useState('');
  const [description, setDescription] = useState('');
  const [derivatives, setDerivatives] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!path.trim()) { toast.error('请输入文件夹路径'); return; }
    setLoading(true);
    try {
      await apiClient.post('/api/v1/folder-watch', {
        path: path.trim(),
        description: description.trim() || undefined,
        generate_derivatives: derivatives,
      });
      toast.success('已开始监听');
      onCreated?.(); onClose();
    } catch { toast.error('创建监听失败'); }
    finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>文件夹监听</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-4 py-2">
          <div className="grid gap-1.5">
            <span className="text-sm">路径</span>
            <Input value={path} onChange={e => setPath(e.target.value)} placeholder="/mnt/user/books/数学" className="min-h-11" />
          </div>
          <div className="grid gap-1.5">
            <span className="text-sm">告知要找什么资料</span>
            <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="数学教材" className="min-h-11" />
          </div>
          <AIProcessingOptions value={derivatives} onChange={setDerivatives} />
          <p className="text-xs text-muted-foreground">批量应用:后续每次入库都使用同样的 AI 处理配置。</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
          <Button onClick={submit} disabled={loading || !path.trim()} className="min-h-11">
            {loading ? '创建中…' : '开始监听'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
