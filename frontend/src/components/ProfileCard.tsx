import { useTranslation } from "react-i18next";

import type { Profile } from "../api/types";
import { fmtDate } from "../i18n";
import Icon from "./Icon";
import { icons } from "./icons";
import { AssignmentRow } from "./academy";

export default function ProfileCard({ profile }: { profile: Profile }) {
  const { t } = useTranslation();
  const b = profile.vacation_balance;
  const rows: [string, string][] = [
    [t("profile.company"), profile.company],
    [t("profile.department"), profile.department],
    [t("profile.position"), profile.position],
    [t("profile.manager"), profile.manager ? `${profile.manager.full_name} (${profile.manager.position})` : t("common.none")],
    [t("profile.hire_date"), fmtDate(profile.hire_date)],
    [t("profile.email"), profile.email || t("common.none")],
    [t("profile.tab_number"), profile.external_id],
  ];

  return (
    <div className="stack">
      <section className="card">
        <h1>{profile.full_name}</h1>
        <p className="readonly-note">
          <Icon src={icons.readOnly} size={16} />
          {t("common.from_zup")}
        </p>
        <dl className="fields">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="card">
        <h2>{t("profile.vacation")}</h2>
        <div className="balance">
          <div>
            <span className="muted small">{t("profile.v_total")}</span>
            <strong>{b.days_total}</strong>
          </div>
          <div>
            <span className="muted small">{t("profile.v_used")}</span>
            <strong>{b.days_used}</strong>
          </div>
          <div>
            <span className="muted small">{t("profile.v_reserved")}</span>
            <strong>{b.days_reserved}</strong>
          </div>
          <div className="accent">
            <span className="muted small">{t("profile.v_available")}</span>
            <strong>{b.days_available}</strong>
          </div>
        </div>
      </section>
      <section className="card">
        <h2>{t("dashboard.learning")}</h2>
        {profile.learning.length === 0 ? (
          <p className="muted">{t("dashboard.no_courses")}</p>
        ) : (
          profile.learning.map((a) => <AssignmentRow key={a.id} a={a} />)
        )}
      </section>
    </div>
  );
}
