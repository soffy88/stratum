import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://aiinote.com"
  ),
  title: {
    default: "AII Note — 你的个人知识基座",
    template: "%s | AII Note",
  },
  description:
    "AII Note 将你的文档、笔记和想法连接成可搜索、可推理的知识网络。康奈尔笔记、知识飞轮、本地优先。",
  keywords: ["知识库", "康奈尔笔记", "个人知识管理", "语义搜索", "笔记", "PKM", "AII Note"],
  openGraph: {
    type: "website",
    locale: "zh_CN",
    url: "https://aiinote.com",
    siteName: "AII Note",
    title: "AII Note — 你的个人知识基座",
    description:
      "将你的文档、笔记和想法连接成可搜索、可推理的知识网络。康奈尔笔记与机器笔记共存。",
  },
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "https://aiinote.com",
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
