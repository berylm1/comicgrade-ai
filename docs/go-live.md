# Going live: the steps that need your accounts

The code side is done: sign-in, scan confirmation, sample-price labels and automatic checks. What's left needs your accounts, your API key or your phone. Work through these in order; each one ends with a check that it worked.

Status (Nov 22, 2026): step 1 is done: migrations 001 to 006 run (nightly snapshots verified), the owner account created and the demo collection loaded (72 books). The backend was checked end to end against it. Next: step 2.

## 1. Supabase project (about 15 minutes)

1. Create a free project at supabase.com. From **Project Settings → API**, copy the **Project URL**, **anon key** and **service_role key**.
2. In the **SQL editor**, run the migrations in order: `supabase/migrations/001` through `006`.
3. **Sign-in.** The app signs in with **email + password**, which works with Supabase's default email settings. Two things to know about those defaults:
   - Supabase's built-in email sender only delivers to members of your Supabase team, a few emails an hour, and its templates can't be edited. That's fine for your own testing. For testers or prospects, set up your own email provider under **Authentication → Emails → SMTP Settings** (Resend, Postmark and others have free tiers).
   - New accounts must confirm their email. The confirmation link opens your **Site URL** (Authentication → URL Configuration), which defaults to `http://localhost:3000`, so the page may not load. The account is confirmed anyway; go back to the app and sign in.
   - Optional, once custom SMTP is set up: to also allow "email me a sign-in code", edit the **Magic Link** template to include `{{ .Token }}`.
4. Create your account in the app (email + password), confirm the email, then copy your user id from **Authentication → Users**.
5. Optional: load the demo collection into your account:
   `cd backend && python scripts/seed_demo.py --user-id <your user id> --fill-runs`
   Seeded prices are labelled "sample", and the app shows them as sample estimates.

Check: the **comics** table has rows for your user id.

## 2. Hosting and phone testing

Follow **[hosting-and-phone.md](hosting-and-phone.md)**. It deploys the backend and the app as a web page on Render from `render.yaml`, with no command line, and ends with the phone test checklist.

Settings the backend needs, for any host (Render asks for them from the blueprint). They are secrets: never commit them.

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | secret key, `sb_secret_...` (or a legacy service_role JWT) |
| `AUTH_REQUIRED` | `true` |
| `VISION_PROVIDER` | `claude` (or `mock` for made-up sample results) |
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `CRON_SECRET` | any long random string |

Leave `DEV_USER_ID` unset in production. The backend verifies each user's token against the project's public signing keys (`/auth/v1/.well-known/jwks.json`), so it needs no extra secret. A signed-out user's token keeps working until it expires, about an hour.

Nightly value snapshots: run `supabase/migrations/006_nightly_snapshots.sql` in the SQL editor. It schedules a job inside Supabase (pg_cron) that records every collection's value at 06:17 UTC each night, so no external cron job is needed. (`POST <backend>/portfolio/snapshot/all` with `X-Cron-Secret` still works for other setups.)

**Why not Expo Go?** The app is on Expo SDK 52; the App Store's Expo Go only opens recent SDKs (58 now). The hosted web page works on the phone today. An SDK upgrade comes before an App Store build.

## 3. Vision benchmark (on the Mac, about 11 API calls per run)

See `docs/vision-test-2026-11.md`. From `backend/`:

```bash
export ANTHROPIC_API_KEY=...
python -m eval.bench run --approach claude --effort low    --photos ~/workspace/goals/comicgrade-ai/test-photos
python -m eval.bench run --approach claude --effort medium --photos ~/workspace/goals/comicgrade-ai/test-photos
```

Commit the reports in `backend/eval/results/`. Before scoring, confirm the year for photo 09 (it looks like the 2024 Ultimate Spider-Man, not 2000).

## 4. Raw pricing (needs a decision)

Raw values come from the sample (mock) provider and are labelled as sample estimates in the app. A real raw-comps source needs a vendor or Comic Vine key, which waits for Beryl's go-ahead. Slabbed books use GoCollect when `GOCOLLECT_API_KEY` is set.
