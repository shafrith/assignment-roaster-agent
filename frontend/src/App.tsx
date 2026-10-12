import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { FullPageSpinner } from './components/ui/FullPageSpinner';
import LandingPage from './pages/LandingPage';

// Route-level code splitting: only the landing page (with the paste-URL form) ships in the
// entry chunk. The roast page (/r/:slug) pulls only its own chunk + markdown.
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const RoastPage = lazy(() => import('./pages/RoastPage'));

/** No login: paste a repo URL on the landing page, follow the roast at /r/:shareSlug. */
export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<FullPageSpinner />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/r/:shareSlug" element={<RoastPage />} />
          {/* Old entry points from the login era. */}
          <Route path="/roast/new" element={<Navigate to="/" replace />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="/login" element={<Navigate to="/" replace />} />

          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
