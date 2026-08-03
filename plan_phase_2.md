# Phase 2 Implementation Plan — PolliSync

> **Goal:** Upgrade the hackathon MVP into a production-style system: Supabase Postgres, multi-level caching (L1 in-memory + L2 Redis), background data sync (Celery), circuit breaker fault tolerance, live Sentinel-2 NDVI, Google Pollen API, Supabase RAG knowledge base, full AI-assistant data access, Google Auth audit, and deployment.

> **Working style:** Implement one module at a time, test it, then move to the next. Never start the next module before the current one is fully tested and committed.

---

## What we are NOT doing in Phase 2

- Adding more crops (staying with the existing crop set)
- Yield prediction
- PWA
- IoT integration
- Rebuilding the Supabase/Postgres DB setup from scratch (already exists — we verify/configure it)
- Fixing Google Pollen API code if the key is missing or the fetch errors (just add the code + env var; it must fall back to the seasonal table)

---

## Module execution order

| # | Module | Status |
|---|--------|--------|
| M1 | Supabase / Postgres — verify & switch | Not Started |
| M2 | Two-level caching (L1 in-memory + L2 Redis) | Not Started |
| M3 | Background scheduler (Celery + Beat, 30 min) | Not Started |
| M4 | Circuit breaker (3 fails / 5 min) | Not Started |
| M5 | Google Pollen API (minimal) | Not Started |
| M6 | Real NDVI — Sentinel-2 (verify) | Not Started |
| M7 | Supabase RAG knowledge base | Not Started |
| M8 | AI assistant full data access | Not Started |
| M9 | Google Auth audit & fixes | Not Started |
| M10 | Deployment & performance | Not Started |

Mark each ✅ Done / 🔄 In Progress / ⬜ Not Started as you work.

---

## Environment variables (used across Phase 2)

Add all of these to `backend/.env` (and mirror to `.env.example`):

```env
# M1 — Postgres
DATABASE_URL=postgresql://...   # Supabase Postgres connection string
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# M2 — Redis
REDIS_URL=redis://...            # Upstash rediss:// or local redis://

# M5 — Google Pollen API (leave blank if no key yet)
POLLEN_API_KEY=

# M6 — Earth Engine (NDVI)
EE_SERVICE_ACCOUNT=
EE_PRIVATE_KEY_FILE=

# Existing auth/LLM vars reused by M8/M9/M10
GEMINI_API_KEY=
LLM_API_KEY=
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_GOOGLE_REDIRECT_URI=
FIRST_PARTY_ORIGINS handling via FRONTEND_ORIGIN / CORS_ORIGINS
```

---

## M1 — Supabase / Postgres (VERIFY, don't rebuild)

The repo already has Supabase/Postgres scaffolding. Do NOT re-create it.

Existing pieces (confirmed):
- `backend/app/database.py` — SQLAlchemy engine auto-detects `postgresql://` vs `sqlite://` and applies the right `connect_args`, pool sizes, and skips the SQLite-only schema reconciliation
- `backend/requirements.txt` — `psycopg2-binary` and `supabase` are already present
- `backend/supabase/migrations/001_initial_schema.sql` — baseline DDL
- `backend/scripts/migrate_sqlite_to_supabase.py` — SQLite → Supabase data migration
- `backend/scripts/seed_embeddings.py` — RAG embedding seeder (used in M7)
- `backend/app/core/config.py` — reads `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`

### Tasks
1. Put the Supabase Postgres connection string into `DATABASE_URL` in `backend/.env`. Use the connection-pooler URL (`?sslmode=require`) or direct connection, whichever Supabase gives us.
2. Run the backend test suite against the new DB:
   - `..\.venv\Scripts\python.exe -m pytest`
   - Fix any test that assumed SQLite-specific behavior (e.g. `DATETIME` columns, `JSON`, booleans, empty-string geography).
3. In `backend/app/database.py`, `init_db()` creates tables automatically and seeds Maharashtra districts for both SQLite and Postgres — verify seeding runs on Supabase.
4. Run `backend/scripts/migrate_sqlite_to_supabase.py` (follow its CLI/output) to copy users, farms, predictions, weather cache, bee occurrences, etc.
5. Verify against Supabase directly:
   - Tables exist (`users`, `farms`, `predictions`, `weather_cache`, `bee_occurrences`, `team_members`, `notifications`, `notification_preferences`, `agent_rate_limit`, `districts`, `refreshtoken`, `revoked_token`...)
   - `GET /api/health` and a farm/prediction round-trip succeed via `GET /api/farms`, `POST /api/predictions`
