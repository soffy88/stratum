'use client';

import { type ReactNode } from 'react';
import { clsx } from 'clsx';

interface DialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange?.(false)} />
      <div className="relative z-50">{children}</div>
    </div>
  );
}

export function DialogContent({ className, children }: { className?: string; children?: ReactNode }) {
  return (
    <div className={clsx('bg-background rounded-lg shadow-lg p-6 w-full max-w-lg', className)}>
      {children}
    </div>
  );
}

export function DialogHeader({ children }: { children?: ReactNode }) {
  return <div className="mb-4">{children}</div>;
}

export function DialogTitle({ children }: { children?: ReactNode }) {
  return <h2 className="text-lg font-semibold">{children}</h2>;
}

export function DialogFooter({ children }: { children?: ReactNode }) {
  return <div className="flex justify-end gap-2 mt-6">{children}</div>;
}
