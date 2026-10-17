import { lazy, StrictMode, Suspense, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ButtonLink, PageLoader } from "./components/ui";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import Auth from "./pages/Auth";
import Landing from "./pages/Landing";
const Configure = lazy(() => import("./pages/Configure"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const History = lazy(() => import("./pages/History"));
const InterviewRoom = lazy(() => import("./pages/InterviewRoom"));
const Profile = lazy(() => import("./pages/Profile"));
const Results = lazy(() => import("./pages/Results"));
const Roadmap = lazy(() => import("./pages/Roadmap"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <h1 className="text-3xl font-extrabold">Page not found</h1>
      <p className="text-muted">That link doesn't lead anywhere. Head back to your dashboard.</p>
      <ButtonLink to="/dashboard">Go to dashboard</ButtonLink>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Auth mode="login" />} />
          <Route path="/signup" element={<Auth mode="signup" />} />
          <Route path="/interview/:id" element={<RequireAuth><InterviewRoom /></RequireAuth>} />
          <Route element={<RequireAuth><AppShell /></RequireAuth>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/interview/new" element={<Configure />} />
            <Route path="/results/:id" element={<Results />} />
            <Route path="/roadmap" element={<Roadmap />} />
            <Route path="/history" element={<History />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
