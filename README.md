# ComicGrade AI

A mobile-first **comic book valuation & grading** prototype.

- **Frontend:** React Native (Expo) with a dark "comic pop" theme via NativeWind (Tailwind CSS)
- **Backend:** Python FastAPI — image routing, AI vision pipeline (mock or OpenAI), Supabase access
- **Database:** Supabase (PostgreSQL) — `profiles`, `comics`, `price_history` + public `cover-images` storage bucket

```
comicgrade-ai/
├── frontend/                  # Expo React Native app
│   ├── App.tsx                # Tabs: Vault / Collection / Scan / Insights (phone frame on desktop web)
│   ├── tailwind.config.js     # Comic-pop dark palette
│   └── src/
│       ├── lib/               # FastAPI client, demo backend (demo.ts), grade report builder, Supabase, env
│       ├── components/        # ui.tsx (badges, pills, toasts) and visuals.tsx (covers, charts, grade dial)
│       └── screens/
│           ├── DashboardScreen.tsx       # Vault: value over time, raw vs slabbed lens, top holdings
│           ├── CollectionScreen.tsx      # Searchable, filterable collection grouped by publisher
│           ├── ScanScreen.tsx            # Guided front/back/spine scan (demo walkthrough or live camera)
│           ├── LiveScanner.tsx           # Camera: front, back, spine → POST /vision/grade → save (demo mode off)
│           ├── InsightsScreen.tsx        # Slab pre-screen queue, run gaps, insurance export
│           └── ComicDetailScreen.tsx     # Explainable grade, value chart, slab decision, price logging
├── backend/                   # FastAPI server
│   └── app/
│       ├── main.py            # App entry (CORS, routers, /health)
│       ├── config.py          # .env settings
│       ├── supabase_client.py # Service-role Supabase client
│       ├── schemas.py         # Pydantic models
│       ├── auth.py            # Verifies the Supabase access token, returns the user id
│       ├── grading.py         # Grade report estimate + slab economics (port of frontend grading.ts)
│       ├── claude_grader.py   # Claude vision grading with structured output
│       └── routers/
│           ├── vision.py      # POST /vision/analyze, POST /vision/grade (mock, OpenAI or Claude)
│           ├── comics.py      # CRUD, grade reports, price history, cover upload to Storage
│           ├── portfolio.py   # Collection value history + nightly snapshots
│           └── runs.py        # Series run gaps
│   ├── scripts/seed_demo.py   # Loads the demo collection into a real Supabase project
│   └── tests/                 # pytest suite (in-memory Supabase fake, mocked Claude SDK)
└── supabase/migrations/       # SQL schema + storage bucket policies
    ├── 001_initial_schema.sql
    ├── 002_storage_bucket.sql
    ├── 003_grade_type.sql
    ├── 004_grading_portfolio_runs.sql
    └── 005_comic_format.sql
```

## Quick demo (no backend needed)

The frontend ships with a **demo mode** that serves the whole app from built-in sample data, so it can be shown to prospects with no Supabase project, API server or camera.

```bash
cd frontend
npm install
npx expo start --web
```

Open http://localhost:8081. On a desktop browser the app is presented inside a phone frame. Demo mode is on whenever `EXPO_PUBLIC_API_BASE_URL` is unset (`EXPO_PUBLIC_DEMO_MODE=1` forces it on, `0` forces it off).

What the demo shows:

1. **Vault**: collection value over time, a raw vs slabbed lens, and a pre-screen pick.
2. **Scan**: a guided front, back and spine capture that ends in an identification, a grade range and a value.
3. **Comic detail**: a per-area breakdown of why the book got its grade, an exterior-only disclaimer, a value chart and a "should you slab it?" calculation net of fees.
4. **Insights**: the submission queue ranked by net uplift, run gaps with prices, and the insurance export.

Titles in the sample set are real books. Grades, dollar values, run gaps and grade reports are **illustrative demo data**, and covers are generated placeholders. To show the same collection from a real backend, load it with `backend/scripts/seed_demo.py` (see below).

**Going live** (Supabase, hosting, phone test, benchmark): see [`docs/go-live.md`](docs/go-live.md). Every push runs the backend tests and the frontend type-check on GitHub (`.github/workflows/ci.yml`).

## 1. Prerequisites

- Node.js ≥ 18 and npm (frontend)
- Python ≥ 3.10 (backend)
- Expo Go on your phone, or an iOS Simulator / Android emulator
- A (free) Supabase project — https://supabase.com

## 2. Database setup (Supabase)

1. Create a project at supabase.com. Grab **Project URL**, **anon key**, and **service_role key** from *Project Settings → API*.
2. In the SQL editor, run:
   1. `supabase/migrations/001_initial_schema.sql`
   2. `supabase/migrations/002_storage_bucket.sql`
   3. `supabase/migrations/003_grade_type.sql` (raw vs slabbed separation)
   4. `supabase/migrations/004_grading_portfolio_runs.sql` (grade reports, value snapshots, series catalog)
   5. `supabase/migrations/005_comic_format.sql` (annuals and collected editions are separate from single issues)

   (Or use the Supabase CLI: `supabase link --project-ref <ref> && supabase db push`.)
3. Create a test user under **Authentication → Users** and copy its user id.

