// Календарь интервью: месяц сеткой и список. HR видит все интервью, руководитель — свои.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { UpcomingInterview } from "../api/types";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { UpcomingInterviews, useLocale } from "../components/recruitment";

const pad = (n: number) => String(n).padStart(2, "0");
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export default function InterviewCalendarPage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const today = new Date();
  const [month, setMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();

  const { data, isLoading } = useQuery({
    queryKey: ["recruitment", "calendar", isoDay(month)],
    queryFn: () => api<UpcomingInterview[]>(`/recruitment/interviews?from=${isoDay(month)}&days=${days}`),
  });

  const byDay = new Map<string, UpcomingInterview[]>();
  for (const i of data ?? []) {
    const key = isoDay(new Date(i.scheduled_at));
    byDay.set(key, [...(byDay.get(key) ?? []), i]);
  }
  const offset = (month.getDay() + 6) % 7; // неделя с понедельника
  const cells = [...Array(offset).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 1 + i).toLocaleDateString(locale, { weekday: "short" }),
  );
  const shift = (delta: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
  const time = (v: string) => new Date(v).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  const upcoming = (data ?? []).filter((i) => new Date(i.scheduled_at) >= new Date(today.getTime() - 3600_000));

  return (
    <div className="stack">
      <h1>{t("hrdash.calendar")}</h1>
      <section className="card">
        <div className="section-head">
          <h2 className="month-title">{month.toLocaleDateString(locale, { month: "long" })} {month.getFullYear()}</h2>
          <div className="row">
            <button className="btn-ghost" onClick={() => shift(-1)} aria-label={t("academy.prev")}>
              <Icon src={icons.back} size={18} />
            </button>
            <button className="btn-ghost" onClick={() => shift(1)} aria-label={t("academy.next")}>
              <Icon src={icons.forward} size={18} />
            </button>
          </div>
        </div>
        {isLoading && <p className="muted">{t("common.loading")}</p>}
        <div className="month-grid">
          {weekdays.map((w) => (
            <span key={w} className="month-weekday">
              {w}
            </span>
          ))}
          {cells.map((day, idx) => {
            if (day === null) return <span key={`e${idx}`} />;
            const key = isoDay(new Date(month.getFullYear(), month.getMonth(), day));
            const items = byDay.get(key) ?? [];
            return (
              <div key={key} className={`month-day${key === isoDay(today) ? " today" : ""}${items.length ? " busy" : ""}`}>
                <span className="month-num">{day}</span>
                {items.map((i) => (
                  <Link key={i.id} to={`/recruitment/${i.candidate.id}`} className={`month-event kind-${i.kind}`}>
                    {time(i.scheduled_at)} {i.candidate.full_name.split(" ")[0]}
                  </Link>
                ))}
              </div>
            );
          })}
        </div>
      </section>

      <section className="card">
        <h2>{t("recruitment.upcoming")}</h2>
        {data && (upcoming.length ? <UpcomingInterviews items={upcoming} /> : <p className="muted">{t("hrdash.no_calendar")}</p>)}
      </section>
    </div>
  );
}
