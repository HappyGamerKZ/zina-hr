import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { BusyVacation, HrRequestDetail, Profile, RequestType } from "../api/types";
import VacationCalendar, { toIso } from "../components/VacationCalendar";
import { fmtDate } from "../i18n";

function daysBetween(from: string, to: string): number {
  if (!from || !to) return 0;
  const diff = (new Date(to).getTime() - new Date(from).getTime()) / 86_400_000;
  return diff >= 0 ? Math.round(diff) + 1 : 0;
}

export default function NewRequestPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const type: RequestType = params.get("type") === "advance" ? "advance" : "vacation";

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [vacationType, setVacationType] = useState("annual");
  const [comment, setComment] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");

  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/me/profile") });
  const busy = useQuery({
    queryKey: ["requests", "vacation-calendar"],
    queryFn: () => api<BusyVacation[]>("/requests/vacation-calendar"),
    enabled: type === "vacation",
  });
  const available = profile.data?.vacation_balance.days_available;
  const days = daysBetween(dateFrom, dateTo);
  const today = toIso(new Date());

  const create = useMutation({
    mutationFn: () =>
      api<HrRequestDetail>("/requests", {
        method: "POST",
        body:
          type === "vacation"
            ? { type, vacation: { date_from: dateFrom, date_to: dateTo, vacation_type: vacationType, comment } }
            : { type, advance: { amount, reason } },
      }),
    onSuccess: (req) => {
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      navigate(`/requests/${req.id}`, { replace: true });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <div className="stack narrow">
      <div className="tabs">
        {(["vacation", "advance"] as const).map((v) => (
          <button key={v} className={type === v ? "active" : ""} onClick={() => setParams({ type: v })}>
            {t(`type.${v}`)}
          </button>
        ))}
      </div>

      <form className="card form" onSubmit={onSubmit}>
        <h1>{type === "vacation" ? t("newRequest.title_vacation") : t("newRequest.title_advance")}</h1>

        {type === "vacation" ? (
          <>
            <VacationCalendar
              busy={busy.data ?? []}
              from={dateFrom}
              to={dateTo}
              minDate={today}
              onChange={(f, tt) => {
                setDateFrom(f);
                setDateTo(tt);
              }}
            />
            {dateFrom && (
              <p className="selected-range">
                {t("newRequest.date_from")}: <strong>{fmtDate(dateFrom)}</strong>
                {dateTo && (
                  <>
                    {" · "}
                    {t("newRequest.date_to")}: <strong>{fmtDate(dateTo)}</strong>
                  </>
                )}
              </p>
            )}
            <label>
              {t("newRequest.vacation_type")}
              <select value={vacationType} onChange={(e) => setVacationType(e.target.value)}>
                <option value="annual">{t("newRequest.annual")}</option>
                <option value="unpaid">{t("newRequest.unpaid")}</option>
              </select>
            </label>
            <p className="hint">
              {days > 0 && <>{t("newRequest.days", { count: days })} · </>}
              {available !== undefined && t("newRequest.available", { count: available })}
            </p>
            <label>
              {t("newRequest.comment")}
              <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
          </>
        ) : (
          <>
            <label>
              {t("newRequest.amount")}
              <input
                type="number"
                min={1}
                step={1}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </label>
            <label>
              {t("newRequest.reason")}
              <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          </>
        )}

        {create.error && <p className="error">{create.error.message}</p>}
        <div className="row">
          <button
            className="btn-primary"
            disabled={create.isPending || (type === "vacation" && (!dateFrom || !dateTo))}
          >
            {t("newRequest.submit")}
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate(-1)}>
            {t("common.cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}
