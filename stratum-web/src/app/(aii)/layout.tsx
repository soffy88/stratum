/**
 * (aii) route-group layout — wraps the ported AII pages in the Helios design
 * system (OAppProviders + LangProvider + AppShell). This is a NESTED layout:
 * the <html>/<body> live in the app root layout, so they are NOT repeated here
 * (the original AII root layout had them; removed during the merge).
 */
import type { Metadata } from 'next';
import { OAppProviders } from '@helios/oui';
import { LangProvider } from '@helios/blocks';
import { AppShell } from '@/aii/components/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'AII · 认识论知识图谱 / Epistemic Knowledge Graph',
  description:
    'AII — query / ingest / health / diagnose / evolution / governance.',
};

export default function AiiLayout({ children }: { children: React.ReactNode }) {
  return (
    <OAppProviders theme="professional">
      <LangProvider lang="zh-en">
        <AppShell>{children}</AppShell>
      </LangProvider>
    </OAppProviders>
  );
}
