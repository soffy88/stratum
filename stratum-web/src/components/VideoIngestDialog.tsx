'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/apiClient';

export function VideoIngestDialog({ open, onClose, onIngested }: {
  open: boolean; onClose: () => void; onIngested?: () => void;
}) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    const trimmed = url.trim();
    if (!trimmed) { toast.error('请输入视频链接'); return; }
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be') && !trimmed.includes('bilibili.com')) {
      toast.error('目前支持 YouTube 和 Bilibili 链接');
      return;
    }
    setLoading(true);
    try {
      await apiClient.post('/api/v1/media/ingest', { video_url: trimmed });
      toast.success('已加入处理队列，字幕提取完成后将出现在文档列表');
      onIngested?.();
      onClose();
    } catch {
      toast.error('提交失败，请检查链接是否有效');
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !loading) submit();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>导入视频</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-4 py-2">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">视频链接</span>
            <Input
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={handleKey}
              placeholder="https://www.youtube.com/watch?v=..."
              className="min-h-11"
              autoFocus
            />
          </div>
          <p className="text-xs text-muted-foreground">
            支持 YouTube · Bilibili（需提供 Cookie）<br />
            视频不存储原文件，仅入库字幕/转录生成的结构化笔记。
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
          <Button onClick={submit} disabled={loading || !url.trim()} className="min-h-11">
            {loading ? '提交中…' : '入库'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
