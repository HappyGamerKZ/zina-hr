// Цветные иллюстрации Jana HR (src/assets/jana-hr-icons/*/illustrations) для пустых состояний.
// В отличие от контурных иконок, у них свои цвета, поэтому для тёмной темы берётся вариант из dark/.
import { useEffect, useState, type ReactNode } from "react";

import { getTheme, THEME_EVENT, type Theme } from "../theme";

const files = import.meta.glob("../assets/jana-hr-icons/*/illustrations/*.svg", {
  eager: true,
  import: "default",
}) as Record<string, string>;

export type IllustrationName =
  | "calendar-check" | "certificate" | "chat" | "clock" | "folder" | "growth" | "leaf" | "team";

function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(getTheme);
  useEffect(() => {
    const update = () => setTheme(getTheme());
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    window.addEventListener(THEME_EVENT, update);
    media?.addEventListener?.("change", update);
    return () => {
      window.removeEventListener(THEME_EVENT, update);
      media?.removeEventListener?.("change", update);
    };
  }, []);
  return theme;
}

export default function Illustration({ name, size = 96 }: { name: IllustrationName; size?: number }) {
  const theme = useTheme();
  const src = files[`../assets/jana-hr-icons/${theme}/illustrations/${name}.svg`];
  return src ? <img src={src} alt="" aria-hidden width={size} height={size} /> : null;
}

/** Пустое состояние: иллюстрация + текст (и, при желании, кнопка). */
export function EmptyState({ name, text, children }: { name: IllustrationName; text: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <Illustration name={name} />
      <p className="muted">{text}</p>
      {children}
    </div>
  );
}
