'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/apiClient';

const PRESET_CATEGORIES = [
  { id: 'q-fin.TR', label: 'q-fin.TR 交易' },
  { id: 'q-fin.PM', label: 'q-fin.PM 组合管理' },
  { id: 'q-fin.CP', label: 'q-fin.CP 计算金融' },
  { id: 'q-fin.RM', label: 'q-fin.RM 风险管理' },
  { id: 'q-fin.MF', label: 'q-fin.MF 数理金融' },
  { id: 'math.PR', label: 'math.PR 概率论' },
  { id: 'math.OC', label: 'math.OC 最优控制' },
  { id: 'stat.ML', label: 'stat.ML 统计机器学习' },
  { id: 'cs.LG', label: 'cs.LG 机器学习' },
  { id: 'cs.AI', label: 'cs.AI 人工智能' },
  { id: 'econ.GN', label: 'econ.GN 经济学' },
  { id: 'physics.data-an', label: 'physics 数据分析' },
];

export function ArxivSubscribeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState('');
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [customCat, setCustomCat] = useState('');
  const [keywords, setKeywords] = useState('');
  const [author, setAuthor] = useState('');
  const [afterDate, setAfterDate] = useState('');
  const [maxResults, setMaxResults] = useState('10');
  const [submitting, setSubmitting] = useState(false);

  const toggleCat = (cat: string) => {
    setSelectedCats(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const allCategories = [
    ...selectedCats.filter(c => !PRESET_CATEGORIES.find(p => p.id === c)),
    ...selectedCats,
  ];

  const handleSubmit = async () => {
    const cats = [
      ...selectedCats,
      ...customCat.split(',').map(s => s.trim()).filter(Boolean),
    ];
    if (!cats.length && !keywords.trim() && !author.trim()) {
      toast.error('请至少选择一个分类、或填写关键词/作者');
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post('/api/v1/arxiv/subscribe', {
        name: name.trim() || undefined,
        categories: cats,
        keywords: keywords.trim() || null,
        author: author.trim() || null,
        after_date: afterDate.trim() || null,
        max_results: parseInt(maxResults, 10) || 10,
      });
      toast.success('arXiv 订阅成功，正在后台抓取，进度在「后台任务」区查看');
      setName(''); setSelectedCats([]); setCustomCat('');
      setKeywords(''); setAuthor(''); setAfterDate(''); setMaxResults('10');
      onClose();
    } catch {
      toast.error('订阅失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={o => { if (!o) onClose(); }}>
      <DialogContent className="max-w-xl max-h-[90vh] flex flex-col p-6 overflow-hidden bg-background border border-border rounded-lg shadow-xl">
        <div className="shrink-0">
          <DialogHeader>
            <DialogTitle>订阅 arXiv 论文</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground mt-1">
            按分类/关键词自动抓取最新论文 PDF 入库，进度在「后台任务」区查看。
          </p>
        </div>

        <div className="flex-1 overflow-y-auto pr-1 py-3 space-y-4">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">订阅名称（可选）</span>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="如：量化RL" className="min-h-10" />
          </div>

          <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
            <span className="text-sm font-medium block">arXiv 分类</span>
            <div className="flex flex-wrap gap-2">
              {PRESET_CATEGORIES.map(cat => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => toggleCat(cat.id)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    selectedCats.includes(cat.id)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
            <div className="grid gap-1 pt-1 border-t border-border/60">
              <span className="text-xs text-muted-foreground">自定义分类（逗号分隔，如 cs.CV,q-fin.EC）</span>
              <Input value={customCat} onChange={e => setCustomCat(e.target.value)} placeholder="cs.CV, q-fin.EC" className="min-h-9 text-xs" />
            </div>
          </div>

          <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
            <span className="text-sm font-medium block">过滤条件（不填 = 仅按分类）</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">关键词（标题/摘要含）</span>
                <Input value={keywords} onChange={e => setKeywords(e.target.value)} placeholder="reinforcement learning" className="min-h-9" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">作者</span>
                <Input value={author} onChange={e => setAuthor(e.target.value)} placeholder="Merton" className="min-h-9" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">发布日期（此日期后）</span>
                <Input type="date" value={afterDate} onChange={e => setAfterDate(e.target.value)} className="min-h-9" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">每次最多获取（篇）</span>
                <Input type="number" value={maxResults} onChange={e => setMaxResults(e.target.value)} min={1} max={50} placeholder="10" className="min-h-9" />
              </div>
            </div>
          </div>
        </div>

        <div className="shrink-0 pt-3 border-t border-border">
          <DialogFooter>
            <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting}
              className="min-h-11"
            >
              {submitting ? '提交中...' : '订阅'}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
