# APilot

**Ask anything. Discover APIs. Visualize real data.**

APilot is an experimental **English-only** full-stack app powered by OpenAI. You ask a question in plain language. The agent then:

1. picks read-only public APIs from the [public-apis catalog](https://github.com/public-apis/public-apis);
2. reads their documentation;
3. fetches real JSON;
4. builds an interactive dashboard from that data.

An **Agent X-Ray** trace shows every step as it happens.

![Status](https://img.shields.io/badge/status-experimental-purple) ![Python](https://img.shields.io/badge/python-3.11-blue) ![React](https://img.shields.io/badge/react-18-blue)

## Features

**Agent**
- Uses only catalog entries listed as **No Auth** and **HTTPS**.
- Natural-language API discovery with OpenAI.
- Reads provider documentation, then calls the API with a constrained, read-only GET tool.
- Analyst stage that checks whether the returned JSON actually answers the question.
- Separate **Generative UI** stage that returns a JSON dashboard definition, never executable HTML or JavaScript.
- Fail-closed verification (see [Verification and failure behavior](#verification-and-failure-behavior)).

**Interface**
- Responsive React UI: stat cards, charts, sortable tables, a results dialog and a raw JSON view.
- **Agent X-Ray** streams live while the agent works, with a Cancel button.
- Export dashboards as PNG or JSON.
- Saved dashboards, stored in the browser, with search, refresh and delete.
- API Roulette for random provider experiments.
- Light and dark themes. The default follows the system setting; a Light / System / Dark toggle sits in the top bar.

**Operations**
- Optional site access passphrase, to limit misuse of your OpenAI API credits.
- Dockerfile, Render Blueprint, and GitHub Actions checks.

**Scope:** this is a learning-oriented MVP. It cannot use every API:
- many providers have incomplete docs, broken links, rate limits or nonstandard authentication;
- some questions cannot be answered from public API data at all.

When no provider works, the app reports a failure rather than inventing observations.

## How it works

A request moves through these steps. Each one is logged to Agent X-Ray.

1. **Catalog.** Parses the public-apis README and keeps No Auth + HTTPS entries. The catalog is cached for 6 hours.
2. **Discovery.** The model turns the question into English keywords and picks a topic.
   - **Curated providers first.** `backend/registry.py` lists reliable keyless providers with hand-written docs and exact URL templates: Open-Meteo, CoinGecko, REST Countries, World Bank, Hacker News, Launch Library 2, PokéAPI, Open Library, USGS, Frankfurter and GitHub. They are matched by the topic and by keywords (English and Hebrew), and tried first.
   - **The catalog is the fallback.** It is ranked by embedding similarity of each API's *description* (names are often misleading), and keyword ranking is used if embeddings fail. Without a curated match, the model picks the 3 most suitable of the top 22.
   - When a provider is named explicitly (example cards, API Roulette), this step is skipped.
   - Catalog providers whose docs cannot be read are skipped for 24 hours.
3. **Documentation.** Curated providers use their own docs. Otherwise the provider's docs page is fetched, and API hosts linked from it are collected.
4. **Data.** The agent calls a single `http_get` tool for up to 4 rounds.
   - Every request is checked against the question's period before it is sent. A forecast question cannot use an archive endpoint or only past dates, and a question about the past cannot use only future dates.
   - If a request fails, the API's own error message is passed back to the agent, e.g. `Timezone is required`. The agent can then correct its parameters.
   - Identical requests are served from a 10-minute cache.
5. **Validation and analysis.**
   - The response is checked for error flags and empty data.
   - The analyst model must confirm that the data covers the requested place, metric and period.
6. **Dashboard.** A second model designs the dashboard as JSON. The server sanitizes it and checks every number against the returned data.

If any step fails, APilot moves on to the next provider, up to 5 in total. If a provider has not finished within 8 seconds, the next one starts alongside it, and the first verified result wins. When every provider fails, the user sees a short message with a **Try again** button; the raw reasons are under *Technical details*.

All model calls use temperature 0, so the same question gives the same choices.

## Verification and failure behavior

APilot uses a **fail-closed** result pipeline: a JSON response alone does not prove that an API request worked.

1. Reject `success: false`, `status: error`, deprecation messages, non-JSON responses and empty result collections.
2. Ask the analyst model whether the returned data actually covers the requested metric, geography and period. If not, try another API.
3. Reject dashboard numbers that are absent from the returned JSON. Displayed rounding is allowed, and so are scaled forms at the displayed precision: 136410000000 may appear as `$136.4B`, and 0.0523 as `5.2%`. Numbers in the request URL (e.g. `date=2004:2023`) count as sourced.
   - The models see only a truncated sample of the response. Counts, totals, averages, minimums and maximums are therefore computed by code from the full response, given to the models as **computed facts**, and accepted by the check. A count the model works out itself is a guess and is rejected.
   - If a dashboard contains an unsourced number, the design model gets one chance to redesign it, told exactly which number failed. A second failure moves on to the next provider.
   - Dates are checked as dates, not as measurements. A date passes if the JSON contains it (as a date string or an epoch timestamp), or if it falls between 8 days ago and tomorrow, which covers "today", "yesterday" and "past week" in any time zone. Any other date is rejected.
   - Times of day such as `14:00` are treated as labels.
4. Only then return `verified: true` to the UI. The frontend refuses to show older, unverified saved results as live dashboards.
5. When every provider fails, show an error instead of an invented dashboard. Agent X-Ray includes the reason for each retry.

**Limits of verification:**
- `verified: true` means the response passed automated provenance checks. It does not mean the measurements were independently audited.
- The numeric check can also reject some legitimate transformations, and the model can misinterpret complex responses.
- The checks deliberately prefer false negatives over fabricated dashboards.

## Example questions

The four example cards on the home page are each **pinned** to one API, so they skip the keyword-ranking step. All four were verified end to end on a deployed instance:

| Question | API |
|---|---|
| Which earthquakes of magnitude 5 or more happened worldwide in the past week? | USGS Earthquake Hazards Program |
| List 10 Isaac Asimov books with their first publication years | Open Library |
| What are the 5 most-starred Python repositories on GitHub? | GithubTrends |
| What is today's US dollar exchange rate against EUR, GBP and JPY? | Frankfurter |

When you change the examples, keep each one to a stable provider and a question that produces a small response (under 750 KB). Open-Meteo, crypto and SpaceX providers have been unreliable as examples.

## Run locally

1. Install Python 3.11+, Node.js 20+ and npm.
2. Create a virtual environment and install the backend dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   pip install -r backend/requirements.txt
   ```
3. Set `OPENAI_API_KEY` as an environment variable (see [Configuration](#configuration) and `.env.example`). `APP_ACCESS_KEY` is optional.
4. Start the API:

   ```bash
   uvicorn main:app --app-dir backend --reload --port 8000
   ```
5. In another shell, start the React frontend:

   ```bash
   cd frontend
   npm install --no-audit --no-fund
   npm run dev
   ```
6. Open `http://localhost:5173`. The dev server proxies `/api` to the backend.

## Tests

```bash
pip install pytest
pytest -q backend                      # backend unit tests
cd frontend && npm run build           # type-check and production build
```

The backend tests run without network access or an OpenAI key; HTTP and the model are stubbed. They cover:
- catalog filtering and URL safety;
- redirects and agent retries;
- streaming;
- payload validation and dashboard number checks;
- curated provider selection, period checks, hedged providers, rate limits and static files.

GitHub Actions runs both commands on every push and pull request.

**Acceptance test against a deployed site.** `scripts/qa_acceptance.py` asks 15 questions across all curated topics. For each one it checks that the answer is verified, arrives within 20 seconds, and that a forecast question used future dates. It uses only the standard library:

```bash
python scripts/qa_acceptance.py https://your-app.onrender.com --key YOUR_APP_ACCESS_KEY
```

Each question costs several OpenAI calls, and a second full run within an hour needs a `RATE_LIMIT_PER_HOUR` above 15.

## Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Your OpenAI API key. Keep it on the server; never commit it or expose it to the frontend. |
| `AGENT_MODEL` | No | `gpt-4.1-mini` | Model for discovery, the data agent and the analyst. |
| `UI_MODEL` | No | `gpt-4.1-mini` | Model that designs the dashboard. |
| `APP_ACCESS_KEY` | Recommended | — | Site passphrase. When set, asking and API Roulette require it; users enter it on the home page. |
| `RATE_LIMIT_PER_HOUR` | No | `20` | Questions per client per hour. |
| `DAILY_REQUEST_CAP` | No | `300` | Questions per day across all clients, to cap OpenAI spend. |
| `EMBED_MODEL` | No | `text-embedding-3-small` | Embedding model for ranking the catalog. |

If OpenAI rejects requests, check your API billing, model access and environment variables. A ChatGPT subscription is separate from API billing.

## Deploy to Render

The recommended setup is a **Render Docker Web Service**: a single service that builds both Node and Python.

1. Push this repository to GitHub.
2. In [Render](https://dashboard.render.com), choose **New > Web Service**, connect the repo and select the Docker runtime. The `Dockerfile` builds the React app, copies it into FastAPI, and starts Uvicorn.
3. Add the environment variables from [Configuration](#configuration).
4. Deploy, then open `/api/health`. It reports the configuration status without revealing secrets.
5. Open the home page, enter your `APP_ACCESS_KEY` if you set one, and ask a question.

Alternatively, deploy with **New > Blueprint**: `render.yaml` uses the same Dockerfile and generates a random `APP_ACCESS_KEY`. Render's plans and options change over time, so review the dashboard when you deploy.

## API endpoints

| Method | Path | Access key | Description |
|---|---|---|---|
| `GET` | `/api/health` | No | Status, whether OpenAI is configured, and whether the site is protected. |
| `GET` | `/api/catalog/stats` | No | Number of indexed APIs and categories. |
| `GET` | `/api/roulette` | Yes | A random catalog entry. |
| `POST` | `/api/ask` | Yes | `{question, forced_api?}` → the final result. |
| `POST` | `/api/ask/stream` | Yes | Same input. Streams Server-Sent Events: `trace` while working, then `result`, or `error` with a short `detail` and the raw `technical` text. |

Both ask endpoints are rate limited (see [Configuration](#configuration)) and return 429 when a limit is reached.

The access key is sent in the `X-APilot-Key` header. Interactive OpenAPI docs are served at `/api/docs`.

## Project structure

```
backend/
  main.py             catalog, ranking, safe HTTP client, agent orchestration, rate limits, API routes
  registry.py         curated providers: docs, URL templates and allowed hosts
  validation.py       fail-closed payload checks, period checks and dashboard number verification
  test_main.py        safety, redirects, agent retries, streaming, chart sanitizing
  test_validation.py  rejected/accepted payloads and number checks
frontend/src/
  App.tsx             app state, asking (live stream with fallback), saved results, theme
  components/         sidebar, explore page, live progress, result dialog, dashboard blocks,
                      JSON viewer, theme toggle, toast
  lib/                API client and SSE parser, progress stages, formatting,
                      safe browser storage, theme, dialog behaviour
  styles.css          design tokens (light and dark) and responsive layout
frontend/public/      favicon, robots.txt and the link-preview image
scripts/
  qa_acceptance.py    acceptance test against a deployed site
```

## Security and limitations

This is an **experimental developer app**. Several measures reduce exposure:

- **Read-only access:** HTTPS-only `GET` requests on port 443, with no credentials sent.
- **Address checks:** every target, including **every redirect hop** (up to 4), must resolve to a public IP. IP literals and private hostnames are blocked.
- **Provider boundary:** data calls are limited to the selected provider's domain, plus API hosts linked from its documentation or listed for a curated provider.
- **Spend limits:** per-client hourly limits and a daily cap on questions. Set `APP_ACCESS_KEY` on any public deployment.
- **Response limits:** 750 KB maximum size, a 15 s timeout, and only text, JSON, XML or YAML content types.

None of this replaces a production-grade egress proxy with pinned DNS/IP routing and an explicit provider allowlist. Treat scraped documentation and third-party API responses as untrusted. Do not store sensitive data here, and do not expose it to public or untrusted users without a further security review.

Only APIs catalogued as no-auth are considered, and provider documentation and terms can change. Some providers publish data with a delay, and "yesterday" may mean a different calendar date in the target location.

## Planned experiments (not in the MVP)

API Mashup, API Battle Arena, live world explorer, data detective, prompt-to-mini-app interactions, recurring monitors, richer semantic search, and capability caching. These are intentionally not claimed as implemented yet.

## License

MIT. See [LICENSE](LICENSE).
