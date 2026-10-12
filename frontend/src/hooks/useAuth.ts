import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from '../context/authContextValue';

export type { AuthContextValue };

/** Current auth state + actions. Must be used under <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

export default useAuth;
