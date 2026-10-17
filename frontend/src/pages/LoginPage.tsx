import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { Lang } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import ResumeForm from "../components/ResumeForm";
import { setLang } from "../i18n";

type Tab = "login" | "resume";

export default function LoginPage() {
  const { me, login } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  // /login?tab=resume (или /careers) — сразу открыть форму резюме
  const tab: Tab = params.get("tab") === "resume" || location.pathname === "/careers" ? "resume" : "login";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (me && tab === "login") return <Navigate to="/" replace />;

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
    <div className="login-page">
      <div className="card login-card">
        <div className="lang-switch login-lang">
          {(["ru", "kk"] as Lang[]).map((l) => (
            <button
              type="button"
              key={l}
              className={i18n.language === l ? "active" : ""}
              onClick={() => setLang(l)}
            >
              {l === "ru" ? "RU" : "KZ"}
            </button>
          ))}
        </div>
        <span className="brand-mark big">J</span>
        <div className="tabs">
          {(["login", "resume"] as Tab[]).map((k) => (
            <button
              key={k}
              type="button"
              className={tab === k ? "active" : ""}
              onClick={() => setParams(k === "resume" ? { tab: "resume" } : {})}
            >
              {k === "login" ? t("careers.tab_login") : t("careers.tab_resume")}
            </button>
          ))}
        </div>

        {tab === "resume" ? (
          <ResumeForm />
        ) : (
          <form className="form" onSubmit={onSubmit}>
            <div>
              <h1>{t("login.title")}</h1>
              <p className="muted">{t("login.subtitle")}</p>
            </div>
            <label>
              {t("login.username")}
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
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
            {error && <p className="error">{error}</p>}
            <button className="btn-primary" disabled={busy}>
              {t("login.submit")}
            </button>
            <p className="muted small">{t("login.demo")}</p>
          </form>
        )}
      </div>
    </div>
  );
}
