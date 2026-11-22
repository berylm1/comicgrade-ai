from datetime import date, timedelta

from app.config import settings
from app.routers.portfolio import month_starts
import jwt

from conftest import AUTH_A, AUTH_B, OTHER_KEY, TOKEN_A, USER_A, USER_B, add_comic, make_token

NEW_ID = "33333333-3333-4333-8333-333333333333"


# ------------------------------------------------------------------ auth


def test_dev_user_fallback_when_no_token(client, sb):
    add_comic(sb, USER_A)
    assert len(client.get("/comics").json()) == 1


def test_invalid_token_is_rejected(client):
    r = client.get("/comics", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_acts_as_its_user(client, sb):
    add_comic(sb, USER_B, title="Spawn")
    assert [c["title"] for c in client.get("/comics", headers=bearer(make_token(USER_B))).json()] == ["Spawn"]


def test_expired_token_is_rejected(client):
    assert client.get("/comics", headers=bearer(make_token(exp_in=-120))).status_code == 401


def test_wrong_audience_or_issuer_is_rejected(client):
    assert client.get("/comics", headers=bearer(make_token(aud="anon"))).status_code == 401
    assert client.get("/comics", headers=bearer(make_token(iss="https://other.supabase.co/auth/v1"))).status_code == 401


def test_token_signed_with_another_key_is_rejected(client):
    assert client.get("/comics", headers=bearer(make_token(key=OTHER_KEY))).status_code == 401


def test_tampered_token_is_rejected(client):
    head, body, sig = TOKEN_A.split(".")
    forged = jwt.encode({"sub": USER_B}, "x", algorithm="HS256").split(".")[1]
    assert client.get("/comics", headers=bearer(f"{head}.{forged}.{sig}")).status_code == 401


def test_token_without_user_id_is_rejected(client):
    assert client.get("/comics", headers=bearer(make_token(sub="not-a-uuid"))).status_code == 401


def test_legacy_hs256_token_falls_back_to_supabase(client, sb):
    legacy = jwt.encode({"sub": USER_B, "aud": "authenticated"}, "legacy-secret-at-least-32-bytes-long!", algorithm="HS256")
    sb.tokens[legacy] = USER_B
    add_comic(sb, USER_B, title="Spawn")
    assert [c["title"] for c in client.get("/comics", headers=bearer(legacy)).json()] == ["Spawn"]
    unknown = jwt.encode({"sub": USER_B}, "another-secret-at-least-32-bytes-long", algorithm="HS256")
    assert client.get("/comics", headers=bearer(unknown)).status_code == 401


def test_malformed_header_is_rejected(client):
    assert client.get("/comics", headers={"Authorization": "Token abc"}).status_code == 401


def test_auth_required_rejects_missing_token(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    assert client.get("/comics").status_code == 401
    assert client.get("/comics", headers=AUTH_A).status_code == 200


def test_no_dev_user_and_no_token_is_401(client, monkeypatch):
    monkeypatch.setattr(settings, "dev_user_id", "")
    assert client.get("/comics").status_code == 401


# ---------------------------------------------------------------- scoping


def test_users_only_see_their_own_books(client, sb):
    mine = add_comic(sb, USER_A, title="Saga")
    theirs = add_comic(sb, USER_B, title="Spawn")
    assert [c["id"] for c in client.get("/comics", headers=AUTH_A).json()] == [mine["id"]]
    assert [c["id"] for c in client.get("/comics", headers=AUTH_B).json()] == [theirs["id"]]
    assert client.get(f"/comics/{theirs['id']}", headers=AUTH_A).status_code == 404
    assert client.get(f"/comics/{theirs['id']}/prices", headers=AUTH_A).status_code == 404
    assert client.get(f"/comics/{theirs['id']}/grade_report", headers=AUTH_A).status_code == 404
    assert client.delete(f"/comics/{theirs['id']}", headers=AUTH_A).status_code == 404
    assert len(sb.rows("comics")) == 2


def test_body_user_id_is_ignored(client, sb):
    r = client.post("/comics", json={"title": "Saga", "issue_number": "1", "user_id": USER_B}, headers=AUTH_A)
    assert r.status_code == 201
    assert r.json()["user_id"] == USER_A


def test_non_uuid_id_is_404_not_500(client):
    assert client.get("/comics/not-a-uuid").status_code == 404


# ------------------------------------------------------- duplicate scans


def test_saving_twice_with_same_id_updates_one_row(client, sb):
    first = client.post("/comics", json={"id": NEW_ID, "title": "Saga", "issue_number": "1", "estimated_grade": 9.4})
    assert first.status_code == 201
    second = client.post(
        "/comics",
        json={"id": NEW_ID, "title": "Saga", "issue_number": "1", "cover_image_url": "https://x/cover.jpg"},
    )
    assert second.status_code == 201
    rows = sb.rows("comics")
    assert len(rows) == 1
    # The second save only sent the cover, so the grade from the first one stays.
    assert rows[0]["estimated_grade"] == 9.4
    assert rows[0]["cover_image_url"] == "https://x/cover.jpg"


def test_cannot_overwrite_another_users_book_by_id(client, sb):
    theirs = add_comic(sb, USER_B)
    r = client.post("/comics", json={"id": theirs["id"], "title": "Mine now", "issue_number": "1"}, headers=AUTH_A)
    assert r.status_code == 404
    assert sb.rows("comics")[0]["title"] == "Saga"


def test_create_records_value_and_creates_profile(client, sb):
    client.post("/comics", json={"title": "Saga", "issue_number": "1", "current_market_value": 180})
    assert [p["id"] for p in sb.rows("profiles")] == [USER_A]
    assert [p["price"] for p in sb.rows("price_history")] == [180]


# ---------------------------------------------------------- grade report


def test_scan_report_is_stored_and_slab_computed_server_side(client, sb):
    report = {
        "grade": 9.4, "grade_low": 9.2, "grade_high": 9.6, "confidence": 0.8,
        "defects": [{"area": "Corners", "score": 9.4, "note": "Sharp"}],
        "source": "claude:claude-opus-5-5", "photos_used": 3,
    }
    r = client.post(
        "/comics",
        json={"id": NEW_ID, "title": "Uncanny X-Men", "issue_number": "266", "estimated_grade": 9.4,
              "current_market_value": 240, "report": report},
    )
    assert r.status_code == 201
    got = client.get(f"/comics/{NEW_ID}/grade_report").json()
    assert got["source"] == "claude:claude-opus-5-5"
    assert got["photos_used"] == 3
    assert got["defects"] == report["defects"]
    # 240 * 1.75 = 420 slabbed, 75 fee, 22 shipping
    assert got["slab"]["slabbed_value"] == 420
    assert got["slab"]["net_uplift"] == 83
    assert got["slab"]["verdict"] == "submit"

    # Slab maths follows the current value, not the value at scan time.
    client.post(f"/comics/{NEW_ID}/prices", params={"price": 100})
    assert client.get(f"/comics/{NEW_ID}/grade_report").json()["slab"]["raw_value"] == 100


def test_grade_report_falls_back_to_estimate(client, sb):
    comic = add_comic(sb, title="Amazing Spider-Man", issue_number="300", estimated_grade=9.2,
                      current_market_value=610)
    got = client.get(f"/comics/{comic['id']}/grade_report").json()
    assert got["source"] == "estimate"
    assert (got["grade_low"], got["grade"], got["grade_high"]) == (8.9, 9.2, 9.4)
    assert got["slab"]["verdict"] == "submit"


def test_slabbed_books_have_no_slab_maths(client, sb):
    comic = add_comic(sb, grade_type="cgc", slab_cert_number="4012345678")
    assert client.get(f"/comics/{comic['id']}/grade_report").json()["slab"] is None


# ----------------------------------------------------------------- prices


def test_future_sale_date_rejected(client, sb):
    comic = add_comic(sb)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(f"/comics/{comic['id']}/prices", params={"price": 10, "sale_date": tomorrow})
    assert r.status_code == 422


def test_change_pct_from_price_history(client, sb):
    comic = add_comic(sb, current_market_value=120)
    sb.table("price_history").insert([
        {"comic_id": comic["id"], "sale_date": "2026-01-05", "price": 100},
        {"comic_id": comic["id"], "sale_date": "2026-06-05", "price": 120},
    ]).execute()
    assert client.get(f"/comics/{comic['id']}").json()["change_pct"] == 20.0


# -------------------------------------------------------------- portfolio


def _months(n=10):
    return [m.strftime("%Y-%m") for m in month_starts(date.today(), n)]


def test_history_uses_snapshots_then_price_history_then_live(client, sb):
    raw = add_comic(sb, current_market_value=150)
    slab = add_comic(sb, title="Invincible", grade_type="cgc", current_market_value=1400)
    months = _months()
    first_month = months[0] + "-10"
    sb.table("price_history").insert([
        {"comic_id": raw["id"], "sale_date": first_month, "price": 100},
        {"comic_id": slab["id"], "sale_date": first_month, "price": 1000},
    ]).execute()
    sb.table("portfolio_snapshots").insert(
        {"user_id": USER_A, "snapshot_date": months[1] + "-28", "lens": "all", "total_value": 1234, "book_count": 2}
    ).execute()

    body = client.get("/portfolio/history", params={"lens": "all"}).json()
    points = body["points"]
    assert [p["month"] for p in points] == months
    assert points[0] == {"month": months[0], "value": 1100, "source": "price_history"}
    assert points[1] == {"month": months[1], "value": 1234, "source": "snapshot"}
    assert points[2]["source"] == "price_history"
    assert points[-1] == {"month": months[-1], "value": 1550, "source": "live"}

    raw_only = client.get("/portfolio/history", params={"lens": "raw"}).json()["points"]
    assert raw_only[0]["value"] == 100 and raw_only[-1]["value"] == 150
    certified = client.get("/portfolio/history", params={"lens": "certified"}).json()["points"]
    assert certified[-1]["value"] == 1400


def test_history_is_scoped_to_user(client, sb):
    add_comic(sb, USER_B, current_market_value=999)
    points = client.get("/portfolio/history", headers=AUTH_A).json()["points"]
    assert all(p["value"] == 0 for p in points)


def test_snapshot_upserts_one_row_per_lens_per_day(client, sb):
    add_comic(sb, current_market_value=100)
    add_comic(sb, grade_type="cgc", current_market_value=50)
    client.post("/portfolio/snapshot")
    r = client.post("/portfolio/snapshot")
    assert r.status_code == 200
    rows = {s["lens"]: s for s in sb.rows("portfolio_snapshots")}
    assert len(sb.rows("portfolio_snapshots")) == 3
    assert rows["all"]["total_value"] == 150 and rows["all"]["book_count"] == 2
    assert rows["raw"]["total_value"] == 100
    assert rows["certified"]["total_value"] == 50


def test_snapshot_all_needs_cron_secret(client, sb, monkeypatch):
    assert client.post("/portfolio/snapshot/all").status_code == 404  # disabled without a secret
    monkeypatch.setattr(settings, "cron_secret", "s3cret")
    assert client.post("/portfolio/snapshot/all", headers={"X-Cron-Secret": "wrong"}).status_code == 401
    add_comic(sb, USER_A)
    add_comic(sb, USER_B)
    r = client.post("/portfolio/snapshot/all", headers={"X-Cron-Secret": "s3cret"})
    assert r.json()["users"] == 2
    assert len(sb.rows("portfolio_snapshots")) == 6


# ------------------------------------------------------------------- runs


def _seed_series(sb, name, match, first, last, keys):
    s = sb.table("series").insert(
        {"name": name, "publisher": "Image", "match_title": match, "first_issue": first, "last_issue": last}
    ).execute().data[0]
    for n, (note, raw, slab) in keys.items():
        sb.table("series_issues").insert(
            {"series_id": s["id"], "issue_number": n, "key_note": note, "raw_price": raw, "slab_price": slab}
        ).execute()
    return s


def test_run_gaps(client, sb):
    _seed_series(sb, "Invincible #1 to #12", "Invincible", 1, 12, {
        "1": ("Series debut", 600, 1400), "2": ("Second issue, low print run", 210, 575),
    })
    _seed_series(sb, "Saga #1 to #3", "Saga", 1, 3, {})
    _seed_series(sb, "Spawn #1 to #2", "Spawn", 1, 2, {})
    for n in ("1", "3", "4"):
        add_comic(sb, title="Invincible", issue_number=n)
    for n in ("1", "2", "3"):
        add_comic(sb, title="saga", issue_number=n)  # complete run, case-insensitive match
    add_comic(sb, USER_B, title="Spawn", issue_number="1")  # someone else's book

    gaps = client.get("/runs/gaps").json()
    assert len(gaps) == 1
    gap = gaps[0]
    assert (gap["owned"], gap["total"]) == (3, 12)
    assert gap["missing_key"] == "#2"
    assert gap["missing_note"] == "Second issue, low print run"
    assert (gap["raw_price"], gap["slab_price"]) == (210, 575)


def test_run_gaps_without_catalogued_keys_picks_first_missing(client, sb):
    _seed_series(sb, "Saga #1 to #5", "Saga", 1, 5, {})
    add_comic(sb, title="Saga", issue_number="1")
    gap = client.get("/runs/gaps").json()[0]
    assert gap["missing_key"] == "#2"
    assert gap["slab_price"] == 0


# ----------------------------------------------------------------- vision


def test_grade_scan_mock_returns_report_value_and_slab(client):
    files = {
        "front": ("front.jpg", b"\xff\xd8front-bytes", "image/jpeg"),
        "back": ("back.jpg", b"\xff\xd8back-bytes", "image/jpeg"),
    }
    r = client.post("/vision/grade", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"]["source"] == "mock"
    assert len(body["report"]["defects"]) == 6
    assert body["estimated_value"] > 0
    assert body["report"]["grade_low"] <= body["report"]["grade"] <= body["report"]["grade_high"]


def test_grade_scan_requires_front(client):
    r = client.post("/vision/grade", files={"back": ("b.jpg", b"x", "image/jpeg")})
    assert r.status_code == 422


def test_grade_scan_rejects_bad_type(client):
    r = client.post("/vision/grade", files={"front": ("f.txt", b"x", "text/plain")})
    assert r.status_code == 415


def test_vision_needs_a_user(client, monkeypatch):
    monkeypatch.setattr(settings, "dev_user_id", "")
    r = client.post("/vision/grade", files={"front": ("f.jpg", b"x", "image/jpeg")})
    assert r.status_code == 401


# -------------------------------------------------------- format / pricing


def test_annuals_do_not_count_toward_runs(client, sb):
    _seed_series(sb, "Amazing Spider-Man #1 to #3", "Amazing Spider-Man", 1, 3, {})
    add_comic(sb, title="Amazing Spider-Man", issue_number="1")
    add_comic(sb, title="Amazing Spider-Man", issue_number="2", format="annual")
    gap = client.get("/runs/gaps").json()[0]
    assert gap["owned"] == 1 and gap["missing_key"] == "#2"


def test_create_keeps_format(client):
    r = client.post("/comics", json={"title": "Detective Comics", "issue_number": "1000", "format": "collected_edition"})
    assert r.json()["format"] == "collected_edition"
    assert client.post("/comics", json={"title": "X", "issue_number": "1", "format": "poster"}).status_code == 422


def test_price_estimate(client):
    r = client.get("/pricing/estimate", params={"title": "Spawn", "issue_number": "1", "grade": 9.4})
    assert r.status_code == 200
    assert r.json()["source"] == "mock" and r.json()["value"] > 0
    assert client.get("/pricing/estimate", params={"title": "", "issue_number": "1"}).status_code == 422


def test_missing_supabase_config_is_503(monkeypatch):
    from fastapi.testclient import TestClient

    from app import supabase_client
    from app.main import app

    monkeypatch.setattr(settings, "supabase_url", "")
    supabase_client.get_supabase.cache_clear()
    try:
        assert TestClient(app).get("/comics").status_code == 503
    finally:
        supabase_client.get_supabase.cache_clear()
