import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/layout/AppLayout";
import PlaceholderPage from "./components/common/PlaceholderPage";
import ProtectedRoute from "./components/common/ProtectedRoute";
import ContentGeneratorPage from
  "./features/content-generator/ContentGeneratorPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import TeamPage from "./features/team/TeamPage";
import Login from "./features/auth/Login";
import Register from "./features/auth/Register";

function App() {
  return (

    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      {/* Everything below requires a logged-in user. */}
      <Route element={<ProtectedRoute />}>
      {/* Every page shares the sidebar + topbar from AppLayout */}
      <Route element={<AppLayout />}>

        <Route index element={<Navigate to="/dashboard" replace />} />

        <Route path="create" element={<ContentGeneratorPage />} />

        <Route path="dashboard" element={<DashboardPage />} />

        {/* These pages aren't built yet, so they show a placeholder. */}
        <Route
          path="content"
          element={<PlaceholderPage title="My Content" />}
        />
        <Route
          path="analytics"
          element={<PlaceholderPage title="Analytics" />}
        />
        <Route
          path="brand-kit"
          element={<PlaceholderPage title="Brand Kit" />}
        />
        <Route path="team" element={<TeamPage />} />
        <Route
          path="settings"
          element={<PlaceholderPage title="Settings" />}
        />
      </Route>
      </Route>
    </Routes>
  );
}

export default App;
