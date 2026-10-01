import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ConfigurationLayout } from "@/components/ConfigurationLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireRoles } from "@/components/RequireRoles";
import { CompaniesListPage } from "@/pages/CompaniesListPage";
import { CompanyFormPage } from "@/pages/CompanyFormPage";
import { ConfigurationGeneralPage } from "@/pages/ConfigurationGeneralPage";
import { LoginPage } from "@/pages/LoginPage";
import { ProjectFormPage } from "@/pages/ProjectFormPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { ReportingPage } from "@/pages/ReportingPage";
import { TimesheetPage } from "@/pages/TimesheetPage";
import { UserFormPage } from "@/pages/UserFormPage";
import { UsersPage } from "@/pages/UsersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* The timesheet is the landing screen. There is deliberately no /timesheet
              route: it falls through to the catch-all below and lands here. */}
          <Route path="/" element={<TimesheetPage />} />
          <Route element={<RequireRoles roles={["project_manager"]} />}>
            <Route path="/reporting" element={<ReportingPage />} />
          </Route>
          <Route element={<RequireRoles roles={["project_admin"]} />}>
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/new" element={<ProjectFormPage />} />
            <Route path="/projects/:projectId" element={<ProjectFormPage />} />
          </Route>
          <Route element={<RequireRoles roles={["administrator"]} />}>
            {/* Bare /configuration redirects to the default tab; unknown sub-paths still
                fall through to the catch-all below like any other unrecognized URL. */}
            <Route path="/configuration" element={<ConfigurationLayout />}>
              <Route index element={<Navigate to="general" replace />} />
              <Route path="general" element={<ConfigurationGeneralPage />} />
              <Route path="companies" element={<CompaniesListPage />} />
              <Route path="companies/new" element={<CompanyFormPage />} />
              <Route path="companies/:companyId" element={<CompanyFormPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="users/new" element={<UserFormPage />} />
              <Route path="users/:userId" element={<UserFormPage />} />
            </Route>
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
