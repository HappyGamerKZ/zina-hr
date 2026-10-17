import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Assignment, CourseListItem } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/Illustration";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { AssignmentRow, useCourseTitle } from "../components/academy";

type Tab = "my" | "catalog" | "team";

export default function AcademyPage() {
  const { t, i18n } = useTranslation();
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const title = useCourseTitle();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "my";
  const tabs: Tab[] = can("team.view") ? ["my", "catalog", "team"] : ["my", "catalog"];

  const my = useQuery({
    queryKey: ["academy", "assignments", "my"],
    queryFn: () => api<Assignment[]>("/academy/assignments?scope=my"),
    enabled: tab === "my",
  });
  const catalog = useQuery({
    queryKey: ["academy", "courses"],
    queryFn: () => api<CourseListItem[]>("/academy/courses"),
    enabled: tab === "catalog",
  });
  const team = useQuery({
    queryKey: ["academy", "assignments", "team"],
    queryFn: () => api<Assignment[]>("/academy/assignments?scope=team"),
    enabled: tab === "team",
  });

  const enroll = useMutation({
    mutationFn: (courseId: number) => api<Assignment>(`/academy/courses/${courseId}/enroll`, { method: "POST" }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: ["academy"] });
      navigate(`/academy/assignments/${a.id}`);
    },
  });

  return (
    <div className="stack">
      <div className="section-head">
        <h1>{t("academy.title")}</h1>
        {can("team.view") && (
          <Link to="/academy/assign" className="btn-primary">
            <Icon src={icons.add} size={18} />
            {t("academy.assign")}
          </Link>
        )}
      </div>
      <div className="tabs">
        {tabs.map((k) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setParams({ tab: k })}>
            {t(`academy.tab_${k}`)}
          </button>
        ))}
      </div>

      {tab === "my" && (
        <section className="card">
          {my.isLoading && <p className="muted">{t("common.loading")}</p>}
          {my.data?.length === 0 && <EmptyState name="certificate" text={t("academy.empty_my")} />}
          {my.data?.map((a) => <AssignmentRow key={a.id} a={a} />)}
        </section>
      )}

      {tab === "catalog" && (
        <div className="course-grid">
          {catalog.data?.map((c) => (
            <section key={c.id} className="card course-card">
              <span className="course-emoji big" aria-hidden>
                {c.cover_emoji}
              </span>
              <h2>{title(c)}</h2>
              <p className="muted small">{i18n.language === "kk" && c.description_kk ? c.description_kk : c.description_ru}</p>
              <p className="small">
                {t("academy.lessons", { count: c.lessons_count })} · {t("academy.minutes", { count: c.duration_min })}
              </p>
              {c.my_assignment ? (
                <Link to={`/academy/assignments/${c.my_assignment.id}`} className="btn-secondary">
                  {c.my_assignment.status === "completed" ? t("academy.open") : t("academy.continue")} ·{" "}
                  {c.my_assignment.progress_pct}%
                </Link>
              ) : (
                <button className="btn-primary" disabled={enroll.isPending} onClick={() => enroll.mutate(c.id)}>
                  {t("academy.enroll")}
                </button>
              )}
            </section>
          ))}
        </div>
      )}

      {tab === "team" && (
        <section className="card">
          {team.isLoading && <p className="muted">{t("common.loading")}</p>}
          {team.data?.length === 0 && <EmptyState name="growth" text={t("academy.empty_team")} />}
          {team.data?.map((a) => <AssignmentRow key={a.id} a={a} showEmployee />)}
        </section>
      )}
    </div>
  );
}
