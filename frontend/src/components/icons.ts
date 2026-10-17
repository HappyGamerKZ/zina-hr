// Иконки Jana HR (src/assets/jana-hr-icons). Используются через <Icon src={icons.x} />:
// контурные «bare»-иконки выводятся маской и берут цвет текста (currentColor), поэтому
// одинаково работают в светлой и тёмной теме. Цветные иллюстрации — в illustrations.ts.

// навигация и общее
import home from "../assets/jana-hr-icons/light/navigation/bare/home.svg";
import documents from "../assets/jana-hr-icons/light/navigation/bare/documents.svg";
import aiAssistant from "../assets/jana-hr-icons/light/navigation/bare/ai-assistant.svg";
import profile from "../assets/jana-hr-icons/light/navigation/bare/profile.svg";
import people from "../assets/jana-hr-icons/light/navigation/bare/people.svg";
import settings from "../assets/jana-hr-icons/light/navigation/bare/settings.svg";
import notifications from "../assets/jana-hr-icons/light/navigation/bare/notifications.svg";
import logOut from "../assets/jana-hr-icons/light/navigation/bare/log-out.svg";
import recruitment from "../assets/jana-hr-icons/light/navigation/bare/recruitment.svg";
import calendar from "../assets/jana-hr-icons/light/navigation/bare/calendar.svg";
import search from "../assets/jana-hr-icons/light/navigation/bare/search.svg";
import help from "../assets/jana-hr-icons/light/navigation/bare/help.svg";
import more from "../assets/jana-hr-icons/light/navigation/bare/more.svg";
import messages from "../assets/jana-hr-icons/light/navigation/bare/messages.svg";
// HR
import training from "../assets/jana-hr-icons/light/hr-employee/bare/training.svg";
import approvals from "../assets/jana-hr-icons/light/hr-employee/bare/approvals.svg";
import leave from "../assets/jana-hr-icons/light/hr-employee/bare/leave.svg";
import expenses from "../assets/jana-hr-icons/light/hr-employee/bare/expenses.svg";
import interview from "../assets/jana-hr-icons/light/hr-employee/bare/interview.svg";
import onboarding from "../assets/jana-hr-icons/light/hr-employee/bare/onboarding.svg";
import policies from "../assets/jana-hr-icons/light/hr-employee/bare/policies.svg";
import tasks from "../assets/jana-hr-icons/light/hr-employee/bare/tasks.svg";
import timeOff from "../assets/jana-hr-icons/light/hr-employee/bare/time-off.svg";
// действия
import add from "../assets/jana-hr-icons/light/actions/bare/add.svg";
import attach from "../assets/jana-hr-icons/light/actions/bare/attach.svg";
import download from "../assets/jana-hr-icons/light/actions/bare/download.svg";
import externalLink from "../assets/jana-hr-icons/light/actions/bare/external-link.svg";
import upload from "../assets/jana-hr-icons/light/actions/bare/upload.svg";
// стрелки
import chevronLeft from "../assets/jana-hr-icons/light/arrows-controls/bare/chevron-left.svg";
import chevronRight from "../assets/jana-hr-icons/light/arrows-controls/bare/chevron-right.svg";
import close from "../assets/jana-hr-icons/light/arrows-controls/bare/close.svg";
import up from "../assets/jana-hr-icons/light/arrows-controls/bare/up.svg";
import down from "../assets/jana-hr-icons/light/arrows-controls/bare/down.svg";

export const icons = {
  // меню
  home,
  requests: documents,
  academy: training,
  ai: aiAssistant,
  profile,
  team: people,
  approvals,
  admin: settings,
  bell: notifications,
  logout: logOut,
  recruitment,
  // общее
  calendar,
  search,
  help,
  more,
  messages,
  documents,
  // заявки и обучение
  vacation: leave,
  advance: expenses,
  interview,
  hired: onboarding,
  readOnly: policies, // щит: данные только для чтения, урок закрыт
  done: tasks, // галочка
  pending: timeOff, // часы
  // действия
  add,
  attach,
  download,
  externalLink,
  upload,
  // стрелки
  back: chevronLeft,
  forward: chevronRight,
  close,
  up,
  down,
};
