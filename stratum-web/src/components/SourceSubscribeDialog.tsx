'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/apiClient';

type SourceType = 'arxiv' | 'gutenberg' | 'oapen';

const SOURCE_OPTIONS: { id: SourceType; label: string; desc: string }[] = [
  { id: 'arxiv',      label: '📰 arXiv 论文',   desc: '自动抓取最新学术论文 PDF' },
  { id: 'gutenberg',  label: '📚 Gutenberg 公版书', desc: '免费电子书 epub/txt（英文公版）' },
  { id: 'oapen',      label: '📖 OAPEN 开放书',  desc: '开放获取学术书（主要 Springer OA，PDF）' },
];

const ARXIV_PRESETS = [
  { id: 'q-fin.TR', label: 'q-fin.TR 交易' },
  { id: 'q-fin.PM', label: 'q-fin.PM 组合管理' },
  { id: 'q-fin.CP', label: 'q-fin.CP 计算金融' },
  { id: 'q-fin.RM', label: 'q-fin.RM 风险管理' },
  { id: 'q-fin.MF', label: 'q-fin.MF 数理金融' },
  { id: 'math.PR',  label: 'math.PR 概率论' },
  { id: 'math.OC',  label: 'math.OC 最优控制' },
  { id: 'stat.ML',  label: 'stat.ML 统计机器学习' },
  { id: 'cs.LG',    label: 'cs.LG 机器学习' },
  { id: 'cs.AI',    label: 'cs.AI 人工智能' },
  { id: 'econ.GN',  label: 'econ.GN 经济学' },
  { id: 'physics.data-an', label: 'physics 数据分析' },
];

