/** Domain types mirrored from backend/app/schemas.py. */

export interface Comic {
  id: string;
  title: string;
  issue_number: string;
  publisher: string;
  cover_image_url?: string | null;
  estimated_grade?: number | null;
  /** 'raw' = our camera/AI estimate; others = professionally slabbed */
  grade_type?: 'raw' | 'cgc' | 'cbcs' | 'pgx' | 'other';
  slab_cert_number?: string | null;
  current_market_value?: number | null;
  user_id?: string | null;
  created_at?: string | null;
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