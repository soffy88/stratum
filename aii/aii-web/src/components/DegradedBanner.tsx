/**
 * DegradedBanner — 红线 #6 实现:LLM 不可用时醒目提示。
 *
 * 设计原则:
 *   - 颜色:warning(yellow ring + bg-alert-warn)— 不是 success,不是 info
 *   - 默认 sticky 在内容顶部,关不掉(只能等结果刷新)
 *   - 文案克制不夸张,但不允许用户忽略
 *   - 提供 retry 按钮(可选)
 *
 * 用法:
 *   {state.degraded && <DegradedBanner onRetry={() => run(...)} />}
 */
'use client';

import type { ReactNode } from 'react';

export interface DegradedBannerProps {
  /** 可选的重试回调 */
  onRetry?: () => void;
  /** 自定义文案;不传用默认 */
  message?: ReactNode;
  className?: string;
}

export function DegradedBanner({ onRetry, message, className }: DegradedBannerProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className={[
        'flex items-start gap-3 px-4 py-3 rounded-md',
        'border-2 border-[color:var(--alert-warn,#d97706)]',
        'bg-[color:var(--alert-warn-bg,#fef3c7)]',
        'text-[color:var(--alert-warn-fg,#78350f)]',
        'text-sm',
        className ?? '',
      ].join(' ')}
    >
      <span aria-hidden="true" className="text-lg leading-5">⚠</span>
      <div className="flex-1 min-w-0">
        <div className="font-medium">
          降级结果 — LLM provider 不可用 / Degraded result — LLM provider unavailable
        </div>
        <div className="mt-1 opacity-80">
          {message ??
            '当前展示的是后端 fallback 数据,不代表完整推理质量。请勿据此做关键决策。/ Showing fallback data; do not use for critical decisions.'}
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 px-3 py-1 rounded border border-current text-xs font-medium hover:opacity-80"
        >
          重试 / Retry
        </button>
      )}
    </div>
  );
}
