import json
from pathlib import Path

import pytest

from app.grading import estimate_report, seeded, slab_economics

# Generated from frontend/src/lib/grading.ts, so server reports match the demo.
REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "grading_ts_reference.json").read_text())


@pytest.mark.parametrize("key", list(REFERENCE["seeded"]))
def test_seeded_prng_matches_typescript(key):
    rng = seeded(key)
    assert [rng() for _ in range(3)] == pytest.approx(REFERENCE["seeded"][key], abs=1e-15)


@pytest.mark.parametrize("case", REFERENCE["reports"], ids=lambda c: c["comic"]["title"])
def test_estimate_report_matches_typescript(case):
    expected = case["report"]
    got = estimate_report(case["comic"]).model_dump()
    for field in ("grade", "grade_low", "grade_high", "confidence", "exterior_only", "defects"):
        assert got[field] == expected[field], field
    assert got["slab"] == expected["slab"]


def test_slab_economics_none_for_slabbed_or_unvalued_books():
    assert slab_economics(9.8, "cgc", 1000) is None
    assert slab_economics(9.2, "raw", None) is None
    assert slab_economics(9.2, "raw", 0) is None


@pytest.mark.parametrize(
    "grade,value,verdict",
    [
        (9.2, 610, "submit"),  # 1068 slabbed, 150 fee: +286
        (8.0, 150, "hold"),  # 218 slabbed, 30 fee: +16, under the submit bar
        (8.0, 60, "skip"),  # 87 slabbed, 30 fee: -25
    ],
)
def test_slab_verdicts(grade, value, verdict):
    slab = slab_economics(grade, "raw", value)
    assert slab.verdict == verdict
    assert slab.net_uplift == slab.slabbed_value - slab.raw_value - slab.grading_fee - slab.shipping


def test_fee_tiers_follow_slabbed_value():
    assert slab_economics(9.8, "raw", 100).grading_fee == 30  # 230 slabbed
    assert slab_economics(9.8, "raw", 300).grading_fee == 75  # 690 slabbed
    assert slab_economics(9.8, "raw", 500).grading_fee == 150  # 1150 slabbed
