# Going live: the steps that need your accounts

The code side is done: sign-in, scan confirmation, sample-price labels and automatic checks. What's left needs your accounts, your API key or your phone. Work through these in order; each one ends with a check that it worked.

## 1. Supabase project (about 15 minutes)

1. Create a free project at supabase.com. From **Project Settings → API**, copy the **Project URL**, **anon key** and **service_role key**.
2. In the **SQL editor**, run the migrations in order: `supabase/migrations/001` through `005`.
3. **Make sign-in emails send a code.** The app signs in with a 6-digit code, not a link. Under **Authentication → Emails → Templates**, edit **Magic Link** so the body includes the code, for example:
   `Your ComicGrade AI sign-in code is {{ .Token }}`
4. Sign in to the app once with your email (step 3 below creates the user). Then copy your user id from **Authentication → Users**.
5. Optional: load the demo collection into your account:
   `cd backend && python scripts/seed_demo.py --user-id <your user id> --fill-runs`
   Seeded prices are labelled "sample", and the app shows them as sample estimates.

Check: the **comics** table has rows for your user id.

## 2. Backend hosting

Any container host works (Render, Fly.io, Railway, Cloud Run). Point it at `backend/Dockerfile`; it listens on `$PORT`. Set these environment variables in the host's dashboard. They are secrets: never commit them.

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key |
| `SUPABASE_ANON_KEY` | anon key |
| `AUTH_REQUIRED` | `true` |
| `VISION_PROVIDER` | `claude` |
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `CRON_SECRET` | any long random string |

Leave `DEV_USER_ID` unset in production.

Nightly value snapshots: schedule a daily call to `POST <backend>/portfolio/snapshot/all` with the header `X-Cron-Secret: <CRON_SECRET>`. Most hosts have a cron feature; a Supabase scheduled function also works.

Check: `GET <backend>/health` returns `{"status":"ok"}`, and `GET <backend>/comics` without a token returns 401.

## 3. App on your phone (Expo Go)

1. Install **Expo Go** on the phone.
2. In `frontend/.env`:
   ```
   EXPO_PUBLIC_SUPABASE_URL=<Project URL>
   EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon key>
   EXPO_PUBLIC_API_BASE_URL=<backend URL, https://...>
   ```
3. `cd frontend && npm install && npx expo start`, then scan the QR code with the phone.

Phone test checklist:
- [ ] Sign in with an email code; sign out from the Vault and sign back in.
- [ ] Scan a book: front, back and spine. Then scan another with front only.
- [ ] On "Is this your book?", pick an alternative, then try typing a book in by hand.
- [ ] Use at least two books **in bags or sleeves** and one in poor light: the benchmark photos are mostly clean scans.
- [ ] The book appears in the Vault with its grade breakdown and the cover photo.
- [ ] Note how long each scan takes from the last photo to the result.

## 4. Vision benchmark (on the Mac, about 11 API calls per run)

See `docs/vision-test-2026-11.md`. From `backend/`:

```bash
export ANTHROPIC_API_KEY=...
python -m eval.bench run --approach claude --effort low    --photos ~/workspace/goals/comicgrade-ai/test-photos
python -m eval.bench run --approach claude --effort medium --photos ~/workspace/goals/comicgrade-ai/test-photos
```

Commit the reports in `backend/eval/results/`. Before scoring, confirm the year for photo 09 (it looks like the 2024 Ultimate Spider-Man, not 2000).

## 5. Raw pricing (needs a decision)

Raw values come from the sample (mock) provider and are labelled as sample estimates in the app. A real raw-comps source needs a vendor or Comic Vine key, which waits for Beryl's go-ahead. Slabbed books use GoCollect when `GOCOLLECT_API_KEY` is set.
