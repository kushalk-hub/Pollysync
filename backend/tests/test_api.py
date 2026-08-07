from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient, email: str = "farm-user@example.com") -> dict[str, str]:
    password = "StrongPass1!"
    payload = {
        "email": email,
        "password": password,
        "full_name": "Farm User",
    }
    registered = client.post("/api/auth/register", json=payload)
    assert registered.status_code in {201, 409}
    logged_in = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "pollisync-api",
    }


def test_create_and_list_farm() -> None:
    payload = {
        "name": "Demo Farm",
        "crop": "Mustard",
        "location": "Nashik, Maharashtra",
        "area_acres": 5.5,
        "soil_type": "loamy",
    }

    with TestClient(app) as client:
        headers = _auth_headers(client)
        created = client.post("/api/farms", json=payload, headers=headers)
        farms = client.get("/api/farms", headers=headers)

    assert created.status_code == 201
    assert created.json()["crop_type"] == "Mustard"
    assert created.json()["crop"] == "Mustard"
    assert created.json()["location"] == "Nashik, Maharashtra"
    assert created.json()["area_acres"] == 5.5
    assert farms.status_code == 200
    assert any(farm["name"] == "Demo Farm" for farm in farms.json())


def test_mark_notification_read() -> None:
    payload = {
        "name": "Alerts Farm",
        "crop": "Sunflower",
        "location": "Pune, Maharashtra",
        "area_acres": 3.0,
        "soil_type": "sandy",
    }

    with TestClient(app) as client:
        headers = _auth_headers(client, email="notify-user@example.com")
        created = client.post("/api/farms", json=payload, headers=headers)
        assert created.status_code == 201

        notifications = client.get("/api/notifications", headers=headers)
        assert notifications.status_code == 200
        assert len(notifications.json()) >= 1

        notification_id = notifications.json()[0]["id"]
        updated = client.patch(f"/api/notifications/{notification_id}/read", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["read"] is True


def test_auth_register_login_refresh_and_logout() -> None:
    email = "api-user@example.com"
    password = "StrongPass1!"
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "API User",
    }

    with TestClient(app) as client:
        registered = client.post("/api/auth/register", json=register_payload)

        assert registered.status_code in {201, 409}
        if registered.status_code == 201:
            registered_body = registered.json()
            assert registered_body["token_type"] == "bearer"
            assert registered_body["user"]["email"] == email

        logged_in = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert logged_in.status_code == 200
        login_body = logged_in.json()
        access_token = login_body["access_token"]
        refresh_token = login_body["refresh_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email

        oauth2_token = client.post(
            "/api/auth/token",
            data={"username": email, "password": password},
        )
        assert oauth2_token.status_code == 200
        assert oauth2_token.json()["token_type"] == "bearer"

        refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert refreshed.status_code == 200
        assert refreshed.json()["refresh_token"] != refresh_token

        logged_out = client.post(
            "/api/auth/logout",
            json={"refresh_token": refreshed.json()["refresh_token"]},
        )
        assert logged_out.status_code == 204


def test_team_idor() -> None:
    with TestClient(app) as client:
        # Create user A and farm A
        headers_a = _auth_headers(client, email="user-a@example.com")
        farm_payload = {
            "name": "Farm A",
            "crop": "Mustard",
            "location": "Nashik, Maharashtra",
            "area_acres": 5.0,
            "soil_type": "loamy",
        }
        res_a = client.post("/api/farms", json=farm_payload, headers=headers_a)
        assert res_a.status_code == 201
        farm_a_id = res_a.json()["id"]

        # Invite a member to Farm A
        invite_payload = {
            "email": "member-a@example.com",
            "name": "Member A",
            "role": "viewer",
        }
        invite_res = client.post(f"/api/farms/{farm_a_id}/team", json=invite_payload, headers=headers_a)
        assert invite_res.status_code == 201
        member_id = invite_res.json()["id"]

        # Create user B
        headers_b = _auth_headers(client, email="user-b@example.com")

        # Try to update member of Farm A using User B's auth -> Should return 404
        update_payload = {"role": "editor"}
        res_update = client.patch(
            f"/api/farms/{farm_a_id}/team/{member_id}",
            json=update_payload,
            headers=headers_b,
        )
        assert res_update.status_code == 404

        # Try to delete member of Farm A using User B's auth -> Should return 404
        res_delete = client.delete(
            f"/api/farms/{farm_a_id}/team/{member_id}",
            headers=headers_b,
        )
        assert res_delete.status_code == 404


def test_csrf_cookie_protection() -> None:
    email = "csrf-user@example.com"
    password = "StrongPass1!"
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "CSRF User",
    }

    with TestClient(app) as client:
        # Register user
        client.post("/api/auth/register", json=register_payload)

        # Login to set cookies (access_token, refresh_token, and XSRF-TOKEN)
        login_res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200
        
        # Verify access_token and XSRF-TOKEN cookies are set
        assert "access_token" in client.cookies
        assert "XSRF-TOKEN" in client.cookies
        csrf_token = client.cookies["XSRF-TOKEN"]

        # Try to create a farm using cookies but without X-XSRF-TOKEN header -> Should return 403 Forbidden
        farm_payload = {
            "name": "CSRF Farm",
            "crop": "Cotton",
            "location": "Amravati, Maharashtra",
            "area_acres": 10.0,
            "soil_type": "black",
        }
        
        # Request without header (clear auth header if default set, but TestClient has none unless passed in headers)
        res_no_header = client.post("/api/farms", json=farm_payload)
        assert res_no_header.status_code == 403
        assert "CSRF" in res_no_header.json()["detail"]

        # Request with mismatching header
        res_bad_header = client.post(
            "/api/farms",
            json=farm_payload,
            headers={"X-XSRF-TOKEN": "invalid-token"},
        )
        assert res_bad_header.status_code == 403

        # Request with correct header -> Should succeed (201)
        res_good_header = client.post(
            "/api/farms",
            json=farm_payload,
            headers={"X-XSRF-TOKEN": csrf_token},
        )
        assert res_good_header.status_code == 201


