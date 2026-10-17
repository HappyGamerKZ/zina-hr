import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AssignmentRow } from "../components/academy";
import Avatar from "../components/Avatar";
import HrOverview from "../components/HrOverview";
import { RecruitmentWidget } from "../components/recruitment";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { EmptyState } from "../components/Illustration";
import RequestList from "../components/RequestList";
import { fmtDate, fmtDateTime } from "../i18n";

const QUICK_ICONS: Record<string, string> = {
  vacation: icons.vacation,
  advance: icons.advance,
  ai: icons.ai,
  academy: icons.academy,
};

export default function DashboardPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const hr = can("recruitment.manage");
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/me/dashboard"),
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error || !data) return <p className="error">{t("common.error")}</p>;

  const { profile } = data;
  const firstName = profile.full_name.split(" ")[1] ?? profile.full_name;

  return (
    <div className="stack">
      <div>
        <h1>{t("dashboard.greeting", { name: firstName })}</h1>
        {hr && <p className="muted page-sub">{t("hrdash.subtitle")}</p>}
      </div>

      <section className="hero card">
        <Link to="/profile" className="profile-hero">
          <Avatar name={profile.full_name} />
          <span className="profile-hero-main">
            <strong>{profile.full_name}</strong>
            <span className="muted">
              {profile.position} · {profile.department}
            </span>
            <span className="row">
              <span className="status status-ok">{t("me_card.active")}</span>
              <span className="status status-neutral">{t("me_card.since", { date: fmtDate(profile.hire_date) })}</span>
            </span>
          </span>
        </Link>
        <div className="hero-stat">
          <span className="muted small">{t("dashboard.vacation_left")}</span>
          <strong>{t("common.days", { count: profile.vacation_balance.days_available })}</strong>
        </div>
      </section>

      {hr && <HrOverview />}

      {can("requests.approve") && data.approvals_count > 0 && (
        <Link to="/team/approvals" className="card alert">
          {t("dashboard.approvals", { count: data.approvals_count })}
          <span className="icon-link">
            {t("dashboard.open_approvals")}
            <Icon src={icons.forward} size={16} />
          </span>
        </Link>
      )}

      <section>
        <h2>{t("dashboard.quick")}</h2>
        <div className="quick-grid">
          {data.quick_services.map((q) => (
            <Link key={q.key} to={q.link} className="card quick">
              <span className="quick-icon" aria-hidden>
                <Icon src={QUICK_ICONS[q.key]} size={24} />
              </span>
              {t(`dashboard.q_${q.key}`)}
            </Link>
          ))}
        </div>
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="section-head">
            <h2>{t("dashboard.recent")}</h2>
            <Link to="/requests" className="icon-link">
              {t("dashboard.all_requests")}
              <Icon src={icons.forward} size={16} />
            </Link>
          </div>
          <RequestList items={data.recent_requests} empty={t("requests.empty")} />
        </section>

        <div className="stack">
          {can("recruitment.interviews") && !hr && <RecruitmentWidget />}
          <section className="card">
            <div className="section-head">
              <h2>{t("dashboard.learning")}</h2>
              <Link to="/academy" aria-label={t("nav.academy")}>
                <Icon src={icons.forward} />
              </Link>
            </div>
            {data.courses.length === 0 ? (
              <EmptyState name="certificate" text={t("dashboard.no_courses")} />
            ) : (
              data.courses.map((a) => <AssignmentRow key={a.id} a={a} />)
            )}
          </section>

          <section className="card">
            <div className="section-head">
              <h2>{t("dashboard.notifications")}</h2>
              <Link to="/notifications" aria-label={t("nav.notifications")}>
                <Icon src={icons.forward} />
              </Link>
            </div>
            {data.notifications.length === 0 ? (
              <EmptyState name="clock" text={t("dashboard.no_notifications")} />
            ) : (
              <ul className="note-list">
                {data.notifications.map((n) => (
                  <li key={n.id} className={n.is_read ? "" : "unread"}>
                    <Link to={n.link || "/notifications"}>
                      <strong>{n.title}</strong>
                      <span className="muted small">{fmtDateTime(n.created_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
