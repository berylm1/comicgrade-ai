/** Shared environment values for the React Native client. */
// In production, keep EXPO_PUBLIC_* keys out of source and use EAS config.
// EXPO_PUBLIC_* vars are inlined at bundle time by Expo.
export const SUPABASE_URL =
  process.env.EXPO_PUBLIC_SUPABASE_URL ?? 'https://your-project-ref.supabase.co';
export const SUPABASE_ANON_KEY =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? 'your-anon-key';
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';