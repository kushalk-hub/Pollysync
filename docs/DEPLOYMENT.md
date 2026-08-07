# Production Deployment — Redis + Celery on Render

This guide wires the Redis L2 cache and the Celery worker/beat scheduler into the
Render deployment. The application code for both already exists:

- `backend/app/core/cache.py` — L1 in-memory + L2 Redis cache (Redis is opt-in via `REDIS_URL`; if unset or unreachable it degrades gracefully to L1-only).
- `backend/app/celery_app.py` — Celery app with a beat schedule that runs the 30-minute farm data refresh.
- `backend/app/tasks/data_refresh.py` — refreshes weather, NDVI, and bee data for all farms.

---

## 1. Provision Redis (Redis Cloud free tier)

1. Create a free database at https://app.redislabs.com (plan: free / 30 MB).
2. Open the database and copy the **public endpoint** and **password** from the
   "Connect" / "Configuration" dialog.
3. Build the connection string:
   - Plain endpoint: `redis://default:<password>@<host>:<port>`
   - TLS endpoint (preferred): `rediss://default:<password>@<host>:<port>`

   `redis-py` handles both schemes; the app's `_get_redis()` just needs a valid URL.
4. Sanity-check it locally before deploying:

   ```bash
   cd backend
   ..\.venv\Scripts\python.exe -c "import redis; r = redis.from_url('rediss://default:<password>@<host>:<port>', socket_timeout=5); print(r.ping())"
   ```

   Expected output: `True`.

> **Security:** never commit the URL/password. Set it only in Render's env dashboard.
> If the password has been shared anywhere (chat logs, issues), rotate it in the Redis Cloud console.

---

## 2. Configure the existing Web service

In the Render dashboard, open your API web service → **Environment** → add:

| Variable     | Value |
|--------------|-------|
| `REDIS_URL`  | your Redis Cloud URL (e.g. `rediss://...`) |

Keep `FRONTEND_ORIGIN` / `CORS_ORIGINS` unchanged. Redeploy the web service.

Verify the L2 cache is live:

```
GET https://<your-api>.onrender.com/api/health/cache
```

Response:

```json
{ "redis": "ok" }
```

Other possible values: `"disabled"` (no `REDIS_URL` set), `"unavailable"` (Redis unreachable — app still works in L1-only mode).

---

## 3. Create the Worker service (Celery + Beat)

1. In Render → **New → Background Worker**.
2. Connect the same repo and branch.
3. **Root Directory**: `backend`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**:

   ```
   celery -A app.celery_app.celery_app worker --beat --loglevel=info
   ```

   `--beat` embeds the beat scheduler so a single service runs both worker and schedule.
6. **Instance Type**: use a **paid (non-sleeping)** instance. Render's free tier spins
   services down after ~15 min idle, which would let the 30-minute beat schedule drift.
7. **Environment**: copy the web service's env (easiest: paste the same values), then
   ensure at least these are present:

   | Variable | Notes |
   |----------|-------|
   | `REDIS_URL` | broker + result backend for Celery, and the task cache layer |
   | `DATABASE_URL` | tasks query the DB for all farms |
   | `SECRET_KEY` | required by settings validation |
   | `EE_SERVICE_ACCOUNT` | NDVI refresh uses Earth Engine |
   | `EE_PRIVATE_KEY_FILE` | NDVI refresh (if you deploy the EE key as a file) |

8. **Deploy** and watch the logs.

---

## 4. Verify

1. **Worker health**: worker logs should show `celery@... ready` and the beat entry:
   `Scheduler: Sending due task refresh-farm-data (app.tasks.data_refresh.refresh_all_farms)`.
2. **First run**: within 30 minutes the log should include `All farm data refreshed successfully`.
3. **Cache**: `GET /api/health/cache` on the web service returns `{"redis": "ok"}`.
4. **Manual task run** (optional): trigger a refresh immediately:

   ```bash
   celery -A app.celery_app.celery_app call app.tasks.data_refresh.refresh_all_farms
   ```

---

## 5. Local development (for reference)

```bash
# Terminal 1: Redis (any of)
docker run -d -p 6379:6379 redis
redis-server

# Terminal 2: worker
cd backend
celery -A app.celery_app.celery_app worker --loglevel=info

# Terminal 3: beat (if not using --beat)
cd backend
celery -A app.celery_app.celery_app beat --loglevel=info

# Terminal 4: API
cd backend
uvicorn app.main:app --reload
```

---

## Troubleshooting

- **`/api/health/cache` returns `"unavailable"`** — check `REDIS_URL` is set and reachable
  from Render; confirm you used the TLS port if your provider requires TLS.
- **Beat never fires** — the worker instance is likely on the free plan and sleeping
  between runs. Move it to a paid instance.
- **`invalid username-password pair`** — the password or `default` user is wrong; copy it
  exactly from the Redis Cloud console (watch for case differences).
- **`SSL: WRONG_VERSION_NUMBER`** — you pointed `rediss://` at a plaintext port. Either use
  `redis://` for that port or find the provider's TLS port.
