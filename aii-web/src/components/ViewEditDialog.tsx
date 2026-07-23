'use client';

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createView, updateView, type View, type ViewFilter } from '@/lib/views';

const MEDIUM_OPTIONS: { value: string; label: string }[] = [
  { value: 'pdf', label: 'PDF' },
  { value: 'paper', label: '论文' },
  { value: 'book', label: '书籍' },
  { value: 'epub', label: '电子书' },
  { value: 'webpage', label: '网页' },
  { value: 'note', label: '笔记' },
];

const SORT_OPTIONS = [
  { value: 'created_at', label: '创建时间' },
  { value: 'updated_at', label: '更新时间' },
  { value: 'title', label: '标题' },
  { value: 'pin_priority', label: '置顶优先级' },
];

const DISPLAY_MODES = [
  { value: 'list', label: '列表' },
  { value: 'grid', label: '网格' },
  { value: 'compact', label: '紧凑' },
];

interface ViewEditDialogProps {
  open: boolean;
  view?: View | null;      // null/undefined = 新建
  onClose: () => void;
  onSaved: () => void;
}

export function ViewEditDialog({ open, view, onClose, onSaved }: ViewEditDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [icon, setIcon] = useState('');
  const [medium, setMedium] = useState<string[]>([]);
  const [tags, setTags] = useState('');
  const [tagExclude, setTagExclude] = useState('rss:*');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [displayMode, setDisplayMode] = useState('list');
  const [saving, setSaving] = useState(false);

  // 编辑时预填
  useEffect(() => {
    if (view) {
      setName(view.name);
      setDescription(view.description ?? '');
      setIcon(view.icon ?? '');
      setMedium(view.filter_json?.medium ?? []);
      setTags((view.filter_json?.tags ?? []).join(', '));
      setTagExclude((view.filter_json?.tag_exclude ?? ['rss:*']).join(', '));
      setSortBy(view.sort_by);
      setSortOrder(view.sort_order);
      setDisplayMode(view.display_mode);
    } else {
      setName(''); setDescription(''); setIcon('');
      setMedium([]); setTags(''); setTagExclude('rss:*');
      setSortBy('created_at'); setSortOrder('desc'); setDisplayMode('list');
    }
  }, [view, open]);

  const toggleMedium = (v: string) =>
    setMedium(m => m.includes(v) ? m.filter(x => x !== v) : [...m, v]);

  const splitTags = (s: string) => s.split(',').map(t => t.trim()).filter(Boolean);

  const save = async () => {
    if (!name.trim()) { toast.error('名称不能为空'); return; }
    const filter_json: ViewFilter = {
      medium: medium.length ? medium : undefined,
      tags: splitTags(tags).length ? splitTags(tags) : undefined,
      tag_exclude: splitTags(tagExclude).length ? splitTags(tagExclude) : undefined,
    };
    const body: Partial<View> = {
      name: name.trim(), description: description.trim() || undefined, icon: icon.trim() || undefined,
      filter_json, sort_by: sortBy, sort_order: sortOrder, display_mode: displayMode,
    };
    setSaving(true);
    try {
      if (view) { await updateView(view.id, body); toast.success('已保存'); }
      else { await createView(body); toast.success('视图已创建'); }
      onSaved(); onClose();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? '保存失败');
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{view ? '编辑视图' : '新建视图'}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="grid gap-1.5">
            <Label>名称 *</Label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="例: 量化金融" />
          </div>
          <div className="grid gap-1.5">
            <Label>说明</Label>
            <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="可选" />
          </div>
          <div className="grid gap-1.5">
            <Label>图标（emoji）</Label>
            <Input value={icon} onChange={e => setIcon(e.target.value)} placeholder="📈" className="w-24" />
          </div>

          <div className="grid gap-1.5">
            <Label>内容类型</Label>
            <div className="grid grid-cols-3 gap-2">
              {MEDIUM_OPTIONS.map(o => (
                <label key={o.value} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={medium.includes(o.value)} onChange={() => toggleMedium(o.value)} />
                  {o.label}
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label>标签（逗号分隔）</Label>
            <Input value={tags} onChange={e => setTags(e.target.value)} placeholder="quant, finance, trading" />
          </div>
          <div className="grid gap-1.5">
            <Label>排除标签（逗号分隔）</Label>
            <Input value={tagExclude} onChange={e => setTagExclude(e.target.value)} placeholder="rss:*" />
          </div>

          <div className="flex gap-3">
            <div className="grid gap-1.5 flex-1">
              <Label>排序</Label>
              <select className="border rounded-md px-2 py-2 text-sm bg-background min-h-11"
                value={sortBy} onChange={e => setSortBy(e.target.value)}>
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="grid gap-1.5 flex-1">
              <Label>顺序</Label>
              <select className="border rounded-md px-2 py-2 text-sm bg-background min-h-11"
                value={sortOrder} onChange={e => setSortOrder(e.target.value)}>
                <option value="desc">降序</option>
                <option value="asc">升序</option>
              </select>
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label>显示模式</Label>
            <div className="flex gap-4">
              {DISPLAY_MODES.map(m => (
                <label key={m.value} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="display_mode" checked={displayMode === m.value}
                    onChange={() => setDisplayMode(m.value)} />
                  {m.label}
                </label>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="min-h-11">取消</Button>
          <Button onClick={save} disabled={saving} className="min-h-11">{saving ? '保存中…' : '保存'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
