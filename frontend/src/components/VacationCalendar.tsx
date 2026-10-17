import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { BusyVacation } from "../api/types";
import Icon from "./Icon";
import { icons } from "./icons";

// Временный календарь для тестирования backend; фронтенд переоформит его под дизайн.
// Даты — строки "YYYY-MM-DD" в локальном времени, их можно сравнивать как строки.

const pad = (n: number) => String(n).padStart(2, "0");
export const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fromIso = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
};

const LOCALES: Record<string, string> = { ru: "ru-RU", kk: "kk-KZ" };

interface Props {
  busy: BusyVacation[];
  from: string;
  to: string;
  minDate: string;
  onChange: (from: string, to: string) => void;
}

export default function VacationCalendar({ busy, from, to, minDate, onChange }: Props) {
  const { t, i18n } = useTranslation();
  const locale = LOCALES[i18n.language] ?? "ru-RU";
  const start = fromIso(from || minDate);
  const [view, setView] = useState({ year: start.getFullYear(), month: start.getMonth() });
  const [hint, setHint] = useState<string | null>(null);

  const busyOn = (iso: string) => busy.find((b) => b.date_from <= iso && iso <= b.date_to);
  const rangeHasBusy = (a: string, b: string) => busy.some((x) => x.date_from <= b && x.date_to >= a);

  const pick = (iso: string) => {
    setHint(null);
    if (!from || to || iso < from) return onChange(iso, "");
    if (rangeHasBusy(from, iso)) {
      setHint(t("calendar.busy_hint"));
      return onChange(iso, "");
    }
    onChange(from, iso);
  };

  const shift = (delta: number) => {
    const d = new Date(view.year, view.month + delta, 1);
    setView({ year: d.getFullYear(), month: d.getMonth() });
  };

  // Сетка месяца, неделя с понедельника
  const first = new Date(view.year, view.month, 1);
  const offset = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();
  const cells: (string | null)[] = [
    ...Array<null>(offset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => toIso(new Date(view.year, view.month, i + 1))),
  ];
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 1 + i).toLocaleDateString(locale, { weekday: "short" }),
  );
  const min = fromIso(minDate);
  const canGoBack = new Date(view.year, view.month, 1) > new Date(min.getFullYear(), min.getMonth(), 1);

  return (
    <div className="calendar">
      <div className="calendar-head">
        <button type="button" className="btn-ghost" onClick={() => shift(-1)} disabled={!canGoBack} aria-label={t("academy.prev")}>
          <Icon src={icons.back} size={18} />
        </button>
        <strong>{first.toLocaleDateString(locale, { month: "long", year: "numeric" })}</strong>
        <button type="button" className="btn-ghost" onClick={() => shift(1)} aria-label={t("academy.next")}>
          <Icon src={icons.forward} size={18} />
        </button>
      </div>
      <div className="calendar-grid">
        {weekdays.map((w) => (
          <span key={w} className="calendar-weekday">
            {w}
          </span>
        ))}
        {cells.map((iso, i) => {
          if (!iso) return <span key={`e${i}`} />;
          const b = busyOn(iso);
          const past = iso < minDate;
          const selected = iso === from || iso === to || (!!from && !!to && from < iso && iso < to);
          const cls = [
            "calendar-day",
            b && (b.status === "approved_sent_to_1c" ? "busy-approved" : "busy-pending"),
            selected && "selected",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              type="button"
              key={iso}
              className={cls}
              disabled={past || !!b}
              title={b ? `${b.number}: ${t(`status.${b.status}`)}` : undefined}
              onClick={() => pick(iso)}
            >
              {Number(iso.slice(8))}
            </button>
          );
        })}
      </div>
      <div className="calendar-legend small">
        <span><i className="dot busy-approved" />{t("calendar.approved")}</span>
        <span><i className="dot busy-pending" />{t("calendar.pending")}</span>
        <span><i className="dot selected" />{t("calendar.selected")}</span>
      </div>
      <p className="hint">{hint ?? (from && !to ? t("calendar.pick_end") : !from ? t("calendar.pick_start") : "")}</p>
    </div>
  );
}
