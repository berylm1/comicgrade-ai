# Going live: the steps that need your accounts

The code side is done: sign-in, scan confirmation, sample-price labels and automatic checks. What's left needs your accounts, your API key or your phone. Work through these in order; each one ends with a check that it worked.

## 1. Supabase project (about 15 minutes)

1. Create a free project at supabase.com. From **Project Settings → API**, copy the **Project URL**, **anon key** and **service_role key**.
2. In the **SQL editor**, run the migrations in order: `supabase/migrations/001` through `005`.
3. **Sign-in.** The app signs in with **email + password**, which works with Supabase's default email settings. Two things to know about those defaults:
   - Supabase's built-in email sender only delivers to members of your Supabase team, a few emails an hour, and its templates can't be edited. That's fine for your own testing. For testers or prospects, set up your own email provider under **Authentication → Emails → SMTP Settings** (Resend, Postmark and others have free tiers).
   - New accounts must confirm their email. The confirmation link opens your **Site URL** (Authentication → URL Configuration), which defaults to `http://localhost:3000`, so the page may not load. The account is confirmed anyway; go back to the app and sign in.
   - Optional, once custom SMTP is set up: to also allow "email me a sign-in code", edit the **Magic Link** template to include `{{ .Token }}`.
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
| `SUPABASE_SERVICE_ROLE_KEY` | secret (service_role) key, `sb_secret_...` or the legacy JWT |
| `SUPABASE_ANON_KEY` | publishable (anon) key; optional for the backend |
| `AUTH_REQUIRED` | `true` |
| `VISION_PROVIDER` | `claude` |
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `CRON_SECRET` | any long random string |

Leave `DEV_USER_ID` unset in production.

Nightly value snapshots: schedule a daily call to `POST <backend>/portfolio/snapshot/all` with the header `X-Cron-Secret: <CRON_SECRET>`. Most hosts have a cron feature; a Supabase scheduled function also works.

Check: `GET <backend>/health` returns `{"status":"ok"}`, and `GET <backend>/comics` without a token returns 401.

How the backend checks sign-ins: it verifies each user's token against the project's public signing keys (`/auth/v1/.well-known/jwks.json`), so it needs no extra secret. A signed-out user's token keeps working until it expires, about an hour.

## 3. App on your phone (Expo Go)

1. Install **Expo Go** on the phone.
2. In `frontend/.env`:
   ```
   EXPO_PUBLIC_SUPABASE_URL=<Project URL>
   EXPO_PUBLIC_SUPABASE_ANON_KEY=<publishable key, sb_publishable_...>
   EXPO_PUBLIC_API_BASE_URL=<backend URL, https://...>
   ```
3. `cd frontend && npm install && npx expo start`, then scan the QR code with the phone.

Phone test checklist:
- [ ] Create an account with email + password, confirm the email, sign in; sign out from the Vault and sign back in.
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
