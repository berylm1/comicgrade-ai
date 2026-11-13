/**
 * Demo-only grade report builder. Produces a deterministic, explainable report
 * (range, per-area scores, slab economics) from a comic's grade and value so the
 * UI can be shown before the real vision pipeline returns this shape.
 */
import type { Comic, DefectScore, GradeReport, SubmitVerdict } from '../types';

export function seeded(key: string): () => number {
  let h = 1779033703 ^ key.length;
  for (let i = 0; i < key.length; i++) {
    h = Math.imul(h ^ key.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const AREAS: { area: string; notes: [string, string, string] }[] = [
  { area: 'Corners', notes: ['Sharp on all four', 'Light blunting, lower right', 'Rounded with small creases'] },
  { area: 'Spine', notes: ['Flat, no stress lines', '2 small non-color-breaking ticks', 'Multiple color-breaking stress lines'] },
  { area: 'Edges', notes: ['Clean cut, no chipping', 'Minor wear along the top edge', 'Chipping and small tears'] },
  { area: 'Surface', notes: ['High gloss, no scuffs', 'Faint finger bend, back cover', 'Scuffing and visible creases'] },
  { area: 'Color', notes: ['Deep blacks, no fading', 'Slight toning at the edges', 'Noticeable fading and tanning'] },
  { area: 'Centering', notes: ['Well centered', 'Shifted slightly left', 'Miswrapped, art off-panel'] },
];

const round1 = (n: number) => Math.round(n * 10) / 10;
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

/** CGC-style tiers get tighter near the top of the scale. */
function halfRange(grade: number): number {
  if (grade >= 9.6) return 0.2;
  if (grade >= 8.5) return 0.3;
  return 0.5;
}

function gradingFee(slabbedValue: number): number {
  if (slabbedValue < 400) return 30;
  if (slabbedValue < 1000) return 75;
  return 150;
}

export function buildReport(comic: Comic): GradeReport {
  const grade = comic.estimated_grade ?? 8.0;
  const rng = seeded(`${comic.title}#${comic.issue_number}`);
  const spread = halfRange(grade);

  const defects: DefectScore[] = AREAS.map(({ area, notes }) => {
    const score = round1(clamp(grade + (rng() - 0.55) * 1.4, 0.5, 10));
    const note = score >= 9.4 ? notes[0] : score >= 7.5 ? notes[1] : notes[2];
    return { area, score, note };
  });

  const isRaw = (comic.grade_type ?? 'raw') === 'raw';
  const raw = comic.current_market_value ?? 0;
  let slab: GradeReport['slab'] = null;
  if (isRaw && raw > 0) {
    // Slab premium grows with grade: buyers pay most for certified high grades.
    const premium = grade >= 9.6 ? 2.3 : grade >= 9.0 ? 1.75 : grade >= 8.0 ? 1.45 : 1.25;
    const slabbed = Math.round(raw * premium);
    const fee = gradingFee(slabbed);
    const shipping = 22;
    const net = slabbed - raw - fee - shipping;
    const verdict: SubmitVerdict =
      net >= 75 && net / raw >= 0.15 ? 'submit' : net > 0 ? 'hold' : 'skip';
    slab = {
      raw_value: raw,
      slabbed_value: slabbed,
      grading_fee: fee,
      shipping,
      net_uplift: net,
      turnaround_days: fee >= 150 ? 20 : fee >= 75 ? 35 : 55,
      verdict,
    };
  }

  return {
    comic_id: comic.id,
    grade,
    grade_low: round1(clamp(grade - spread, 0.5, 10)),
    grade_high: round1(clamp(grade + spread * 0.67, 0.5, 10)),
    confidence: grade >= 9.6 ? 0.88 : grade >= 8.5 ? 0.82 : 0.74,
    defects,
    exterior_only: true,
    slab,
  };
}
