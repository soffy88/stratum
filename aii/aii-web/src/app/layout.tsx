/**
 * root layout — providers + shell。
 *
 * 装配顺序(由外到内):
 *   1. <OAppProviders theme="professional" />  — ThemeProvider + 全套 Helios Providers
 *   2. <LangProvider lang="zh-en" />            — Wiki 拍板,中英并列默认
 *   3. <AppShell />                              — topbar + sidebar + content
 *   4. children                                  — Page 内容
 *
 * 注意:OAppProviders 已经包含 ThemeProvider;不要再嵌套 ThemeProvider。
 * LangProvider 是 v1.9.0 新加的,跟 ThemeProvider 平行,需要显式包一层。
 */
import type { Metadata } from 'next';
import { OAppProviders } from '@helios/oui';
import { LangProvider } from '@helios/blocks';
import { AppShell } from '@/components/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'AII · 认识论知识图谱 / Epistemic Knowledge Graph',
  description:
    'AII web — query / ingest / health / diagnose / evolution / governance. Frontend by Helios.',
  viewport: 'width=device-width, initial-scale=1, viewport-fit=cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <OAppProviders theme="professional">
          <LangProvider lang="zh-en">
            <AppShell>{children}</AppShell>
          </LangProvider>
        </OAppProviders>
      </body>
    </html>
  );
}
