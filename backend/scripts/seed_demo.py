"""Load the demo collection into a real Supabase project for one user.

Writes the 14 sample books from frontend/src/lib/demo.ts, ten months of price
history per book, monthly portfolio snapshots, and the three series catalogs
used for run gaps. Safe to run again: books get stable ids per user, so a
rerun replaces them instead of adding copies.

Grades and dollar values are ILLUSTRATIVE sample data, not market data.

Usage (from backend/, with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env):

    python scripts/seed_demo.py --user-id <uuid from Authentication > Users>
    python scripts/seed_demo.py --user-id <uuid> --fill-runs   # also add run books
    python scripts/seed_demo.py --user-id <uuid> --reset       # wipe that user's books first
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.routers.portfolio import LENSES, in_lens, month_end, month_starts  # noqa: E402

MONTHS = 10
NAMESPACE = uuid.UUID("6f1d3c3e-5b8a-4a43-9a51-1c0de6a7c0de")

# title, issue, publisher, year, grade, grade_type, value, 10-month trend, key note
BOOKS: list[tuple] = [
    ("Amazing Spider-Man", "300", "Marvel", 1988, 9.2, "raw", 610, 0.14, "1st full appearance of Venom"),
    ("Amazing Spider-Man", "129", "Marvel", 1974, 7.5, "cgc", 2150, 0.09, "1st appearance of the Punisher"),
    ("New Mutants", "98", "Marvel", 1991, 9.8, "cgc", 1050, -0.06, "1st appearance of Deadpool"),
    ("Uncanny X-Men", "266", "Marvel", 1990, 9.4, "raw", 240, 0.21, "1st full appearance of Gambit"),
    ("X-Men", "1", "Marvel", 1991, 9.6, "raw", 28, 0.02, None),
    ("Batman Adventures", "12", "DC", 1993, 9.0, "raw", 780, 0.18, "1st appearance of Harley Quinn"),
    ("Batman", "423", "DC", 1988, 8.5, "raw", 95, 0.05, "Classic Todd McFarlane cover"),
    ("Swamp Thing", "37", "DC", 1985, 8.0, "raw", 310, 0.11, "1st appearance of John Constantine"),
    ("The Walking Dead", "1", "Image", 2003, 9.2, "raw", 1650, -0.04, "Series debut, low print run"),
    ("Invincible", "1", "Image", 2003, 9.8, "cgc", 1400, 0.32, "Series debut"),
    ("Saga", "1", "Image", 2012, 9.6, "raw", 180, 0.07, "1st printing"),
    ("Spawn", "1", "Image", 1992, 9.4, "raw", 32, 0.03, None),
    ("Something Is Killing the Children", "1", "Boom! Studios", 2019, 9.8, "cgc", 420, 0.12, "Series debut"),
    ("Mighty Morphin Power Rangers", "1", "Boom! Studios", 2016, 9.6, "raw", 18, 0.0, None),
]

# name, publisher, match_title, first, last, owned target (for --fill-runs), key issues
RUNS: list[tuple] = [
    (
        "Amazing Spider-Man · McFarlane era", "Marvel", "Amazing Spider-Man", 298, 325, 21,
        {
            "298": ("McFarlane's first issue on the title", 140, 640),
            "300": ("1st full appearance of Venom", 610, 1400),
        },
    ),
    (
        "Invincible #1 to #12", "Image", "Invincible", 1, 12, 9,
        {
            "1": ("Series debut", 600, 1400),
            "2": ("Second issue, low print run", 210, 575),
        },
    ),
    (
        "Saga #1 to #54", "Image", "Saga", 1, 54, 31,
        {
            "1": ("1st printing", 180, 420),
            "19": ("Start of the third arc", 12, 70),
        },
    ),
]


def months_ago(today: date, n: int, day: int) -> date:
    start = month_starts(today, n + 1)[0]
    d = date(start.year, start.month, min(day, month_end(start).day))
    return min(d, today)  # never date a sample sale in the future


def price_history(comic_id: str, value: float, trend: float, source: str, today: date) -> list[dict]:
    rng = random.Random(comic_id)
    start = value / (1 + trend)
    out = []
    for k in range(MONTHS):
        last = k == MONTHS - 1
        base = start * (1 + trend * k / (MONTHS - 1))
        price = value if last else base * (1 + (rng.random() - 0.5) * 0.07)
        out.append(
            {
                "comic_id": comic_id,
                "sale_date": str(today if last else months_ago(today, MONTHS - 1 - k, 3 + rng.randrange(22))),
                "price": round(price, 2),
                "source": "raw-comps" if source == "raw" else "gocollect",
            }
        )
    return out


def comic_id_for(user_id: str, title: str, issue: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{user_id}|{title.lower()}|{issue}"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True, help="Supabase auth user id (uuid)")
    parser.add_argument("--reset", action="store_true", help="delete this user's books and snapshots first")
    parser.add_argument(
        "--fill-runs", action="store_true",
        help="also add filler issues so run progress matches the demo (21/28, 9/12, 31/54)",
    )
    args = parser.parse_args()

    try:
        uid = str(uuid.UUID(args.user_id))
    except ValueError:
        sys.exit("--user-id must be a uuid (Supabase > Authentication > Users)")
    if not settings.supabase_service_role_key:
        sys.exit("SUPABASE_SERVICE_ROLE_KEY is required in backend/.env to seed data.")

    from app.supabase_client import get_supabase

    sb = get_supabase()
    today = date.today()
    created = datetime.combine(months_ago(today, MONTHS, 4), datetime.min.time(), timezone.utc)

    if args.reset:
        sb.table("comics").delete().eq("user_id", uid).execute()
        sb.table("portfolio_snapshots").delete().eq("user_id", uid).execute()
        print("Removed existing books and snapshots for", uid)

    sb.table("profiles").upsert({"id": uid}, ignore_duplicates=True).execute()

    # ---- series catalog (shared reference data)
    series_ids: dict[str, str] = {}
    for name, publisher, match, first, last, _, keys in RUNS:
        row = sb.table("series").upsert(
            {"name": name, "publisher": publisher, "match_title": match, "first_issue": first, "last_issue": last},
            on_conflict="match_title,first_issue,last_issue",
        ).execute().data[0]
        series_ids[match] = row["id"]
        sb.table("series_issues").upsert(
            [
                {"series_id": row["id"], "issue_number": n, "key_note": note, "raw_price": raw, "slab_price": slab}
                for n, (note, raw, slab) in keys.items()
            ]
        ).execute()
    print(f"Catalogued {len(RUNS)} series")

    # ---- books
    books = [
        {
            "title": t, "issue_number": i, "publisher": p, "year": y, "estimated_grade": g,
            "grade_type": gt, "current_market_value": v, "key_note": k, "trend": tr,
        }
        for (t, i, p, y, g, gt, v, tr, k) in BOOKS
    ]
    if args.fill_runs:
        rng = random.Random(uid)
        for name, publisher, match, first, last, target, keys in RUNS:
            owned = {
                b["issue_number"] for b in books
                if b["title"] == match and first <= int(b["issue_number"]) <= last
            }
            missing_key = min(
                (n for n in keys if n not in owned), key=lambda n: (-keys[n][2], int(n)), default=None
            )
            pool = [str(n) for n in range(first, last + 1) if str(n) not in owned and str(n) != missing_key]
            rng.shuffle(pool)
            for issue in sorted(pool[: max(0, target - len(owned))], key=int):
                books.append(
                    {
                        "title": match, "issue_number": issue, "publisher": publisher, "year": None,
                        "estimated_grade": rng.choice([8.0, 8.5, 9.0, 9.2, 9.4]), "grade_type": "raw",
                        "current_market_value": float(rng.randrange(6, 40)), "key_note": None,
                        "trend": round(rng.uniform(-0.03, 0.08), 3),
                    }
                )

    comic_rows, history = [], []
    for b in books:
        cid = comic_id_for(uid, b["title"], b["issue_number"])
        trend = b.pop("trend")
        cert = None
        if b["grade_type"] != "raw":
            cert = f"40{random.Random(cid).randrange(10**8):08d}"
        comic_rows.append(
            {
                **b, "id": cid, "user_id": uid, "slab_cert_number": cert,
                "series_id": series_ids.get(b["title"]), "created_at": created.isoformat(),
            }
        )
        history.extend(price_history(cid, float(b["current_market_value"]), trend, b["grade_type"], today))

    ids = [c["id"] for c in comic_rows]
    sb.table("comics").upsert(comic_rows).execute()
    # Replace (not append to) the history of these books so reruns stay clean.
    for chunk in range(0, len(ids), 100):
        sb.table("price_history").delete().in_("comic_id", ids[chunk : chunk + 100]).execute()
    for chunk in range(0, len(history), 500):
        sb.table("price_history").insert(history[chunk : chunk + 500]).execute()
    print(f"Upserted {len(comic_rows)} books and {len(history)} price points")

    # ---- month-end snapshots for the last nine months, plus today
    snapshots = []
    for start in month_starts(today, MONTHS)[:-1]:
        cutoff = str(month_end(start))
        for lens in LENSES:
            total, count = 0.0, 0
            for c in comic_rows:
                if not in_lens(c["grade_type"], lens):
                    continue
                points = [h for h in history if h["comic_id"] == c["id"]]
                before = [h["price"] for h in points if h["sale_date"] <= cutoff]
                total += before[-1] if before else points[0]["price"]
                count += 1
            snapshots.append(
                {"user_id": uid, "snapshot_date": cutoff, "lens": lens, "total_value": round(total, 2), "book_count": count}
            )
    for lens in LENSES:
        group = [c for c in comic_rows if in_lens(c["grade_type"], lens)]
        snapshots.append(
            {
                "user_id": uid, "snapshot_date": str(today), "lens": lens,
                "total_value": round(sum(float(c["current_market_value"]) for c in group), 2),
                "book_count": len(group),
            }
        )
    sb.table("portfolio_snapshots").upsert(snapshots, on_conflict="user_id,snapshot_date,lens").execute()
    print(f"Wrote {len(snapshots)} portfolio snapshots")
    print("Done. Sign in as this user, or set DEV_USER_ID to it in backend/.env.")


if __name__ == "__main__":
    main()
