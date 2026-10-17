// Переключение светлой / тёмной темы без правок styles.css.
// Цвета берутся из уже существующих правил: `:root { --... }` (светлая) и
// `@media (prefers-color-scheme: dark) { :root { --... } }` (тёмная). Выбранная тема
// применяется инлайн-переменными на <html>, они сильнее правил из CSS.
// Дизайнер меняет палитру в styles.css — переключатель подхватывает её сам.

export type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

type Tokens = Record<string, string>;
let cache: { light: Tokens; dark: Tokens } | null = null;

function collect(style: CSSStyleDeclaration, into: Tokens) {
  for (let i = 0; i < style.length; i++) {
    const name = style[i];
    if (name.startsWith("--")) into[name] = style.getPropertyValue(name).trim();
  }
}

function readTokens() {
  if (cache) return cache;
  const light: Tokens = {};
  const dark: Tokens = {};
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // стили с другого домена (шрифты) прочитать нельзя
    }
    for (const rule of Array.from(rules)) {
      if (rule instanceof CSSStyleRule && rule.selectorText === ":root") collect(rule.style, light);
      if (rule instanceof CSSMediaRule && rule.conditionText.includes("prefers-color-scheme: dark")) {
        for (const inner of Array.from(rule.cssRules)) {
          if (inner instanceof CSSStyleRule && inner.selectorText === ":root") collect(inner.style, dark);
        }
      }
    }
  }
  if (Object.keys(light).length) cache = { light, dark };
  return { light, dark };
}

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function getTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage недоступен — берём системную тему */
  }
  return systemTheme();
}

export function applyTheme(theme: Theme) {
  const { light, dark } = readTokens();
  const root = document.documentElement;
  // тёмная палитра переопределяет только часть переменных, поэтому кладём её поверх светлой
  const tokens = theme === "dark" ? { ...light, ...dark } : light;
  for (const [name, value] of Object.entries(tokens)) root.style.setProperty(name, value);
  root.style.colorScheme = theme; // системные элементы (скроллбары, поля дат) тоже в теме
}

export function setTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* тема просто не запомнится */
  }
  applyTheme(theme);
}

/** При запуске: применить тему, только если пользователь выбирал её сам; иначе работает системная. */
export function initTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") applyTheme(saved);
  } catch {
    /* без localStorage — системная тема */
  }
}
