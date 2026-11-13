/** Shared environment values for the React Native client. */
// In production, keep EXPO_PUBLIC_* keys out of source and use EAS config.
// EXPO_PUBLIC_* vars are inlined at bundle time by Expo.
export const SUPABASE_URL =
  process.env.EXPO_PUBLIC_SUPABASE_URL ?? 'https://your-project-ref.supabase.co';
export const SUPABASE_ANON_KEY =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? 'your-anon-key';
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Demo mode serves the whole app from in-memory sample data (src/lib/demo.ts):
 * no backend, no Supabase, no camera. It is on unless a backend URL is configured,
 * and EXPO_PUBLIC_DEMO_MODE=1 / 0 forces it either way.
 */
export const DEMO_MODE =
  process.env.EXPO_PUBLIC_DEMO_MODE === '1' ||
  (process.env.EXPO_PUBLIC_DEMO_MODE !== '0' && !process.env.EXPO_PUBLIC_API_BASE_URL);