6. Update `backend/.env.example` comments if the pooler URL format differs from the SQLite default.

### Success criteria
- Backend starts with `DATABASE_URL=postgresql://...` and all API endpoints work against Supabase.
- `pytest` passes against Postgres.
- Existing local data is migrated and visible.

---

## M2 — Two-level caching (L1 in-memory + L2 Redis)

Flowchart: request → L1 in-memory (5–15 min TTL) → L2 Redis (shared) → Supabase Postgres (miss). Target sub-500ms for cached responses.

### Dependency
Add to `backend/requirements.txt`:
```
redis>=5.0.0
```

### New/edited files
- `backend/app/core/cache.py` (new) — cache layer:
  - LRU/TTL in-memory cache (use `functools.lru_cache` + timestamps or a simple `dict` with `expires_at`), TTL 5–15 min per key.
  - Redis client lazy-initialized from `settings.redis_url`.
  - `get_value(key, group)`, `set_value(key, value, ttl)`, `delete_group(group)`.
  - Graceful degradation: if Redis is unreachable, fall through to in-memory, then DB.
- `backend/app/services/weather_service.py` — use cache before reading `weather_cache` table.
- `backend/app/services/bee_service.py` — cache GBIF lookups.
- `backend/app/services/environment_service.py` — cache NDVI / NASA POWER results.
- `backend/app/api/routes/dashboard` / `prediction_service` — cache summary reads.

### Tasks
1. Add `redis` to requirements; add `REDIS_URL` to config + `.env(.example)`.
2. Implement `cache.py` with key namespacing (`weather:{farm_id}`, `bees:{farm_id}`, `ndvi:{lat},{lon}`, `dash:{farm_id}`).
3. Wrap weather/bee/NDVI reads: L1 in-memory → L2 Redis → existing DB cache → live fetch (and backfill cache on fetch).
4. Invalidate/overwrite cache entries whenever fresh data is stored by the scheduler (M3).
5. Local Redis only — `docker run redis` or a local Redis install. If none available in the hackathon environment, keep L1-only and log a warning; do not block the whole module.

### Success criteria
- A repeated `GET /weather/current` and dashboard request comes back from cache (log the source: L1/L2/DB).
- Cache TTLs are honored (5–15 min).
- Redis goes down → app still serves from L1/DB with a logged warning.

---

## M3 — Background scheduler (Celery + Beat, every 30 min)

Flowchart: a scheduler every 30 min pulls fresh Open-Meteo, NASA POWER, and GBIF data into cache + Postgres ahead of user requests.

### Dependency
- Add to `backend/requirements.txt`: `celery[redis]>=5.3.0`

### New/edited files
- `backend/app/celery_app.py` (new) — Celery app, broker = `REDIS_URL`, default queue from Redis URL, `beat_schedule` with a 30-minute periodic task.
- `backend/app/tasks/data_refresh.py` (new) — Celery tasks:
  - `refresh_weather_batch()` — iterate active farms, call `services/weather_service.get_or_create_weather()` and cache results.
  - `refresh_ndvi_batch()` — recompute NDVI via `services/environment_service.fetch_ndvi()` and update `pollisync` features/cache.
  - `refresh_bees_batch()` — call `services/bee_service` for each farm, refresh cache.
  - Each task must be wrapped in try/except with stale-cache fallback (circuit breaker state is handled in M4).

### Tasks
1. Install Celery, create `celery_app.py` with beat schedule.
2. Update `backend/scripts/` or `README` / `SETUP.md` with worker start commands:
   - Worker: `celery -A app.celery_app.celery_app worker --loglevel=info` (placed accordingly from `backend/`).
   - Beat: `celery -A app.celery_app.celery_app beat --loglevel=info`.
   - In production (M10), both run on Render (one worker + one beat, or a single `--beat` worker), reading `REDIS_URL`.
3. Wire scheduler tasks to populate cache layers + DB.
4. If Redis/Celery is not available (dev), prediction endpoints still work on-demand (existing behavior) — graceful fallback.

