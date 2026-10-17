// Supabase client for React Native.
// Requires 'react-native-url-polyfill' before createClient on RN < 0.72-style runtimes.
import 'react-native-url-polyfill/auto';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { SUPABASE_ANON_KEY, SUPABASE_URL } from './env';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) {
    if (SUPABASE_URL.includes('your-project-ref')) {
      console.warn(
        '[ComicGrade] Supabase credentials are placeholders. ' +
          'Create frontend/.env with EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY.',
      );
    }
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        storage: getAsyncStorageCompat(),
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
  }
  return client;
}

// AsyncStorage is optional; sessions fall back to in-memory if it isn't installed.
function getAsyncStorageCompat(): any | undefined {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const AsyncStorageMod = require('@react-native-async-storage/async-storage');
    return AsyncStorageMod.default ?? AsyncStorageMod;
  } catch {
    return undefined;
  }
}