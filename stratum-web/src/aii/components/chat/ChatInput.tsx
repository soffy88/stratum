'use client';

import { useState, type KeyboardEvent } from 'react';

export function ChatInput({
  onSubmit,
  disabled,
}: {
  onSubmit: (message: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState('');

  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    onSubmit(t);
    setValue('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div style={{ display: 'flex', gap: 'var(--space-2, 8px)', alignItems: 'flex-end' }}>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        rows={2}
        placeholder="提问… (Enter 发送, Shift+Enter 换行)"
        style={{
          flex: 1,
          padding: 'var(--space-2-5, 10px) var(--space-3, 12px)',
          borderRadius: 'var(--radius, 0.5rem)',
          border: '1.5px solid var(--border)',
          background: 'var(--input)',
          color: 'var(--foreground)',
          fontSize: 'var(--text-sm, 0.8125rem)',
          lineHeight: 'var(--lh-normal, 1.5)',
          resize: 'none',
          outline: 'none',
          transition: 'border-color var(--duration-fast, 100ms)',
          fontFamily: 'inherit',
        }}
        onFocus={(e) => (e.target.style.borderColor = 'var(--ring)')}
        onBlur={(e)  => (e.target.style.borderColor = 'var(--border)')}
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        style={{
          padding: 'var(--space-2-5, 10px) var(--space-4, 16px)',
          borderRadius: 'var(--radius, 0.5rem)',
          background: 'var(--primary)',
          color: 'var(--primary-foreground)',
          border: 'none',
          cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
          fontSize: 'var(--text-sm, 0.8125rem)',
          fontWeight: 600,
          opacity: disabled || !value.trim() ? 0.45 : 1,
          transition: 'opacity var(--duration-fast, 100ms), transform var(--duration-fast, 100ms)',
          alignSelf: 'flex-end',
          flexShrink: 0,
        }}
        onMouseDown={(e) => { if (!disabled && value.trim()) (e.currentTarget as HTMLElement).style.transform = 'scale(0.97)'; }}
        onMouseUp={(e)   => { (e.currentTarget as HTMLElement).style.transform = 'scale(1)'; }}
      >
        {disabled ? '…' : '发送'}
      </button>
    </div>
  );
}
