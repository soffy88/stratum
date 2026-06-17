'use client';

/**
 * UrlIngestDialog — 输入网址抓取,含 AI 处理选项(§2.4)
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

export function UrlIngestDialog({ open, onClose, onIngested }: {
  open: boolean; onClose: () => void; onIngested?: () => void;
}) {
  const [url, setUrl] = useState('');
  const [derivatives, setDerivatives] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!url.trim()) { toast.error('请输入网址'); return; }
    setLoading(true);
    try {
      await apiClient.post('/api/v1/inbox/submit', {
        url: url.trim(),
        generate_derivatives: derivatives,
      });
      toast.success('已提交抓取');
      onIngested?.(); onClose();
    } catch { toast.error('抓取失败'); }
    finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>输入网址</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-4 py-2">
          <div className="grid gap-1.5">
            <span className="text-sm">URL</span>
            <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." className="min-h-11" />
          </div>
          <AIProcessingOptions value={derivatives} onChange={setDerivatives} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
          <Button onClick={submit} disabled={loading || !url.trim()} className="min-h-11">
            {loading ? '抓取中…' : '抓取'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
