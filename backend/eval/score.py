"""Scoring for the vision identification test.

Input is a results file (see bench.py for the format) from any approach:
Claude, OpenAI, or an external pipeline such as CLIP retrieval or on-device
OCR. Output is a markdown report with the per-photo table, top-1/top-3,
per-field accuracy, the trap checks, and cost/latency.

Rules (from the test brief):
* A candidate is right when series, issue number and format all match, plus
  the variant flag on photos where the cover names a variant.
* Variant is only scored where the cover names it; never on art alone.
* Any printing claim is a failure: printings cannot be settled from a front
  cover, so a candidate that names one is wrong.
* Years are informational only.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Optional

GROUND_TRUTH = Path(__file__).with_name("ground_truth.json")
FORMATS = {"single_issue", "annual", "collected_edition", "other"}


def load_truth(path: Path = GROUND_TRUTH) -> dict:
    return json.loads(Path(path).read_text())


def norm_series(name: str) -> tuple[str, Optional[str]]:
    """Normalized series name, plus a format implied by the name if any."""
    text = (name or "").lower().replace("&", " and ")
    implied = None
    if re.search(r"\bannual\b", text):
        implied = "annual"
    if re.search(r"\b(deluxe|edition|omnibus|hardcover|tpb|trade paperback)\b", text):
        implied = "collected_edition"
    text = re.sub(r"\(.*?\)", " ", text)  # "(2024)", "(vol. 2)"
    text = text.split("#", 1)[0]  # "Detective Comics #1000: The Deluxe Edition"
    text = re.sub(r"\b(vol|volume)\.?\s*\d+\b", " ", text)
    text = re.sub(r"\b(annual|the deluxe edition|deluxe edition)\b", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)  # spider-man -> spiderman, drop ':' etc.
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^the ", "", text)
    return text, implied


def norm_issue(value) -> str:
    text = str(value if value is not None else "").strip().lstrip("#").strip()
    return text.lstrip("0") or ("0" if text else "")


def check_candidate(cand: dict, truth: dict) -> dict:
    series, implied = norm_series(cand.get("series", ""))
    fmt = cand.get("format") if cand.get("format") in FORMATS else None
    fmt = implied if implied and fmt in (None, "single_issue") else (fmt or "single_issue")
    series_ok = series in {norm_series(s)[0] for s in truth["series"]}
    issue_ok = norm_issue(cand.get("issue_number")) == norm_issue(truth["issue"])
    format_ok = fmt == truth.get("format", "single_issue")
    variant_ok = None
    if "variant_named_on_cover" in truth:
        variant_ok = bool(cand.get("variant_named_on_cover")) == bool(truth["variant_named_on_cover"])
    printing = cand.get("printing")
    printing_claim = bool(printing and str(printing).strip().lower() not in {"none", "null", "unknown", "n/a"})
    ok = series_ok and issue_ok and format_ok and variant_ok is not False and not printing_claim
    return {
        "series_ok": series_ok, "issue_ok": issue_ok, "format_ok": format_ok,
        "variant_ok": variant_ok, "printing_claim": printing_claim, "format": fmt, "ok": ok,
    }


def label(cand: Optional[dict]) -> str:
    if not cand:
        return "(none)"
    text = f"{cand.get('series', '?')} #{norm_issue(cand.get('issue_number')) or '?'}"
    extras = []
    if cand.get("format") not in (None, "single_issue"):
        extras.append(cand["format"].replace("_", " "))
    if cand.get("variant_named_on_cover"):
        extras.append("variant")
    if cand.get("printing"):
        extras.append(f"printing: {cand['printing']}")
    if cand.get("cover_year"):
        extras.append(str(cand["cover_year"]))
    return text + (f" ({', '.join(extras)})" if extras else "")


def score(results: dict, truth: Optional[dict] = None) -> dict:
    truth = truth or load_truth()
    by_id = {p["id"]: p for p in results.get("photos", [])}
    rows = []
    for t in truth["photos"]:
        r = by_id.get(t["id"])
        if r is None or r.get("status") == "missing":
            rows.append({"id": t["id"], "truth": t, "status": "missing"})
            continue
        cands = (r.get("candidates") or [])[:3]
        checks = [check_candidate(c, t) for c in cands]
        top1 = checks[0] if checks else None
        rows.append({
            "id": t["id"], "truth": t, "status": "error" if r.get("error") else "ok",
            "error": r.get("error"), "candidates": cands, "checks": checks,
            "top1_ok": bool(top1 and top1["ok"]), "top3_ok": any(c["ok"] for c in checks),
            "latency_s": r.get("latency_s"), "cost_usd": r.get("cost_usd"),
            "served_model": r.get("served_model"),
        })

    scored = [r for r in rows if r["status"] != "missing"]
    n = len(scored)

    def rate(values):
        values = [v for v in values if v is not None]
        return (sum(values) / len(values), len(values)) if values else (None, 0)

    first = lambda r: r["checks"][0] if r.get("checks") else {}  # noqa: E731
    by = {r["id"]: r for r in rows}

    def top1(pid, field="ok"):
        r = by.get(pid)
        if not r or r["status"] == "missing":
            return None
        return bool(first(r).get(field))

    traps = {}
    t = truth.get("traps", {})
    if "same_issue_two_arts" in t:
        a, b = t["same_issue_two_arts"]
        vals = [top1(a, "series_ok") and top1(a, "issue_ok"), top1(b, "series_ok") and top1(b, "issue_ok")]
        traps["same_issue_two_arts"] = None if None in vals else all(vals)
    if "new_vs_old_avengers" in t:
        vals = [top1(pid, "series_ok") for pid in t["new_vs_old_avengers"]]
        traps["new_vs_old_avengers"] = None if None in vals else all(vals)
    for name in ("deluxe_not_single", "annual_not_monthly"):
        if name in t:
            traps[name] = top1(t[name][0], "format_ok")
    offenders = [r["id"] for r in scored if any(c["printing_claim"] for c in r.get("checks", []))]
    traps["no_printing_claims"] = (not offenders) if n else None

    costs = [r["cost_usd"] for r in scored if r.get("cost_usd") is not None]
    lats = [r["latency_s"] for r in scored if r.get("latency_s") is not None]
    targets = truth.get("targets", {})
    top1_rate = sum(r["top1_ok"] for r in scored) / n if n else None
    top3_rate = sum(r["top3_ok"] for r in scored) / n if n else None
    return {
        "rows": rows,
        "n_scored": n,
        "missing": [r["id"] for r in rows if r["status"] == "missing"],
        "errors": [r["id"] for r in scored if r["status"] == "error"],
        "top1": top1_rate,
        "top3": top3_rate,
        "top1_meets_target": top1_rate is not None and top1_rate >= targets.get("top1", 0.8),
        "top3_meets_target": top3_rate is not None and top3_rate >= targets.get("top3", 0.95),
        "fields": {
            # A photo with no answer (error, refusal) counts as wrong on every field.
            "series": rate([bool(first(r).get("series_ok")) for r in scored]),
            "issue": rate([bool(first(r).get("issue_ok")) for r in scored]),
            # Variant is only scored where the ground truth names one.
            "variant": rate([
                bool(first(r).get("variant_ok")) for r in scored if "variant_named_on_cover" in r["truth"]
            ]),
        },
        "traps": traps,
        "printing_offenders": offenders,
        "cost": {
            "mean": statistics.mean(costs) if costs else None,
            "max": max(costs) if costs else None,
            "total": sum(costs) if costs else None,
            "over_flag": bool(costs) and statistics.mean(costs) > targets.get("max_cost_per_scan_usd", 0.10),
        },
        "latency": {
            "median": statistics.median(lats) if lats else None,
            "max": max(lats) if lats else None,
        },
    }


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _yn(value) -> str:
    return "n/a" if value is None else ("pass" if value else "FAIL")


def render(results: dict, s: dict) -> str:
    meta = results.get("meta", {})
    lines = [
        f"# Vision test: {meta.get('approach', 'unknown approach')}",
        "",
        f"- Model: {meta.get('model', 'n/a')} · effort: {meta.get('effort', 'n/a')} · runs: {meta.get('runs_on', 'n/a')}",
        f"- Run at: {meta.get('run_at', 'n/a')}",
        f"- Photos scored: {s['n_scored']} of {s['n_scored'] + len(s['missing'])}"
        + (f" (missing: {', '.join(s['missing'])})" if s["missing"] else "")
        + (f" (errors counted as wrong: {', '.join(s['errors'])})" if s["errors"] else ""),
        "",
        "## Summary",
        "",
        f"| Measure | Result | Target |",
        f"|---|---|---|",
        f"| Top-1 | {_pct(s['top1'])} | >= 80% ({'met' if s['top1_meets_target'] else 'not met'}) |",
        f"| Top-3 | {_pct(s['top3'])} | >= 95% ({'met' if s['top3_meets_target'] else 'not met'}) |",
        f"| Series right (top-1) | {_pct(s['fields']['series'][0])} | |",
        f"| Issue number right (top-1) | {_pct(s['fields']['issue'][0])} | |",
        f"| Variant right (top-1, scored on {s['fields']['variant'][1]} photo(s)) | {_pct(s['fields']['variant'][0])} | |",
        f"| Cost per scan, mean / max | {_money(s['cost']['mean'])} / {_money(s['cost']['max'])} | <= $0.10{' (OVER)' if s['cost']['over_flag'] else ''} |",
        f"| Latency per scan, median / max | {_secs(s['latency']['median'])} / {_secs(s['latency']['max'])} | |",
        "",
        "## Traps",
        "",
        f"- 01 vs 03, same issue, different art (both read as Action Comics #1000): {_yn(s['traps'].get('same_issue_two_arts'))}",
        f"- 11 vs 04, New Avengers vs Avengers: {_yn(s['traps'].get('new_vs_old_avengers'))}",
        f"- 06, Deluxe Edition reported as a collected edition: {_yn(s['traps'].get('deluxe_not_single'))}",
        f"- 08, reported as an Annual: {_yn(s['traps'].get('annual_not_monthly'))}",
        f"- No printing claims: {_yn(s['traps'].get('no_printing_claims'))}"
        + (f" (claimed on {', '.join(s['printing_offenders'])})" if s["printing_offenders"] else ""),
        "",
        "## Per photo",
        "",
        "| # | Expected | Top-1 | Top-3 | Top-1 right | Top-3 right | Latency | Cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in s["rows"]:
        t = r["truth"]
        expected = label({"series": t["series"][0], "issue_number": t["issue"], "format": t.get("format"),
                          "variant_named_on_cover": t.get("variant_named_on_cover"), "cover_year": t.get("year")})
        if r["status"] == "missing":
            lines.append(f"| {r['id']} | {expected} | photo missing | | | | | |")
            continue
        if r["status"] == "error" and not r["candidates"]:
            lines.append(f"| {r['id']} | {expected} | error: {r['error']} | | no | no | {_secs(r['latency_s'])} | |")
            continue
        others = "; ".join(label(c) for c in r["candidates"][1:]) or "(none)"
        lines.append(
            f"| {r['id']} | {expected} | {label(r['candidates'][0] if r['candidates'] else None)} | {others} | "
            f"{'yes' if r['top1_ok'] else 'no'} | {'yes' if r['top3_ok'] else 'no'} | "
            f"{_secs(r['latency_s'])} | {_money(r['cost_usd'])} |"
        )
    notes = [f"- {p['id']}: {p['year_disputed']}" for p in load_truth()["photos"] if p.get("year_disputed")]
    if notes:
        lines += ["", "## Ground-truth notes", "", *notes]
    return "\n".join(lines) + "\n"


def _money(v) -> str:
    return "n/a" if v is None else f"${v:.4f}"


def _secs(v) -> str:
    return "n/a" if v is None else f"{v:.1f}s"