def test_csrf_skipped_for_allowed_origin(monkeypatch) -> None:
    import uuid
    from types import SimpleNamespace
    import app.auth as auth_module

    real = auth_module.settings
    monkeypatch.setattr(
        auth_module,
        "settings",
        SimpleNamespace(
            allowed_origins=["https://front.test"],
            is_production=real.is_production,
            access_token_minutes=real.access_token_minutes,
            refresh_token_days=real.refresh_token_days,
            secret_key=real.secret_key,
            algorithm=real.algorithm,
        ),
    )

    email = f"origin-{uuid.uuid4()}@example.com"
    password = "StrongPass1!"
    farm_payload = {
        "name": "Origin Farm",
        "crop": "Cotton",
        "location": "Amravati, Maharashtra",
        "area_acres": 10.0,
        "soil_type": "black",
    }

    with TestClient(app) as client:
        reg = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "full_name": "Origin User"},
        )
        assert reg.status_code == 201
        login = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        assert "access_token" in client.cookies
        assert "XSRF-TOKEN" in client.cookies

        # Allowed Origin without X-XSRF-TOKEN header -> trusted, should succeed
        res_allowed = client.post(
            "/api/farms",
            json=farm_payload,
            headers={"Origin": "https://front.test"},
        )
        assert res_allowed.status_code == 201

        # Disallowed Origin without X-XSRF-TOKEN header -> blocked
        res_evil = client.post(
            "/api/farms",
            json=farm_payload,
            headers={"Origin": "https://evil.test"},
        )
        assert res_evil.status_code == 403
        assert "CSRF" in res_evil.json()["detail"]


def test_account_lockout() -> None:
    import uuid
    email = f"lockout-{uuid.uuid4()}@example.com"
    password = "StrongPass1!"
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "Lockout User",
    }
    with TestClient(app) as client:
        reg_res = client.post("/api/auth/register", json=register_payload)
        assert reg_res.status_code == 201

        # 4 failed attempts (unlocked)
        for _ in range(4):
            res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
            assert res.status_code == 401

        # 5th failed attempt triggers lockout
        res_5 = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
        assert res_5.status_code == 401

        # 6th attempt (even with correct password) is locked out
        res_locked = client.post("/api/auth/login", json={"email": email, "password": password})
        assert res_locked.status_code == 403
        assert "locked" in res_locked.json()["detail"].lower()


def test_access_token_blacklisting_on_logout() -> None:
    import uuid
    email = f"blacklisted-{uuid.uuid4()}@example.com"
    password = "StrongPass1!"
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "Blacklist User",
    }
    with TestClient(app) as client:
        reg_res = client.post("/api/auth/register", json=register_payload)
        assert reg_res.status_code == 201

        login_res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res_me = client.get("/api/auth/me", headers=headers)
        assert res_me.status_code == 200

        res_logout = client.post("/api/auth/logout", headers=headers)
        assert res_logout.status_code == 204

        res_me_revoked = client.get("/api/auth/me", headers=headers)
        assert res_me_revoked.status_code == 401
        assert "revoked" in res_me_revoked.json()["detail"].lower()


def test_http_security_headers() -> None:
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert "max-age=" in res.headers.get("Strict-Transport-Security", "")


def test_agent_endpoint_auth_and_limit() -> None:
    with TestClient(app) as client:
        res_no_auth = client.post(
            "/api/agent/chat",
            json={"messages": [{"role": "user", "content": "Hello PolliSync"}]},
        )
        assert res_no_auth.status_code == 401

        headers = _auth_headers(client, email="agent-tester@example.com")
        res_auth = client.post(
            "/api/agent/chat",
            json={"messages": [{"role": "user", "content": "Hello PolliSync"}]},
            headers=headers,
        )
        assert res_auth.status_code in {200, 502, 503}
