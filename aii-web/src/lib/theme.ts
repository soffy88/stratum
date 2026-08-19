export type Theme = "zen" | "light" | "dark";

// 注意: 用 window.localStorage 而非裸 localStorage —— Node 26 实验性全局
// localStorage(--localstorage-file 未提供时不可用)会遮蔽 jsdom 的 window 属性。
function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;  // 隐私模式/禁用存储时降级为默认主题
  }
}

export function getTheme(): Theme {
  const s = storage();
  if (!s) return "zen";
  return (s.getItem("stratum-theme") as Theme) || "zen";
}

export function setTheme(theme: Theme) {
  const s = storage();
  if (!s) return;
  s.setItem("stratum-theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
}
