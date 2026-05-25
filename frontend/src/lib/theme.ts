export type Theme = "light" | "dark";

const STORAGE_KEY = "llm-nexus-theme";

export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : "dark";
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
  window.localStorage.setItem(STORAGE_KEY, theme);
}

/** SSR hydration 직전 깜빡임 방지 — <head> 에 inline 으로 실행. */
export const themeBootstrapScript = `
(function(){try{
  var v=localStorage.getItem('${STORAGE_KEY}');
  var t=(v==='light'||v==='dark')?v:'dark';
  if(t==='dark')document.documentElement.classList.add('dark');
}catch(e){document.documentElement.classList.add('dark');}})();
`;
