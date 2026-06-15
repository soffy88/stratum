'use client';

import { type ReactNode, type ButtonHTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface AlertDialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: ReactNode;
}

export function AlertDialog({ open, onOpenChange, children }: AlertDialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange?.(false)} />
      <div className="relative z-50">{children}</div>
    </div>
  );
}

export function AlertDialogContent({ children }: { children?: ReactNode }) {
  return (
    <div className="bg-background rounded-lg shadow-lg p-6 w-full max-w-md">
      {children}
    </div>
  );
}

export function AlertDialogHeader({ children }: { children?: ReactNode }) {
  return <div className="mb-4">{children}</div>;
}

export function AlertDialogTitle({ children }: { children?: ReactNode }) {
  return <h2 className="text-lg font-semibold">{children}</h2>;
}

export function AlertDialogDescription({ children }: { children?: ReactNode }) {
  return <p className="text-sm text-muted-foreground mt-1">{children}</p>;
}

export function AlertDialogFooter({ children }: { children?: ReactNode }) {
  return <div className="flex justify-end gap-2 mt-6">{children}</div>;
}

export function AlertDialogCancel({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={clsx('inline-flex items-center justify-center rounded-md border px-4 py-2 text-sm font-medium', className)}
      {...props}
    />
  );
}

export function AlertDialogAction({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={clsx('inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium', className)}
      {...props}
    />
  );
}
