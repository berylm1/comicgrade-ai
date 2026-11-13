import type { GradeScanResult, ScanMatch } from '../types';

/** Turn a POST /vision/grade response into a book ready to add to the Vault. */
export function toScanMatch(result: GradeScanResult): ScanMatch {
  const { identification: id, report } = result;
  return {
    comic: {
      title: id.title,
      issue_number: id.issue_number,
      publisher: id.publisher,
      year: id.year ?? null,
      key_note: id.key_note ?? null,
      estimated_grade: report.grade,
      grade_type: 'raw',
      current_market_value: result.estimated_value ?? null,
    },
    report,
    match_confidence: result.match_confidence,
  };
}
