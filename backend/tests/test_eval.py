import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from eval import bench, providers
from eval.score import check_candidate, load_truth, norm_series, render, score

TRUTH = load_truth()
BY_ID = {p["id"]: p for p in TRUTH["photos"]}


def right_answer(t: dict) -> dict:
    return {
        "series": t["series"][0], "issue_number": t["issue"], "format": t["format"],
        "variant_named_on_cover": t.get("variant_named_on_cover", False), "printing": None,
        "cover_year": t["year"],
    }


def results_with(overrides: dict | None = None, skip=("07",)) -> dict:
    photos = []
    for t in TRUTH["photos"]:
        if t["id"] in skip:
            continue
        cands = (overrides or {}).get(t["id"], [right_answer(t)])
        photos.append({"id": t["id"], "candidates": cands, "latency_s": 2.0, "cost_usd": 0.03})
    return {"meta": {"approach": "test"}, "photos": photos}


# ------------------------------------------------------------ normalization


@pytest.mark.parametrize("raw,expected", [
    ("The Amazing Spider-Man Annual", ("amazing spiderman", "annual")),
    ("Detective Comics #1000: The Deluxe Edition", ("detective comics", "collected_edition")),
    ("Ultimate Spider-Man (2024)", ("ultimate spiderman", None)),
    ("The New Avengers", ("new avengers", None)),
    ("Avengers Vol. 1", ("avengers", None)),
    ("Batman: Detective Comics", ("batman detective comics", None)),
])
def test_norm_series(raw, expected):
    assert norm_series(raw) == expected


def test_issue_number_forms_match():
    t = BY_ID["04"]
    assert check_candidate({"series": "Avengers", "issue_number": "#09"}, t)["ok"]


# ------------------------------------------------------------ trap rules


def test_annual_read_as_monthly_is_wrong():
    t = BY_ID["08"]
    assert not check_candidate({"series": "Amazing Spider-Man", "issue_number": "2", "format": "single_issue"}, t)["ok"]
    assert check_candidate({"series": "Amazing Spider-Man Annual", "issue_number": "2"}, t)["ok"]


def test_deluxe_read_as_single_issue_is_wrong():
    t = BY_ID["06"]
    assert not check_candidate({"series": "Detective Comics", "issue_number": "1000"}, t)["ok"]
    assert check_candidate({"series": "Detective Comics", "issue_number": "1000", "format": "collected_edition"}, t)["ok"]


def test_new_avengers_is_not_avengers():
    assert not check_candidate({"series": "Avengers", "issue_number": "1"}, BY_ID["11"])["ok"]
    assert not check_candidate({"series": "New Avengers", "issue_number": "9"}, BY_ID["04"])["ok"]


def test_any_printing_claim_fails():
    cand = {**right_answer(BY_ID["10"]), "printing": "1st printing"}
    result = check_candidate(cand, BY_ID["10"])
    assert result["printing_claim"] and not result["ok"]


def test_variant_only_scored_where_cover_names_it():
    # Saying "variant" on 03 is not scored either way: the cover does not name one.
    assert check_candidate({**right_answer(BY_ID["03"]), "variant_named_on_cover": True}, BY_ID["03"])["variant_ok"] is None
    missed = check_candidate({**right_answer(BY_ID["09"]), "variant_named_on_cover": False}, BY_ID["09"])
    assert missed["variant_ok"] is False and not missed["ok"]


# ------------------------------------------------------------ aggregate


def test_perfect_run_scores_full_marks_and_reports_missing_photo():
    s = score(results_with())
    assert s["missing"] == ["07"]
    assert s["n_scored"] == 10
    assert s["top1"] == 1.0 and s["top3"] == 1.0
    assert s["top1_meets_target"] and s["top3_meets_target"]
    assert all(s["traps"].values())
    assert s["fields"]["variant"] == (1.0, 1)
    assert s["cost"]["mean"] == pytest.approx(0.03) and not s["cost"]["over_flag"]


