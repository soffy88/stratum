export type Theme = "zen" | "light" | "dark";

export function getTheme(): Theme {
  if (typeof window === "undefined") return "zen";
  return (localStorage.getItem("stratum-theme") as Theme) || "zen";
}

export function setTheme(theme: Theme) {
  localStorage.setItem("stratum-theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
}
