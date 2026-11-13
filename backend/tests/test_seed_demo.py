import importlib
import sys
from pathlib import Path

import pytest

from app import supabase_client
from app.config import settings
from conftest import USER_A

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
seed_demo = importlib.import_module("seed_demo")


def run_seed(sb, monkeypatch, *flags):
    monkeypatch.setattr(settings, "supabase_service_role_key", "test-key")
    monkeypatch.setattr(supabase_client, "get_supabase", lambda: sb)
    monkeypatch.setattr(sys, "argv", ["seed_demo.py", "--user-id", USER_A, *flags])
    seed_demo.main()


def test_seed_loads_demo_collection(client, sb, monkeypatch):
    run_seed(sb, monkeypatch)
    comics = client.get("/comics").json()
    assert len(comics) == 14
    assert sum(c["current_market_value"] for c in comics) == pytest.approx(8963)
    assert len(sb.rows("price_history")) == 14 * 10

    points = client.get("/portfolio/history").json()["points"]
    assert [p["source"] for p in points] == ["snapshot"] * 9 + ["live"]
    assert points[-1]["value"] == 8963

    gaps = {g["name"]: g for g in client.get("/runs/gaps").json()}
    assert gaps["Amazing Spider-Man · McFarlane era"]["missing_key"] == "#298"
    assert gaps["Invincible #1 to #12"]["missing_key"] == "#2"
    assert gaps["Saga #1 to #54"]["missing_key"] == "#19"


def test_seed_is_idempotent_and_fill_runs_matches_demo(client, sb, monkeypatch):
    run_seed(sb, monkeypatch, "--fill-runs")
    run_seed(sb, monkeypatch, "--fill-runs")
    gaps = {g["name"]: (g["owned"], g["total"], g["missing_key"]) for g in client.get("/runs/gaps").json()}
    assert gaps == {
        "Amazing Spider-Man · McFarlane era": (21, 28, "#298"),
        "Invincible #1 to #12": (9, 12, "#2"),
        "Saga #1 to #54": (31, 54, "#19"),
    }
    assert len(sb.rows("series")) == 3
    ids = [c["id"] for c in sb.rows("comics")]
    assert len(ids) == len(set(ids))
