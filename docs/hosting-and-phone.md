# Put ComicGrade AI online and use it on your phone

This guide gets the app running on your phone with no command line. When you're done you'll have two web addresses:

- **The backend** (`comicgrade-api`): the server that grades scans and stores your collection.
- **The app** (`comicgrade-app`): a web page you open in your phone's browser and can add to your home screen.

Both are hosted on [Render](https://render.com), which deploys straight from the GitHub repository. Time needed: about 20 minutes, most of it waiting for builds.

> **Why a web page and not Expo Go?** The app is built on Expo SDK 52, and the Expo Go app in the App Store only opens projects on recent SDKs (58 at the time of writing). Opened in the phone's browser, the same app works today, camera included, because Render serves it over HTTPS. Moving to a newer SDK, or building a real App Store app, is a separate step for later.

## What you need first

| Item | Where to find it |
|---|---|
| Supabase **Project URL** | Supabase → Project Settings → API |
| Supabase **publishable key** (`sb_publishable_...`) | Supabase → Project Settings → API Keys |
| Supabase **secret key** (`sb_secret_...`) | Same page. **Keep it private**: it only ever goes into Render's backend settings |
| Anthropic **API key** | [console.anthropic.com](https://console.anthropic.com) → API Keys. Each scan is one paid API call |
| A GitHub account with access to `berylm1/comicgrade-ai` | |

No Anthropic key yet? You can still deploy: set `VISION_PROVIDER` to `mock` in step 2. Scans then return **made-up sample results** for trying the flow only. Switch to `claude` once you have a key.

## 1. Create the two services from the blueprint

1. Sign up at [render.com](https://render.com) with your GitHub account.
2. Click **New → Blueprint**.
3. Connect GitHub if asked, and pick the **comicgrade-ai** repository.
4. For **Branch**, choose `feature/comicgrade-ai` (or `main` once the pull request is merged).
5. Render reads `render.yaml` and lists two services: `comicgrade-api` and `comicgrade-app`. It then asks for the values marked secret:

| Setting | What to enter |
|---|---|
| `SUPABASE_URL` (comicgrade-api) | your Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` (comicgrade-api) | your **secret** key |
| `ANTHROPIC_API_KEY` (comicgrade-api) | your Anthropic key (leave empty if using `mock`) |
| `EXPO_PUBLIC_SUPABASE_URL` (comicgrade-app) | your Project URL |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` (comicgrade-app) | your **publishable** key, never the secret one |
| `EXPO_PUBLIC_API_BASE_URL` (comicgrade-app) | type `https://placeholder` for now; you'll fix it in step 3 |

6. Click **Apply**. Both services start building.

## 2. Check the backend is up

1. Open **comicgrade-api** in Render and wait until it says **Live** (a few minutes).
2. Copy its address at the top of the page, for example `https://comicgrade-api.onrender.com`. Yours may have extra letters on the end.
3. Open that address followed by `/health` in a browser, e.g. `https://comicgrade-api.onrender.com/health`. You should see `{"status":"ok"}`.
4. Using mock scans for now? In **Environment**, change `VISION_PROVIDER` to `mock` and save.

> **Free plan note:** Render's free backend goes to sleep after about 15 minutes without use. The first request after that takes up to a minute while it wakes. If the app shows an error right after opening, wait a moment and pull down to refresh. A paid plan keeps it awake.

## 3. Point the app at the backend

1. Open **comicgrade-app** → **Environment**.
2. Set `EXPO_PUBLIC_API_BASE_URL` to the backend address from step 2: `https://...onrender.com` with no `/health` and no trailing slash.
3. Save, then click **Manual Deploy → Deploy latest commit**. This is needed because the address is built into the page.
4. When it says **Live**, copy the app's address, for example `https://comicgrade-app.onrender.com`.

## 4. Tell Supabase where the app lives

So that account-confirmation emails open the app instead of a dead `localhost` page:

1. In Supabase, open **Authentication → URL Configuration**.
2. Set **Site URL** to the app address from step 3.
3. Save.

## 5. Open it on your phone

1. On the phone, open the **app address** in Safari (iPhone) or Chrome (Android).
2. Sign in with the email and password of your account. Your demo collection of 72 books is already there.
3. Optional: add it to your home screen. In Safari: **Share → Add to Home Screen**. In Chrome: **⋮ → Add to Home screen**.
4. Go to **Scan**. When the browser asks for the camera, tap **Allow**.

### Phone test checklist

- [ ] Sign out from the Vault, then sign back in.
- [ ] Scan a book: front, back and spine. Then scan another with only the front.
- [ ] On **Is this your book?**, pick an alternative, then try typing a book in by hand.
- [ ] Scan at least two books **in bags or sleeves**, and one in poor light.
- [ ] The book appears in the Vault with its grade breakdown and cover photo.
- [ ] Roughly how long does each scan take from the last photo to the result?

Write down anything odd (wrong book, slow scan, error message) and share it: that's what decides what to fix next.

## Updating

Every push to the chosen branch redeploys both services automatically. Changing a setting in Render's **Environment** tab needs a manual deploy for the app (`EXPO_PUBLIC_*` values are built into the page); the backend picks up its settings on restart.

## If something goes wrong

| What you see | Likely cause and fix |
|---|---|
| App says "API 401" or keeps returning to sign-in | Sign out and back in. If it continues, check `SUPABASE_URL` on the backend matches the app's `EXPO_PUBLIC_SUPABASE_URL` |
| App says "API 503: Server is not connected to Supabase" | `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` missing or wrong on comicgrade-api |
| Network error or "Failed to fetch" | Backend asleep (wait a minute) or `EXPO_PUBLIC_API_BASE_URL` wrong (redo step 3) |
| "Grading failed: ANTHROPIC_API_KEY is missing or invalid" | Add the key on comicgrade-api, or set `VISION_PROVIDER` to `mock` |
| Camera never asks for permission | The page must be opened over `https://`. Check the phone's browser settings allow camera for the site |
| No confirmation email arrives | Supabase's built-in sender only mails members of your Supabase team, a few per hour. See [go-live.md](go-live.md) for custom email |

## What this does not cover yet

- **Nightly value snapshots.** The backend has the route; scheduling it needs a Render cron job (paid) or a Supabase scheduled function. Until then, value history comes from price records.
- **Real raw-book prices.** They're sample estimates, labelled as such in the app.
- **An App Store or Play Store app.** That needs an Expo SDK upgrade and an Apple or Google developer account.
