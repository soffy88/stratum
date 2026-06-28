# AII 成果展示视图 + 基座升级 — 交付说明 (v0.7.0)

本版做两件事:
1. **基座升级**:blocks 2.0.0 → 2.8.0,oui 1.0.1 → 1.7.0;清理 vendor 历史 tgz。
2. **5 个成果展示视图**(AII-FRONTEND-DISPLAY-001):dashboard / knowledge / graph / clusters / books。

## 版本线说明
此前 starter → v0.6.0 的 package.json 一直是 0.1.0,版本号只体现在文件名,
每版真正变的是 vendor 基座。本版正式 bump 到 **0.7.0**,且 package.json 与之一致。

## 基座升级
- vendor 现仅保留:`helios-blocks-2.8.0.tgz`、`helios-oui-1.7.0.tgz`(历史 tgz 已清)。
- 跨版本(2.0.0→2.8.0 / 1.0.1→1.7.0)对本项目**无破坏性改动**:
  全 12 页升级后真实渲染验证,16/16 通过,无 JS 错误。
- globals.css CSS import 已对齐新基座导出(blocks 2.8.0 有 base.css;oui 1.7.0 导出 oui.css)。

## 新增页面(命门:诚实呈现可信度)
- `/dashboard` — 概览;可信度分布卡醒目标"绝大多数未确证"(proven 1 / unverified 9302)
- `/knowledge` — KU 浏览;grade 徽标 + 多书共有 + 筛选/分页 + 详情抽屉
- `/graph` — 知识子图;节点色=grade,实线=rule 边 / 虚线=llm 边,contradicts 标红
- `/clusters` — KC;"AII 综合·非原文断言"标注
- `/books` — BU;主要论断带 stance("X书主张")+ 独立 claim_grade;论点→论据 grade 独立

## 后端联调
- 8 个新 endpoint 走 `USE_MOCK` 开关,契约见 `src/types/api.ts` 末段。
- 当前 mock 模式可完整渲染验证;真后端就绪后设 `NEXT_PUBLIC_USE_MOCK=false`(默认)即接真实 `/api/...`。

## ReactFlow(重依赖,项目侧安装)
- `/graph` 动态导入 `reactflow`,未装时自动降级为内置 SVG 渲染(只读,功能完整)。
- 装后自动启用拖拽/缩放:`npm i reactflow`。build 不依赖它,缺失仅一条非致命 warning。

## 待跟进(非本轮)
- 无学科字段:仪表盘暂按 medium 展示,需后端加 subject。
- grade 几乎全 unverified:确证终审待批量推进(诚实,非缺陷)。

---

## v0.7.1 — BU 详情页视觉减负(AII-FRONTEND-BU-VISUAL-001)

问题:BU 详情排版拥挤(框线套框线、冗余图标、stance 重标签、留白不足)。
改法:留白 + 分隔线 + 缩进 + 轻量色标,取代层层边框 + 重标签 + 装饰图标。

- 论断:去独立框,改"左色条(stance 颜色)+ 留白 + grade 小色点"
- 论据:去套框,改"缩进 + 细竖线 + 小圆点 + grade 小色点 + 文字深浅"
- stance 立场:重标签框 → 灰色文字前缀 +左色条(stanceMeta:主张=琥珀/实证=青/事实=绿)
- grade 强弱:每条 OEpistemicBadge → 小色点 GradeDot(hover 看具体 grade)
- 删 📄🔵🟡 装饰图标
- "AII 综合"橙标:每卡挂 → 顶部一句说明
- 列表/详情留白加大

命门保留(轻量表达):stance 可辨、grade 强弱可辨、综合声明在顶部。
新增轻量件 `src/components/GradeMarkers.tsx`(GradeDot / gradeTextClass / stanceMeta)——
若 KU/KC/其它项目也要密集列表标 grade,可评估上提 blocks 做 OEpistemicBadge variant="dot"。

验证:mock 模式渲染,BU 列表+详情 7/8 通过(1 项为"AII综合"文本计数误报,非缺陷);
减负确认 rounded-md border 框 = 0;命门 grade 色点 25 个渲染;前后对比截图确认。

注:本轮仅改 BU(最拥挤)。KU/KC/graph 同类减负待后续(BU-VISUAL-001 §五)。
