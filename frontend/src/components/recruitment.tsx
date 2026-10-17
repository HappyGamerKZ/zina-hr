// Общие элементы раздела «Подбор» (временный UI для тестирования backend).
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { CandidateStage, RecruitmentSummary, UpcomingInterview, VacancyShort, VacancyStatus } from "../api/types";
import { fmtMoney } from "../i18n";
import Icon from "./Icon";
import { EmptyState } from "./Illustration";
import { icons } from "./icons";

const TONE: Record<CandidateStage, string> = {
  screening: "warn",
  hr_interview: "info",
  tech_interview: "info",
  hired: "ok",
  rejected: "bad",
};

const VACANCY_TONE: Record<VacancyStatus, string> = { draft: "neutral", active: "ok", closed: "bad" };

export function StageBadge({ stage }: { stage: CandidateStage }) {
  const { t } = useTranslation();
  return <span className={`status status-${TONE[stage]}`}>{t(`recruitment.stage.${stage}`)}</span>;
}

export function VacancyStatusBadge({ status }: { status: VacancyStatus }) {
  const { t } = useTranslation();
  return <span className={`status status-${VACANCY_TONE[status]}`}>{t(`vac.status.${status}`)}</span>;
}

/** Балл соответствия вакансии: полоска и процент. */
export function MatchBadge({ score }: { score: number }) {
  return (
    <span className="match" title={`${score}%`}>
      <span className="match-bar">
        <span style={{ width: `${score}%` }} />
      </span>
      <strong>{score}%</strong>
    </span>
  );
}

export function useVacancyTitle() {
  const { i18n } = useTranslation();
  return (v: VacancyShort) => (i18n.language === "kk" && v.title_kk ? v.title_kk : v.title_ru);
}

export function useLocale() {
  const { i18n } = useTranslation();
  return i18n.language === "kk" ? "kk-KZ" : "ru-RU";
}

export function salary(value: number | null) {
  return value === null ? "—" : fmtMoney(value);
}

export function useRecruitmentSummary() {
  return useQuery({
    queryKey: ["recruitment", "summary"],
    queryFn: () => api<RecruitmentSummary>("/recruitment/summary"),
  });
}

/** Плашка даты: число и месяц. */
export function DateChip({ value }: { value: string }) {
  const locale = useLocale();
  const d = new Date(value);
  return (
    <span className="date-chip">
      <strong>{d.getDate()}</strong>
      <small>{d.toLocaleDateString(locale, { month: "short" }).replace(".", "")}</small>
    </span>
  );
}

export function UpcomingInterviews({ items }: { items: UpcomingInterview[] }) {
  const { t } = useTranslation();
  const title = useVacancyTitle();
  const locale = useLocale();
  if (items.length === 0) return <EmptyState name="calendar-check" text={t("recruitment.no_upcoming")} />;
  return (
    <ul className="interview-list">
      {items.map((i) => (
        <li key={i.id}>
          <Link to={`/recruitment/${i.candidate.id}`} className="interview-row">
            <DateChip value={i.scheduled_at} />
            <span className="interview-main">
              <strong>{i.candidate.full_name}</strong>
              <span className="muted small">
                {title(i.candidate.vacancy)} · {t(`recruitment.kind.${i.kind}`)}
                {i.interviewer && ` · ${i.interviewer.full_name}`}
              </span>
              {i.location && <span className="small">{i.location}</span>}
            </span>
            <strong className="small interview-time">
              {new Date(i.scheduled_at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })}
            </strong>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Виджет на главной для руководителей-интервьюеров (у HR — обзор подбора целиком, см. HrOverview). */
export function RecruitmentWidget() {
  const { t } = useTranslation();
  const { data } = useRecruitmentSummary();
  if (!data) return null;
  return (
    <section className="card">
      <div className="section-head">
        <h2>{t("recruitment.upcoming")}</h2>
        <Link to="/recruitment" className="icon-link">
          {t("recruitment.all_resumes")}
          <Icon src={icons.forward} size={16} />
        </Link>
      </div>
      {data.new_resumes !== undefined && data.new_resumes > 0 && (
        <Link to="/recruitment?stage=screening" className="card alert">
          {t("recruitment.new_resumes", { count: data.new_resumes })}
          <Icon src={icons.forward} />
        </Link>
      )}
      <UpcomingInterviews items={data.upcoming_interviews.slice(0, 5)} />
    </section>
  );
}
