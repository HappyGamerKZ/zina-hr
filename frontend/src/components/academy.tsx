// Общие элементы Jana Academy (временный UI для тестирования backend).
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { Assignment, AssignmentStatus, CourseShort } from "../api/types";
import { fmtDate } from "../i18n";
import Icon from "./Icon";
import { courseIcon } from "./icons";

const TONE: Record<AssignmentStatus, string> = {
  assigned: "warn",
  in_progress: "info",
  completed: "ok",
  failed: "bad",
};

/** Обложка курса: иконка из набора Jana HR. */
export function CourseCover({ course, big = false }: { course: CourseShort; big?: boolean }) {
  return (
    <span className={`course-emoji${big ? " big" : ""}`} aria-hidden>
      <Icon src={courseIcon(course.cover_icon)} size={big ? 30 : 24} />
    </span>
  );
}

export function useCourseTitle() {
  const { i18n } = useTranslation();
  return (c: CourseShort) => (i18n.language === "kk" && c.title_kk ? c.title_kk : c.title_ru);
}

export function AssignmentBadge({ status }: { status: AssignmentStatus }) {
  const { t } = useTranslation();
  return <span className={`status status-${TONE[status]}`}>{t(`academy.status.${status}`)}</span>;
}

export function Progress({ value }: { value: number }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${value}%` }} />
    </div>
  );
}

/** Курс сотрудника одной строкой: обложка, название, статус, прогресс, срок / результат. */
export function AssignmentRow({ a, showEmployee = false }: { a: Assignment; showEmployee?: boolean }) {
  const { t } = useTranslation();
  const title = useCourseTitle();
  return (
    <Link to={`/academy/assignments/${a.id}`} className="assignment-row">
      <CourseCover course={a.course} />
      <div className="assignment-main">
        <div className="row">
          <strong>{title(a.course)}</strong>
          <AssignmentBadge status={a.status} />
        </div>
        {showEmployee && <span className="small">{a.employee.full_name}</span>}
        <Progress value={a.progress_pct} />
        <span className="muted small">
          {a.progress_pct}%
          {a.score !== null && ` · ${t("academy.score")}: ${a.score}%`}
          {a.due_date && a.status !== "completed" && ` · ${t("academy.due", { date: fmtDate(a.due_date) })}`}
          {" · "}
          {a.assigned_by_name ? t("academy.assigned_by", { name: a.assigned_by_name }) : t("academy.self_enrolled")}
        </span>
      </div>
    </Link>
  );
}
