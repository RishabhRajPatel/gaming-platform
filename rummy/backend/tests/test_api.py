from conftest import register_and_login


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_register_login_me(client):
    tok = register_and_login(client, "bob@example.com", "bob")
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/auth/me", headers=h).json()["username"] == "bob"


def test_duplicate_register_conflicts(client):
    client.post("/api/v1/auth/register", json={
        "email": "dup@example.com", "username": "dup", "password": "password123"})
    r = client.post("/api/v1/auth/register", json={
        "email": "dup@example.com", "username": "dup2", "password": "password123"})
    assert r.status_code == 409


def test_wallet_requires_auth(client):
    assert client.get("/api/v1/wallet").status_code == 401


def test_create_and_list_table(client):
    tok = register_and_login(client, "carol@example.com", "carol")
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/v1/tables", json={
        "name": "My Table", "mode": "free", "max_players": 4, "num_deals": 2}, headers=h)
    assert r.status_code == 201
    tid = r.json()["id"]
    assert client.get(f"/api/v1/tables/{tid}").json()["name"] == "My Table"


def test_real_money_table_needs_fee(client):
    tok = register_and_login(client, "dave@example.com", "dave")
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/v1/tables", json={
        "name": "RM", "mode": "real_money", "entry_fee_paise": 0}, headers=h)
    assert r.status_code == 400
