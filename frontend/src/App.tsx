import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { AppShell } from './components/layout/AppShell';
import { FullPageSpinner } from './components/ui/FullPageSpinner';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';

// Route-level code splitting: only the landing + login pages ship in the entry chunk.
// The share page (/r/:slug) — the viral entry path — pulls only its own chunk + markdown.
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const NewRoastPage = lazy(() => import('./pages/NewRoastPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const PublicRoastPage = lazy(() => import('./pages/PublicRoastPage'));
const RoastResultPage = lazy(() => import('./pages/RoastResultPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<FullPageSpinner />}>
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/r/:shareSlug" element={<PublicRoastPage />} />

          {/* Authenticated */}
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/roast/new" element={<ProtectedRoute><NewRoastPage /></ProtectedRoute>} />
          <Route path="/roasts/:id" element={<ProtectedRoute><RoastResultPage /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />

          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
