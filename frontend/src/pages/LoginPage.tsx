import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { Lang } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import ResumeForm from "../components/ResumeForm";
import TrackForm from "../components/TrackForm";
import { setLang } from "../i18n";
import logo from "../assets/logo.webp";

// Шаги входа: выбор роли → вход (сотрудник / HR) или раздел кандидата (резюме / статус заявки).
// Роль на экране выбора — только подсказка: права определяет учётная запись на сервере.
type Role = "employee" | "hr" | "candidate";
type CandidateTab = "resume" | "track";

const ROLES: { key: Role; icon: string }[] = [
  { key: "employee", icon: icons.profile },
  { key: "hr", icon: icons.employees },
  { key: "candidate", icon: icons.candidates },
];

function SignInForm({ role }: { role: "employee" | "hr" }) {
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={onSubmit}>
      <div>
        <h1>{role === "hr" ? t("auth.login_hr") : t("auth.login_employee")}</h1>
        <p className="muted">{t("login.subtitle")}</p>
      </div>
      <label>
        {t("auth.username")}
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
      </label>
      <label>
        {t("login.password")}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      <button type="button" className="link-btn forgot" onClick={() => setForgot((v) => !v)}>
        {t("auth.forgot")}
      </button>
      {forgot && <p className="hint">{t("auth.forgot_hint")}</p>}
      {error && <p className="error">{error}</p>}
      <button className="btn-primary" disabled={busy}>
        <Icon src={icons.logIn} size={18} />
        {t("login.submit")}
      </button>
      <p className="muted small">{t("login.demo")}</p>
    </form>
  );
}

export default function LoginPage() {
  const { me } = useAuth();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [params, setParams] = useSearchParams();

  // /careers и /login?tab=resume — сразу форма резюме; ?tab=track — статус заявки
  const tabParam = params.get("tab");
  const candidateTab: CandidateTab = tabParam === "track" ? "track" : "resume";
  const role: Role | null =
    location.pathname === "/careers" || tabParam === "resume" || tabParam === "track"
      ? "candidate"
      : (params.get("role") as Role | null);

  if (me && role !== "candidate") return <Navigate to="/" replace />;

  const go = (next: Record<string, string>) => setParams(next);

  return (
    <div className="auth-split">
      <div className="auth-main">
        <div className="auth-top">
          <div className="auth-brand">
            <img src={logo} alt="" className="auth-logo" />
            <strong>{t("app.name")}</strong>
          </div>
          <div className="lang-switch">
            {(["ru", "kk"] as Lang[]).map((l) => (
              <button type="button" key={l} className={i18n.language === l ? "active" : ""} onClick={() => setLang(l)}>
                {l === "ru" ? "RU" : "KZ"}
              </button>
            ))}
          </div>
        </div>

        <div className="auth-body">
          {role === null && (
            <div className="stack">
              <div>
                <h1>{t("auth.choose_title")}</h1>
                <p className="muted">{t("auth.choose_sub")}</p>
              </div>
              {ROLES.map((r, idx) => (
                <button key={r.key} type="button" className={`role-card tone-${idx + 1}`} onClick={() => go({ role: r.key })}>
                  <span className="role-icon">
                    <Icon src={r.icon} size={24} />
                  </span>
                  <span className="role-text">
                    <strong>{t(`auth.${r.key}`)}</strong>
                    <small>{t(`auth.${r.key}_sub`)}</small>
                  </span>
                  <Icon src={icons.forward} />
                </button>
              ))}
            </div>
          )}

          {role !== null && (
            <div className="stack">
              <button type="button" className="link-btn back-link" onClick={() => go({})}>
                <Icon src={icons.back} size={16} />
                {t("auth.other_role")}
              </button>
              {role === "candidate" ? (
                <>
                  <div className="tabs">
                    {(["resume", "track"] as CandidateTab[]).map((k) => (
                      <button key={k} type="button" className={candidateTab === k ? "active" : ""} onClick={() => go({ tab: k })}>
                        {k === "resume" ? t("careers.tab_resume") : t("track.tab")}
                      </button>
                    ))}
                  </div>
                  {candidateTab === "resume" ? <ResumeForm /> : <TrackForm />}
                </>
              ) : (
                <SignInForm role={role} />
              )}
            </div>
          )}
        </div>
      </div>

      <aside className="auth-side" aria-hidden>
        <img src={logo} alt="" className="auth-side-logo" />
        <h2>{t("app.name")}</h2>
        <p>{t("app.tagline")}</p>
        <div className="auth-side-card">{t("auth.side_text")}</div>
      </aside>
    </div>
  );
}
