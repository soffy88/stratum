# Stratum — 你的 AI 知识管家

把英文资料消化成自己的知识。PDF / 网页 / RSS / 研究主题 → AI 翻译 / 摘要 / 朗读 / 插图 / 概念图谱。

> 当前版本: **alpha v1.0** (Phase 17.10)  
> 立即试用: **https://stratum.uex.hk**（免费注册）

---

## 真功能 (alpha v1.0)

### 主动获取
- 📄 **上传文件** — PDF、EPUB、Markdown、图片，拖拽或点击上传，含进度条
- 🌐 **URL 抓取网页** — 粘贴任意网页链接，服务端抓全文入库
- 📡 **RSS 订阅** — 输入网站首页或 Feed URL，自动发现，周期自动拉取
- 🔬 **AI 研究员** (待 omodul ship) — 输入研究主题，自动找资料 + 总结

### AI 加工
- 🌏 **英文翻译中文** — Translation Worker Agent
- 📝 **每日 / 每周摘要** — Daily Digest / Weekly Review Agent
- 🎧 **音频朗读** — edge-tts 驱动 (需配置 TTS)
- 🖼️ **插图生成** — DashScope wanxiang (需配置 DASHSCOPE_API_KEY)
- 💬 **阅读伙伴** — 针对你的资料库问答 (Reading Companion Agent)
- 🔧 **知识库 lint** — 检查结构问题 (Lint Bot Agent)

### 知识体系
- 🔍 **三层融合检索** — BM25 + 向量混合，覆盖文档 / 笔记 / hevi 内容
- 🧠 **概念图谱** — 概念节点 + 关联资料 ReactFlow 可视化
- 🔗 **反向链接 / wikilink** — `[[note_id]]` 笔记互链 + 反向链接面板
- ⏰ **时光机** — 按月查看历史入库内容

### 隐私
- alpha 期：数据存服务器，你删 = 真删
- 引流后 Pro tier 可选：用户网盘 (Google Drive / OneDrive) 同步

---

## 立即试用

```
https://stratum.uex.hk
```

1. 注册免费账号
2. 上传一份 PDF 或粘贴网页 URL
3. 跑 Translation Worker → 看中文翻译
4. 用融合搜索找资料

---

## 跟 Obsidian / Notion 真区别

| 功能             | Obsidian | Notion   | Stratum                      |
|------------------|----------|----------|------------------------------|
| AI 翻译          | ❌        | ❌        | ✅                            |
| AI 摘要 / 总结   | 🟡 插件  | 🟡 AI 加 | ✅                            |
| AI 主动研究      | ❌        | ❌        | ✅ (待 omodul ship)          |
| 音频朗读         | ❌        | ❌        | ✅                            |
| RSS 自动订阅入库 | ❌        | ❌        | ✅                            |
| 三层融合检索     | ❌        | ❌        | ✅ (含 hevi 专业内容)        |
| 双链 + 图谱      | ✅        | 🟡        | ✅                            |
| 数据所有权       | ✅ 本地  | ❌ 云     | 🟡 短期云, 长期 Pro 网盘    |

---

## 技术栈

- **前端**: Next.js 15 + TypeScript + Tailwind + @helios/blocks + ReactFlow
- **后端**: FastAPI + Python 3.14 + DuckDB + LanceDB + Tantivy
- **AI**: DashScope (Qwen3) + edge-tts + wanxiang
- **基础库**: obase / oprim / oskill / omodul (3O paradigm)
- **部署**: Docker Compose + Cloudflare Tunnel + nginx

---

## 本地开发

```bash
# Backend (stratum-sl / stratum-api)
cd /path/to/stratum
python3 -m pytest tests/ -q          # 292 tests

# Frontend
cd stratum-web
pnpm install && pnpm dev              # http://localhost:3000

# Docker 全栈
cd deploy
docker compose up -d
```

环境变量见 `/path/to/keys/.env` — 需要 `DASHSCOPE_API_KEY`, `JWT_SECRET`, `STRATUM_DB_PATH`。

---

## 反馈

页面右下角 FeedbackWidget 内嵌反馈，或联系 wiki@helios-plat.com。
