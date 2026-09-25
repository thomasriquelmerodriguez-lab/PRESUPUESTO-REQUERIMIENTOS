from tests.conftest import login


def test_manager_can_create_user_and_public_login_selector_lists_it(client):
    csrf = login(client)
    response = client.post(
        "/api/users",
        json={
            "display_name": "Usuario de consulta",
            "password": "clave-segura-2026",
            "active": True,
            "areas": ["municipal"],
            "permissions": ["requirements.view"],
        },
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["display_name"] == "Usuario de consulta"
    assert created["areas"] == ["municipal"]
    assert created["permissions"] == ["requirements.view"]

    client.post(
        "/api/auth/logout",
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )
    options = client.get("/api/auth/login-options")
    assert options.status_code == 200
    selected = next(item for item in options.json() if item["display_name"] == "Usuario de consulta")

    logged = client.post(
        "/api/auth/login",
        json={"user_id": selected["id"], "password": "clave-segura-2026"},
        headers={"origin": "http://testserver"},
    )
    assert logged.status_code == 200, logged.text
    session = logged.json()
    assert session["user"]["areas"] == ["municipal"]
    assert session["user"]["permissions"] == ["requirements.view"]

    visible = client.get("/api/requirements", params={"area": "municipal", "page_size": 1})
    assert visible.status_code == 200
    forbidden = client.post(
        "/api/requirements",
        json={
            "area": "municipal",
            "budget_year": 2026,
            "request_date": "2026-08-06",
            "expedient": "TEST-001",
            "subject": "Prueba",
            "amount": 1,
            "department": "",
            "management_area": "",
            "notes": "",
            "account_code": "215-22-01-000-000-000",
            "allow_over_budget": False,
            "over_budget_reason": "",
        },
        headers={
            "origin": "http://testserver",
            "x-csrf-token": session["csrf_token"],
        },
    )
    assert forbidden.status_code == 403


def test_non_manager_cannot_manage_users(client):
    login(client, "salud")
    response = client.get("/api/users")
    assert response.status_code == 403
