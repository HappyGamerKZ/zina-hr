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

export interface VacancyWithCounts extends VacancyShort {
  is_open: boolean;
  candidates_count: number;
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

export interface CandidateListItem {
  id: number;
  full_name: string;
  vacancy: VacancyShort;
  stage: CandidateStage;
  reviewed: boolean;
  expected_salary: number | null;
  created_at: string;
  next_interview: { kind: "hr" | "tech"; scheduled_at: string } | null;
}

export interface CandidateDetail extends CandidateListItem {
  email: string;
  phone: string;
  social: string;
  profile_url: string;
  resume_url: string | null; // /api/v1/recruitment/candidates/{id}/resume — только для HR и интервьюера
  comment: string;
  decision_stage: CandidateStage | "";
  steps: { key: CandidateStage | "decision"; label: string; state: StepState }[];
  allowed_actions: CandidateAction[];
  interviews: CandidateInterview[];
  events: { id: number; action: string; stage: CandidateStage; actor_name: string | null; comment: string; created_at: string }[];
}

export interface UpcomingInterview extends CandidateInterview {
  candidate: { id: number; full_name: string; vacancy: VacancyShort; stage: CandidateStage };
}

export interface RecruitmentSummary {
  new_resumes?: number; // только HR
  by_stage?: Record<CandidateStage, number>; // только HR
  upcoming_interviews: UpcomingInterview[];
}
