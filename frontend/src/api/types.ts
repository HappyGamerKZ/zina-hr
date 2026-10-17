// Типы ответов API. Позже заменяются сгенерированными: npm run gen:api → src/api/schema.d.ts

export type Role = "employee" | "manager" | "hr_admin";
export type Lang = "ru" | "kk";

export interface Me {
  id: number;
  username: string;
  role: Role;
  locale: Lang;
  employee_id: number | null;
  full_name: string;
  permissions: string[];
}

export interface VacationBalance {
  days_total: number;
  days_used: number;
  days_reserved: number;
  days_available: number;
  as_of: string | null;
  synced_at: string | null;
}

export interface Profile {
  id: number;
  full_name: string;
  company: string;
  department: string;
  position: string;
  manager: { id: number; full_name: string; position: string } | null;
  hire_date: string;
  email: string;
  external_id: string;
  source: string;
  synced_at: string | null;
  vacation_balance: VacationBalance;
}

export type RequestType = "vacation" | "advance";
export type RequestStatus =
  | "draft"
  | "waiting_manager_approval"
  | "waiting_hr_approval"
  | "approved_sent_to_1c"
  | "rejected"
  | "cancelled";
export type RequestAction = "submit" | "approve_manager" | "approve_hr" | "reject" | "cancel";

export interface HrRequest {
  id: number;
  number: string;
  type: RequestType;
  status: RequestStatus;
  employee: { id: number; full_name: string };
  vacation: { date_from: string; date_to: string; days: number; vacation_type: string; comment: string } | null;
  advance: { amount: string; reason: string; pay_date: string | null } | null;
  created_at: string;
  updated_at: string;
}

export interface RequestEvent {
  id: number;
  from_status: RequestStatus | "";
  to_status: RequestStatus;
  actor_name: string | null;
  comment: string;
  created_at: string;
}

export interface HrRequestDetail extends HrRequest {
  events: RequestEvent[];
  allowed_actions: RequestAction[];
  external_doc_id: string;
  external_zup_id: string;
  external_accounting_id: string;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  body: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface Dashboard {
  profile: Profile;
  quick_services: { key: string; link: string }[];
  recent_requests: HrRequest[];
  approvals_count: number;
  courses: { id: number; title: string; progress_pct: number; status: string }[];
  notifications: Notification[];
  unread_notifications: number;
}

export interface TeamMember {
  id: number;
  full_name: string;
  department: string;
  position: string;
  hire_date: string;
  vacation_days_available: number;
  active_requests: number;
}
