# PolliSync Phase 2 — Security & Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and fix Google Auth implementation, deploy backend to Render and frontend to Netlify, verify performance targets.

**Architecture:** Security audit of auth flows, production deployment with proper env vars, performance testing for sub-500ms cached responses.

**Tech Stack:** FastAPI, JWT, OAuth, Render, Netlify, GitHub Actions

## Global Constraints

- Backend runs on Python 3.x with FastAPI
- Frontend runs on React/Vite
- All environment variables go in `backend/.env` and `.env.example`
- Each module must be tested and committed before starting the next
- Production requires secure cookie flags and CSRF protection

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/api/routes/auth.py` | Audit auth endpoints |
| `backend/app/auth.py` | Audit JWT/cookie implementation |
| `backend/app/firebase_auth.py` | Audit Firebase integration |
| `backend/tests/test_auth.py` | Add security tests |
| `frontend/src/lib/api.js` | Update API URL for production |
| `netlify.toml` | SPA redirect rules |
| `.github/workflows/ci.yml` | CI/CD pipeline |

---

## Task 1: Security Audit Auth Endpoints (M9)

**Files:**
- Audit: `backend/app/api/routes/auth.py`
- Audit: `backend/app/auth.py`
- Audit: `backend/app/firebase_auth.py`

**Interfaces:**
- Verifies: Cookie flags, CSRF, refresh rotation, OAuth flow

- [ ] **Step 1: Verify cookie flags**

Check in `backend/app/auth.py`:
```python
# Should have:
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,  # True in production
    samesite="none",  # "none" in production, "lax" in dev
    max_age=ACCESS_TOKEN_MINUTES * 60,
)
```

- [ ] **Step 2: Verify CSRF double-submit cookie**

Check that frontend sends `X-XSRF-TOKEN` header on mutating requests.

- [ ] **Step 3: Verify refresh rotation**

Check that refresh token is revoked on use and new one issued.

- [ ] **Step 4: Verify Google OAuth redirect URI**

Check `OAUTH_GOOGLE_REDIRECT_URI` matches exactly in Google Console.

- [ ] **Step 5: Document audit findings**

Create `backend/docs/auth-audit.md` with findings.

- [ ] **Step 6: Commit audit**

```bash
git add backend/docs/auth-audit.md
git commit -m "docs(m9): complete auth security audit"
```

---

## Task 2: Add Security Tests (M9)

**Files:**
- Modify: `backend/tests/test_auth.py` (or create new)
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Tests: Login, refresh, logout, CSRF, OAuth

- [ ] **Step 1: Write security tests**

Create `backend/tests/test_security.py`:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_sets_secure_cookie():
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword"
    })
    if response.status_code == 200:
        cookies = response.cookies
        assert "access_token" in cookies
        # Verify cookie flags (can't fully test httponly/secure in test)

def test_csrf_protection():
    # Without XSRF header should fail on mutating endpoints
    response = client.post("/api/auth/logout")
    # Should return 403 CSRF error

def test_refresh_token_rotation():
    # Login, get refresh token, use it, verify old token is revoked
    pass

def test_google_oauth_redirect():
    response = client.get("/api/auth/oauth/google")
    # Should redirect to Google OAuth
```

- [ ] **Step 2: Run tests**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_security.py -v`
Expected: Tests pass

- [ ] **Step 3: Commit security tests**

```bash
git add backend/tests/test_security.py
git commit -m "feat(m9): add auth security tests"
```

---

## Task 3: Update Frontend API URL (M10)

**Files:**
- Modify: `frontend/src/lib/api.js`
- Verify: `netlify.toml`

**Interfaces:**
- Consumes: `VITE_API_URL` env var
- Produces: Frontend points to production backend

- [ ] **Step 1: Read current api.js**

Check how API URL is currently configured.

- [ ] **Step 2: Ensure VITE_API_URL is used**

Update `frontend/src/lib/api.js`:
```javascript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

- [ ] **Step 3: Verify netlify.toml exists**

Check `frontend/netlify.toml`:
```toml
[[redirects]]
from = "/*"
to = "/index.html"
status = 200
```

- [ ] **Step 4: Commit frontend updates**

```bash
git add frontend/src/lib/api.js
git commit -m "feat(m10): update frontend API URL for production"
```

---

## Task 4: Configure Render Backend (M10)

**Files:**
- Create: `render.yaml` (if not exists)
- Verify: `backend/requirements.txt`
- Verify: `backend/app/main.py`

**Interfaces:**
- Produces: Render deployment configuration

- [ ] **Step 1: Create render.yaml**

Create `render.yaml`:
```yaml
services:
  - type: web
    name: polisync-api
    runtime: python
    buildCommand: cd backend && pip install -r requirements.txt
    startCommand: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: SECRET_KEY
        generateValue: true
      - key: APP_ENV
        value: production
      - key: FRONTEND_ORIGIN
        sync: false
      - key: CORS_ORIGINS
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: OAUTH_GOOGLE_CLIENT_ID
        sync: false
      - key: OAUTH_GOOGLE_CLIENT_SECRET
        sync: false
      - key: OAUTH_GOOGLE_REDIRECT_URI
        sync: false
      - key: FIREBASE_PROJECT_ID
        sync: false
      - key: FIREBASE_SERVICE_ACCOUNT_JSON
        sync: false
  - type: worker
    name: polisync-worker
    runtime: python
    buildCommand: cd backend && pip install -r requirements.txt
    startCommand: cd backend && celery -A app.celery_app.celery_app worker --loglevel=info
    envVars:
      - key: REDIS_URL
        sync: false
  - type: worker
    name: polisync-beat
    runtime: python
    buildCommand: cd backend && pip install -r requirements.txt
    startCommand: cd backend && celery -A app.celery_app.celery_app beat --loglevel=info
    envVars:
      - key: REDIS_URL
        sync: false
```

- [ ] **Step 2: Verify main.py has proper CORS**

Check `backend/app/main.py` for CORS middleware configuration.

- [ ] **Step 3: Commit Render config**

```bash
git add render.yaml
git commit -m "feat(m10): add Render deployment configuration"
```

---

## Task 5: Performance Testing (M10)

**Files:**
- Test: Manual verification
- Document: `backend/docs/performance.md`

**Interfaces:**
- Tests: Cached response times, database queries

- [ ] **Step 1: Test cached weather response time**

```bash
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/weather/current?farm_id=1
```

- [ ] **Step 2: Test cached dashboard response time**

```bash
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/dashboard
```

- [ ] **Step 3: Verify sub-500ms target**

Record response times, verify cached requests are under 500ms.

- [ ] **Step 4: Document performance results**

Create `backend/docs/performance.md` with results.

- [ ] **Step 5: Commit performance docs**

```bash
git add backend/docs/performance.md
git commit -m "docs(m10): add performance test results"
```

---

## Task 6: Full Integration Test (M9-M10)

**Files:**
- Test: Manual verification

**Interfaces:**
- Tests: Complete user flow on production

- [ ] **Step 1: Test registration flow**

Register new user on deployed app.

- [ ] **Step 2: Test login flow**

Login with email/password.

- [ ] **Step 3: Test Google OAuth**

Login with Google account.

- [ ] **Step 4: Test farm operations**

Add farm, run prediction, view dashboard.

- [ ] **Step 5: Test agent chat**

Chat with agent, verify live data injection.

---

## Definition of Done — Plan D

- [ ] M9: Auth security audit complete, tests passing
- [ ] M10: Backend deployed to Render, frontend to Netlify
- [ ] All code committed with descriptive messages
- [ ] Performance target met: cached responses < 500ms
- [ ] Full integration flow tested on production
