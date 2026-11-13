/**
 * In-memory demo backend. Mirrors the shape of the FastAPI client in api.ts so the
 * whole app runs with no Supabase project, no server and no camera.
 * All titles are real books; grades and dollar values are ILLUSTRATIVE, not market data.
 */
import type {
  Comic,
  GradeReport,
  PricePoint,
  RunGap,
  ScanMatch,
  ValueLens,
  VisionResult,
} from '../types';
import { buildReport, seeded } from './grading';

const MONTHS = 10;
const wait = <T,>(value: T, ms = 220) => new Promise<T>((r) => setTimeout(() => r(value), ms));

type Seed = [
  title: string,
  issue: string,
  publisher: string,
  year: number,
  grade: number,
  type: Comic['grade_type'],
  value: number,
  trend: number,
  keyNote: string | null,
  palette: [string, string, string],
];

const SEEDS: Seed[] = [
  ['Amazing Spider-Man', '300', 'Marvel', 1988, 9.2, 'raw', 610, 0.14, '1st full appearance of Venom', ['#b3122a', '#1a1030', '#ffd21f']],
  ['Amazing Spider-Man', '129', 'Marvel', 1974, 7.5, 'cgc', 2150, 0.09, '1st appearance of the Punisher', ['#f2b705', '#c2410c', '#12121f']],
  ['New Mutants', '98', 'Marvel', 1991, 9.8, 'cgc', 1050, -0.06, '1st appearance of Deadpool', ['#e11d48', '#7c2d12', '#35e0d2']],
  ['Uncanny X-Men', '266', 'Marvel', 1990, 9.4, 'raw', 240, 0.21, '1st full appearance of Gambit', ['#6d28d9', '#1e1b4b', '#ff2fb9']],
  ['X-Men', '1', 'Marvel', 1991, 9.6, 'raw', 28, 0.02, null, ['#2f6bff', '#0b1a4a', '#ffd21f']],
  ['Batman Adventures', '12', 'DC', 1993, 9.0, 'raw', 780, 0.18, '1st appearance of Harley Quinn', ['#111827', '#7f1d1d', '#ff3b3b']],
  ['Batman', '423', 'DC', 1988, 8.5, 'raw', 95, 0.05, 'Classic Todd McFarlane cover', ['#0f172a', '#1d4ed8', '#35e0d2']],
  ['Swamp Thing', '37', 'DC', 1985, 8.0, 'raw', 310, 0.11, '1st appearance of John Constantine', ['#14532d', '#052e16', '#a3e635']],
  ['The Walking Dead', '1', 'Image', 2003, 9.2, 'raw', 1650, -0.04, 'Series debut · low print run', ['#27272a', '#0a0a12', '#ff3b3b']],
  ['Invincible', '1', 'Image', 2003, 9.8, 'cgc', 1400, 0.32, 'Series debut', ['#fbbf24', '#1d4ed8', '#12121f']],
  ['Saga', '1', 'Image', 2012, 9.6, 'raw', 180, 0.07, '1st printing', ['#be185d', '#4c1d95', '#fde68a']],
  ['Spawn', '1', 'Image', 1992, 9.4, 'raw', 32, 0.03, null, ['#166534', '#450a0a', '#ff3b3b']],
  ['Something Is Killing the Children', '1', 'Boom! Studios', 2019, 9.8, 'cgc', 420, 0.12, 'Series debut', ['#0c4a6e', '#020617', '#f59e0b']],
  ['Mighty Morphin Power Rangers', '1', 'Boom! Studios', 2016, 9.6, 'raw', 18, 0.0, null, ['#dc2626', '#1e3a8a', '#fde047']],
];

const SCAN_QUEUE: Seed[] = [
  ['Ultimate Fallout', '4', 'Marvel', 2011, 9.4, 'raw', 390, 0.16, '1st appearance of Miles Morales', ['#18181b', '#991b1b', '#f5f5fa']],
  ['Edge of Spider-Verse', '2', 'Marvel', 2014, 9.6, 'raw', 520, 0.1, '1st appearance of Spider-Gwen', ['#f5f5fa', '#be185d', '#12121f']],
  ['Y: The Last Man', '1', 'Vertigo', 2002, 9.0, 'raw', 85, 0.04, 'Series debut', ['#1f2937', '#064e3b', '#fbbf24']],
];

