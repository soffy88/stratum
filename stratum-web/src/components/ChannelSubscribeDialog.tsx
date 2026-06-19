'use client';

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AIProcessingOptions } from './AIProcessingOptions';
import { apiClient } from '@/lib/apiClient';

interface ChannelSubscription {
  id: string;
  channel_url: string;
  channel_title: string | null;
  status: 'active' | 'paused';
  scan_status: 'idle' | 'scanning' | 'completed' | 'error';
  last_check: string | null;
  found_count: number;
  ingested_count: number;
  current_video: string | null;
}

export function ChannelSubscribeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [channelUrl, setChannelUrl] = useState('');
  
  // 过滤规则
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
  const [subscriptions, setSubscriptions] = useState<ChannelSubscription[]>([]);
  const [loadingList, setLoadingList] = useState(false);

  // 加载订阅列表
  const fetchSubscriptions = async () => {
    try {
      const res = await apiClient.get<ChannelSubscription[]>('/api/v1/channels');
      setSubscriptions(res.data || []);
    } catch {
      toast.error('加载订阅列表失败');
    }
  };

  useEffect(() => {
    if (open) {
      setLoadingList(true);
      fetchSubscriptions().finally(() => setLoadingList(false));
    }
  }, [open]);

  // 进度轮询：如果列表中有正在扫描的通道，每 5 秒轮询一次
  useEffect(() => {
    const hasScanning = subscriptions.some(sub => sub.scan_status === 'scanning');
    let timer: NodeJS.Timeout | null = null;
    if (open && hasScanning) {
      timer = setInterval(() => {
        fetchSubscriptions();
      }, 5000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [subscriptions, open]);

  // 提交订阅
  const handleSubmit = async () => {
    if (!channelUrl.trim()) {
      toast.error('请输入频道地址');
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        channel_url: channelUrl.trim(),
        after_date: afterDate.trim() || null,
        limit: limit ? parseInt(limit, 10) : null,
        min_duration_min: minDurationMin ? parseFloat(minDurationMin) : null,
        max_duration_min: maxDurationMin ? parseFloat(maxDurationMin) : null,
        title_include: titleInclude ? titleInclude.split(',').map(s => s.trim()).filter(Boolean) : [],
        title_exclude: titleExclude ? titleExclude.split(',').map(s => s.trim()).filter(Boolean) : [],
        llm_filter: llmFilter.trim() || null,
        incremental,
      };

      await apiClient.post('/api/v1/channels/subscribe', body);
      toast.success('订阅成功');
      setChannelUrl('');
      // 重置规则表单
      setAfterDate('');
      setLimit('');
      setMinDurationMin('');
      setMaxDurationMin('');
      setTitleInclude('');
      setTitleExclude('');
      setLlmFilter('');
      
      // 刷新列表
      fetchSubscriptions();
    } catch (err) {
      toast.error('订阅失败');
    } finally {
      setSubmitting(false);
    }
  };

  // 切换暂停/恢复
  const toggleStatus = async (sub: ChannelSubscription) => {
    const nextStatus = sub.status === 'active' ? 'paused' : 'active';
    try {
      await apiClient.patch(`/api/v1/channels/${sub.id}`, { status: nextStatus });
      toast.success(nextStatus === 'active' ? '已重新激活订阅' : '已暂停订阅');
      fetchSubscriptions();
    } catch {
      toast.error('切换状态失败');
    }
  };

  // 删除订阅
  const handleDelete = async (subId: string) => {
    if (!confirm('确认要删除该订阅吗？')) return;
    try {
      await apiClient.delete(`/api/v1/channels/${subId}`);
      toast.success('已删除订阅');
      fetchSubscriptions();
    } catch {
      toast.error('删除订阅失败');
    }
  };

  // 格式化时间戳显示
  const formatTime = (tsStr: string | null) => {
    if (!tsStr) return '从未';
    try {
      const d = new Date(tsStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' (' + d.toLocaleDateString() + ')';
    } catch {
      return tsStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-6 overflow-hidden bg-background border border-border rounded-lg shadow-xl">
        <div className="shrink-0">
          <DialogHeader>
            <DialogTitle>订阅频道</DialogTitle>
          </DialogHeader>
        </div>
        
        <div className="flex-1 overflow-y-auto pr-1 py-2 space-y-6">
          {/* 订阅表单 */}
          <div className="space-y-4">
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">频道地址</span>
              <Input
                value={channelUrl}
                onChange={e => setChannelUrl(e.target.value)}
                placeholder="YouTube 频道/播放列表 URL (例如: https://www.youtube.com/@3blue1brown)"
                className="min-h-11"
              />
            </div>

            <div className="border border-border/80 rounded-lg p-4 space-y-4 bg-muted/20">
              <span className="text-sm font-medium block">过滤规则（不填 = 全部）</span>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">时间范围 (某日期后)</span>
                  <Input
                    type="date"
                    value={afterDate}
                    onChange={e => setAfterDate(e.target.value)}
                    className="min-h-10"
                  />
                </div>
                
                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">数量上限 (最新 N 个)</span>
                  <Input
                    type="number"
                    value={limit}
                    onChange={e => setLimit(e.target.value)}
                    placeholder="例如: 5"
                    className="min-h-10"
                  />
                </div>

                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">时长范围-最小 (分钟)</span>
                  <Input
                    type="number"
                    value={minDurationMin}
                    onChange={e => setMinDurationMin(e.target.value)}
                    placeholder="0"
                    className="min-h-10"
                  />
                </div>

                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">时长范围-最大 (分钟)</span>
                  <Input
                    type="number"
                    value={maxDurationMin}
                    onChange={e => setMaxDurationMin(e.target.value)}
                    placeholder="无限制"
                    className="min-h-10"
                  />
                </div>

                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">标题包含 (逗号分隔)</span>
                  <Input
                    value={titleInclude}
                    onChange={e => setTitleInclude(e.target.value)}
                    placeholder="关键词1, 关键词2"
                    className="min-h-10"
                  />
                </div>

                <div className="grid gap-1.5">
                  <span className="text-xs text-muted-foreground">标题排除 (逗号分隔)</span>
                  <Input
                    value={titleExclude}
                    onChange={e => setTitleExclude(e.target.value)}
                    placeholder="排除词1, 排除词2"
                    className="min-h-10"
                  />
                </div>
              </div>

              <div className="grid gap-1.5 pt-2 border-t border-border/60">
                <span className="text-xs text-muted-foreground">智能筛选 (LLM 语义筛选描述)</span>
                <Input
                  value={llmFilter}
                  onChange={e => setLlmFilter(e.target.value)}
                  placeholder="例如: 只保留讲解线性代数或几何学相关的视频"
                  className="min-h-10"
                />
              </div>

              <label className="flex items-center gap-2 text-sm pt-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={incremental}
                  onChange={e => setIncremental(e.target.checked)}
                  className="rounded text-primary focus:ring-primary"
                />
                <span className="text-xs font-medium">增量订阅（新发布视频自动入库）</span>
              </label>
            </div>

            <div className="border border-border/80 rounded-lg p-4 bg-muted/20">
              <AIProcessingOptions value={derivatives} onChange={setDerivatives} />
            </div>
          </div>

          {/* 订阅列表 */}
          <div className="pt-4 border-t border-border">
            <span className="text-sm font-medium block mb-3">订阅列表</span>
            
            {loadingList ? (
              <div className="text-xs text-muted-foreground text-center py-6">正在加载订阅...</div>
            ) : subscriptions.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-6">暂无任何频道订阅。</div>
            ) : (
              <div className="space-y-3 max-h-56 overflow-y-auto pr-1">
                {subscriptions.map(sub => (
                  <div key={sub.id} className="flex items-start justify-between gap-4 p-3 border border-border rounded-lg bg-card hover:bg-muted/10 transition-colors">
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-base">📺</span>
                        <span className="text-sm font-medium truncate" title={sub.channel_title || sub.channel_url}>
                          {sub.channel_title || sub.channel_url}
                        </span>
                        {sub.status === 'paused' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">已暂停</span>
                        )}
                      </div>
                      
                      <div className="text-xs text-muted-foreground space-y-0.5 pl-6">
                        {sub.scan_status === 'scanning' ? (
                          <div className="flex items-center gap-2 text-primary font-medium">
                            <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                            <span>
                              扫描中... {sub.current_video ? `当前: ${sub.current_video}` : ''} 
                              {sub.ingested_count > 0 ? ` (已入库 ${sub.ingested_count})` : ''}
                            </span>
                          </div>
                        ) : sub.scan_status === 'completed' ? (
                          <div>
                            ✓ 上次检查: {formatTime(sub.last_check)} · 共入库: <span className="font-semibold text-foreground">{sub.ingested_count}</span>
                          </div>
                        ) : sub.scan_status === 'error' ? (
                          <div className="text-destructive font-medium break-all">
                            ❌ 失败: {sub.current_video || '未知错误'}
                          </div>
                        ) : (
                          <div>未激活扫描</div>
                        )}
                        <div className="text-[10px] text-muted-foreground/80 truncate break-all">
                          URL: {sub.channel_url}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 pt-0.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleStatus(sub)}
                        className="h-8 px-2.5 text-xs"
                      >
                        {sub.status === 'active' ? '暂停' : '激活'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(sub.id)}
                        className="h-8 px-2.5 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 pt-4 border-t border-border">
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
