import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useLiveNotifications } from "../api/live";
import type { Lang } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { setLang } from "../i18n";
import { getTheme, setTheme, type Theme } from "../theme";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  permission?: string;
  mobile?: boolean;
}

export default function Layout() {
  const { me, logout, can } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  // Уведомления: live-поток (SSE) присылает событие сразу → перечитываем счётчик.
  // Пришло новое уведомление (изменился latest_id) — обновляем заявки, главную и список
  // уведомлений без перезагрузки страницы. Пока поток не подключён — опрос раз в 10 с.
  const qc = useQueryClient();
  const live = useLiveNotifications(() => qc.invalidateQueries({ queryKey: ["notifications"] }));
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api<{ count: number; latest_id: number | null }>("/notifications/unread-count"),
    refetchInterval: live ? 60_000 : 10_000,
    refetchIntervalInBackground: true,
  });
  const latestId = unread.data?.latest_id;
  const seenId = useRef<number | null | undefined>(undefined);
  useEffect(() => {
    if (latestId === undefined) return;
    if (seenId.current !== undefined && seenId.current !== latestId) {
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["notifications", "list"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    }
    seenId.current = latestId;
  }, [latestId, qc]);

  const items: NavItem[] = [
    { to: "/", label: t("nav.home"), icon: "⌂", mobile: true },
    { to: "/requests", label: t("nav.requests"), icon: "✎", mobile: true },
    { to: "/academy", label: t("nav.academy"), icon: "▶", mobile: true },
    { to: "/ai", label: t("nav.ai"), icon: "✦", mobile: true },
    { to: "/profile", label: t("nav.profile"), icon: "☺", mobile: true },
    { to: "/team", label: t("nav.team"), icon: "☷", permission: "team.view" },
    { to: "/team/approvals", label: t("nav.approvals"), icon: "✓", permission: "requests.approve" },
    { to: "/recruitment", label: t("recruitment.nav"), icon: "◎", permission: "recruitment.interviews" },
  ];
  const visible = items.filter((i) => !i.permission || can(i.permission));

  const [theme, setThemeState] = useState<Theme>(getTheme);
  const toggleTheme = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setThemeState(next);
  };

  const switchLang = (lang: Lang) => {
    setLang(lang);
    api("/me", { method: "PATCH", body: { locale: lang } }).catch(() => undefined);
  };

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const count = unread.data?.count ?? 0;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">J</span>
          <div>
            <div className="brand-name">{t("app.name")}</div>
            <div className="brand-sub">{t("app.tagline")}</div>
          </div>
        </div>
        <nav>
          {visible.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/" || i.to === "/team"} className="nav-link">
              <span className="nav-icon" aria-hidden>
                {i.icon}
              </span>
              {i.label}
            </NavLink>
          ))}
          {can("hr.admin") && (
            <a className="nav-link" href="/admin/" target="_blank" rel="noreferrer">
              <span className="nav-icon" aria-hidden>
                ⚙
              </span>
              {t("nav.admin")}
            </a>
          )}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-user">
            <strong>{me?.full_name}</strong>
            {me && <span className="role-chip">{t(`role.${me.role}`)}</span>}
          </div>
          <div className="topbar-actions">
            <div className="lang-switch" role="group" aria-label="Language">
              {(["ru", "kk"] as Lang[]).map((l) => (
                <button
                  key={l}
                  className={i18n.language === l ? "active" : ""}
                  onClick={() => switchLang(l)}
                >
                  {l === "ru" ? "RU" : "KZ"}
                </button>
              ))}
            </div>
            <button
              className="btn-ghost"
              onClick={toggleTheme}
              title={theme === "dark" ? t("theme.to_light") : t("theme.to_dark")}
              aria-label={theme === "dark" ? t("theme.to_light") : t("theme.to_dark")}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
            <NavLink to="/notifications" className="bell" aria-label={t("nav.notifications")}>
              🔔{count > 0 && <span className="badge-count">{count}</span>}
            </NavLink>
            <button className="btn-ghost" onClick={onLogout}>
              {t("nav.logout")}
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-nav">
        {visible
          .filter((i) => i.mobile)
          .map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"} className="bottom-link">
              <span aria-hidden>{i.icon}</span>
              <small>{i.label}</small>
            </NavLink>
          ))}
      </nav>
    </div>
  );
}
