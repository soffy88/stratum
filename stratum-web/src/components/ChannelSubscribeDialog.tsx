'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AIProcessingOptions } from './AIProcessingOptions';
import { apiClient } from '@/lib/apiClient';

export function ChannelSubscribeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [channelUrl, setChannelUrl] = useState('');
  const [afterDate, setAfterDate] = useState('');
  const [limit, setLimit] = useState('');
  const [minDurationMin, setMinDurationMin] = useState('');
  const [maxDurationMin, setMaxDurationMin] = useState('');
  const [titleInclude, setTitleInclude] = useState('');
  const [titleExclude, setTitleExclude] = useState('');
  const [llmFilter, setLlmFilter] = useState('');
  const [incremental, setIncremental] = useState(true);
  const [derivatives, setDerivatives] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!channelUrl.trim()) { toast.error('请输入频道地址'); return; }
    setSubmitting(true);
    try {
      await apiClient.post('/api/v1/channels/subscribe', {
        channel_url: channelUrl.trim(),
        after_date: afterDate.trim() || null,
        limit: limit ? parseInt(limit, 10) : null,
        min_duration_min: minDurationMin ? parseFloat(minDurationMin) : null,
        max_duration_min: maxDurationMin ? parseFloat(maxDurationMin) : null,
        title_include: titleInclude ? titleInclude.split(',').map(s => s.trim()).filter(Boolean) : [],
        title_exclude: titleExclude ? titleExclude.split(',').map(s => s.trim()).filter(Boolean) : [],
        llm_filter: llmFilter.trim() || null,
        incremental,
      });
      toast.success('订阅成功，进度在页面「后台任务」区查看');
      setChannelUrl(''); setAfterDate(''); setLimit('');
      setMinDurationMin(''); setMaxDurationMin('');
      setTitleInclude(''); setTitleExclude(''); setLlmFilter('');
      onClose();
    } catch { toast.error('订阅失败'); }
    finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-xl max-h-[90vh] flex flex-col p-6 overflow-hidden bg-background border border-border rounded-lg shadow-xl">
        <div className="shrink-0">
          <DialogHeader>
            <DialogTitle>订阅频道</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground mt-1">订阅后进度显示在「后台任务」区，无需保持此窗口开启。</p>
        </div>

        <div className="flex-1 overflow-y-auto pr-1 py-3 space-y-4">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">频道地址</span>
            <Input
              value={channelUrl}
              onChange={e => setChannelUrl(e.target.value)}
              placeholder="YouTube 频道/播放列表 URL"
              className="min-h-11"
            />
          </div>

          <div className="border border-border/80 rounded-lg p-4 space-y-4 bg-muted/20">
            <span className="text-sm font-medium block">过滤规则（不填 = 全部）</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">时间范围 (某日期后)</span>
                <Input type="date" value={afterDate} onChange={e => setAfterDate(e.target.value)} className="min-h-10" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">数量上限 (最新 N 个)</span>
                <Input type="number" value={limit} onChange={e => setLimit(e.target.value)} placeholder="例如: 5" className="min-h-10" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">时长最小 (分钟)</span>
                <Input type="number" value={minDurationMin} onChange={e => setMinDurationMin(e.target.value)} placeholder="0" className="min-h-10" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">时长最大 (分钟)</span>
                <Input type="number" value={maxDurationMin} onChange={e => setMaxDurationMin(e.target.value)} placeholder="无限制" className="min-h-10" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">标题包含 (逗号分隔)</span>
                <Input value={titleInclude} onChange={e => setTitleInclude(e.target.value)} placeholder="关键词1, 关键词2" className="min-h-10" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">标题排除 (逗号分隔)</span>
                <Input value={titleExclude} onChange={e => setTitleExclude(e.target.value)} placeholder="排除词1, 排除词2" className="min-h-10" />
              </div>
            </div>
            <div className="grid gap-1 pt-1 border-t border-border/60">
              <span className="text-xs text-muted-foreground">智能筛选 (LLM 语义描述)</span>
              <Input value={llmFilter} onChange={e => setLlmFilter(e.target.value)} placeholder="只保留讲线性代数的视频" className="min-h-10" />
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={incremental} onChange={e => setIncremental(e.target.checked)} className="rounded" />
              <span className="text-xs font-medium">增量订阅（新发布视频自动入库）</span>
            </label>
          </div>

          <div className="border border-border/80 rounded-lg p-4 bg-muted/20">
            <AIProcessingOptions value={derivatives} onChange={setDerivatives} />
          </div>
        </div>

        <div className="shrink-0 pt-3 border-t border-border">
          <DialogFooter>
            <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
            <Button onClick={handleSubmit} disabled={submitting || !channelUrl.trim()} className="min-h-11">
              {submitting ? '订阅中...' : '订阅'}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
