import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import Icon from "./Icon";
import { icons } from "./icons";
import { AiChatProvider, AiPopup, clearStoredChats } from "./AiChat";
import { api } from "../api/client";
import { useLiveNotifications } from "../api/live";
import type { Lang } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { setLang } from "../i18n";
import { getTheme, setTheme, type Theme } from "../theme";
import logo from "../assets/logo.webp";
 
interface NavItem {
  to: string;
  label: string;
  icon: string; // путь к svg-файлу (см. icons.ts)
  permission?: string;
  mobile?: boolean;
}
 
export default function Layout() {
  const { me, logout, can } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [chatOpen, setChatOpen] = useState(false); // всплывающее окно AI Jana
  useEffect(() => {
    if (pathname === "/ai") setChatOpen(false); // на странице чата окно не нужно
  }, [pathname]);
 
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
    { to: "/", label: t("nav.home"), icon: icons.home, mobile: true },
    { to: "/requests", label: t("nav.requests"), icon: icons.requests, mobile: true },
    { to: "/academy", label: t("nav.academy"), icon: icons.academy, mobile: true },
    { to: "/ai", label: t("nav.ai"), icon: icons.ai, mobile: true },
    { to: "/profile", label: t("nav.profile"), icon: icons.profile, mobile: true },
    { to: "/team", label: t("nav.team"), icon: icons.team, permission: "team.view" },
    { to: "/team/approvals", label: t("nav.approvals"), icon: icons.approvals, permission: "requests.approve" },
    { to: "/recruitment/vacancies", label: t("hrdash.nav_vacancies"), icon: icons.recruitment, permission: "recruitment.manage" },
    {
      to: "/recruitment",
      label: can("recruitment.manage") ? t("hrdash.nav_candidates") : t("recruitment.nav"),
      icon: icons.candidates,
      permission: "recruitment.interviews",
    },
    { to: "/recruitment/calendar", label: t("hrdash.nav_calendar"), icon: icons.calendar, permission: "recruitment.interviews" },
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
    // содержимое курсов приходит с сервера на языке запроса — перечитать на новом языке
    qc.invalidateQueries({ queryKey: ["academy"] });
  };
 
  const onLogout = async () => {
    clearStoredChats(); // переписка AI Jana не должна достаться следующему пользователю вкладки
    await logout();
    navigate("/login");
  };
 
  const count = unread.data?.count ?? 0;
 
  return (
    <AiChatProvider>
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img src={logo} alt="" className="brand-logo" />
          <div>
            <div className="brand-name">{t("app.name")}</div>
            <div className="brand-sub">{t("app.tagline")}</div>
          </div>
        </div>
        <nav>
          {visible.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/" || i.to === "/team" || i.to === "/recruitment"} className="nav-link">
              <span className="nav-icon" aria-hidden>
                <Icon src={i.icon} />
              </span>
              {i.label}
            </NavLink>
          ))}
          {can("hr.admin") && (
            <a className="nav-link" href="/admin/" target="_blank" rel="noreferrer">
              <span className="nav-icon" aria-hidden>
                <Icon src={icons.admin} />
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
              <Icon src={theme === "dark" ? icons.sun : icons.moon} size={18} />
            </button>
            <NavLink to="/notifications" className="bell" aria-label={t("nav.notifications")}>
              <Icon src={icons.bell} size={22} />
              {count > 0 && <span className="badge-count">{count}</span>}
            </NavLink>
            <button className="btn-ghost" onClick={onLogout}>
              <Icon src={icons.logout} size={18} />
              {t("nav.logout")}
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
        {pathname !== "/ai" && (
          <>
            {chatOpen && <AiPopup onClose={() => setChatOpen(false)} />}
            <button
              type="button"
              className={`ai-fab${chatOpen ? " open" : ""}`}
              onClick={() => setChatOpen((v) => !v)}
              aria-expanded={chatOpen}
              aria-label={chatOpen ? t("ai.close") : t("me_card.ai_fab")}
              title={chatOpen ? t("ai.close") : t("me_card.ai_fab")}
            >
              <Icon src={chatOpen ? icons.close : icons.ai} size={26} />
            </button>
          </>
        )}
      </div>
 
      <nav className="bottom-nav">
        {visible
          .filter((i) => i.mobile)
          .map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"} className="bottom-link">
              <Icon src={i.icon} size={22} />
              <small>{i.label}</small>
            </NavLink>
          ))}
      </nav>
    </div>
    </AiChatProvider>
  );
}
