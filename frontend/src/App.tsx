import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ConfigurationLayout } from "@/components/ConfigurationLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireRoles } from "@/components/RequireRoles";
import { LoginPage } from "@/pages/LoginPage";
import { TimesheetPage } from "@/pages/TimesheetPage";

// Login and the timesheet are what every user opens, so they (and the layouts and route
// guards around them) are in the main bundle. Every other page is role-gated or occasional
// and is downloaded the first time it is visited: a user without the role is redirected by
// the guard before the page renders, so they never download it at all. The pages keep their
// named exports, hence the `default` wrapper `lazy` needs. The Suspense fallback and the
// error boundary for a failed download are in AppLayout and ConfigurationLayout.
const ReportingPage = lazy(() =>
  import("@/pages/ReportingPage").then((m) => ({ default: m.ReportingPage })),
);
const ProjectsPage = lazy(() =>
  import("@/pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage })),
);
const ProjectFormPage = lazy(() =>
  import("@/pages/ProjectFormPage").then((m) => ({ default: m.ProjectFormPage })),
);
const ConfigurationGeneralPage = lazy(() =>
  import("@/pages/ConfigurationGeneralPage").then((m) => ({
    default: m.ConfigurationGeneralPage,
  })),
);
const CompaniesListPage = lazy(() =>
  import("@/pages/CompaniesListPage").then((m) => ({ default: m.CompaniesListPage })),
);
const CompanyFormPage = lazy(() =>
  import("@/pages/CompanyFormPage").then((m) => ({ default: m.CompanyFormPage })),
);
const UsersPage = lazy(() =>
  import("@/pages/UsersPage").then((m) => ({ default: m.UsersPage })),
);
const UserFormPage = lazy(() =>
  import("@/pages/UserFormPage").then((m) => ({ default: m.UserFormPage })),
);

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
