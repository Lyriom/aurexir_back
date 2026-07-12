def test_register_devuelve_token_y_usuario(client):
    res = client.post(
        "/auth/register",
        json={"email": "Nuevo@Test.com", "password": "password123", "name": "Nuevo"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["access_token"]
    assert data["user"]["email"] == "nuevo@test.com"  # normalizado a minúsculas
    assert data["user"]["role"] == "customer"
    assert "password" not in data["user"]


def test_register_email_duplicado_da_409(client):
    body = {"email": "dup@test.com", "password": "password123", "name": "Dup"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409


def test_register_password_corta_da_422(client):
    res = client.post(
        "/auth/register", json={"email": "x@test.com", "password": "corta", "name": "X"}
    )
    assert res.status_code == 422


def test_login_y_me(client):
    client.post(
        "/auth/register",
        json={"email": "login@test.com", "password": "password123", "name": "Login"},
    )
    res = client.post("/auth/login", json={"email": "login@test.com", "password": "password123"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "login@test.com"


def test_login_password_incorrecta_da_401(client):
    client.post(
        "/auth/register",
        json={"email": "mal@test.com", "password": "password123", "name": "Mal"},
    )
    res = client.post("/auth/login", json={"email": "mal@test.com", "password": "incorrecta1"})
    assert res.status_code == 401


def test_me_sin_token_da_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_con_token_invalido_da_401(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer no-es-un-jwt"})
    assert res.status_code == 401