function isoMonthsAgo(monthsAgo: number, day: number): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - monthsAgo);
  d.setDate(day);
  // Never date a sample sale in the future.
  const today = new Date();
  return (d > today ? today : d).toISOString().slice(0, 10);
}

function fromSeed(seed: Seed, id: string): Comic {
  const [title, issue_number, publisher, year, grade, grade_type, value, trend, key_note, palette] = seed;
  return {
    id,
    title,
    issue_number,
    publisher,
    year,
    estimated_grade: grade,
    grade_type,
    slab_cert_number: grade_type === 'raw' ? null : `40${(seeded(id)() * 1e8).toFixed(0).padStart(8, '0')}`,
    current_market_value: value,
    change_pct: Math.round(trend * 1000) / 10,
    key_note,
    cover_palette: palette,
    created_at: isoMonthsAgo(MONTHS, 4),
  };
}

function historyFor(comic: Comic, trend: number): PricePoint[] {
  const rng = seeded(comic.id + 'px');
  const value = comic.current_market_value ?? 0;
  const source = (comic.grade_type ?? 'raw') === 'raw' ? 'raw-comps' : 'gocollect';
  const start = value / (1 + trend);
  return Array.from({ length: MONTHS }, (_, k) => {
    const last = k === MONTHS - 1;
    const base = start * (1 + (trend * k) / (MONTHS - 1));
    const price = last ? value : base * (1 + (rng() - 0.5) * 0.07);
    return {
      comic_id: comic.id,
      sale_date: isoMonthsAgo(MONTHS - 1 - k, 3 + Math.floor(rng() * 22)),
      price: Math.round(price * 100) / 100,
      source,
    };
  });
}

const comics: Comic[] = [];
const prices: Record<string, PricePoint[]> = {};
SEEDS.forEach((seed, i) => {
  const comic = fromSeed(seed, `demo-${i + 1}`);
  comics.push(comic);
  const history = historyFor(comic, seed[7]);
  prices[comic.id] = history;
  // Match the change shown on the detail screen: first recorded sale to today.
  comic.change_pct = Math.round((history[history.length - 1].price / history[0].price - 1) * 1000) / 10;
});

let scanCursor = 0;
let nextId = SEEDS.length + 1;

function inLens(comic: Comic, lens: ValueLens): boolean {
  const raw = (comic.grade_type ?? 'raw') === 'raw';
  return lens === 'all' || (lens === 'raw' ? raw : !raw);
}

function find(id: string): Comic {
  const comic = comics.find((c) => c.id === id);
  if (!comic) throw new Error('Comic not found');
  return comic;
}

function recordPrice(id: string, price: number, source: string): PricePoint {
  const comic = find(id);
  const point: PricePoint = {
    comic_id: id,
    sale_date: new Date().toISOString().slice(0, 10),
    price: Math.round(price * 100) / 100,
    source,
  };
  const list = (prices[id] ||= []);
  list.push(point);
  comic.current_market_value = point.price;
  comic.change_pct = Math.round((point.price / list[0].price - 1) * 1000) / 10;
  return point;
}

const RUNS: RunGap[] = [
  {
    id: 'run-asm',
    name: 'Amazing Spider-Man · McFarlane era',
    publisher: 'Marvel',
    owned: 21,
    total: 28,
    missing_key: '#298',
    missing_note: "McFarlane's first issue on the title",
    raw_price: 140,
    slab_price: 640,
  },
  {
    id: 'run-invincible',
    name: 'Invincible #1 to #12',
    publisher: 'Image',
    owned: 9,
    total: 12,
    missing_key: '#2',
    missing_note: 'Second issue, low print run',
    raw_price: 210,
    slab_price: 575,
  },
  {
    id: 'run-saga',
    name: 'Saga #1 to #54',
    publisher: 'Image',
    owned: 31,
    total: 54,
    missing_key: '#19',
    missing_note: 'Start of the third arc',
    raw_price: 12,
    slab_price: 70,
  },
];

