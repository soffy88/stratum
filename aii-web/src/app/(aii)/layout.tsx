'use client';

/**
 * (aii) route-group layout — AII pages inside Stratum's app shell (Sidebar + auth)
 * with the Helios providers @helios/blocks needs.
 *
 * Theme unification: the @helios theme follows Stratum's `data-theme` so the AII
 * pages are light/dark in sync with the rest of the app (no more black-AII /
 * white-Stratum split). Stratum dark → @helios "professional"; otherwise "zen".
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { OAppProviders } from '@helios/oui';
import { LangProvider } from '@helios/blocks';
import './globals.css';

function heliosTheme(dataTheme: string | null): string {
  return dataTheme === 'dark' ? 'professional' : 'zen';
}

export default function AiiLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, loadCurrentUser } = useAuthStore();
  const router = useRouter();
  const [theme, setTheme] = useState('zen');

  useEffect(() => { loadCurrentUser(); }, [loadCurrentUser]);

  // Mirror Stratum's data-theme onto the @helios theme, reactively.
  useEffect(() => {
    const el = document.documentElement;
    const sync = () => setTheme(heliosTheme(el.getAttribute('data-theme')));
    sync();
    const obs = new MutationObserver(sync);
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }
  if (!user) {
    router.replace('/login');
    return null;
  }

  return (
    <OAppProviders theme={theme}>
      <LangProvider lang="zh-en">
        <div className="flex flex-col md:flex-row h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
        </div>
      </LangProvider>
    </OAppProviders>
  );
}
