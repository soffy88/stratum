import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: {
    default: "aii — 你的个人知识基座",
    template: "%s | aii",
  },
  description:
    "aii 将你的文档、笔记和想法连接成可搜索、可推理的知识网络。本地优先，隐私安全。",
  keywords: ["知识库", "个人知识管理", "语义搜索", "笔记", "PKM"],
  openGraph: {
    type: "website",
    locale: "zh_CN",
    siteName: "aii",
    title: "aii — 你的个人知识基座",
    description:
      "将你的文档、笔记和想法连接成可搜索、可推理的知识网络。",
  },
  robots: {
    index: true,
    follow: true,
  },
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
