'use client';

import { useState, useCallback } from 'react';
import { toast } from 'sonner';

const DOCS_BASE = process.env.NEXT_PUBLIC_DOCS_BASE || '/docs';

export default function DocToolsPage() {
  const [tab, setTab] = useState<'convert' | 'generate' | 'analyze' | 'extract' | 'ku'>('convert');
  const [busy, setBusy] = useState(false);

  // ── 转换 ──
  const [convertFile, setConvertFile] = useState<File | null>(null);
  const [convertType, setConvertType] = useState('pdf-to-md');
  const [convertResult, setConvertResult] = useState<{ md?: string; info?: string } | null>(null);

  const runConvert = useCallback(async () => {
    if (!convertFile) { toast.error('请选择文件'); return; }
    setBusy(true); setConvertResult(null);
    try {
      const fd = new FormData();
      fd.append('file', convertFile);
      const r = await fetch(`${DOCS_BASE}/convert/${convertType}`, { method: 'POST', body: fd });
      if (!r.ok) { toast.error('转换失败'); return; }
      if (convertType === 'pdf-to-docx') {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = (convertFile.name.replace(/\.\w+$/, '') || 'output') + '.docx';
        a.click(); URL.revokeObjectURL(url);
        toast.success('Word 已下载');
      } else {
        const d = await r.json();
        setConvertResult({ md: d.md, info: JSON.stringify(d.analyze || {}, null, 1) });
        toast.success('转换完成');
      }
    } catch (e) { toast.error('请求失败: ' + String(e)); }
    finally { setBusy(false); }
  }, [convertFile, convertType]);

  // ── AI 生成 ──
  const [genType, setGenType] = useState('docx');
  const [genTopic, setGenTopic] = useState('');
  const [genPrompt, setGenPrompt] = useState('');

  const runGenerate = useCallback(async () => {
    if (!genTopic) { toast.error('请输入主题'); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('doc_type', genType);
      fd.append('topic', genTopic);
      fd.append('prompt', genPrompt || `创建一份关于 ${genTopic} 的${genType === 'pptx' ? '演示文稿' : genType === 'xlsx' ? '表格' : '文档'}`);
      const r = await fetch(`${DOCS_BASE}/office/generate`, { method: 'POST', body: fd });
      if (!r.ok) { const e = await r.json().catch(() => null); toast.error('生成失败: ' + (e?.error || r.status)); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${genTopic}.${genType}`;
      a.click(); URL.revokeObjectURL(url);
      toast.success('已生成并下载');
    } catch (e) { toast.error('请求失败: ' + String(e)); }
    finally { setBusy(false); }
  }, [genType, genTopic, genPrompt]);

  // ── 分析 ──
  // ── KU 证据审查 ──
  const [kuSub, setKuSub] = useState('');
  const [kuHtml, setKuHtml] = useState('');

  const runKuReview = useCallback(async () => {
    if (!kuSub) { toast.error('请输入 substrate_id'); return; }
    setBusy(true); setKuHtml('');
    try {
      const fd = new FormData();
      fd.append('substrate', kuSub);
      fd.append('limit', '60');
      const r = await fetch(`${DOCS_BASE}/ku-visualize`, { method: 'POST', body: fd });
      if (!r.ok) { toast.error('失败 ' + r.status); return; }
      const d = await r.json();
      if (!d.ok) { toast.error('生成失败: ' + (d.log || '').slice(-100)); return; }
      setKuHtml(d.html || '');
      toast.success('已生成');
    } catch (e) { toast.error('请求失败: ' + String(e)); }
    finally { setBusy(false); }
  }, [kuSub]);

  // ── 结构化提取(LangExtract) ──
  const [exFile, setExFile] = useState<File | null>(null);
  const [exPrompt, setExPrompt] = useState('');
  const [exResult, setExResult] = useState<any>(null);

  const runExtract = useCallback(async () => {
    if (!exFile) { toast.error('请选择文件'); return; }
    if (!exPrompt) { toast.error('请输入提取指令'); return; }
    setBusy(true); setExResult(null);
    try {
      const fd = new FormData();
      fd.append('file', exFile);
      fd.append('prompt', exPrompt.startsWith('Extract') ? exPrompt : 'Extract as JSON. ' + exPrompt);
      fd.append('examples_json', '[]');
      const r = await fetch(`${DOCS_BASE}/extract`, { method: 'POST', body: fd });
      if (!r.ok) { toast.error('提取失败 ' + r.status); return; }
      setExResult(await r.json());
      toast.success('提取完成');
    } catch (e) { toast.error('请求失败: ' + String(e)); }
    finally { setBusy(false); }
  }, [exFile, exPrompt]);


  const runAnalyze = useCallback(async () => {
    if (!anFile) { toast.error('请选择文件'); return; }
    setBusy(true); setAnResult(null);
    try {
      const fd = new FormData();
      fd.append('file', anFile);
      const r = await fetch(`${DOCS_BASE}/convert/analyze`, { method: 'POST', body: fd });
      if (!r.ok) { toast.error('分析失败'); return; }
      setAnResult(await r.json());
      toast.success('分析完成');
    } catch (e) { toast.error('请求失败: ' + String(e)); }
    finally { setBusy(false); }
  }, [anFile]);

  const tabBtn = (id: typeof tab, label: string) => (
    <button onClick={() => setTab(id)} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}>{label}</button>
  );

  const fileInput = (set: (f: File | null) => void) => (
    <input type="file" onChange={(e) => set(e.target.files?.[0] || null)} className="block w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 file:text-sm file:font-medium" />
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">📄 文档工具</h1>
      <p className="text-sm text-gray-500 mb-6">PDF/Office 转换（pdf-inspector / anydoc 最强引擎）· AI 生成 Office（officecli）</p>

      <div className="flex gap-2 mb-6">{tabBtn('convert', '转换')}{tabBtn('generate', 'AI 生成')}{tabBtn('analyze', '分析')}{tabBtn('extract', '提取')}{tabBtn('ku', 'KU审查')}</div>

      {tab === 'convert' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">选择文件</label>
            {fileInput(setConvertFile)}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">转换类型</label>
            <select value={convertType} onChange={(e) => setConvertType(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
              <option value="pdf-to-md">PDF → Markdown（pdf-inspector 最强）</option>
              <option value="office-to-md">Office(docx/pptx/xlsx) → Markdown（anydoc）</option>
              <option value="pdf-to-docx">PDF → Word 全页图</option>
              <option value="epub-to-md">EPUB → Markdown</option>
            </select>
          </div>
          <button onClick={runConvert} disabled={busy} className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50">{busy ? '转换中...' : '开始转换'}</button>
          {convertResult?.md && (
            <div className="mt-4">
              <div className="text-xs text-gray-400 mb-1">分析：{convertResult.info}</div>
              <pre className="bg-gray-50 rounded-lg p-3 text-xs max-h-80 overflow-auto whitespace-pre-wrap">{convertResult.md.slice(0, 8000)}</pre>
            </div>
          )}
        </div>
      )}

      {tab === 'generate' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">类型</label>
            <select value={genType} onChange={(e) => setGenType(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
              <option value="docx">Word 文档</option>
              <option value="pptx">PPT 演示</option>
              <option value="xlsx">Excel 表格</option>
              <option value="report">报告（需输入文件）</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">主题</label>
            <input value={genTopic} onChange={(e) => setGenTopic(e.target.value)} placeholder="如：季度业务汇报" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">内容要求（可选）</label>
            <textarea value={genPrompt} onChange={(e) => setGenPrompt(e.target.value)} rows={4} placeholder="如：包含业绩增长、成本问题、下季度计划三部分" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <button onClick={runGenerate} disabled={busy} className="px-5 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium disabled:opacity-50">{busy ? '生成中（约1-3分钟）...' : '生成并下载'}</button>
          <p className="text-xs text-gray-400">生成走 officecli（NIM 模型），约 1-3 分钟，完成后自动下载。</p>
        </div>
      )}

      {tab === 'analyze' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">选择 PDF</label>
            {fileInput(setAnFile)}
          </div>
          <button onClick={runAnalyze} disabled={busy} className="px-5 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium disabled:opacity-50">{busy ? '分析中...' : '分析'}</button>
          {anResult && (
            <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-1">
              <p><span className="text-gray-500">类型：</span><b>{anResult.pdf_type}</b> <span className="text-gray-400">(置信度 {anResult.confidence})</span></p>
              <p><span className="text-gray-500">页数：</span>{anResult.page_count} 页 · 章节 {anResult.chapters}</p>
              {anResult.pages_needing_ocr?.length > 0 && (
                <p><span className="text-amber-600">⚠ 需要 OCR 的页：</span>{anResult.pages_needing_ocr.slice(0, 30).join(', ')}{anResult.pages_needing_ocr.length > 30 ? '...' : ''}</p>
              )}
              <p><span className="text-gray-500">分类：</span>{anResult.category}</p>
            </div>
          )}
        </div>
      )}

      {tab === 'extract' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">选择文件（txt/md/转换后的文档）</label>
            {fileInput(setExFile)}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">提取指令</label>
            <input value={exPrompt} onChange={(e) => setExPrompt(e.target.value)} placeholder="如：项目名称/建设单位/编制单位/项目地点" className="w-full px-3 py-2 border rounded-lg text-sm" />
            <p className="text-xs text-gray-400 mt-1">LangExtract 引擎：每个提取值精确映射回原文位置</p>
          </div>
          <button onClick={runExtract} disabled={busy} className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium disabled:opacity-50">{busy ? '提取中...' : '开始提取'}</button>
          {exResult?.extractions && (
            <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-1 max-h-80 overflow-auto">
              {exResult.extractions.slice(0, 30).map((e: any, i: number) => (
                <p key={i}><span className="text-violet-600 font-medium">[{e.class}]</span> {e.text}</p>
              ))}
              <p className="text-xs text-gray-400">共 {exResult.count} 条</p>
            </div>
          )}
        </div>
      )}

      {tab === 'ku' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">substrate_id（飞轮入库的书）</label>
            <input value={kuSub} onChange={(e) => setKuSub(e.target.value)} placeholder="如 math_prog_xxx / misc_zh_xxx" className="w-full px-3 py-2 border rounded-lg text-sm" />
            <p className="text-xs text-gray-400 mt-1">KU 证据字符级高亮审查（A 仓质量抽查）</p>
          </div>
          <button onClick={runKuReview} disabled={busy} className="px-5 py-2 rounded-lg bg-rose-600 text-white text-sm font-medium disabled:opacity-50">{busy ? '生成中...' : '生成审查视图'}</button>
          {kuHtml && <iframe srcDoc={kuHtml} className="w-full h-[70vh] border rounded-lg" />}
        </div>
      )}
    </div>
  );
}
