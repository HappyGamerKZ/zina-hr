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
  learning: Assignment[];
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
  approver: RequestApprover | null; // кто сейчас согласует шаг руководителя
}

export interface RequestApprover {
  kind: "manager" | "deputy" | "escalated" | "hr_pool";
  employee: { id: number; full_name: string } | null; // null — общий пул HR
  acting_for: { id: number; full_name: string } | null; // за кого действует И.О.
  note: string;
}

export interface Delegation {
  id: number;
  manager: { id: number; full_name: string; position: string };
  deputy: { id: number; full_name: string; position: string };
  date_from: string;
  date_to: string;
  revoked_at: string | null;
  state: "planned" | "active" | "finished" | "revoked";
}

export interface DelegationsInfo {
  can_delegate: boolean;
  candidates: { id: number; full_name: string; position: string }[];
  delegations: Delegation[];
  acting_for: Delegation[];
}

// --- Jana Academy ---

export type AssignmentStatus = "assigned" | "in_progress" | "completed" | "failed";
export type LessonKind = "text" | "quiz"; // материал из блоков или тест
export type BlockKind = "heading" | "text" | "note" | "image" | "video" | "file";

export interface LessonBlock {
  id: number;
  type: BlockKind;
  text: string;
  url: string; // загруженный файл (/media/...) или внешняя ссылка
  file_name: string;
  embed_url: string; // YouTube для встраивания
}
export type QuestionKind = "single" | "multiple" | "ordering" | "fill_blanks";

export interface CourseShort {
  id: number;
  title_ru: string;
  title_kk: string;
  cover_emoji: string;
  cover_icon: string; // ключ иконки из набора (icons.ts → courseIcons)
}

export interface CourseListItem extends CourseShort {
  description_ru: string;
  description_kk: string;
  duration_min: number;
  lessons_count: number;
  my_assignment: { id: number; status: AssignmentStatus; progress_pct: number } | null;
}

export interface Assignment {
  id: number;
  course: CourseShort;
  employee: { id: number; full_name: string };
  status: AssignmentStatus;
  progress_pct: number;
  score: number | null;
  best_score: number | null;
  cycle: number;
  due_date: string | null;
  assigned_by_name: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  can_restart: boolean; // сотрудник может перепройти сданный курс
  can_reassign: boolean; // HR / руководитель может назначить повторно
}

export interface QuizState {
  id: number;
  pass_score: number;
  max_attempts: number;
  attempts_used: number;
  attempts_left: number | null; // null — без ограничений
  best_score: number | null;
  passed: boolean;
}

export interface OutlineLesson {
  id: number;
  title: string;
  type: LessonKind;
  duration_min: number;
  status: "completed" | "available" | "locked";
  quiz?: QuizState;
}

export interface AssignmentDetail extends Assignment {
  modules: { id: number; title: string; lessons: OutlineLesson[] }[];
}

export interface QuizQuestion {
  id: number;
  type: QuestionKind;
  text: string;
  points: number;
  options: { id: number; text: string }[];
  blanks?: number[];
}

/** single → id; multiple / ordering → id[]; fill_blanks → {номер пропуска: id} */
export type Answer = number | number[] | Record<string, number>;

export interface AttemptResult {
  id: number;
  score: number;
  passed: boolean;
  created_at: string;
  pass_score: number;
  attempts_left: number | null;
  answers_revealed: boolean;
  details: {
    question_id: number;
    fraction: number;
    correct: boolean;
    your_answer?: Answer;
    correct_answer?: Answer;
    explanation?: string;
  }[];
}

export interface LessonDetail {
  id: number;
  title: string;
  type: LessonKind;
  blocks: LessonBlock[];
  module: string;
  completed: boolean;
  prev_lesson_id: number | null;
  next_lesson_id: number | null;
  quiz?: QuizState & { questions: QuizQuestion[]; last_attempt: AttemptResult | null };
}

export interface BusyVacation {
  request_id: number;
  number: string;
  status: RequestStatus;
  date_from: string;
  date_to: string;
  days: number;
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
  courses: Assignment[];
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
  // в отпуске сейчас, отпуск в ближайшие 30 дней (утверждённый) или уволен; null — на месте
  absence: { state: "vacation" | "planned" | "dismissed"; date_from: string; date_to: string | null } | null;
  deputy: { id: number; full_name: string; date_from: string; date_to: string } | null; // И.О. на эти даты
}

// --- Подбор персонала ---

