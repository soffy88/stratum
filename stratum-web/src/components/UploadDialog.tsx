"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface UploadResult {
  substrate_id: string | null;
  title: string;
  medium: string;
  status: string;
  derivatives_queued: string[];
}

type Phase = "input" | "uploading" | "success" | "error";
type OptionalDerivative = "translation" | "audio" | "illustration";

const OPTIONAL_DERIVATIVES: { key: OptionalDerivative; label: string }[] = [
  { key: "translation", label: "翻译为中文" },
  { key: "audio", label: "生成音频朗读" },
  { key: "illustration", label: "生成插图" },
];

function isPdfOrEpub(files: File[]): boolean {
  return files.length > 0 && files.every(
    (f) => f.type === "application/pdf" || f.name.endsWith(".pdf") || f.name.endsWith(".epub"),
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function UploadDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess?: (substrateId: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [derivatives, setDerivatives] = useState<Set<OptionalDerivative>>(new Set());
  const [phase, setPhase] = useState<Phase>("input");
  const [progress, setProgress] = useState(0);
  const [currentFileName, setCurrentFileName] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const singleFile = files.length === 1;
  const showChapters = isPdfOrEpub(files);

  function toggleDerivative(key: OptionalDerivative) {
    setDerivatives((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function reset() {
    setFiles([]);
    setTitle("");
    setTags("");
    setDerivatives(new Set());
    setPhase("input");
    setProgress(0);
    setCurrentFileName("");
    setResult(null);
    setErrorMsg("");
    if (inputRef.current) inputRef.current.value = "";
  }

  function pickFiles(fileList: FileList) {
    setFiles(Array.from(fileList));
  }

  async function handleUpload() {
    if (!files.length) return;
    setPhase("uploading");
    setProgress(0);
    const token = apiClient.getAccessToken();
    let lastResult: UploadResult | null = null;

    for (const file of files) {
      setCurrentFileName(file.name);
      try {
        const r = await new Promise<UploadResult>((resolve, reject) => {
          const form = new FormData();
          form.append("file", file);
          if (singleFile && title.trim()) form.append("title_override", title.trim());
          if (tags.trim()) form.append("tags", tags.trim());
          for (const d of derivatives) form.append("derivatives", d);

          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/v1/inbox/submit");
          if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
          xhr.withCredentials = true;
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
          };
          xhr.onload = () => {
            let data: Record<string, unknown> = {};
            try {
              data = JSON.parse(xhr.responseText) as Record<string, unknown>;
            } catch { /* empty */ }
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(data as unknown as UploadResult);
            } else {
              reject(new Error((data.detail as string) ?? `HTTP ${xhr.status}`));
            }
          };
          xhr.onerror = () => reject(new Error("网络错误"));
          xhr.ontimeout = () => reject(new Error("上传超时"));
          xhr.send(form);
        });
        lastResult = r;
        if (r.substrate_id && onSuccess) onSuccess(r.substrate_id);
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : String(e));
        setPhase("error");
        return;
      }
    }

    setResult(lastResult);
    setPhase("success");
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-lg shadow-xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">上传文件</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* ── Input Phase ── */}
        {phase === "input" && (
          <div className="space-y-4">
            {/* File picker */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                文件 <span className="text-red-500">*</span>
              </label>
              <div
                className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:bg-[var(--color-border)]/10 transition"
                onClick={() => inputRef.current?.click()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files.length) pickFiles(e.dataTransfer.files);
                }}
                onDragOver={(e) => e.preventDefault()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  hidden
                  onChange={(e) => {
                    if (e.target.files?.length) pickFiles(e.target.files);
                  }}
                />
                {files.length === 0 ? (
                  <span className="text-sm text-[var(--color-muted)]">
                    点击选择 或拖拽文件到此处
                  </span>
                ) : (
                  <ul className="text-sm text-left space-y-0.5">
                    {files.map((f, i) => (
                      <li key={i} className="text-[var(--color-foreground)]">
                        {f.name}{" "}
                        <span className="text-[var(--color-muted)] text-xs">
                          ({(f.size / 1024).toFixed(0)} KB)
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Title override — single file only */}
            {singleFile && (
              <div>
                <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                  标题{" "}
                  <span className="text-[var(--color-muted)] font-normal">(可选，留空用文件名)</span>
                </label>
                <input
                  type="text"
                  placeholder={files[0]?.name ?? ""}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
                />
              </div>
            )}

            {/* Tags */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                标签{" "}
                <span className="text-[var(--color-muted)] font-normal">(可选，逗号分隔)</span>
              </label>
              <input
                type="text"
                placeholder="机器学习, python, 论文"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
              />
            </div>

            {/* AI options */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-2">
                AI 处理选项
              </label>
              <div className="space-y-2 pl-0.5">
                {/* Always-on base options */}
                <label className="flex items-center gap-2 text-sm text-[var(--color-muted)]">
                  <input type="checkbox" checked readOnly className="accent-[var(--color-primary)]" />
                  提取 markdown
                  <span className="text-xs">(基础，不可取消)</span>
                </label>
                {showChapters && (
                  <label className="flex items-center gap-2 text-sm text-[var(--color-muted)]">
                    <input type="checkbox" checked readOnly className="accent-[var(--color-primary)]" />
                    章节切分
                    <span className="text-xs">(PDF/EPUB 自动)</span>
                  </label>
                )}
                {/* Optional derivatives */}
                {OPTIONAL_DERIVATIVES.map(({ key, label }) => (
                  <label
                    key={key}
                    className="flex items-center gap-2 text-sm cursor-pointer hover:text-[var(--color-foreground)] text-[var(--color-muted)]"
                  >
                    <input
                      type="checkbox"
                      checked={derivatives.has(key)}
                      onChange={() => toggleDerivative(key)}
                      className="accent-[var(--color-primary)]"
                    />
                    {label}
                  </label>
                ))}
                {/* Coming soon */}
                <label className="flex items-center gap-2 text-sm opacity-40 cursor-not-allowed">
                  <input type="checkbox" disabled />
                  自动抽取概念
                  <span className="text-xs">(即将推出)</span>
                </label>
              </div>
            </div>

            <button
              onClick={() => void handleUpload()}
              disabled={!files.length}
              className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
            >
              {files.length > 1 ? `上传 ${files.length} 个文件` : "上传"}
            </button>
          </div>
        )}

        {/* ── Uploading Phase ── */}
        {phase === "uploading" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-8 h-8 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
            <div>
              <p className="text-sm font-medium">正在处理 {currentFileName}...</p>
              <p className="text-xs text-[var(--color-muted)] mt-1">AI 解析通常需要 10-60 秒</p>
            </div>
            {progress > 0 && progress < 100 && (
              <div className="w-48 bg-[var(--color-border)] rounded-full h-1.5 overflow-hidden">
                <div
                  className="h-full bg-[var(--color-primary)] transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* ── Success Phase ── */}
        {phase === "success" && result && (
          <div className="space-y-4">
            <div className="p-4 bg-green-50 border border-green-200 rounded">
              <p className="text-sm font-semibold text-green-800 mb-3">✓ 已入库</p>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-xs text-[var(--color-muted)]">标题</dt>
                  <dd className="font-medium">{result.title || currentFileName}</dd>
                </div>
                <div className="flex gap-6 flex-wrap">
                  <div>
                    <dt className="text-xs text-[var(--color-muted)]">类型</dt>
                    <dd>{result.medium}</dd>
                  </div>
                  {result.derivatives_queued?.length > 0 && (
                    <div>
                      <dt className="text-xs text-[var(--color-muted)]">后台处理中</dt>
                      <dd className="text-xs">{result.derivatives_queued.join("、")}</dd>
                    </div>
                  )}
                </div>
              </dl>
            </div>
            <div className="flex gap-2 flex-wrap">
              {result.substrate_id && (
                <Link
                  href={`/documents/${result.substrate_id}`}
                  onClick={onClose}
                  className="px-4 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
                >
                  查看完整 →
                </Link>
              )}
              <button
                onClick={reset}
                className="px-4 py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]"
              >
                继续上传
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-[var(--color-muted)] hover:underline"
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {/* ── Error Phase ── */}
        {phase === "error" && (
          <div className="space-y-4">
            <div className="p-4 bg-red-50 border border-red-200 rounded">
              <p className="text-sm font-medium text-red-800 mb-1">上传失败</p>
              <p className="text-sm text-red-700">{errorMsg}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={reset}
                className="px-4 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
              >
                重试
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-[var(--color-muted)] hover:underline"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
