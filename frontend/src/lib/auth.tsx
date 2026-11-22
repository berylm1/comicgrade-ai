/**
 * Sign-in state. Live mode uses Supabase email + password, or a one-time email
 * code once the project has custom SMTP and a template with {{ .Token }}. Demo mode and a
 * placeholder Supabase config skip sign-in (the backend then falls back to
 * DEV_USER_ID, which only works while the backend has AUTH_REQUIRED=false).
 */
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { Session } from '@supabase/supabase-js';

import { DEMO_MODE, SUPABASE_URL } from './env';
import { getSupabase } from './supabase';

/** Sign-in is needed only in live mode with a real Supabase project configured. */
export const AUTH_ENABLED = !DEMO_MODE && !SUPABASE_URL.includes('your-project-ref');

type AuthState = {
  session: Session | null;
  loading: boolean;
  email: string | null;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  /** Returns true when signed in straight away, false when the email must be confirmed first. */
  signUp: (email: string, password: string) => Promise<boolean>;
  sendCode: (email: string) => Promise<void>;
  verifyCode: (email: string, code: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(AUTH_ENABLED);

  useEffect(() => {
    if (!AUTH_ENABLED) return;
    const sb = getSupabase();
    sb.auth
      .getSession()
      .then(({ data }) => setSession(data.session))
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
    const { data } = sb.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      loading,
      email: session?.user.email ?? null,
      signInWithPassword: async (email, password) => {
        const { error } = await getSupabase().auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
      },
      signUp: async (email, password) => {
        const { data, error } = await getSupabase().auth.signUp({ email: email.trim(), password });
        if (error) throw error;
        return Boolean(data.session);
      },
      sendCode: async (email) => {
        const { error } = await getSupabase().auth.signInWithOtp({
          email: email.trim(),
          options: { shouldCreateUser: true },
        });
        if (error) throw error;
      },
      verifyCode: async (email, code) => {
        const { error } = await getSupabase().auth.verifyOtp({
          email: email.trim(),
          token: code.trim(),
          type: 'email',
        });
        if (error) throw error;
      },
      signOut: async () => {
        if (AUTH_ENABLED) await getSupabase().auth.signOut();
      },
    }),
    [session, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