### Success criteria
- On a local Redis, running worker + beat refreshes farm data every 30 min into Redis + `weather_cache`/`bee_occurrences`.
- Stale-in-the-face-of-crashfallback: if a batch task throws, no unhandled exceptions crash the worker and previously cached data still serves.

---

## M4 — Circuit breaker (3 fails / 5 min, then serve cached)

Flowchart: if an external API fails 3 times within 5 minutes, the circuit opens — stop calling it and serve cached data until the service recovers.

### New/edited files
- `backend/app/core/circuit_breaker.py` (new):
  - Per-service breaker keyed by name (e.g. `open-meteo`, `nasa-power`, `ee`, `gbif`, `gemini`, `pollen`).
  - States: `CLOSED` (normal) → `OPEN` after 3 failures inside a 5-min window → `HALF_OPEN` after a cooldown → one trial call, success closes / failure reopens.
  - Exposes an async decorator/helper: `async def protected_call(name, coro, *, fallback)` — on open circuit call `fallback` (cached data or mock/seasonal).
  - Store state in a thread-safe module-level dict, optionally mirrored to Redis if present.
- `backend/app/services/weather_service.py` — wrap Open-Meteo fetch.
- `backend/app/services/environment_service.py` — wrap NASA POWER + Earth Engine NDVI.
- `backend/app/services/bee_service.py` — wrap GBIF.
- `backend/app/agent/router.py` + `recommendation` — wrap Gemini calls.
- `backend/app/services/pollen_service.py` (from M5) — wrap Pollen API calls.

### Tasks
1. Implement circuit breaker with count-window + cooldown.
2. Instrument each external caller with the decorator and a fallback that returns the last-good cache or the seasonal/mock value.
3. Log state transitions (`circuit OPEN for open-meteo — serving cached`).

### Success criteria
- Simulate failures (bad URL / monkeypatched error): after 3 fails in 5 min the circuit opens and immediately falls back to cached data with no hang.
- After cooldown + a healthy call, circuit closes again.

---

## M5 — Google Pollen API (minimal)

Per your instruction: just add the env var + fetch code; if the key is missing or the fetch errors, leave it alone (fall back to the existing seasonal table). Do NOT keep debugging the fetch logic.

Existing: `backend/app/services/feature_engineering.py` has `SEASONAL_POLLEN` + `get_pollen_for_month()`; `environment_service.py` and `prediction_service.py` consume `pollen_tree/pollen_grass/pollen_weed`.

### Tasks
1. Add `POLLEN_API_KEY=...` to `backend/.env` and `backend/.env.example`.
2. New `backend/app/services/pollen_service.py`:
   - `async fetch_pollen(lat, lon, date)` — call the Google Pollen API with the key. See their v1 endpoint (`https://mypollen.googleapis.com/v1/...` or whichever endpoint the current API uses); if it uses a different URL inside the codebase, keep that.
   - Return `{"tree": x, "grass": y, "weed": z}` formatted to match the model's `pollen_*` features.
   - On any error (auth/rate-limit/empty) or when `POLLEN_API_KEY` is unset → **return the `SEASONAL_POLLEN` fallback** from `feature_engineering.get_pollen_for_month()`. Do not raise.
3. `get_environment_features()` / feature builder — prefer live pollen when it returns without error, else seasonal.
4. If the fetch code you write has an error you can't fix quickly, leave it with the fallback intact and move on. Mark `pollen_service` TODO in code if needed.

### Success criteria
- With a confirm key: prediction returns live pollen numbers.
- Without a key or on failure: app falls back silently to seasonal pollen; no crash, no log spam.

---

## M6 — Real NDVI — Sentinel-2 (verify existing)

Already implemented in `backend/app/services/environment_service.py`:
- `fetch_ndvi()` queries `COPERNICUS/S2_SR_HARMONIZED` via Google Earth Engine (threaded call), most-cloud-free, mean over 20-day window.
- Env vars `EE_SERVICE_ACCOUNT` / `EE_PRIVATE_KEY_FILE` are read directly from `os.getenv()` — add them to `settings` and `.env(.example)`.

### Tasks
1. Add `ee_system_account` / `ee_private_key_file` to `app/core/config.py` `Settings` and `.env(.example)`.
2. In `environment_service._init_earth_engine()`, prefer `settings.ee_*` instead of raw `os.getenv`.
3. Test with known coordinates (e.g. Nashik) — verify real NDVI returns a `-0.2..0.9` value.
4. Confirm fallback: when EE/creds unavailable or no clear scenes, `ndvi=None` and downstream code falls back to NASA POWER/seasonal NDVI.

