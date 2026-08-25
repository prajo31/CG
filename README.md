# Corporate Governance Analyzer

A Streamlit app for BA 435 that walks any publicly traded ticker through the Week 2 corporate governance framework:

1. **Corporate Governance** — voting structure, ownership structure, top shareholders, CEO/management, board of directors, compensation
2. **Bondholder Concerns** — debt type, covenants, default risk measures
3. **Financial Markets** — trading & liquidity, analyst following
4. **Society & Other Stakeholders** — employee satisfaction, reputation

Quantitative fields (price, market cap, shares outstanding, float, beta, ownership %, top institutional holders, analyst ratings/targets, debt/cash/EBITDA) are pulled **live** from Yahoo Finance via `yfinance` for whatever ticker you type in. Qualitative governance fields that require reading an actual filing — board composition, CEO background, pay mix, debt covenants, credit rating, employee sentiment, ESG narrative — aren't reliably available from a free API for an arbitrary company, so those are guided manual-entry fields. This mirrors the course's AI-assisted, human-verified research protocol: get a first-pass number fast, then verify it against a primary source (DEF 14A, 10-K, Glassdoor, a ratings agency) before treating it as final.

The **Report** tab compiles everything — live and manual — into a single Markdown report you can download.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Push to your GitHub account

From this folder:

```bash
git init
git add .
git commit -m "Initial commit: BA 435 corporate governance analyzer"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

(Create the empty repo first at github.com/new — don't initialize it with a README there, or the push will conflict.)

If you'd rather not use the command line: create the repo on github.com, then use the "Add file → Upload files" button on the repo page and drag in `app.py`, `requirements.txt`, and this `README.md`.

## Deploy for free on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **New app**, pick the repo you just pushed, branch `main`, and set the main file path to `app.py`.
3. Click **Deploy**. It builds from `requirements.txt` automatically and gives you a public URL (e.g. `your-app-name.streamlit.app`) within a couple of minutes.
4. Any time you push a new commit to `main`, the deployed app redeploys automatically.

## Using this with a class (~20 students)

Streamlit itself handles this fine — each student's browser tab gets its own session state, so their inputs never collide. The real constraint is Yahoo Finance: `yfinance` is an unofficial scraper with no rate-limit guarantees, and Streamlit Community Cloud's free tier shares a small pool of outbound IPs across many apps. If most students are on *different* tickers (the normal case, since this course assigns one company per student) and everyone clicks "Load" within the same minute — e.g., right as class starts — Yahoo can occasionally throttle a burst of first-time requests.

This version mitigates that two ways: a 4-hour cache (so reloading the same ticker never re-hits Yahoo), and a small retry-with-backoff on the main data call. It cannot fully eliminate the risk. If a student sees the "Yahoo Finance didn't respond" warning, waiting 30-60 seconds and clicking **Load / Refresh Live Data** again usually clears it — and the manual-entry fields in every tab work regardless of whether the live pull succeeded. For an in-class exercise, it's worth telling students up front that a transient warning is expected behavior, not a broken app.

## Notes / known limitations

- Yahoo Finance data (via `yfinance`) is free but unofficial — fields occasionally go missing for a given ticker, and the service can rate-limit or briefly go down. The app is written to degrade gracefully (shows "Not available" or a retry warning rather than crashing) if that happens.
- Board of directors, CEO background, compensation mix, debt covenants, credit ratings, employee sentiment, and ESG narrative are **not** filled in automatically for any ticker — that's by design, not a bug. Free financial-data APIs don't expose this from a proxy statement or 10-K in a structured way, so the app leaves guided fields for you to fill in after doing that research yourself.
- Manual entries reset if you reload the page (they live only in the browser session's memory) — download the Report tab's Markdown file before closing the tab if you want to keep your work.
