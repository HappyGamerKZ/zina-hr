import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { CandidateAction, CandidateDetail, CandidateInterview, StepState } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { StageBadge, salary, useVacancyTitle } from "../components/recruitment";
import { fmtDate, fmtDateTime } from "../i18n";

// Шаги: серый — ещё не пройден, синий — текущий, ✓ — пройден, ✕ — отказ
const STEP_ICON: Record<StepState, string> = {
  done: "✅",
  current: "🔵",
  pending: "⚪",
  skipped: "⚪",
  rejected: "❌",
  hired: "🎉",
};

const ACTION_STYLE: Partial<Record<CandidateAction, string>> = {
  review: "btn-secondary",
  next: "btn-primary",
  reject: "btn-danger",
  hire: "btn-primary",
};

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["recruitment"] });
}

function ScheduleForm({ c }: { c: CandidateDetail }) {
  const { t } = useTranslation();
  const invalidate = useInvalidate();
  const kind = c.stage === "hr_interview" ? "hr" : "tech";
  const existing = c.interviews.find((i) => i.kind === kind && i.status === "scheduled");
  const [when, setWhen] = useState("");
  const [duration, setDuration] = useState(60);
  const [interviewer, setInterviewer] = useState("");
  const [location, setLocation] = useState(existing?.location ?? "");
  const interviewers = useQuery({
    queryKey: ["recruitment", "interviewers"],
    queryFn: () => api<{ id: number; full_name: string; role: string }[]>("/recruitment/interviewers"),
  });
  const schedule = useMutation({
    mutationFn: () =>
      api(`/recruitment/candidates/${c.id}/interviews`, {
        method: "POST",
        // datetime-local — локальное время браузера; в ISO с часовым поясом для сервера
        body: {
          scheduled_at: new Date(when).toISOString(),
          duration_min: duration,
          interviewer_id: interviewer ? Number(interviewer) : null,
          location,
        },
      }),
    onSuccess: () => {
      setWhen("");
      invalidate();
    },
  });

  return (
    <section className="card form">
      <h2>
        {existing ? t("recruitment.reschedule_title") : t("recruitment.schedule_title")} ·{" "}
        {t(`recruitment.kind.${kind}`)}
      </h2>
      <div className="row-2">
        <label>
          {t("recruitment.when")}
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
        </label>
        <label>
          {t("recruitment.duration")}
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            {[30, 45, 60, 90, 120].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        {t("recruitment.interviewer")}
        <select value={interviewer} onChange={(e) => setInterviewer(e.target.value)}>
          <option value="">{t("recruitment.default_interviewer")}</option>
          {interviewers.data?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name} · {t(`role.${u.role}`)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {t("recruitment.location")}
        <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Zoom / кабинет 3" />
      </label>
      {schedule.error && <p className="error">{schedule.error.message}</p>}
      <div>
        <button className="btn-primary" disabled={!when || schedule.isPending} onClick={() => schedule.mutate()}>
          📅 {t("recruitment.schedule")}
        </button>
      </div>
    </section>
  );
}

function InterviewCard({ i, canFeedback }: { i: CandidateInterview; canFeedback: boolean }) {
  const { t } = useTranslation();
  const invalidate = useInvalidate();
  const [text, setText] = useState(i.feedback);
  const save = useMutation({
    mutationFn: () => api(`/recruitment/interviews/${i.id}/feedback`, { method: "POST", body: { feedback: text } }),
    onSuccess: invalidate,
  });
  return (
    <li className="stack" style={{ gap: 6, padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
      <div className="section-head">
        <strong>
          {t(`recruitment.kind.${i.kind}`)} · {fmtDateTime(i.scheduled_at)} · {i.duration_min} мин
        </strong>
        <span className={`status status-${i.status === "done" ? "ok" : i.status === "cancelled" ? "neutral" : "info"}`}>
          {t(`recruitment.istatus.${i.status}`)}
        </span>
      </div>
      <span className="muted small">
        {i.interviewer?.full_name} {i.location && `· ${i.location}`}
      </span>
      {canFeedback && i.status !== "cancelled" ? (
        <>
          <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("recruitment.feedback_placeholder")} />
          <div>
            <button className="btn-ghost" disabled={!text.trim() || save.isPending} onClick={() => save.mutate()}>
              {t("recruitment.save_feedback")}
            </button>
          </div>
        </>
      ) : (
        i.feedback && <p className="small comment">«{i.feedback}»</p>
      )}
    </li>
  );
}

export default function CandidatePage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { me, can } = useAuth();
  const title = useVacancyTitle();
  const invalidate = useInvalidate();
  const [comment, setComment] = useState("");

  const { data: c, isLoading, error } = useQuery({
    queryKey: ["recruitment", "candidate", id],
    queryFn: () => api<CandidateDetail>(`/recruitment/candidates/${id}`),
    retry: false,
  });
  const act = useMutation({
    mutationFn: (action: CandidateAction) =>
      api(`/recruitment/candidates/${id}/actions`, { method: "POST", body: { action, comment } }),
    onSuccess: () => {
      setComment("");
      invalidate();
    },
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error instanceof ApiError && error.status === 404) return <p className="error">404</p>;
  if (error || !c) return <p className="error">{t("common.error")}</p>;

  const decisions = c.allowed_actions.filter((a) => a !== "schedule");
  const hr = can("recruitment.manage");

  return (
    <div className="stack narrow">
      <Link to="/recruitment" className="muted">
        ← {t("recruitment.title")}
      </Link>

      <section className="card stack">
        <div className="section-head">
          <div>
            <h1>{c.full_name}</h1>
            <span className="muted">
              {title(c.vacancy)} · {t("recruitment.salary")}: <strong>{salary(c.expected_salary)}</strong> ·{" "}
              {t("recruitment.received")}: {fmtDate(c.created_at)}
            </span>
          </div>
          <StageBadge stage={c.stage} />
        </div>

        <ol className="steps">
          {c.steps.map((s) => (
            <li key={s.key} className={`step step-${s.state}`}>
              <span aria-hidden>{STEP_ICON[s.state]}</span>
              <span>{s.key === "decision" ? t("recruitment.actions") : t(`recruitment.stage.${s.key}`)}</span>
            </li>
          ))}
        </ol>

        {decisions.length > 0 && (
          <div className="actions">
            <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder={t("recruitment.comment_placeholder")} />
            <div className="row">
              {decisions.map((a) => (
                <button key={a} className={ACTION_STYLE[a]} disabled={act.isPending} onClick={() => act.mutate(a)}>
                  {t(`recruitment.action.${a}`)}
                </button>
              ))}
            </div>
            {act.error && <p className="error">{act.error.message}</p>}
          </div>
        )}
      </section>

      {c.allowed_actions.includes("schedule") && <ScheduleForm key={c.stage} c={c} />}

      <section className="card">
        <h2>{t("recruitment.contacts")}</h2>
        <dl className="fields">
          <div>
            <dt>{t("careers.email")}</dt>
            <dd><a href={`mailto:${c.email}`}>{c.email}</a></dd>
          </div>
          <div>
            <dt>{t("careers.phone")}</dt>
            <dd><a href={`tel:${c.phone.replace(/\s/g, "")}`}>{c.phone}</a></dd>
          </div>
          <div>
            <dt>{t("careers.social")}</dt>
            <dd>{c.social || "—"}</dd>
          </div>
          <div>
            <dt>{t("careers.profile_url")}</dt>
            <dd>{c.profile_url ? <a href={c.profile_url} target="_blank" rel="noreferrer">{c.profile_url}</a> : "—"}</dd>
          </div>
        </dl>
        {c.comment && (
          <>
            <h2 style={{ marginTop: 16 }}>{t("recruitment.candidate_comment")}</h2>
            <p className="block-text">{c.comment}</p>
          </>
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h2>{t("recruitment.resume")}</h2>
          {c.resume_url && (
            <a href={c.resume_url} target="_blank" rel="noreferrer">
              {t("recruitment.open_pdf")}
            </a>
          )}
        </div>
        {c.resume_url ? (
          <iframe className="resume-frame" src={c.resume_url} title={t("recruitment.resume")} />
        ) : (
          <p className="muted">{t("recruitment.no_resume")}</p>
        )}
      </section>

      {c.interviews.length > 0 && (
        <section className="card">
          <h2>{t("recruitment.interviews")}</h2>
          <ul className="request-list">
            {c.interviews.map((i) => (
              <InterviewCard key={i.id} i={i} canFeedback={hr || i.interviewer?.id === me?.id} />
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2>{t("recruitment.history")}</h2>
        <ol className="timeline">
          {c.events.map((ev) => (
            <li key={ev.id}>
              <div className="timeline-head">
                <strong className="small">{t(`recruitment.event.${ev.action}`)}</strong>
                <span className="muted small">{t(`recruitment.stage.${ev.stage}`)}</span>
                <span className="muted small">{fmtDateTime(ev.created_at)}</span>
              </div>
              <span className="small">{ev.actor_name ?? t("requests.system")}</span>
              {ev.comment && <p className="small comment">«{ev.comment}»</p>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
