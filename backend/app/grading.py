"""Grade reports and slab economics.

Python port of frontend/src/lib/grading.ts so the server returns the same
numbers the demo shows. Two pieces:

* `slab_economics` turns a raw book's grade and value into the slab-or-not
  maths. It always runs server side, whatever produced the grade.
* `estimate_report` builds a deterministic, explainable report from a stored
  grade when no scan report exists yet (books added by hand, seeded books).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .schemas import DefectScore, GradeReportBody, SlabEconomics

MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """JavaScript Math.imul: 32-bit signed multiply."""
    r = ((a & MASK32) * (b & MASK32)) & MASK32
    return r - 0x100000000 if r & 0x80000000 else r


def _to_int32(n: int) -> int:
    n &= MASK32
    return n - 0x100000000 if n & 0x80000000 else n


def _urshift(n: int, s: int) -> int:
    return (n & MASK32) >> s


def seeded(key: str) -> Callable[[], float]:
    """Same seeded PRNG as grading.ts (string hash into mulberry32).

    Uses UTF-16 code units like JavaScript's charCodeAt so keys with
    non-ASCII characters produce identical sequences on both sides.
    """
    units = key.encode("utf-16-le")
    codes = [units[i] | (units[i + 1] << 8) for i in range(0, len(units), 2)]
    h = _to_int32(1779033703 ^ len(codes))
    for c in codes:
        h = _imul(h ^ c, 3432918353)
        h = _to_int32((h << 13) | _urshift(h, 19))
    state = [h & MASK32]

    def next_float() -> float:
        state[0] = _to_int32(state[0] + 0x6D2B79F5)
        a = state[0]
        t = _imul(a ^ _urshift(a, 15), 1 | a)
        t = _to_int32(t + _imul(t ^ _urshift(t, 7), 61 | t)) ^ t
        return _urshift(t ^ _urshift(t, 14), 0) / 4294967296

    return next_float


AREAS: list[tuple[str, tuple[str, str, str]]] = [
    ("Corners", ("Sharp on all four", "Light blunting, lower right", "Rounded with small creases")),
    ("Spine", ("Flat, no stress lines", "2 small non-color-breaking ticks", "Multiple color-breaking stress lines")),
    ("Edges", ("Clean cut, no chipping", "Minor wear along the top edge", "Chipping and small tears")),
    ("Surface", ("High gloss, no scuffs", "Faint finger bend, back cover", "Scuffing and visible creases")),
    ("Color", ("Deep blacks, no fading", "Slight toning at the edges", "Noticeable fading and tanning")),
    ("Centering", ("Well centered", "Shifted slightly left", "Miswrapped, art off-panel")),
]
AREA_NAMES = [name for name, _ in AREAS]

# Flat return shipping + insurance estimate used by the demo.
SHIPPING = 22.0


def round1(n: float) -> float:
    # JS Math.round rounds .5 up; Python round() is banker's rounding.
    return math.floor(n * 10 + 0.5) / 10


def clamp(n: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, n))


def half_range(grade: float) -> float:
    """CGC-style tiers get tighter near the top of the scale."""
    if grade >= 9.6:
        return 0.2
    if grade >= 8.5:
        return 0.3
    return 0.5


def grading_fee(slabbed_value: float) -> float:
    if slabbed_value < 400:
        return 30.0
    if slabbed_value < 1000:
        return 75.0
    return 150.0


def slab_premium(grade: float) -> float:
    """Slab premium grows with grade: buyers pay most for certified high grades."""
    if grade >= 9.6:
        return 2.3
    if grade >= 9.0:
        return 1.75
    if grade >= 8.0:
        return 1.45
    return 1.25


def confidence_for(grade: float) -> float:
    if grade >= 9.6:
        return 0.88
    if grade >= 8.5:
        return 0.82
    return 0.74


def slab_economics(
    grade: float, grade_type: Optional[str], raw_value: Optional[float]
) -> Optional[SlabEconomics]:
    """Slab-or-not maths for a raw book. None for slabbed or unvalued books."""
    if (grade_type or "raw") != "raw" or not raw_value or raw_value <= 0:
        return None
    raw = float(raw_value)
    slabbed = float(math.floor(raw * slab_premium(grade) + 0.5))  # JS Math.round
    fee = grading_fee(slabbed)
    net = slabbed - raw - fee - SHIPPING
    if net >= 75 and net / raw >= 0.15:
        verdict = "submit"
    elif net > 0:
        verdict = "hold"
    else:
        verdict = "skip"
    return SlabEconomics(
        raw_value=raw,
        slabbed_value=slabbed,
        grading_fee=fee,
        shipping=SHIPPING,
        net_uplift=round(net, 2),
        turnaround_days=20 if fee >= 150 else 35 if fee >= 75 else 55,
        verdict=verdict,
    )


def estimate_report(comic: dict) -> GradeReportBody:
    """Deterministic report from a stored grade, matching grading.ts buildReport."""
    grade = comic.get("estimated_grade")
    grade = float(grade) if grade is not None else 8.0
    rng = seeded(f"{comic.get('title', '')}#{comic.get('issue_number', '')}")
    spread = half_range(grade)

    defects: list[DefectScore] = []
    for area, notes in AREAS:
        score = round1(clamp(grade + (rng() - 0.55) * 1.4, 0.5, 10))
        note = notes[0] if score >= 9.4 else notes[1] if score >= 7.5 else notes[2]
        defects.append(DefectScore(area=area, score=score, note=note))

    return GradeReportBody(
        grade=grade,
        grade_low=round1(clamp(grade - spread, 0.5, 10)),
        grade_high=round1(clamp(grade + spread * 0.67, 0.5, 10)),
        confidence=confidence_for(grade),
        defects=defects,
        exterior_only=True,
        source="estimate",
        photos_used=0,
        slab=slab_economics(grade, comic.get("grade_type"), comic.get("current_market_value")),
    )


def normalize_report(
    grade: float,
    grade_low: float,
    grade_high: float,
    confidence: float,
    defects: list[DefectScore],
) -> tuple[float, float, float, float, list[DefectScore]]:
    """Clamp model output to the 0.5 to 10 scale and keep low <= grade <= high."""
    g = round1(clamp(grade, 0.5, 10))
    lo = round1(clamp(min(grade_low, g), 0.5, 10))
    hi = round1(clamp(max(grade_high, g), 0.5, 10))
    conf = round(clamp(confidence, 0, 1), 2)
    fixed = [
        DefectScore(area=d.area, score=round1(clamp(d.score, 0.5, 10)), note=d.note.strip())
        for d in defects
    ]
    return g, lo, hi, conf, fixed
