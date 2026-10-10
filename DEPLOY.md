# Dama Drop — deploy guide

Your kendama stock tracker, on a real public link in about 10 minutes.
No terminal needed — everything happens in your browser.

## What you need (all free)

1. A GitHub account — [github.com](https://github.com) → Sign up
2. A Render account — [render.com](https://render.com) → sign up **with GitHub** (one click)
3. The `dama-drop.zip` file (it has the whole site + today's real stock data baked in)

## Steps

### 1. Put the code on GitHub
1. Unzip `dama-drop.zip` on your phone/computer.
2. Go to [github.com/new](https://github.com/new), name the repository `dama-drop`, leave it Public, click **Create repository**.
3. Click **uploading an existing file**, drag in everything from the unzipped folder, then **Commit changes**.

### 2. Deploy on Render
1. In the Render dashboard click **New +** → **Blueprint**.
2. Connect your `dama-drop` repository and click **Apply**.
3. Render builds the site (takes ~2 minutes) and gives you a public link like `https://dama-drop.onrender.com`. That's your site — share it with anyone.

### 3. Turn on email alerts (whenever you're ready)
The site collects signups from day one. To actually *send* the alert emails:
1. Make a free account at [resend.com](https://resend.com) and copy your API key (starts with `re_`).
2. In Render, open your `dama-drop` service → **Environment** → add:
   - `RESEND_API_KEY` = your key
   - `OWNER_EMAIL` = your email
3. Save — Render redeploys automatically and alerts start flowing.

## How it works
- The site checks Sweets, KROM, Grain Theory, and Erratic's stores **every hour** for restocks and new drops.
- Kendama USA's section links straight to their shop (their site blocks automatic stock checks).
- Free Render servers "sleep" after 15 minutes of no visitors — the first visit may take ~30–60 seconds to wake up, then it's fast.

## Fine print
- On Render's free plan, the subscriber list lives in a small database file that can reset if the service is ever fully rebuilt. Fine for starting out; a free Postgres upgrade fixes it permanently if the list grows.