### Success criteria
- Real Sentinel-2 NDVI flows into feature engineering for a test coordinate.
- Earth Engine down/not configured → prediction completes with cached/seasonal NDVI (no crash).

---

## M7 — Supabase RAG knowledge base

Flowchart requires RAG KB: agricultural best practices, crop info, research papers, farming guidelines. The agent already has a vector-store client.

Existing in code (confirmed):
- `backend/app/agent/embedder.py` — `SupabaseVectorStore` with `upsert_embeddings`, `search`, `ensure_table`, `count`, `delete_all`; uses `agent_knowledge` table + RPCs `upsert_embeddings`/`match_embeddings`, pgvector 768.
- `backend/scripts/seed_embeddings.py` — seeder.
- `backend/app/agent/router.py` — chat + search endpoints that call `store.search(...)` when `farm_data` present, and `search_knowledge` endpoint.

### Tasks
1. Ensure the `agent_knowledge` table + RPCs exist in Supabase (run `ensure_table` once, or apply the SQL in `supabase/migrations/`/docs).
2. Build a knowledge base (markdown/text documents): crop-specific guides (mustard, wheat, sunflower, rice, cotton), general pollination best practices, risk-mitigation advice. Put sources in `backend/data/knowledge/` (or `docs/knowledge/`).
3. Run `seed_embeddings.py` (from `backend/`) so embeddings land in Supabase. Verify `count()` returns> 5 chunks.
4. Confirm agent chat injects RAG context (it already queries `store.search(query_vec, top_k=3)`).
5. Add graceful log on missing knowledge base (already handled — continues without context).

### Success criteria
- `SupabaseVectorStore.count()` returnsseeded chunks.
- `/api/agent/text/knowledge` or `/api/agent/chat` returns at least one `documented` best-practice surfaced in replies.
- RAG status is checked via `search` response.

---

## M8 — AI assistant full data access (ML + API data + RAG)

**Confirmed gap:** `agent/router.py` chat only receives a `farm_data` snapshot from the frontend (`crop_name`, `location`, `risk_level`) + RAG context. It cannot fetch live weather/rainfall/wind/bee/NDVI and cannot run PSI/flowering/risk models.

Task: give the agent access to BOTH the live API-fetched data AND the ML prediction outputs, combined with RAG.

### Approach (server-side tool/context assembly — no agent model tool-calling required)
1. In `agent/router.py`, when a `farm_id` is provided in the chat payload:
   - Load farm + latest prediction from DB.
   - Fetch current weather via `services/weather_service` (cache-first).
   - Fetch bee/NDVI via `environment_service` (best-effort).
   - Recompute prediction if absent: call `prediction_service.run_prediction(farm)`.
   - Assemble a structured "live data" block: temperature, humidity, rainfall, wind, ndvi, bee_richness, flowering window, PSI, risk.
2. Inject this into the `system_prompt` alongside the RAG context (both). Example prefix:
   `\n\nLive farm conditions:\n{crop}\n{district} weather: ...\nModel outputs: flowering ..., PSI ..., risk ...`
3. Optionally expose a small endpoint `GET /api/agent/context?farm_id=` returning this assembled data (helps debugging and testing).
4. If farm data isn't provided, keep existing generic chat behavior.

### Verification (test scenarios)
- Ask the agent: "What is the weather at my farm right now?" → must quote real numbers (from the live context, not invented).
- Ask: "What is my PSI and risk?" → must quote the ML model outputs.
- Ask a crop practice question → answered from RAG context.
- No farm selected → generic reply still works.

### Success criteria
- Agent replies to weather/PSI/risk questions with actual stored/model values.
- Both RAG + live/ML data are present in a single request→response.
- No regression in `/api/agent/chat` generic flow.

---

## M9 — Google Auth audit & fixes

Existing:
- `backend/app/api/routes/auth.py` — `/auth/register`, `/auth/login`, `/auth/me`, `/auth/firebase`, `/auth/oauth/google`, refresh, logout, token endpoints.
- `backend/app/auth.py` — JWT access/refresh via httpOnly cookies, `XSRF-TOKEN` double-submit cookie CSRF, refresh rotation with hashed tokens + revocation table, blacklist `RevokedToken` for access.)
- `backend/app/firebase_auth.py` — Firebase Admin verify + dev-mode unverified fallback.