## 3. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in your Supabase credentials
uvicorn app.main:app --reload --port 8000
```

- Interactive API docs: **http://localhost:8000/docs**
- `GET /health`: liveness check

**Auth.** Every route except `/health` acts as one user. The app sends the signed-in user's Supabase access token as `Authorization: Bearer <token>` and the backend verifies it with Supabase, then scopes every query to that user. For local testing without a sign-in screen, leave `AUTH_REQUIRED=false` and set `DEV_USER_ID` to your test user's id: requests with no token then act as that user. Set `AUTH_REQUIRED=true` anywhere real.

**Grading.**
- `POST /vision/grade`: multipart `front` (required), `back` and `spine` photos. Returns the identification, the full grade report (range, confidence, per-area scores) and a raw value estimate with the slab-or-not maths.
- `POST /vision/analyze`: single `image` upload, returns `{title, issue_number, publisher, tentative_grade, ...}`.
- Providers (`VISION_PROVIDER`): `mock` (default, no keys), `openai` (front cover only), and `claude`, which reads all three photos and scores each area. For Claude set `ANTHROPIC_API_KEY`; the model (`CLAUDE_VISION_MODEL`, default `claude-opus-5-5`) and effort (`CLAUDE_EFFORT`, default `medium`) are configurable. Server-side refusal fallbacks are enabled, so a request a safety classifier declines is retried on a fallback model in the same call; a final refusal returns 422. Claude accepts JPEG, PNG and WebP up to 5 MB per photo.

**Collection.**
- `POST /comics`: create a comic. Send an `id` to update that book instead of adding a second one, and an optional `report` (from `/vision/grade`) to store its grade report.
- `GET /pricing/estimate?title=&issue_number=&grade=`: value for a book not saved yet (used when the user corrects a scan).
- `GET /comics/{id}/grade_report`: the stored scan report, or one estimated from the stored grade. Slab economics are always computed from the book's current value.
- `POST /comics/{id}/cover`: upload the cover photo to Storage and attach it.
- `POST /comics/{id}/prices?price=249.99&source=ebay`: logs a price point and updates `current_market_value`.
- `POST /comics/{id}/refresh_value`: re-values a comic from the source matching its `grade_type`: **slabbed** books (cgc/cbcs/pgx) price via the **GoCollect Insights API** (grade-keyed: `GET /v1/insights/item/{id}?grade=9.8`, needs `GOCOLLECT_API_KEY` — free account = basic API access, full FMV = Pro/Enterprise); **raw** books use the built-in mock raw-comps provider until a raw comps partner is wired (eBay's sold-listing APIs were decommissioned Feb 2025). Every refresh writes a `price_history` row tagged with the source name, so provenance is auditable in the UI.

**Value history and runs.**
- `GET /portfolio/history?lens=all|raw|certified&months=10`: month-end collection value. Past months use that month's nightly snapshot when there is one, else they are rebuilt from `price_history`; the current month is the live total.
- `POST /portfolio/snapshot`: record today's totals for the signed-in user. `POST /portfolio/snapshot/all` snapshots every user; it needs `CRON_SECRET` set and sent as the `X-Cron-Secret` header, so a nightly cron job or Supabase scheduled function can call it.
- `GET /runs/gaps`: runs the user has started but not finished (from the `series` catalog), with the best missing issue to buy next.

**Load the demo collection** into your project (needs `SUPABASE_SERVICE_ROLE_KEY`):

```bash
python scripts/seed_demo.py --user-id <your test user id>
python scripts/seed_demo.py --user-id <id> --fill-runs   # also add run books so progress matches the demo
python scripts/seed_demo.py --user-id <id> --reset       # remove that user's books first
```

It writes the 14 sample books, ten months of price history, monthly snapshots and the three run catalogs. Running it again replaces those books rather than duplicating them.

**Tests:**

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 4. Frontend (Expo)

```bash
cd frontend
npm install

cp .env.example .env             # EXPO_PUBLIC_SUPABASE_URL / ANON_KEY / API_BASE_URL
npx expo start
```

- Scan the QR code with **Expo Go** (Android) or the Camera app (iOS), or press `i` for the iOS Simulator.
- On a **physical device**, set `EXPO_PUBLIC_API_BASE_URL` to your Mac's LAN IP (e.g. `http://192.168.1.x:8000`) — `localhost` won't resolve from the phone.
- Grant camera permission when prompted; the screen shows the yellow cover reticle and the dashed cyan spine strip.

## 5. Full flow to try

1. Start the backend, then the Expo app.
2. **Scan** tab → photograph the front, back and spine (back and spine can be skipped) → `/vision/grade` returns the best identification plus up to two alternatives, the grade range and per-area scores → on **Is this your book?** pick the right one or type it in (the value is re-priced) → **Add to Vault** saves the book with its report and uploads the front photo as the cover.
3. **Collection** tab → your scan is grouped by publisher with its grade badge.
4. Tap a comic → **log price points** → the timeline and value delta update.
5. **Dashboard** tab → total collection value, average grade, gem-tier count, top holdings.

## Notes / limitations

- Vision **mock** mode returns plausible synthetic results. Set `VISION_PROVIDER=claude` (or `openai`) for real identification and grading.
- RLS policies restrict each user to their own rows; the backend uses the service-role key, so it bypasses RLS by design.
- Sign-in uses Supabase email + password (an email code is optional once custom SMTP is set up) and is required whenever the app points at a real Supabase project. The backend verifies tokens against the project's public signing keys. With the placeholder Supabase config, sign-in is skipped and the backend falls back to `DEV_USER_ID` (only while `AUTH_REQUIRED=false`).
- Raw values come from a sample (mock) provider until a real raw-comps source is chosen; the app labels them as sample estimates.
- Books from the backend have no `cover_palette`, so books without a cover photo show the default placeholder colors.