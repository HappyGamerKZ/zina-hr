import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { AssignmentDetail, LessonKind } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BackLink from "../components/BackLink";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { AssignmentBadge, CourseCover, Progress, useCourseTitle } from "../components/academy";
import { fmtDate } from "../i18n";

const KIND_ICON: Record<LessonKind, string> = { text: icons.documents, quiz: icons.help };

export default function AssignmentPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { me } = useAuth();
  const title = useCourseTitle();
  const { data: a, isLoading, error } = useQuery({
    queryKey: ["academy", "assignment", id],
    queryFn: () => api<AssignmentDetail>(`/academy/assignments/${id}`),
    retry: false,
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error instanceof ApiError && error.status === 404) return <p className="error">404</p>;
  if (error || !a) return <p className="error">{t("common.error")}</p>;

  const own = me?.employee_id === a.employee.id;
  const lessons = a.modules.flatMap((m) => m.lessons);
  const next = lessons.find((l) => l.status === "available");

  return (
    <div className="stack narrow">
      <BackLink to="/academy">{t("academy.title")}</BackLink>
      <section className="card">
        <div className="section-head">
          <div className="row">
            <CourseCover course={a.course} big />
            <div>
              <h1>{title(a.course)}</h1>
              {!own && <span className="muted">{a.employee.full_name}</span>}
            </div>
          </div>
          <AssignmentBadge status={a.status} />
        </div>
        <Progress value={a.progress_pct} />
        <p className="muted small">
          {t("academy.progress")}: {a.progress_pct}%
          {a.score !== null && ` · ${t("academy.score")}: ${a.score}%`}
          {a.best_score !== null && a.cycle > 1 && ` · ${t("academy.best", { score: a.best_score })}`}
          {a.cycle > 1 && ` · ${t("academy.cycle", { n: a.cycle })}`}
          {a.due_date && ` · ${t("academy.due", { date: fmtDate(a.due_date) })}`}
          {a.assigned_by_name && ` · ${t("academy.assigned_by", { name: a.assigned_by_name })}`}
        </p>
        {own && next && (
          <Link to={`/academy/assignments/${a.id}/lessons/${next.id}`} className="btn-primary">
            {a.status !== "assigned" && `${t("academy.continue")}: `}
            {next.title}
            <Icon src={icons.forward} size={18} />
          </Link>
        )}
        {(a.can_restart || a.can_reassign) && <RestartPanel id={a.id} selfRestart={a.can_restart} />}
        {!own && <p className="muted small">{t("academy.not_owner")}</p>}
      </section>

      {a.modules.map((m) => (
        <section key={m.id} className="card">
          <h2>{m.title}</h2>
          <ul className="lesson-list">
            {m.lessons.map((l) => {
              const body = (
                <>
                  <span className="lesson-icon" aria-hidden>
                    <Icon src={l.status === "completed" ? icons.done : l.status === "locked" ? icons.readOnly : KIND_ICON[l.type]} />
                  </span>
                  <span className="lesson-title">
                    {l.title}
                    <span className="muted small">
                      {" · "}
                      {t(`academy.kind.${l.type}`)} · {t("academy.minutes", { count: l.duration_min })}
                      {l.quiz?.best_score != null && ` · ${t("academy.best", { score: l.quiz.best_score })}`}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={l.id} className={`lesson-row ${l.status}`} title={l.status === "locked" ? t("academy.locked") : undefined}>
                  {own && l.status !== "locked" ? (
                    <Link to={`/academy/assignments/${a.id}/lessons/${l.id}`}>{body}</Link>
                  ) : (
                    <div>{body}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** «Пройти заново» для сотрудника (сданный курс) или «Назначить повторно» для HR / руководителя. */
function RestartPanel({ id, selfRestart }: { id: number; selfRestart: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [due, setDue] = useState("");
  const restart = useMutation({
    mutationFn: () =>
      api(`/academy/assignments/${id}/restart`, { method: "POST", body: selfRestart ? {} : { due_date: due || null } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["academy"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });
  return (
    <div className="restart-panel">
      {!selfRestart && (
        <label>
          {t("academy.due_date")}
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
      )}
      <button className="btn-secondary" onClick={() => restart.mutate()} disabled={restart.isPending}>
        ↻ {selfRestart ? t("academy.restart") : t("academy.reassign")}
      </button>
      <span className="muted small">{selfRestart ? t("academy.restart_hint") : t("academy.reassign_hint")}</span>
      {restart.error && <p className="error">{restart.error.message}</p>}
    </div>
  );
}
