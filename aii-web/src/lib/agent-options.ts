export type AgentOption = {
  value: string;
  label: string;
  description: string;
  requiresParam?: string;
};

export const AGENT_OPTIONS: AgentOption[] = [
  { value: "daily_digest_simple", label: "日报 (本地)", description: "写入「日报·日期」笔记 + 通知，无需 omodul" },
  { value: "daily_digest", label: "Daily Digest (omodul)", description: "omodul 工作流版每日摘要" },
  { value: "knowledge_lint", label: "知识库 Lint (本地)", description: "断链/孤立/矛盾 → Lint 报告笔记" },
  { value: "lint_bot", label: "Lint Bot (omodul)", description: "omodul LintBotAgent" },
  { value: "extract_merge", label: "Extract & Merge", description: "抽实体并补到概念页", requiresParam: "substrate_id" },
  { value: "weekly_review", label: "Weekly Review (周复盘)", description: "复盘本周的知识积累" },
  { value: "knowledge_curator", label: "Knowledge Curator (知识整理)", description: "整理 inbox 文件并自动分类" },
  { value: "translation_worker", label: "Translation Worker (翻译)", description: "翻译英文资料到中文" },
  { value: "reading_companion", label: "Reading Companion (阅读伙伴)", description: "针对你的资料库回答问题", requiresParam: "question" },
  { value: "audio_generator", label: "Audio Generator (音频朗读)", description: "为 substrate 生成朗读音频", requiresParam: "substrate_id" },
  { value: "illustration_agent", label: "Illustration Agent (插图生成)", description: "为 substrate 生成插图", requiresParam: "substrate_id" },
  { value: "researcher", label: "Researcher (主动研究)", description: "输入研究主题, 自动找资料 + 总结", requiresParam: "query" },
];
