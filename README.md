# APilot

**Ask anything. Discover APIs. Visualize real data.**

APilot is an experimental **English-only** full-stack application powered by OpenAI. It selects read-only public APIs from the [public-apis catalog](https://github.com/public-apis/public-apis), reads provider documentation, attempts to retrieve actual JSON data, and creates a custom interactive dashboard. It includes an **Agent X-Ray** trace for understanding what happened.

![Status](https://img.shields.io/badge/status-experimental-purple) ![Python](https://img.shields.io/badge/python-3.11-blue) ![React](https://img.shields.io/badge/react-18-blue)

## MVP Features

- Public APIs catalog ingestion (filters for entries listed as **No Auth** and **HTTPS**).
- Natural-language API discovery with OpenAI.
- Documentation reading and constrained, read-only API tool calls.
- Analyst stage that summarizes returned JSON and identifies data limitations.
- Separate **Generative UI** stage that returns JSON dashboard definitions — not executable AI-generated HTML or JavaScript.
- Responsive React UI with cards, charts, sortable tables, a results popup, and **Agent X-Ray** streamed live while the agent works (with cancel).
- Export dashboards as PNG or JSON; search, refresh and delete saved dashboards.
- Light and dark themes: follows the system setting by default, with a Light / System / Dark toggle in the top bar.
- API Roulette (random provider experiments) and browser-local saved dashboards.
- Optional site access passphrase to reduce misuse of your OpenAI API credits.
- Dockerfile and Render blueprint, plus GitHub Actions checks.

**Scope:** This is a learning-oriented MVP, not a guarantee that any arbitrary API can be used. Many providers have incomplete docs, broken links, rate limits, or nonstandard authentication. Some questions cannot be answered from public API data. The app retries selected providers and reports a failure rather than inventing observations. Generative explanations and chart values are model-created from sampled API data and are **not independently certified**; check source data for high-stakes decisions.

## Verification and failure behavior

APilot uses a **fail-closed** result pipeline. A JSON response is not sufficient proof that an API request worked.

1. Reject `success: false`, `status: error`, deprecation messages, non-JSON responses, and empty result collections.
2. Ask the analyst model whether the returned data actually covers the requested metric, geography, and period. If not, try another API.
3. Reject generated dashboard numbers that are absent from the returned JSON (except displayed rounding or exact record counts).
4. Only then return `verified: true` to the UI. The frontend refuses to display older unverified saved results as live dashboards.
5. After failed providers, present an error instead of an invented dashboard. Agent X-Ray includes retry reasons.

**Limits:** `verified: true` means the response passed automated provenance checks, not that its measurements are independently audited. Numeric checks can also reject some legitimate transformations and the model can misinterpret complex responses. Real provider acceptance tests are still needed. These stricter checks deliberately prefer false negatives over fabricated dashboards.

## Run locally

1. Install Python 3.11+, Node.js 20+, and npm.
2. Create a virtual environment and install backend dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\\Scripts\\activate
   pip install -r backend/requirements.txt
   ```
3. Export `OPENAI_API_KEY` as an environment variable (copy `.env.example` for reference). Optionally set `APP_ACCESS_KEY`.
4. Start the API:

   ```bash
   uvicorn main:app --app-dir backend --reload --port 8000
   ```
5. In another shell, run the React frontend:

   ```bash
   cd frontend
   npm install --no-audit --no-fund
   npm run dev
   ```
6. Open `http://localhost:5173`. The development server proxies `/api` to the backend.

Example question: `Which earthquakes of magnitude 5 or more happened worldwide in the past week?`

## Deploy to Render

**Recommended: Render Docker Web Service** (reliable single-service Node + Python build).

1. Push this repository to GitHub.
2. In [Render](https://dashboard.render.com), select **New > Web Service**, connect the repo, and choose the Docker runtime. The included `Dockerfile` builds React, copies the compiled static assets into FastAPI, and starts Uvicorn.
3. Add environment variables:

   | Key | Value |
   |---|---|
   | `OPENAI_API_KEY` | Your private OpenAI API key. Never expose it in GitHub or frontend. |
   | `AGENT_MODEL` | `gpt-4.1-mini` (or any compatible OpenAI model) |
   | `UI_MODEL` | `gpt-4.1-mini` |
   | `APP_ACCESS_KEY` | Your random private site passphrase (**recommended**). |

4. Deploy and visit `/api/health`. It returns configuration status without disclosing secrets.
5. Load the home page, enter your `APP_ACCESS_KEY` if enabled, and ask a question.

`render.yaml` is a Render Blueprint using the same Dockerfile. You can deploy with **New > Blueprint** instead of manually selecting a Web Service. Render may change plans and environment capabilities; review its dashboard when deploying.

If OpenAI rejects requests, verify API billing, available model access, and environment variables. A ChatGPT subscription is separate from API billing.

## Key internals

- `backend/main.py`: catalog parsing, provider ranking, OpenAI orchestration, constrained GET tool, UI schema sanitizer, API.
  `POST /api/ask/stream` streams Agent X-Ray events as Server-Sent Events while the agent works; `POST /api/ask` returns only the final result.
- `frontend/src/App.tsx`: app state, asking (live stream with a fallback to estimated progress), saved results.
- `frontend/src/components/`: sidebar, explore page, live progress panel, result dialog, dashboard blocks, JSON viewer, toast.
- `frontend/src/lib/`: API client and SSE parser, progress stages, formatting, safe browser storage, dialog behaviour.
- `frontend/src/styles.css`: design tokens and responsive design.
- `backend/test_main.py`: no-auth filter, safety, chart sanitizing and streaming tests.

### Security and limitations

This is an **experimental developer app**. HTTPS and public-address checks, a provider-host restriction, disabled redirects, response size/time limits, and read-only GET requests reduce exposure. They do not replace a production-grade egress proxy with pinned DNS/IP routing and an explicit provider allowlist. Treat scraped documentation and third-party API responses as untrusted. Do not store sensitive data or use this without additional security review for public/untrusted users.

By default, only APIs catalogued as no-auth are considered. Provider documentation and terms may change. Some providers use data with delays, and "yesterday" may mean a different calendar date in the target locale.

### Planned experiments (not in the MVP)

API Mashup, API Battle Arena, live world explorer, data detective, prompt-to-mini-app interactions, recurring monitors, richer semantic search, and capability caching. These are intentionally not claimed as implemented yet.

## License

MIT — see LICENSE.
