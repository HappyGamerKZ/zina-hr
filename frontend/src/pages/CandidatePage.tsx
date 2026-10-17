import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { CandidateAction, CandidateDetail, CandidateInterview, StepState } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BackLink from "../components/BackLink";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { Progress } from "../components/academy";
import Avatar from "../components/Avatar";
import Modal from "../components/Modal";
import { MatchBadge, StageBadge, salary, useVacancyTitle } from "../components/recruitment";
import { fmtDate, fmtDateTime } from "../i18n";

// Шаги: часы — ещё не пройден, собеседование — текущий, галочка — пройден, крестик — отказ
const STEP_ICON: Record<StepState, string> = {
  done: icons.done,
  current: icons.interview,
  pending: icons.pending,
  skipped: icons.more,
  rejected: icons.close,
  hired: icons.hired,
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
          <Icon src={icons.calendar} size={18} />
          {t("recruitment.schedule")}
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

/** Ход собеседований: шаги с датами и общий прогресс. «Резюме получено» — всегда первый пройденный шаг. */
function ProgressPanel({ c }: { c: CandidateDetail }) {
  const { t } = useTranslation();
  const rows = [
    { key: "received", label: t("cand.received"), state: "done" as StepState, date: c.created_at as string | null },
    ...c.steps.map((s) => ({
      key: s.key,
      label: s.key === "decision" ? t("recruitment.actions") : t(`recruitment.stage.${s.key}`),
      state: s.state,
      date: s.date,
    })),
  ];
  const done = rows.filter((r) => r.state === "done" || r.state === "hired").length;
  const pct = Math.round((done / rows.length) * 100);
  const dateText = (r: (typeof rows)[number]) => {
    if (r.state === "skipped") return "—";
    if (!r.date) return r.key !== "decision" && (r.state === "pending" || r.state === "current") ? t("cand.not_scheduled") : "";
    return r.state === "current" ? t("cand.planned", { date: fmtDateTime(r.date) }) : fmtDate(r.date);
  };

  return (
    <section className="card progress-panel">
      <div className="section-head">
        <h2>{t("cand.progress")}</h2>
        <span className="status status-info">{t("cand.stages_of", { done, total: rows.length })}</span>
      </div>
      <ol className="progress-steps">
        {rows.map((r) => (
          <li key={r.key} className={`progress-step progress-${r.state}`}>
            <span className="progress-dot">
              <Icon src={STEP_ICON[r.state]} size={18} />
            </span>
            <span className="progress-text">
              <strong>{r.label}</strong>
              <span className="muted small">{dateText(r)}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="section-head">
        <strong>{t("cand.overall")}</strong>
        <strong>{pct}%</strong>
      </div>
      <Progress value={pct} />
    </section>
  );
}

/** Подтверждение найма: что произойдёт после нажатия. */
function HireModal({ c, busy, onConfirm, onClose }: {
  c: CandidateDetail;
  busy: boolean;
  onConfirm: (closeVacancy: boolean) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [closeVacancy, setCloseVacancy] = useState(false);
  return (
    <Modal onClose={onClose}>
      <div className="hire-modal">
        <span className="hire-icon">
          <Icon src={icons.offer} size={36} />
        </span>
        <h2>{t("cand.hire_title", { name: c.full_name })}</h2>
        <p className="muted">{t("cand.hire_text")}</p>
        <ul className="hire-steps">
          {[icons.done, icons.bell, icons.calendar, icons.documents].map((icon, idx) => (
            <li key={idx}>
              <Icon src={icon} size={20} />
              {t(`cand.hire_${idx + 1}`)}
            </li>
          ))}
        </ul>
        {c.vacancy_status === "active" && (
          <label className="check-row">
            <input type="checkbox" checked={closeVacancy} onChange={(e) => setCloseVacancy(e.target.checked)} />
            {t("cand.hire_close")}
          </label>
        )}
        <div className="row-2">
          <button className="btn-ghost" onClick={onClose}>
            {t("cand.cancel")}
          </button>
          <button className="btn-primary" disabled={busy} onClick={() => onConfirm(closeVacancy)}>
            {t("cand.hire_confirm")}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function CandidatePage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { me, can } = useAuth();
  const title = useVacancyTitle();
  const invalidate = useInvalidate();
  const [comment, setComment] = useState("");
  const [hiring, setHiring] = useState(false);

  const { data: c, isLoading, error } = useQuery({
    queryKey: ["recruitment", "candidate", id],
    queryFn: () => api<CandidateDetail>(`/recruitment/candidates/${id}`),
    retry: false,
  });
  const act = useMutation({
    mutationFn: ({ action, closeVacancy = false }: { action: CandidateAction; closeVacancy?: boolean }) =>
      api(`/recruitment/candidates/${id}/actions`, {
        method: "POST",
        body: { action, comment, close_vacancy: closeVacancy },
      }),
    onSuccess: () => {
      setComment("");
      setHiring(false);
      invalidate();
    },
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error instanceof ApiError && error.status === 404) return <p className="error">404</p>;
  if (error || !c) return <p className="error">{t("common.error")}</p>;

  const decisions = c.allowed_actions.filter((a) => a !== "schedule");
  const hr = can("recruitment.manage");

  return (
    <div className="stack">
      <BackLink to="/recruitment">{t("cand.back")}</BackLink>

      <div className="cand-layout">
        <div className="stack">
          <section className="card cand-card">
            <div className="cand-head">
              <Avatar name={c.full_name} size={64} />
              <div className="cand-title">
                <h1>{c.full_name}</h1>
                <strong>{title(c.vacancy)}</strong>
                <span className="row">
                  <StageBadge stage={c.stage} />
                  <span title={t("hrdash.match_hint")}>
                    <MatchBadge score={c.match.score} />
                  </span>
                </span>
              </div>
            </div>
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
                <dt>{t("recruitment.salary")}</dt>
                <dd>{salary(c.expected_salary)}</dd>
              </div>
              <div>
                <dt>{t("recruitment.received")}</dt>
                <dd>{fmtDate(c.created_at)}</dd>
              </div>
              <div>
                <dt>{t("careers.social")}</dt>
                <dd>{c.social || "—"}</dd>
              </div>
              <div>
                <dt>{t("cand.number")}</dt>
                <dd>{c.number}</dd>
              </div>
              {c.profile_url && (
                <div className="field-wide">
                  <dt>{t("careers.profile_url")}</dt>
                  <dd><a href={c.profile_url} target="_blank" rel="noreferrer">{c.profile_url}</a></dd>
                </div>
              )}
            </dl>
            <details className="match-details">
              <summary className="small">{t("hrdash.match")}: {c.match.score}%</summary>
              <ul className="match-factors">
                {c.match.factors.map((f) => (
                  <li key={f.key}>
                    <span className="small">{t(`hrdash.factor.${f.key}`)}</span>
                    <span className="small muted">
                      {f.points} / {f.max}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="muted small">{t("hrdash.match_hint")}</p>
            </details>
          </section>

          {decisions.length > 0 && (
            <section className="card actions">
              <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder={t("recruitment.comment_placeholder")} />
              <div className="row">
                {decisions.map((a) => (
                  <button
                    key={a}
                    className={ACTION_STYLE[a]}
                    disabled={act.isPending}
                    onClick={() => (a === "hire" ? setHiring(true) : act.mutate({ action: a }))}
                  >
                    {t(`recruitment.action.${a}`)}
                  </button>
                ))}
              </div>
              {act.error && !hiring && <p className="error">{act.error.message}</p>}
            </section>
          )}

          {c.comment && (
            <section className="card">
              <h2>{t("recruitment.candidate_comment")}</h2>
              <p className="block-text">{c.comment}</p>
            </section>
          )}
        </div>

        <ProgressPanel c={c} />
      </div>

      {c.allowed_actions.includes("schedule") && <ScheduleForm key={c.stage} c={c} />}

      <section className="card">
        <div className="section-head">
          <h2>{t("recruitment.resume")}</h2>
          {c.resume_url && (
            <a href={c.resume_url} target="_blank" rel="noreferrer" className="icon-link">
              {t("recruitment.open_pdf")}
              <Icon src={icons.externalLink} size={16} />
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

      {hiring && (
        <HireModal
          c={c}
          busy={act.isPending}
          onClose={() => setHiring(false)}
          onConfirm={(closeVacancy) => act.mutate({ action: "hire", closeVacancy })}
        />
      )}
    </div>
  );
}
