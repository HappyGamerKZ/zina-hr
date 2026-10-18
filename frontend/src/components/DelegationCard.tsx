// Замещение руководителя (И.О.): назначить на даты отпуска, посмотреть и отменить.
// Временный UI для тестирования backend — дизайн сделает фронтенд.
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Delegation, DelegationsInfo } from "../api/types";
import { fmtDate } from "../i18n";
import Icon from "./Icon";
import { icons } from "./icons";

const TONE: Record<Delegation["state"], string> = { planned: "info", active: "ok", finished: "neutral", revoked: "neutral" };

export function useDelegations() {
  return useQuery({ queryKey: ["delegations"], queryFn: () => api<DelegationsInfo>("/me/delegations") });
}

/** Плашка для сотрудника, который сейчас (или скоро) исполняет обязанности руководителя. */
export function ActingNotice() {
  const { t } = useTranslation();
  const { data } = useDelegations();
  const acting = data?.acting_for.filter((d) => d.state === "active" || d.state === "planned") ?? [];
  if (!acting.length) return null;
  return (
    <section className="card acting-notice">
      {acting.map((d) => (
        <p key={d.id} className="icon-link">
          <Icon src={icons.approvals} size={18} />
          <strong>
            {t("delegation.acting", { name: d.manager.full_name, from: fmtDate(d.date_from), to: fmtDate(d.date_to) })}
          </strong>
        </p>
      ))}
      <p className="muted small">{t("delegation.acting_hint")}</p>
    </section>
  );
}

export default function DelegationCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useDelegations();
  const [deputy, setDeputy] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["delegations"] });
    qc.invalidateQueries({ queryKey: ["requests"] });
  };
  const create = useMutation({
    mutationFn: () => api("/me/delegations", { method: "POST", body: { deputy_id: Number(deputy), date_from: from, date_to: to } }),
    onSuccess: () => {
      setDeputy("");
      setFrom("");
      setTo("");
      refresh();
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => api(`/me/delegations/${id}/revoke`, { method: "POST" }),
    onSuccess: refresh,
  });

  if (!data?.can_delegate) return null;
  const today = new Date().toISOString().slice(0, 10);
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <section className="card">
      <h2 className="icon-title">
        <Icon src={icons.employees} />
        {t("delegation.title")}
      </h2>
      <p className="hint">{t("delegation.hint")}</p>

      <form className="form delegation-form" onSubmit={onSubmit}>
        <label>
          {t("delegation.deputy")}
          <select value={deputy} onChange={(e) => setDeputy(e.target.value)} required>
            <option value="">{t("delegation.choose")}</option>
            {data.candidates.map((c) => (
              <option key={c.id} value={c.id}>
                {c.full_name} · {c.position}
              </option>
            ))}
          </select>
        </label>
        <div className="row-2">
          <label>
            {t("delegation.from")}
            <input type="date" min={today} value={from} onChange={(e) => setFrom(e.target.value)} required />
          </label>
          <label>
            {t("delegation.to")}
            <input type="date" min={from || today} value={to} onChange={(e) => setTo(e.target.value)} required />
          </label>
        </div>
        {create.error && <p className="error">{create.error.message}</p>}
        <div>
          <button className="btn-primary" disabled={create.isPending}>
            <Icon src={icons.add} size={18} />
            {t("delegation.assign")}
          </button>
        </div>
      </form>

      {data.delegations.length === 0 ? (
        <p className="muted small">{t("delegation.none")}</p>
      ) : (
        <ul className="request-list">
          {data.delegations.map((d) => (
            <li key={d.id} className="request-row">
              <div className="request-main">
                <strong>{d.deputy.full_name}</strong>
                <span className="muted small">
                  {fmtDate(d.date_from)} – {fmtDate(d.date_to)}
                </span>
              </div>
              <div className="row">
                <span className={`status status-${TONE[d.state]}`}>{t(`delegation.state.${d.state}`)}</span>
                {(d.state === "planned" || d.state === "active") && (
                  <button className="btn-ghost btn-small" disabled={revoke.isPending} onClick={() => revoke.mutate(d.id)}>
                    {t("delegation.revoke")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
