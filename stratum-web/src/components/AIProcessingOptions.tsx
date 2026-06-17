'use client';

/**
 * AIProcessingOptions — AI 处理选项(上传/URL/文件夹共用)
 * markdown 必选不可取消;concepts disabled(即将推出)。
 */

interface AIProcessingOptionsProps {
  value: string[];           // 已选,如 ['translation', 'audio']
  onChange: (v: string[]) => void;
}

interface AIOption {
  key: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  hint?: string;
}

const OPTIONS: AIOption[] = [
  { key: 'markdown', label: '提取 Markdown', required: true },
  { key: 'translation', label: '翻译为中文', hint: '仅英文内容' },
  { key: 'audio', label: '生成音频朗读' },
  { key: 'illustration', label: '生成插图' },
  { key: 'concepts', label: '自动抽取概念', disabled: true, hint: '即将推出' },
];

export function AIProcessingOptions({ value, onChange }: AIProcessingOptionsProps) {
  const toggle = (key: string) =>
    onChange(value.includes(key) ? value.filter(k => k !== key) : [...value, key]);

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-muted-foreground">AI 处理选项</div>
      <div className="flex flex-col gap-1.5">
        {OPTIONS.map(opt => {
          const checked = opt.required || value.includes(opt.key);
          return (
            <label
              key={opt.key}
              className={`flex items-center gap-2 text-sm min-h-9 ${opt.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={opt.required || opt.disabled}
                onChange={() => !opt.required && !opt.disabled && toggle(opt.key)}
              />
              <span>{opt.label}</span>
              {opt.required && <span className="text-xs text-muted-foreground">(基础,不可取消)</span>}
              {opt.hint && <span className="text-xs text-muted-foreground">（{opt.hint}）</span>}
            </label>
          );
        })}
      </div>
    </div>
  );
}
