import { useTranslation } from "react-i18next";

import type { RequestStatus } from "../api/types";

const TONE: Record<RequestStatus, string> = {
  draft: "neutral",
  waiting_manager_approval: "warn",
  waiting_hr_approval: "info",
  approved_sent_to_1c: "ok",
  rejected: "bad",
  cancelled: "neutral",
};

export default function StatusBadge({ status }: { status: RequestStatus }) {
  const { t } = useTranslation();
  return <span className={`status status-${TONE[status]}`}>{t(`status.${status}`)}</span>;
}
