import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import type { HrRequest } from "../api/types";
import { fmtDate, fmtMoney } from "../i18n";
import StatusBadge from "./StatusBadge";

export function requestSummary(r: HrRequest, t: TFunction): string {
  if (r.vacation) {
    return `${fmtDate(r.vacation.date_from)} – ${fmtDate(r.vacation.date_to)} · ${t("common.days", {
      count: r.vacation.days,
    })}`;
  }
  if (r.advance) return fmtMoney(r.advance.amount);
  return "";
}

export default function RequestList({
  items,
  showEmployee = false,
  empty,
}: {
  items: HrRequest[];
  showEmployee?: boolean;
  empty: string;
}) {
  const { t } = useTranslation();
  if (items.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="request-list">
      {items.map((r) => (
        <li key={r.id}>
          <Link to={`/requests/${r.id}`} className="request-row">
            <div className="request-main">
              <span className="request-type">{t(`type.${r.type}`)}</span>
              <span className="muted small">
                {r.number} · {fmtDate(r.created_at)}
                {showEmployee && ` · ${r.employee.full_name}`}
              </span>
              <span className="small">{requestSummary(r, t)}</span>
            </div>
            <StatusBadge status={r.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
