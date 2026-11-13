/** Thin typed client for the ComicGrade AI FastAPI backend. */
import { API_BASE_URL, DEMO_MODE } from './env';
import { demoApi } from './demo';
import type {
  Comic,
  GradeReport,
  PricePoint,
  RunGap,
  ScanMatch,
  ValueLens,
  VisionResult,
} from '../types';

const BASE = API_BASE_URL.replace(/\/$/, '');

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const liveApi: typeof demoApi = {
  health: () => fetch(`${BASE}/health`).then(() => true).catch(() => false),

  analyzeCover: async (imageUri: string): Promise<VisionResult> => {
    const form = new FormData();
    // React Native FormData accepts the { uri, name, type } file shape.
    form.append('image', {
      uri: imageUri,
      name: 'cover.jpg',
      type: 'image/jpeg',
    } as any);
    const res = await fetch(`${BASE}/vision/analyze`, {
      method: 'POST',
      body: form,
    });
    return handle<VisionResult>(res);
  },

  listComics: (userId?: string | null) =>
    fetch(`${BASE}/comics${userId ? `?user_id=${userId}` : ''}`).then(handle<Comic[]>),

  getComic: (id: string) => fetch(`${BASE}/comics/${id}`).then(handle<Comic>),

  createComic: (comic: Partial<Comic>) =>
    fetch(`${BASE}/comics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(comic),
    }).then(handle<Comic>),

  deleteComic: (id: string) =>
    fetch(`${BASE}/comics/${id}`, { method: 'DELETE' }).then((r) => handle<void>(r)),

  listPrices: (id: string) =>
    fetch(`${BASE}/comics/${id}/prices`).then(handle<PricePoint[]>),

  refreshValue: (id: string) =>
    fetch(`${BASE}/comics/${id}/refresh_value`, { method: 'POST' }).then(handle<PricePoint>),

  addPrice: (id: string, price: number, source = 'manual') =>
    fetch(`${BASE}/comics/${id}/prices?price=${price}&source=${source}`, {
      method: 'POST',
    }).then(handle<PricePoint>),

  // Not served by the backend yet: the screens hide these sections when empty.
  getGradeReport: async (_id: string): Promise<GradeReport | null> => null,
  portfolioHistory: async (_lens: ValueLens = 'all'): Promise<number[]> => [],
  listRunGaps: async (): Promise<RunGap[]> => [],
  peekScan: (): ScanMatch => {
    throw new Error('peekScan is demo-only: live scans use the camera');
  },
  commitScan: async (_match: ScanMatch): Promise<Comic> => {
    throw new Error('commitScan is demo-only: live scans use the camera');
  },
};

export const api = DEMO_MODE ? demoApi : liveApi;
