# ComicGrade AI

A mobile-first **comic book valuation & grading** prototype.

- **Frontend:** React Native (Expo) with a dark "comic pop" theme via NativeWind (Tailwind CSS)
- **Backend:** Python FastAPI — image routing, AI vision pipeline (mock or OpenAI), Supabase access
- **Database:** Supabase (PostgreSQL) — `profiles`, `comics`, `price_history` + public `cover-images` storage bucket

```
comicgrade-ai/
├── frontend/                  # Expo React Native app
│   ├── App.tsx                # Bottom-tab nav: Scan / Collection / Dashboard
│   ├── tailwind.config.js     # Comic-pop dark palette
│   └── src/
│       ├── lib/               # Supabase client, FastAPI client, env
│       ├── components/        # Grade badges, stat chips, loading states
│       └── screens/
│           ├── CameraScreen.tsx          # Framed cover/spine capture → vision → upload
│           ├── CollectionScreen.tsx      # Scanned collection grouped by publisher
│           ├── DashboardScreen.tsx       # Valuation dashboard (total value, avg grade, top holdings)
│           └── ComicDetailScreen.tsx     # Detail + price history + manual price logging
├── backend/                   # FastAPI server
│   └── app/
│       ├── main.py            # App entry (CORS, routers, /health)
│       ├── config.py          # .env settings
│       ├── supabase_client.py # Service-role Supabase client
│       ├── schemas.py         # Pydantic models
│       └── routers/
│           ├── vision.py      # POST /vision/analyze — mock or OpenAI vision grading
│           └── comics.py      # CRUD, price history, cover upload to Storage
└── supabase/migrations/       # SQL schema + storage bucket policies
    ├── 001_initial_schema.sql
    └── 002_storage_bucket.sql
```

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

   (Or use the Supabase CLI: `supabase link --project-ref <ref> && supabase db push`.)
3. Create a test user under **Authentication → Users** (the backend accepts an optional `user_id` on comic creation).

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
- `GET /health` — liveness check
- `POST /vision/analyze` — accepts a multipart `image` upload, returns `{title, issue_number, publisher, tentative_grade, ...}`. Works out of the box with the **mock** provider; set `VISION_PROVIDER=openai` + `OPENAI_API_KEY` in `.env` for real vision grading.
- `POST /comics/{id}/prices?price=249.99&source=ebay` — logs a price point and updates `current_market_value`.

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
2. **Scan** tab → snap a cover → the vision route returns a title/issue + tentative CGC-style grade (e.g. **9.2**) → the image is saved to your photo library and uploaded to Supabase Storage, and the comic row is created via the backend.
3. **Collection** tab → your scan is grouped by publisher with its grade badge.
4. Tap a comic → **log price points** → the timeline and value delta update.
5. **Dashboard** tab → total collection value, average grade, gem-tier count, top holdings.

## Notes / limitations

- Vision **mock** mode returns plausible synthetic results — swap in `VISION_PROVIDER=openai` for real identification.
- RLS policies restrict each user to their own rows; the backend uses the service-role key, so it bypasses RLS by design.
- Prototype only: no auth UI yet (sign-in with Supabase Auth is the natural next step), grade estimate is a single float rather than a graded slab record.