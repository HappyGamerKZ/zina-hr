import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { Lang } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { setLang } from "../i18n";

export default function LoginPage() {
  const { me, login } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to="/" replace />;

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
      <form className="card login-card" onSubmit={onSubmit}>
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
        <h1>{t("login.title")}</h1>
        <p className="muted">{t("login.subtitle")}</p>
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
    </div>
  );
}
