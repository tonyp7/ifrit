import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireRoles } from "@/components/RequireRoles";
import { CompaniesListPage } from "@/pages/CompaniesListPage";
import { CompanyFormPage } from "@/pages/CompanyFormPage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { ProjectFormPage } from "@/pages/ProjectFormPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { TimesheetPage } from "@/pages/TimesheetPage";
import { UserFormPage } from "@/pages/UserFormPage";
import { UsersPage } from "@/pages/UsersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/timesheet" element={<TimesheetPage />} />
          <Route element={<RequireRoles roles={["manager"]} />}>
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/new" element={<ProjectFormPage />} />
            <Route path="/projects/:projectId" element={<ProjectFormPage />} />
          </Route>
          <Route element={<RequireRoles roles={["administrator"]} />}>
            {/* Bare /configuration has no page of its own — the Configuration nav
                icon opens a dropdown instead (see docs/requirements/home.md
                #configuration-menu), so there's no single "right" destination to
                redirect to. Deliberately no route for it here: it falls through to
                the catch-all below, same as any other unrecognized URL. */}
            <Route path="/configuration/companies" element={<CompaniesListPage />} />
            <Route path="/configuration/companies/new" element={<CompanyFormPage />} />
            <Route
              path="/configuration/companies/:companyId"
              element={<CompanyFormPage />}
            />
            <Route path="/configuration/users" element={<UsersPage />} />
            <Route path="/configuration/users/new" element={<UserFormPage />} />
            <Route path="/configuration/users/:userId" element={<UserFormPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
