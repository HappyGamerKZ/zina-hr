// Общие элементы раздела «Подбор» (временный UI для тестирования backend).
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { CandidateStage, RecruitmentSummary, UpcomingInterview, VacancyShort } from "../api/types";
import { fmtDateTime, fmtMoney } from "../i18n";
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

export function StageBadge({ stage }: { stage: CandidateStage }) {
  const { t } = useTranslation();
  return <span className={`status status-${TONE[stage]}`}>{t(`recruitment.stage.${stage}`)}</span>;
}

export function useVacancyTitle() {
  const { i18n } = useTranslation();
  return (v: VacancyShort) => (i18n.language === "kk" && v.title_kk ? v.title_kk : v.title_ru);
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

export function UpcomingInterviews({ items }: { items: UpcomingInterview[] }) {
  const { t } = useTranslation();
  const title = useVacancyTitle();
  if (items.length === 0) return <EmptyState name="calendar-check" text={t("recruitment.no_upcoming")} />;
  return (
    <ul className="request-list">
      {items.map((i) => (
        <li key={i.id}>
          <Link to={`/recruitment/${i.candidate.id}`} className="request-row">
            <div className="request-main">
              <span className="request-type">{i.candidate.full_name}</span>
              <span className="muted small">
                {title(i.candidate.vacancy)} · {t(`recruitment.kind.${i.kind}`)}
                {i.interviewer && ` · ${i.interviewer.full_name}`}
              </span>
              {i.location && <span className="small">{i.location}</span>}
            </div>
            <strong className="small">{fmtDateTime(i.scheduled_at)}</strong>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Виджет на главной для HR и руководителей-интервьюеров. */
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
