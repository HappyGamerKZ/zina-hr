import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { HrRequestDetail, RequestAction } from "../api/types";
import StatusBadge from "../components/StatusBadge";
import { fmtDate, fmtDateTime, fmtMoney } from "../i18n";

const ACTION_STYLE: Record<RequestAction, string> = {
  submit: "btn-primary",
  approve_manager: "btn-primary",
  approve_hr: "btn-primary",
  reject: "btn-danger",
  cancel: "btn-ghost",
};

// PATCH /requests/{id}/approve-manager, /approve-hr, /reject, /cancel, /submit
const ACTION_PATH: Record<RequestAction, string> = {
  submit: "submit",
  approve_manager: "approve-manager",
  approve_hr: "approve-hr",
  reject: "reject",
  cancel: "cancel",
};

export default function RequestDetailPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");

  const { data: req, isLoading, error } = useQuery({
    queryKey: ["requests", "detail", id],
    queryFn: () => api<HrRequestDetail>(`/requests/${id}`),
  });

  const transition = useMutation({
    mutationFn: (action: RequestAction) =>
      api<HrRequestDetail>(`/requests/${id}/${ACTION_PATH[action]}`, { method: "PATCH", body: { comment } }),
    onSuccess: (updated) => {
      qc.setQueryData(["requests", "detail", id], updated);
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      setComment("");
    },
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  // 404 приходит и для чужой заявки — сервер не раскрывает её существование
  if (error instanceof ApiError && error.status === 404) return <p className="error">404</p>;
  if (error || !req) return <p className="error">{t("common.error")}</p>;

  return (
    <div className="stack narrow">
      <Link to="/requests" className="muted">
        ← {t("common.back")}
      </Link>
      <section className="card">
        <div className="section-head">
          <div>
            <h1>{t(`type.${req.type}`)}</h1>
            <span className="muted">
              {req.number} · {fmtDate(req.created_at)}
            </span>
          </div>
          <StatusBadge status={req.status} />
        </div>

        <dl className="fields">
          <div>
            <dt>{t("requests.employee")}</dt>
            <dd>{req.employee.full_name}</dd>
          </div>
          {req.vacation && (
            <>
              <div>
                <dt>{t("requests.period")}</dt>
                <dd>
                  {fmtDate(req.vacation.date_from)} – {fmtDate(req.vacation.date_to)} (
                  {t("common.days", { count: req.vacation.days })})
                </dd>
              </div>
              {req.vacation.comment && (
                <div>
                  <dt>{t("requests.comment")}</dt>
                  <dd>{req.vacation.comment}</dd>
                </div>
              )}
            </>
          )}
          {req.advance && (
            <>
              <div>
                <dt>{t("requests.amount")}</dt>
                <dd>{fmtMoney(req.advance.amount)}</dd>
              </div>
              {req.advance.reason && (
                <div>
                  <dt>{t("requests.reason")}</dt>
                  <dd>{req.advance.reason}</dd>
                </div>
              )}
            </>
          )}
          {req.external_accounting_id && (
            <div>
              <dt>{t("requests.accounting_id")}</dt>
              <dd>{req.external_accounting_id}</dd>
            </div>
          )}
        </dl>

        {req.allowed_actions.length > 0 && (
          <div className="actions">
            {req.allowed_actions.some((a) => a === "approve_manager" || a === "approve_hr" || a === "reject") && (
              <textarea
                rows={2}
                placeholder={t("requests.comment_placeholder")}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            )}
            <div className="row">
              {req.allowed_actions.map((a) => (
                <button
                  key={a}
                  className={ACTION_STYLE[a]}
                  disabled={transition.isPending}
                  onClick={() => transition.mutate(a)}
                >
                  {t(`action.${a}`)}
                </button>
              ))}
            </div>
            {transition.error && <p className="error">{transition.error.message}</p>}
          </div>
        )}
      </section>

      <section className="card">
        <h2>{t("requests.history")}</h2>
        <ol className="timeline">
          {req.events.map((ev) => (
            <li key={ev.id}>
              <div className="timeline-head">
                {ev.from_status ? <StatusBadge status={ev.to_status} /> : <strong>{t("requests.created_event")}</strong>}
                <span className="muted small">{fmtDateTime(ev.created_at)}</span>
              </div>
              <span className="small">{ev.actor_name ?? t("requests.system")}</span>
              {ev.comment && <p className="small comment">«{ev.comment}»</p>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
