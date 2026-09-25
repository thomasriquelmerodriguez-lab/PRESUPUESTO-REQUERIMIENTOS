from tests.conftest import login


def test_seeded_data_and_permissions(client):
    login(client)
    response = client.get("/api/budgets/municipal/2026/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog["accounts"]) == 180
    assert catalog["total_new_requirements"] == 2_522_408_220
    account = next(item for item in catalog["accounts"] if item["code"] == "215-22-01-001-000-000")
    assert account["new_requirements"] == 15_561_208
    assert account["obligated_cas"] == 1_691_755
    assert account["available"] == 32_747_037
    response = client.get("/api/requirements?area=municipal&page_size=1")
    assert response.status_code == 200
    assert response.json()["total"] == 655
    assert response.json()["total_amount"] == 2_522_408_220


def test_area_user_isolation(client):
    login(client, "salud")
    response = client.get("/api/requirements?area=municipal")
    assert response.status_code == 403


def test_csrf_required_for_mutations(client):
    login(client)
    catalog = client.get("/api/budgets/municipal/2026/catalog").json()
    account = catalog["accounts"][0]
    response = client.patch(
        f"/api/budgets/municipal/2026/accounts/{account['id']}/obligated-cas",
        json={"amount": 0, "row_version": account["row_version"]},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 403


def test_optimistic_concurrency_for_obligated_cas(client):
    csrf = login(client)
    headers = {"origin": "http://testserver", "x-csrf-token": csrf}
    catalog = client.get("/api/budgets/municipal/2026/catalog").json()
    account = catalog["accounts"][0]
    first = client.patch(
        f"/api/budgets/municipal/2026/accounts/{account['id']}/obligated-cas",
        json={"amount": 1, "row_version": account["row_version"]},
        headers=headers,
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/api/budgets/municipal/2026/accounts/{account['id']}/obligated-cas",
        json={"amount": 2, "row_version": account["row_version"]},
        headers=headers,
    )
    assert stale.status_code == 409


def test_security_headers_and_private_cache(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_session_cookie_is_http_only_and_same_site(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "encargado de presupuesto", "password": "2026"},
        headers={"origin": "http://testserver"},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_budget_upload_extension_allowlist(client):
    csrf = login(client)
    response = client.post(
        "/api/budgets/import/preview",
        data={"area": "municipal", "year": "2026"},
        files={"file": ("malware.exe", b"not executable", "application/octet-stream")},
        headers={"origin": "http://testserver", "x-csrf-token": csrf},
    )
    assert response.status_code == 415


def test_search_input_is_data_not_sql(client):
    login(client)
    response = client.get(
        "/api/requirements",
        params={"area": "municipal", "q": "' OR 1=1 --", "page_size": 10},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_two_users_cannot_edit_same_requirement_at_once(client):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.base import SessionLocal
    from app.db.models import Area, User, UserArea
    from app.main import app

    with SessionLocal() as db:
        second = db.execute(select(User).where(User.username == "presupuesto auxiliar")).scalar_one_or_none()
        if not second:
            area = db.execute(select(Area).where(Area.slug == "municipal")).scalar_one()
            second = User(
                username="presupuesto auxiliar",
                display_name="Presupuesto auxiliar",
                role="area_user",
                password_hash=hash_password("clave-auxiliar-segura"),
            )
            db.add(second)
            db.flush()
            db.add(UserArea(user_id=second.id, area_id=area.id))
            db.commit()

    csrf_first = login(client)
    record = client.get(
        "/api/requirements", params={"area": "municipal", "page_size": 1}
    ).json()["items"][0]
    first_lock = client.post(
        f"/api/requirements/{record['id']}/lock",
        params={"area": "municipal"},
        headers={"origin": "http://testserver", "x-csrf-token": csrf_first},
    )
    assert first_lock.status_code == 200

    with TestClient(app) as second_client:
        second_login = second_client.post(
            "/api/auth/login",
            json={"username": "presupuesto auxiliar", "password": "clave-auxiliar-segura"},
            headers={"origin": "http://testserver"},
        )
        csrf_second = second_login.json()["csrf_token"]
        second_lock = second_client.post(
            f"/api/requirements/{record['id']}/lock",
            params={"area": "municipal"},
            headers={"origin": "http://testserver", "x-csrf-token": csrf_second},
        )
        assert second_lock.status_code == 409

    unlock = client.delete(
        f"/api/requirements/{record['id']}/lock",
        params={"area": "municipal"},
        headers={"origin": "http://testserver", "x-csrf-token": csrf_first},
    )
    assert unlock.status_code == 200


def test_manager_can_create_new_budget_year(client):
    csrf = login(client)
    headers = {"origin": "http://testserver", "x-csrf-token": csrf}
    response = client.post(
        "/api/budgets/municipal/years",
        json={"year": 2027},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    period = response.json()
    assert period["year"] == 2027
    assert period["has_budget"] is False
    years = client.get("/api/budgets/municipal/years")
    assert years.status_code == 200
    assert any(item["year"] == 2027 for item in years.json())


def test_duplicate_budget_year_is_rejected(client):
    csrf = login(client)
    headers = {"origin": "http://testserver", "x-csrf-token": csrf}
    first = client.post(
        "/api/budgets/salud/years",
        json={"year": 2027},
        headers=headers,
    )
    assert first.status_code == 200
    duplicate = client.post(
        "/api/budgets/salud/years",
        json={"year": 2027},
        headers=headers,
    )
    assert duplicate.status_code == 409


def test_new_year_can_receive_budget_upload(client):
    csrf = login(client)
    headers = {"origin": "http://testserver", "x-csrf-token": csrf}
    created = client.post(
        "/api/budgets/educacion/years",
        json={"year": 2028},
        headers=headers,
    )
    assert created.status_code == 200
    csv_data = (
        "CUENTA;DENOMINACIÓN;PRESUPUESTO VIGENTE;PRE OBLIGADO ZE COMPRAS;OBLIGADO CAS\n"
        "215-22-01-000-000-000;ALIMENTOS Y BEBIDAS;54000000;0;0\n"
        "215-22-01-001-000-000;PARA PERSONAS;50000000;0;0\n"
        "215-22-01-002-000-000;PARA ANIMALES;4000000;0;0\n"
    ).encode("utf-8")
    preview = client.post(
        "/api/budgets/import/preview",
        data={"area": "educacion", "year": "2028"},
        files={"file": ("presupuesto_2028.csv", csv_data, "text/csv")},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    token = preview.json()["token"]
    applied = client.post(
        "/api/budgets/import/apply",
        json={"token": token, "area": "educacion", "year": 2028},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    periods = client.get("/api/budgets/educacion/years").json()
    period = next(item for item in periods if item["year"] == 2028)
    assert period["has_budget"] is True
    assert period["total_budget"] == 54_000_000


def test_available_is_budget_minus_requirements_minus_cas_per_account(client):
    login(client)
    catalog = client.get("/api/budgets/municipal/2026/catalog").json()
    account = next(
        item for item in catalog["accounts"]
        if item["code"] == "215-22-01-001-000-000"
    )
    assert account["available"] == (
        account["budget"] - account["new_requirements"] - account["obligated_cas"]
    )


def test_budget_import_preserves_existing_cas_when_cas_column_is_omitted(client):
    csrf = login(client)
    headers = {"origin": "http://testserver", "x-csrf-token": csrf}
    before = client.get("/api/budgets/municipal/2026/catalog").json()
    target = next(
        item for item in before["accounts"]
        if item["code"] == "215-22-01-001-000-000"
    )
    expected_cas = target["obligated_cas"]
    csv_data = (
        "CUENTA;DENOMINACIÓN;PRESUPUESTO VIGENTE\n"
        "215-22-01-000-000-000;ALIMENTOS Y BEBIDAS;54000000\n"
        "215-22-01-001-000-000;PARA PERSONAS;50000000\n"
        "215-22-01-002-000-000;PARA ANIMALES;4000000\n"
    ).encode("utf-8")
    preview = client.post(
        "/api/budgets/import/preview",
        data={"area": "municipal", "year": "2026"},
        files={"file": ("modificacion_sin_cas.csv", csv_data, "text/csv")},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    applied = client.post(
        "/api/budgets/import/apply",
        json={"token": preview.json()["token"], "area": "municipal", "year": 2026},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    after = client.get("/api/budgets/municipal/2026/catalog").json()
    updated = next(
        item for item in after["accounts"]
        if item["code"] == "215-22-01-001-000-000"
    )
    assert updated["obligated_cas"] == expected_cas
    assert updated["available"] == (
        updated["budget"] - updated["new_requirements"] - updated["obligated_cas"]
    )