def test_trap_failures_and_top3_rescue():
    wrong_new = {"series": "Avengers", "issue_number": "1", "format": "single_issue"}
    s = score(results_with({
        "11": [wrong_new, right_answer(BY_ID["11"])],  # right answer only at rank 2
        "08": [{"series": "Amazing Spider-Man", "issue_number": "2", "format": "single_issue"}],
    }))
    assert s["traps"]["new_vs_old_avengers"] is False
    assert s["traps"]["annual_not_monthly"] is False
    assert s["top1"] == pytest.approx(8 / 10)
    assert s["top3"] == pytest.approx(9 / 10)


def test_error_counts_as_wrong_and_cost_flag():
    res = results_with()
    res["photos"][0] = {"id": "01", "candidates": [], "error": "refused", "latency_s": 1.0}
    for p in res["photos"][1:]:
        p["cost_usd"] = 0.2
    s = score(res)
    assert s["errors"] == ["01"]
    assert s["top1"] == pytest.approx(9 / 10)
    assert s["fields"]["series"][0] == pytest.approx(9 / 10)
    assert s["traps"]["same_issue_two_arts"] is False
    assert s["cost"]["over_flag"]


def test_report_renders_every_photo():
    report = render(results_with(), score(results_with()))
    for t in TRUTH["photos"]:
        assert f"| {t['id']} |" in report
    assert "photo missing" in report
    assert "2024 Ultimate Spider-Man" in report  # ground-truth note is surfaced


# ------------------------------------------------------------ claude


def response(payload=None, stop_reason="end_turn", model="claude-opus-5-5"):
    content = [SimpleNamespace(type="thinking", thinking="")]
    if payload is not None:
        content.append(SimpleNamespace(type="text", text=json.dumps(payload)))
    return SimpleNamespace(
        stop_reason=stop_reason, content=content, model=model, stop_details=None,
        usage=SimpleNamespace(input_tokens=2000, output_tokens=1000),
    )


def test_parse_claude_candidates_and_cost():
    cands = [right_answer(BY_ID["01"])] * 5
    out = providers.parse_claude(response({"candidates": cands, "evidence": "Logo and #1000."}))
    assert len(out.candidates) == 3
    assert out.cost_usd == pytest.approx(2000 / 1e6 * 4 + 1000 / 1e6 * 20)
    assert out.error is None


def test_parse_claude_refusal_checked_first():
    r = response(None, stop_reason="refusal")
    r.stop_details = SimpleNamespace(category="cyber")
    out = providers.parse_claude(r)
    assert out.error == "refused (cyber)" and out.candidates == []
    assert out.cost_usd is not None  # a refusal is still billed


def test_unknown_served_model_has_no_price():
    out = providers.parse_claude(response({"candidates": [right_answer(BY_ID["01"])], "evidence": ""}, model="claude-opus-5"))
    assert out.cost_usd is None


def test_schema_is_valid_for_structured_outputs():
    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for v in node.values():
                yield from objects(v)
        elif isinstance(node, list):
            for v in node:
                yield from objects(v)

    for obj in objects(providers.ID_SCHEMA):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_bench_run_end_to_end(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for t in TRUTH["photos"]:
        if t["id"] == "07":
            continue  # not supplied this weekend
        ext = ".png" if t["id"] == "10" else ".jpg"
        (photos / (t["file"].rsplit(".", 1)[0] + ext)).write_bytes(b"\xff\xd8" + t["id"].encode())

    async def create(**kwargs):
        image = kwargs["messages"][0]["content"][0]["source"]
        photo_id = __import__("base64").standard_b64decode(image["data"])[2:].decode()
        return response({"candidates": [right_answer(BY_ID[photo_id])], "evidence": "test"})

    mock = AsyncMock(side_effect=create)
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=mock)))
    results = asyncio.run(bench.run("claude", photos, "claude-opus-5-5", "low", client=client))

    kwargs = mock.await_args.kwargs
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["output_config"]["effort"] == "low"
    assert mock.await_count == 10
    png = [c for c in mock.await_args_list if c.kwargs["messages"][0]["content"][0]["source"]["media_type"] == "image/png"]
    assert len(png) == 1

    report = bench.write(results, tmp_path / "out", "run")
    s = score(json.loads((tmp_path / "out" / "run.json").read_text()))
    assert s["top1"] == 1.0 and s["missing"] == ["07"]
    assert "photo missing" in report.read_text()