### Audit checklist
1. Cookie flags: `secure=True` + `SameSite=none` in prod, `SameSite=lax` dev — already implemented; verify.
2. CSRF double-submit: confirm frontend sends `X-XSRF-TOKEN` header on mutating requests.
3. Refresh rotation: confirm refresh is revoked on use, expired/revoked rejects, logout revokes all.
4. Google OAuth: redirect URI matches exactly; `state`/nonce handling; user-account linking when the same email logs in via Google vs email-password; provider-conflict 409 message.
5. Firebase: verified in prod, dev unverified fallback documented, token revoked.
6. Write/fix tests in `backend/tests/` for: login, refresh, logout, CSRF 403, Google OAuth success/failure, password hashing.

### Success criteria
- Playwright/manual flow: register → login → refresh → CSRF request works; wrong token gives 401/403; Google OAuth sign-in works on deployed env.

---

## M10 — Deployment (Netlify + Render) & performance

### Backend — Render (or any free container host you choose)
- Root dir `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Env: all from the top-of-this-doc env block (`DATABASE_URL`, `SUPABASE_URL`, keys, `REDIS_URL`, `EE_*`, `OAUTH_GOOGLE_*`, `GEMINI_API_KEY`, `CORS_ORIGINS`, `FRONTEND_ORIGIN`, `APP_ENV=production`) + a strong 32-char secret `SECRET_KEY`.
- One web service (API) + one worker + one beat (using `REDIS_URL` as broker).
- Postgres (Supabase) + Redis externally hosted, not in the web service.

### Frontend — Netlify
- Base dir `frontend`, build `npm run build`, publish `dist`, `netlify.toml` SPA redirect rule present.
- Env: `VITE_API_URL` → deployed backend, `VITE_FIREBASE_*` etc. (existing).
- Update any hardcoded `http://localhost:8000` to the Render URL in `frontend/src/lib/api.js`.

### CI/CD
- Extend `.github/workflows/ci.yml` if needed; auto-deploy main to Netlify + Render (existing hooks if configured).

### Full-flow integration test
- Register → Login (email + Google) → Add Farm → Predict → Dashboard (weather, NDVI, PSI gauge, bee map, AI advice) → Agent chat with farm context → all green `pytest` and `npm run build`.

### Performance target
- Cached dashboard/weather reads: sub-500 ms (target from flowchart). Measure with devtools/`curl -w` calls against production; if Redis/DB not on the request path, report — do not silently accept.

---

## File touch-map (quick reference)

```
backend/requirements.txt                 + redis, celery[redis]
backend/app/core/config.py               + redis_url, ee_*, pollen key, supabase*
backend/app/core/cache.py                NEW — L1/L2 cache
backend/app/core/circuit_breaker.py      NEW — per-service breaker
backend/app/celery_app.py                NEW — worker + beat + 30-min schedule
backend/app/tasks/data_refresh.py        NEW — weather/ndvi/bees batch tasks
backend/app/services/pollen_service.py    NEW (M5)
backend/app/services/weather_service.py   M2/M4 wrap
backend/app/services/bee_service.py       M2/M4 wrap
backend/app/services/environment_service.py  M2/M4/M6
backend/app/agent/router.py               M4 (gemini wrap), M7 link, M8 context
backend/app/agent/embedder.py             M7 (verify/pg)
backend/app/api/routes/auth.py            M9 audit
backend/app/auth.py                       M9 audit
backend/app/firebase_auth.py              M9 audit
backend/.env.example                      env updates every module
backend/supabase/migrations/001_initial_schema.sql  M1 verify + M7 RPCs
backend/scripts/migrate_sqlite_to_supabase.py      M1
backend/scripts/seed_embeddings.py                M7
frontend/src/lib/api.js                   M10
.github/workflows/*.yml                   M10
```

---

## Definition of Done (whole phase)

- [ ] M1–M10 each implemented, tested, committed.
- [ ] Backend runs fully on Supabase Postgres with Redis caching; Celery Beat keeping data fresh; circuit breaker protects all external APIs.
- [ ] Agent answers with ML + live + RAG data; Google auth audited/fixed.
- [ ] App deployed (Render backend + Netlify frontend), CI green, integration flow tested, cached requests sub-500ms.