export function SourceSubscribeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [sourceType, setSourceType] = useState<SourceType>('arxiv');
  const [name, setName] = useState('');
  const [maxResults, setMaxResults] = useState('10');
  const [submitting, setSubmitting] = useState(false);

  // arXiv state
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [customCat, setCustomCat] = useState('');
  const [keywords, setKeywords] = useState('');
  const [author, setAuthor] = useState('');
  const [afterDate, setAfterDate] = useState('');

  // Gutenberg state
  const [gbTopic, setGbTopic] = useState('');
  const [gbLanguages, setGbLanguages] = useState('en');
  const [gbKeywords, setGbKeywords] = useState('');
  const [gbAuthor, setGbAuthor] = useState('');

  // OAPEN state
  const [oapenQuery, setOapenQuery] = useState('');
  const [oapenLang, setOapenLang] = useState('');

  const toggleCat = (cat: string) => {
    setSelectedCats(prev => prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]);
  };

  const buildQuery = (): Record<string, unknown> => {
    if (sourceType === 'arxiv') {
      const cats = [...selectedCats, ...customCat.split(',').map(s => s.trim()).filter(Boolean)];
      return {
        categories: cats,
        keywords: keywords.trim() || null,
        author: author.trim() || null,
        after_date: afterDate.trim() || null,
      };
    }
    if (sourceType === 'gutenberg') {
      return {
        topic: gbTopic.trim() || null,
        languages: gbLanguages.split(',').map(s => s.trim()).filter(Boolean),
        keywords: gbKeywords.trim() || null,
        author: gbAuthor.trim() || null,
      };
    }
    return {
      query: oapenQuery.trim(),
      language: oapenLang.trim() || null,
    };
  };

  const validate = (): string | null => {
    if (sourceType === 'arxiv') {
      const cats = [...selectedCats, ...customCat.split(',').map(s => s.trim()).filter(Boolean)];
      if (!cats.length && !keywords.trim() && !author.trim())
        return '请至少选一个分类、或填写关键词/作者';
    }
    if (sourceType === 'gutenberg') {
      if (!gbTopic.trim() && !gbKeywords.trim() && !gbAuthor.trim())
        return '请填写主题、关键词或作者';
    }
    if (sourceType === 'oapen') {
      if (!oapenQuery.trim()) return '请填写搜索词';
    }
    return null;
  };

  const handleSubmit = async () => {
    const err = validate();
    if (err) { toast.error(err); return; }
    setSubmitting(true);
    try {
      await apiClient.post('/api/v1/sources/subscribe', {
        name: name.trim() || undefined,
        source_type: sourceType,
        query: buildQuery(),
        max_results: parseInt(maxResults, 10) || 10,
      });
      toast.success('订阅成功，正在后台抓取，进度在「后台任务」区查看');
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
            <DialogTitle>订阅资料源</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground mt-1">
            自动抓取新内容入库，进度在「后台任务」区查看。
          </p>
        </div>

        <div className="flex-1 overflow-y-auto pr-1 py-3 space-y-4">
          {/* 源选择 */}
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">选择来源</span>
            <div className="grid grid-cols-3 gap-2">
              {SOURCE_OPTIONS.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSourceType(s.id)}
                  className={`text-xs px-2 py-2.5 rounded-lg border text-left transition-colors ${
                    sourceType === s.id
                      ? 'bg-primary/10 border-primary text-primary font-medium'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <div>{s.label}</div>
                  <div className="text-muted-foreground mt-0.5 leading-tight">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 订阅名称 */}
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">订阅名称（可选）</span>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="如：量化金融资料" className="min-h-10" />
          </div>

          {/* arXiv 表单 */}
          {sourceType === 'arxiv' && (
            <>
              <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
                <span className="text-sm font-medium block">arXiv 分类</span>
                <div className="flex flex-wrap gap-2">
                  {ARXIV_PRESETS.map(cat => (
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
                  <span className="text-xs text-muted-foreground">自定义分类（逗号分隔）</span>
                  <Input value={customCat} onChange={e => setCustomCat(e.target.value)} placeholder="cs.CV, q-fin.EC" className="min-h-9 text-xs" />
                </div>
              </div>
              <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
                <span className="text-sm font-medium block">过滤条件</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="grid gap-1">
                    <span className="text-xs text-muted-foreground">关键词</span>
                    <Input value={keywords} onChange={e => setKeywords(e.target.value)} placeholder="reinforcement learning" className="min-h-9" />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-xs text-muted-foreground">作者</span>
                    <Input value={author} onChange={e => setAuthor(e.target.value)} placeholder="Merton" className="min-h-9" />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-xs text-muted-foreground">发布日期（此后）</span>
                    <Input type="date" value={afterDate} onChange={e => setAfterDate(e.target.value)} className="min-h-9" />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-xs text-muted-foreground">每次最多获取（篇）</span>
                    <Input type="number" value={maxResults} onChange={e => setMaxResults(e.target.value)} min={1} max={50} placeholder="10" className="min-h-9" />
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Gutenberg 表单 */}
          {sourceType === 'gutenberg' && (
            <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
              <span className="text-sm font-medium block">搜索条件</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="grid gap-1">
                  <span className="text-xs text-muted-foreground">主题（Gutenberg 分类）</span>
                  <Input value={gbTopic} onChange={e => setGbTopic(e.target.value)} placeholder="mathematics" className="min-h-9" />
                </div>
                <div className="grid gap-1">
                  <span className="text-xs text-muted-foreground">语言（逗号分隔）</span>
                  <Input value={gbLanguages} onChange={e => setGbLanguages(e.target.value)} placeholder="en" className="min-h-9" />
                </div>
                <div className="grid gap-1">
                  <span className="text-xs text-muted-foreground">关键词</span>
                  <Input value={gbKeywords} onChange={e => setGbKeywords(e.target.value)} placeholder="calculus" className="min-h-9" />
                </div>
                <div className="grid gap-1">
                  <span className="text-xs text-muted-foreground">作者名</span>
                  <Input value={gbAuthor} onChange={e => setGbAuthor(e.target.value)} placeholder="Euclid" className="min-h-9" />
                </div>
              </div>
              <div className="grid gap-1 pt-1 border-t border-border/60">
                <span className="text-xs text-muted-foreground">每次最多获取（本）</span>
                <Input type="number" value={maxResults} onChange={e => setMaxResults(e.target.value)} min={1} max={20} placeholder="5" className="min-h-9 max-w-[120px]" />
              </div>
              <p className="text-[11px] text-muted-foreground">
                下载 epub（优先）或 txt 格式，入库后可阅读和检索。
              </p>
            </div>
          )}

          {/* OAPEN 表单 */}
          {sourceType === 'oapen' && (
            <div className="border border-border/80 rounded-lg p-4 space-y-3 bg-muted/20">
              <span className="text-sm font-medium block">搜索条件</span>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">搜索词（学科/主题）</span>
                <Input value={oapenQuery} onChange={e => setOapenQuery(e.target.value)} placeholder="economics finance" className="min-h-9" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">语言过滤（可选，如 en）</span>
                <Input value={oapenLang} onChange={e => setOapenLang(e.target.value)} placeholder="en" className="min-h-9 max-w-[120px]" />
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">每次最多获取（本）</span>
                <Input type="number" value={maxResults} onChange={e => setMaxResults(e.target.value)} min={1} max={20} placeholder="5" className="min-h-9 max-w-[120px]" />
              </div>
              <p className="text-[11px] text-amber-600/80 dark:text-amber-400/80 bg-amber-50 dark:bg-amber-950/30 rounded p-2 leading-relaxed">
                ⚠️ 仅支持 Springer OA（PDF 可直接下载）；T&amp;F、Nomos 等出版商书目可能跳过。首次扫描耗时较长（逐书查询 Unpaywall）。
              </p>
            </div>
          )}
        </div>

        <div className="shrink-0 pt-3 border-t border-border">
          <DialogFooter>
            <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
            <Button onClick={handleSubmit} disabled={submitting} className="min-h-11">
              {submitting ? '提交中...' : '订阅'}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