export const demoApi = {
  health: () => wait(true),

  analyzeCover: (_imageUri: string): Promise<VisionResult> => {
    const [title, issue_number, publisher, , grade] = SCAN_QUEUE[scanCursor % SCAN_QUEUE.length];
    return wait(
      { title, issue_number, publisher, tentative_grade: grade, signature_detected: false, notes: 'Demo scan' },
      900,
    );
  },

  listComics: (_userId?: string | null) => wait(comics.map((c) => ({ ...c }))),

  getComic: (id: string) => wait({ ...find(id) }),

  createComic: (comic: Partial<Comic>) => {
    const created: Comic = {
      title: 'Untitled',
      issue_number: '1',
      publisher: 'Unknown',
      grade_type: 'raw',
      ...comic,
      id: comic.id ?? `demo-${nextId++}`,
      created_at: new Date().toISOString(),
    };
    const at = comics.findIndex((c) => c.id === created.id);
    if (at >= 0) comics[at] = created;
    else comics.unshift(created);
    if (created.current_market_value != null && !prices[created.id]) {
      prices[created.id] = [];
      recordPrice(created.id, created.current_market_value, 'raw-comps');
    }
    return wait({ ...created });
  },

  deleteComic: (id: string): Promise<void> => {
    const at = comics.findIndex((c) => c.id === id);
    if (at >= 0) comics.splice(at, 1);
    delete prices[id];
    return wait<void>(undefined);
  },

  listPrices: (id: string) => wait([...(prices[id] ?? [])]),

  refreshValue: (id: string) => {
    const comic = find(id);
    const drift = 1 + (seeded(id + (prices[id]?.length ?? 0))() - 0.4) * 0.05;
    const source = (comic.grade_type ?? 'raw') === 'raw' ? 'raw-comps' : 'gocollect';
    return wait(recordPrice(id, (comic.current_market_value ?? 0) * drift, source), 700);
  },

  addPrice: (id: string, price: number, source = 'manual') => wait(recordPrice(id, price, source)),

  /** Explainable grade + slab economics. */
  getGradeReport: (id: string): Promise<GradeReport | null> => wait(buildReport(find(id))),

  /** Monthly collection value for the dashboard chart. */
  portfolioHistory: (lens: ValueLens = 'all'): Promise<number[]> => {
    const series = Array.from({ length: MONTHS }, () => 0);
    comics
      .filter((c) => inLens(c, lens))
      .forEach((c) => {
        const list = prices[c.id] ?? [];
        // Books scanned recently have short histories: carry their first price back.
        const padded = [...Array(Math.max(0, MONTHS - list.length)).fill(list[0]?.price ?? 0), ...list.map((p) => p.price)];
        padded.slice(-MONTHS).forEach((price, k) => {
          series[k] += k === MONTHS - 1 ? c.current_market_value ?? price : price;
        });
      });
    return wait(series.map((n) => Math.round(n)));
  },

  listRunGaps: (): Promise<RunGap[]> => wait(RUNS),

  /** What the next scan will "see". Demo stand-in for the camera + vision pipeline. */
  peekScan: (): ScanMatch => {
    const seed = SCAN_QUEUE[scanCursor % SCAN_QUEUE.length];
    const { id, ...comic } = fromSeed(seed, `scan-${scanCursor}`);
    const { comic_id, ...report } = buildReport({ id, ...comic });
    return { comic, report, match_confidence: 0.97 - (scanCursor % 3) * 0.02 };
  },

  /** Add the scanned book to the collection and move on to the next sample. */
  commitScan: async (match: ScanMatch): Promise<Comic> => {
    scanCursor += 1;
    return demoApi.createComic(match.comic);
  },
};
