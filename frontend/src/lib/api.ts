/** Thin typed client for the ComicGrade AI FastAPI backend. */
import { API_BASE_URL } from './env';
import type { Comic, PricePoint, VisionResult } from '../types';

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

export const api = {
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

  addPrice: (id: string, price: number, source = 'manual') =>
    fetch(`${BASE}/comics/${id}/prices?price=${price}&source=${source}`, {
      method: 'POST',
    }).then(handle<PricePoint>),
};