export type CandidateStage = "screening" | "hr_interview" | "tech_interview" | "hired" | "rejected";
export type CandidateAction = "review" | "next" | "reject" | "hire" | "schedule";
export type StepState = "done" | "current" | "pending" | "rejected" | "skipped" | "hired";

export interface VacancyShort {
  id: number;
  title_ru: string;
  title_kk: string;
}

export interface PublicVacancy extends VacancyShort {
  department: string;
  description: string;
}

export type VacancyStatus = "draft" | "active" | "closed";
export type EmploymentType = "full_time" | "part_time" | "contract" | "internship";

export interface VacancyWithCounts extends VacancyShort {
  is_open: boolean;
  candidates_count: number;
  status: VacancyStatus;
  department: { id: number; name: string } | null;
  employment_type: EmploymentType;
  salary_from: number | null;
  salary_to: number | null;
  description: string;
  active_candidates_count: number;
  created_at: string;
}

export interface VacancyInput {
  title_ru: string;
  title_kk?: string;
  department_id?: number | null;
  hiring_manager_id?: number | null;
  employment_type?: EmploymentType;
  description?: string;
  salary_from?: number | null;
  salary_to?: number | null;
  status?: VacancyStatus;
}

export interface CandidateInterview {
  id: number;
  kind: "hr" | "tech";
  scheduled_at: string;
  duration_min: number;
  interviewer: { id: number; full_name: string } | null;
  location: string;
  status: "scheduled" | "done" | "cancelled";
  feedback: string;
}

export interface CandidateStep {
  key: CandidateStage | "decision";
  label: string;
  state: StepState;
  date: string | null; // когда пройден (для интервью — их дата)
}

export type MatchFactor = "salary" | "resume" | "letter" | "progress" | "interviews";

export interface CandidateListItem {
  id: number;
  full_name: string;
  vacancy: VacancyShort;
  stage: CandidateStage;
  reviewed: boolean;
  expected_salary: number | null;
  created_at: string;
  next_interview: { kind: "hr" | "tech"; scheduled_at: string } | null;
  number: string; // CV-0018 — по нему кандидат смотрит статус
  match_score: number; // 0..100, соответствие вакансии (правила, не AI)
}

export interface CandidateDetail extends CandidateListItem {
  email: string;
  phone: string;
  social: string;
  profile_url: string;
  resume_url: string | null; // /api/v1/recruitment/candidates/{id}/resume — только для HR и интервьюера
  comment: string;
  decision_stage: CandidateStage | "";
  steps: CandidateStep[];
  allowed_actions: CandidateAction[];
  interviews: CandidateInterview[];
  events: { id: number; action: string; stage: CandidateStage; actor_name: string | null; comment: string; created_at: string }[];
  match: { score: number; factors: { key: MatchFactor; points: number; max: number }[] };
  vacancy_status: VacancyStatus;
}

export interface UpcomingInterview extends CandidateInterview {
  candidate: { id: number; full_name: string; vacancy: VacancyShort; stage: CandidateStage };
}

export interface RecruitmentSummary {
  new_resumes?: number; // только HR
  by_stage?: Record<CandidateStage, number>; // только HR
  upcoming_interviews: UpcomingInterview[];
  upcoming_count: number;
  open_vacancies?: number; // дальше — только HR
  active_candidates?: number;
  pending_requests?: number;
  top_candidates?: CandidateListItem[];
}

export interface Interviewer {
  id: number;
  full_name: string;
  role: Role;
  employee_id: number | null;
}

/** Публичный статус заявки кандидата (по номеру и почте). */
export interface ApplicationStatus {
  number: string;
  full_name: string;
  vacancy: VacancyShort;
  stage: CandidateStage;
  created_at: string;
  steps: { key: CandidateStage | "decision"; state: StepState; date: string | null }[];
  next_interview: { kind: "hr" | "tech"; scheduled_at: string; location: string } | null;
}

// --- AI Jana ---

export interface AiAnswer {
  answer: string;
  lang: "ru" | "kk";
  found: boolean; // ответ из базы знаний
  can_escalate: boolean; // показать «Передать в HR»
  sources: { id: string; title: string }[];
  draft: { type: "vacation"; date_from: string; date_to: string; days: number; available: number } | null;
}

export interface AiQuestion {
  id: number;
  author: string;
  question: string;
  ai_answer: string;
  lang: string;
  status: "open" | "answered";
  hr_answer: string;
  answered_by: string | null;
  answered_at: string | null;
  created_at: string;
}
