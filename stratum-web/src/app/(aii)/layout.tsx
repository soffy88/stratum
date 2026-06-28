'use client';

/**
 * (aii) route-group layout — the ported AII pages now live INSIDE Stratum's app
 * shell (same Sidebar + auth as the (app) group), wrapped in the Helios providers
 * the @helios/blocks components need. This makes AII a set of modules within the
 * Stratum frontend rather than a separate site.
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { OAppProviders } from '@helios/oui';
import { LangProvider } from '@helios/blocks';
import './globals.css';

export default function AiiLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, loadCurrentUser } = useAuthStore();
  const router = useRouter();

  useEffect(() => { loadCurrentUser(); }, [loadCurrentUser]);

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }
  if (!user) {
    router.replace('/login');
    return null;
  }

  return (
    <OAppProviders theme="professional">
      <LangProvider lang="zh-en">
        <div className="flex flex-col md:flex-row h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
        </div>
      </LangProvider>
    </OAppProviders>
  );
}
