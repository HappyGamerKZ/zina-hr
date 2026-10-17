import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import AcademyPage from "./pages/AcademyPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import AssignCoursePage from "./pages/AssignCoursePage";
import AssignmentPage from "./pages/AssignmentPage";
import CandidatePage from "./pages/CandidatePage";
import LessonPage from "./pages/LessonPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import NewRequestPage from "./pages/NewRequestPage";
import NotificationsPage from "./pages/NotificationsPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import ProfilePage from "./pages/ProfilePage";
import RecruitmentPage from "./pages/RecruitmentPage";
import RequestDetailPage from "./pages/RequestDetailPage";
import RequestsPage from "./pages/RequestsPage";
import TeamMemberPage from "./pages/TeamMemberPage";
import TeamPage from "./pages/TeamPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();
  if (loading) return <div className="center muted">{t("common.loading")}</div>;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

/** Скрывает раздел в интерфейсе. Настоящая проверка прав — на сервере. */
function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(permission) ? <>{children}</> : <Navigate to="/" replace />;
}

export default function App() {
  const { t } = useTranslation();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/careers" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="requests" element={<RequestsPage />} />
        <Route path="requests/new" element={<NewRequestPage />} />
        <Route path="requests/:id" element={<RequestDetailPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="academy" element={<AcademyPage />} />
        <Route
          path="academy/assign"
          element={
            <RequirePermission permission="team.view">
              <AssignCoursePage />
            </RequirePermission>
          }
        />
        <Route path="academy/assignments/:id" element={<AssignmentPage />} />
        <Route path="academy/assignments/:id/lessons/:lessonId" element={<LessonPage />} />
        <Route path="ai" element={<PlaceholderPage title={t("nav.ai")} />} />
        <Route
          path="team"
          element={
            <RequirePermission permission="team.view">
              <TeamPage />
            </RequirePermission>
          }
        />
        <Route
          path="team/approvals"
          element={
            <RequirePermission permission="requests.approve">
              <ApprovalsPage />
            </RequirePermission>
          }
        />
        <Route
          path="team/:id"
          element={
            <RequirePermission permission="team.view">
              <TeamMemberPage />
            </RequirePermission>
          }
        />
        <Route
          path="recruitment"
          element={
            <RequirePermission permission="recruitment.interviews">
              <RecruitmentPage />
            </RequirePermission>
          }
        />
        <Route
          path="recruitment/:id"
          element={
            <RequirePermission permission="recruitment.interviews">
              <CandidatePage />
            </RequirePermission>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
