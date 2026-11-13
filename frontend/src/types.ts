/** Domain types mirrored from backend/app/schemas.py. */

export type GradeType = 'raw' | 'cgc' | 'cbcs' | 'pgx' | 'other';

export interface Comic {
  id: string;
  title: string;
  issue_number: string;
  publisher: string;
  cover_image_url?: string | null;
  estimated_grade?: number | null;
  /** 'raw' = our camera/AI estimate; others = professionally slabbed */
  grade_type?: GradeType;
  slab_cert_number?: string | null;
  current_market_value?: number | null;
  user_id?: string | null;
  created_at?: string | null;

  // Optional presentation fields (not yet returned by the backend).
  year?: number | null;
  /** Why the book matters, e.g. a first appearance. */
  key_note?: string | null;
  /** Percent change between the first and latest recorded price. */
  change_pct?: number | null;
  /** [background from, background to, accent] for the generated placeholder cover. */
  cover_palette?: [string, string, string] | null;
}

/** Result of POST /vision/analyze on the FastAPI backend. */
export interface VisionResult {
  title: string;
  issue_number: string;
  publisher: string;
  tentative_grade: number;
  signature_detected: boolean;
  notes: string;
}

export interface PricePoint {
  comic_id: string;
  sale_date: string;
  price: number;
  source: string;
}

export type ValueLens = 'all' | 'raw' | 'certified';

export interface DefectScore {
  area: string;
  /** 0-10, same scale as the grade. */
  score: number;
  note: string;
}

export type SubmitVerdict = 'submit' | 'hold' | 'skip';

/** Explainable grade: range + per-area breakdown + the slab-or-not maths. */
export interface GradeReport {
  comic_id: string;
  grade: number;
  grade_low: number;
  grade_high: number;
  /** 0-1 confidence that a third-party grade lands inside the range. */
  confidence: number;
  defects: DefectScore[];
  /** Photos cannot see restoration or interior pages. */
  exterior_only: boolean;
  /** Which pipeline produced it: 'claude:<model>', 'openai:<model>', 'mock' or 'estimate'. */
  source?: string;
  /** How many photos (front, back, spine) the grade was based on. */
  photos_used?: number;
  /** Present for raw books only. */
  slab?: {
    raw_value: number;
    slabbed_value: number;
    grading_fee: number;
    shipping: number;
    net_uplift: number;
    turnaround_days: number;
    verdict: SubmitVerdict;
  } | null;
}

export interface RunGap {
  id: string;
  name: string;
  publisher: string;
  owned: number;
  total: number;
  missing_key: string;
  missing_note: string;
  raw_price: number;
  slab_price: number;
}

/** A scan result ready to be added to the collection. */
export interface ScanMatch {
  comic: Omit<Comic, 'id'>;
  report: Omit<GradeReport, 'comic_id'>;
  match_confidence: number;
}

/** The photos taken during a live scan (local file or blob URIs). */
export interface ScanPhotos {
  front: string;
  back?: string | null;
  spine?: string | null;
}

/** Who the scanned book is, from POST /vision/grade. */
export interface ScanIdentification {
  title: string;
  issue_number: string;
  publisher: string;
  year?: number | null;
  key_note?: string | null;
  signature_detected: boolean;
  notes: string;
}

/** Response of POST /vision/grade: identification plus the full grade report. */
export interface GradeScanResult {
  identification: ScanIdentification;
  report: Omit<GradeReport, 'comic_id'>;
  match_confidence: number;
  estimated_value?: number | null;
  value_source?: string | null;
}
