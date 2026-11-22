import type { GradeScanResult, ScanIdentification, ScanMatch } from '../types';

/** True when a value came from the sample (mock) price source, not real sales. */
export const isSamplePrice = (source?: string | null) => !source || /^(mock|sample|demo)/.test(source);

/** Every identification the scan offers: the best answer first, then alternatives. */
export function scanChoices(result: GradeScanResult): ScanIdentification[] {
  return [result.identification, ...(result.alternatives ?? [])];
}

/** Turn a POST /vision/grade response into a book ready to add to the Vault. */
export function toScanMatch(
  result: GradeScanResult,
  chosen: ScanIdentification = result.identification,
  value: number | null = result.estimated_value ?? null,
): ScanMatch {
  return {
    comic: {
      title: chosen.title,
      issue_number: chosen.issue_number,
      publisher: chosen.publisher,
      year: chosen.year ?? null,
      format: chosen.format ?? 'single_issue',
      key_note: chosen.key_note ?? null,
      estimated_grade: result.report.grade,
      grade_type: 'raw',
      current_market_value: value,
    },
    report: result.report,
    match_confidence: chosen === result.identification ? result.match_confidence : 1,
  };
}
