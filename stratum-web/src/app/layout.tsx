import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Stratum",
  description: "Knowledge base system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" data-theme="zen">
      <body className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
