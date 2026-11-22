/** Thin typed client for the ComicGrade AI FastAPI backend. */
import { Platform } from 'react-native';

import { API_BASE_URL, DEMO_MODE, SUPABASE_URL } from './env';
import { demoApi } from './demo';
import { getSupabase } from './supabase';
import type {
  Comic,
  GradeReport,
  GradeScanResult,
  PriceEstimate,
  PricePoint,
  RunGap,
  ScanMatch,
  ScanPhotos,
  ValueLens,
  VisionResult,
} from '../types';

const BASE = API_BASE_URL.replace(/\/$/, '');

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Bearer token of the signed-in Supabase user, if any. */
async function authHeaders(): Promise<Record<string, string>> {
  if (SUPABASE_URL.includes('your-project-ref')) return {};
  try {
    const { data } = await getSupabase().auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = { ...(await authHeaders()), ...((init.headers as Record<string, string>) ?? {}) };
  return fetch(`${BASE}${path}`, { ...init, headers }).then((r) => handle<T>(r));
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/** Add a local photo to a multipart form (blob on web, { uri } file on native). */
async function appendPhoto(form: FormData, field: string, uri: string): Promise<void> {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(uri)).blob();
    form.append(field, blob, `${field}.jpg`);
  } else {
    // React Native FormData accepts the { uri, name, type } file shape.
    form.append(field, { uri, name: `${field}.jpg`, type: 'image/jpeg' } as any);
  }
}

const liveApi: typeof demoApi = {
  health: () => fetch(`${BASE}/health`).then(() => true).catch(() => false),

  analyzeCover: async (imageUri: string): Promise<VisionResult> => {
    const form = new FormData();
    await appendPhoto(form, 'image', imageUri);
    return request<VisionResult>('/vision/analyze', { method: 'POST', body: form });
  },

  /** Identify and grade a book from the front, and optionally back and spine, photos. */
  gradeScan: async (photos: ScanPhotos): Promise<GradeScanResult> => {
    const form = new FormData();
    await appendPhoto(form, 'front', photos.front);
    if (photos.back) await appendPhoto(form, 'back', photos.back);
    if (photos.spine) await appendPhoto(form, 'spine', photos.spine);
    return request<GradeScanResult>('/vision/grade', { method: 'POST', body: form });
  },

  /**
   * Save a scanned book with its grade report, then attach the front photo as
   * the cover. One row per scan: the cover goes to POST /comics/{id}/cover
   * instead of a second create.
   */
  saveScan: async (match: ScanMatch, frontUri?: string | null): Promise<Comic> => {
    const comic = await request<Comic>('/comics', json({ ...match.comic, report: match.report }));
    if (!frontUri) return comic;
    try {
      const form = new FormData();
      await appendPhoto(form, 'image', frontUri);
      return await request<Comic>(`/comics/${comic.id}/cover`, { method: 'POST', body: form });
    } catch (err) {
      console.warn('[ComicGrade] cover upload failed, keeping the book without it:', err);
      return comic;
    }
  },

  /** Value for a book that is not saved yet (the scan review re-prices on a correction). */
  estimateValue: (title: string, issueNumber: string, grade?: number | null): Promise<PriceEstimate> => {
    const q = new URLSearchParams({ title, issue_number: issueNumber });
    if (grade != null) q.set('grade', String(grade));
    return request<PriceEstimate>(`/pricing/estimate?${q}`);
  },

  // The backend reads the user from the auth token; the argument is kept for API parity.
  listComics: (_userId?: string | null) => request<Comic[]>('/comics'),

  getComic: (id: string) => request<Comic>(`/comics/${id}`),

  createComic: (comic: Partial<Comic>) => request<Comic>('/comics', json(comic)),

  deleteComic: (id: string) => request<void>(`/comics/${id}`, { method: 'DELETE' }),

  listPrices: (id: string) => request<PricePoint[]>(`/comics/${id}/prices`),

  refreshValue: (id: string) => request<PricePoint>(`/comics/${id}/refresh_value`, { method: 'POST' }),

  addPrice: (id: string, price: number, source = 'manual') =>
    request<PricePoint>(
      `/comics/${id}/prices?price=${price}&source=${encodeURIComponent(source)}`,
      { method: 'POST' },
    ),

  getGradeReport: async (id: string): Promise<GradeReport | null> => {
    try {
      return await request<GradeReport>(`/comics/${id}/grade_report`);
    } catch (err: any) {
      if (String(err?.message).startsWith('API 404')) return null;
      throw err;
    }
  },

  /** Every book's grade report in one request (optionally one grade type, e.g. 'raw'). */
  listGradeReports: (gradeType?: string) =>
    request<GradeReport[]>(`/comics/grade_reports${gradeType ? `?grade_type=${encodeURIComponent(gradeType)}` : ''}`),

  portfolioHistory: async (lens: ValueLens = 'all'): Promise<number[]> => {
    const body = await request<{ points: { value: number }[] }>(`/portfolio/history?lens=${lens}`);
    return body.points.map((p) => p.value);
  },

  listRunGaps: () => request<RunGap[]>('/runs/gaps'),

  peekScan: (): ScanMatch => {
    throw new Error('peekScan is demo-only: live scans use the camera');
  },
  commitScan: async (_match: ScanMatch): Promise<Comic> => {
    throw new Error('commitScan is demo-only: live scans use the camera');
  },
};

export const api = DEMO_MODE ? demoApi : liveApi;
