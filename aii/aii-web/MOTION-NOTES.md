# aii-web v0.7.2 — anime.js (motion) 集成

## 背景
oui 1.7.0 已把 anime.js 设计为 optionalDependency:`@helios/oui/motion` 提供
staggerReveal / animateValue / orchestrate / motionAvailable,装了用动画、没装降级 no-op。
本版在 aii-web 真正激活它(此前 motion 调用全走降级路径,能力闲置)。

## v4 兼容性(已实测确认)
- 安装 animejs@^4 → 实际 4.5.0。
- v4 用命名导出:namespace 直接暴露 animate / stagger / createTimeline(default 为 undefined)。
- oui motion 层 `await import('animejs')` 后调 `_anime.animate/.stagger/.createTimeline` —— 与 v4 完全对上。
- 实测:数字滚动动画真实运行(中途值≠终值),无 JS 错误。

## 接入点
- 新增 `src/components/motion/Motion.tsx`:
  - `AnimatedNumber`:KPI/统计数字滚动(animateValue)。
  - `useStaggerReveal`:容器子元素交错入场(staggerReveal)。
- dashboard:矛盾发现 88 / 合并 1,683 / 节省 2,822 三处数字改 AnimatedNumber;
  区块卡片(.dash-card)数据到达后交错入场。

## 降级安全(已实测两路)
- 装了 animejs:数字滚动 + 卡片交错入场(5/5 验证)。
- 移走 animejs 重新构建+运行:build 仍 exit 0,数字直接显示终值,卡片可见,零 JS 错误(5/5 验证)。
- prefers-reduced-motion:motion 层内部直接置终值 / no-op(oui 已实现)。

## 后续(未做,YAGNI)
- 仅 dashboard 接入。其它页(knowledge 列表交错、hevi 队列入场)如需要可同法接,缺了再加。
- motion 现有 4 个 API 够用;路由转场/手势等更多场景需扩 oui motion 层(单独一轮)。
