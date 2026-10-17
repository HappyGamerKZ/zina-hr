// Кандидат узнаёт статус заявки по номеру и почте (публично, без входа).
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { ApplicationStatus, StepState } from "../api/types";
import { fmtDate, fmtDateTime } from "../i18n";
import Icon from "./Icon";
import { icons } from "./icons";
import { StageBadge, useVacancyTitle } from "./recruitment";

const STEP_ICON: Record<StepState, string> = {
  done: icons.done,
  current: icons.interview,
  pending: icons.pending,
  skipped: icons.more,
  rejected: icons.close,
  hired: icons.hired,
};

export default function TrackForm({ initialNumber = "" }: { initialNumber?: string }) {
  const { t } = useTranslation();
  const title = useVacancyTitle();
  const [number, setNumber] = useState(initialNumber);
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<ApplicationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      // публичный адрес: вход и CSRF не нужны
      const res = await fetch("/api/v1/careers/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: number.trim(), email: email.trim() }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(res.status === 429 ? t("common.error") : body?.detail ?? body?.error?.message ?? `HTTP ${res.status}`);
      setResult(body as ApplicationStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <form className="form" onSubmit={onSubmit}>
        <div>
          <h1>{t("track.title")}</h1>
          <p className="muted">{t("track.subtitle")}</p>
        </div>
        <label>
          {t("track.number")}
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="CV-0018" required />
        </label>
        <label>
          {t("track.email")}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn-primary" disabled={busy}>
          <Icon src={icons.search} size={18} />
          {t("track.check")}
        </button>
      </form>

      {result && (
        <section className="track-result">
          <div className="section-head">
            <div>
              <strong>{title(result.vacancy)}</strong>
              <p className="muted small">
                {result.number} · {t("track.applied", { date: fmtDate(result.created_at) })}
              </p>
            </div>
            <StageBadge stage={result.stage} />
          </div>
          <p className="track-state">{t(`track.state.${result.stage}`)}</p>
          <ol className="steps">
            {result.steps.map((s) => (
              <li key={s.key} className={`step step-${s.state}`}>
                <Icon src={STEP_ICON[s.state]} size={18} />
                <span>{s.key === "decision" ? t("recruitment.actions") : t(`recruitment.stage.${s.key}`)}</span>
              </li>
            ))}
          </ol>
          {result.next_interview && (
            <p className="icon-link">
              <Icon src={icons.calendar} size={18} />
              <span>
                {t("track.interview")}: <strong>{fmtDateTime(result.next_interview.scheduled_at)}</strong>
                {result.next_interview.location && ` · ${result.next_interview.location}`}
              </span>
            </p>
          )}
          {result.stage === "hired" && (
            <div>
              <strong>{t("track.docs_title")}</strong>
              <ul className="hire-steps">
                {[1, 2, 3, 4].map((n) => (
                  <li key={n}>
                    <Icon src={icons.documents} size={18} />
                    {t(`track.doc_${n}`)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
