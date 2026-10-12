import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { saveReturnTo } from '../../lib/returnTo';
import { FullPageSpinner } from '../ui/FullPageSpinner';

export interface ProtectedRouteProps {
  children: ReactNode;
}

/** Spinner while auth boots; unauthenticated users go to /login (and come back after). */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isLoading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <FullPageSpinner />;
  }

  if (!isAuthenticated) {
    saveReturnTo(`${location.pathname}${location.search}${location.hash}`);
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
