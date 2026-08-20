from app.andar_bahar import engine
from conftest import register_and_login


def test_engine_winner_matches_middle_rank():
    for n in range(300):
        r = engine.play_provably_fair("srv", "client", n)
        last = r.steps[-1]["card"]
        assert last.rank == r.middle.rank
        assert r.winner in ("andar", "bahar")


def test_engine_start_side_by_colour():
    assert engine.start_side(engine.Card(7, "S")) == "andar"   # black
    assert engine.start_side(engine.Card(7, "C")) == "andar"
    assert engine.start_side(engine.Card(7, "H")) == "bahar"   # red
    assert engine.start_side(engine.Card(7, "D")) == "bahar"


def test_engine_deterministic():
    a = engine.play_provably_fair("s", "c", 5).winner
    b = engine.play_provably_fair("s", "c", 5).winner
    assert a == b


def test_settlement_math():
    win = engine.settle("bahar", 100, "bahar")
    assert win["won"] and win["payout"] == 100 and win["returned"] == 200
    lose = engine.settle("andar", 100, "bahar")
    assert not lose["won"] and lose["returned"] == 0


def test_bet_endpoint_virtual_flow(client):
    tok = register_and_login(client, "ab@example.com", "abuser")
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/v1/andar-bahar/bet", headers=h, json={
        "bet": "andar", "stake": 50, "client_seed": "seed-abc", "nonce": 1, "mode": "virtual",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["round"]["winner"] in ("andar", "bahar")
    assert body["server_seed_hash"] == engine.server_seed_hash(body["server_seed"])
    # welcome grant 1000 - stake 50, +/- payout; balance is consistent
    won = body["settlement"]["won"]
    expected = 1000 - 50 + (50 + body["settlement"]["payout"] if won else 0)
    assert body["balance"] == expected


def test_bet_endpoint_idempotent(client):
    tok = register_and_login(client, "ab2@example.com", "abuser2")
    h = {"Authorization": f"Bearer {tok}"}
    payload = {"bet": "bahar", "stake": 30, "client_seed": "dup", "nonce": 7, "mode": "virtual"}
    b1 = client.post("/api/v1/andar-bahar/bet", headers=h, json=payload).json()
    b2 = client.post("/api/v1/andar-bahar/bet", headers=h, json=payload).json()
    # same stake/seed/nonce must not double-charge -> identical resulting balance
    assert b1["balance"] == b2["balance"]


def test_bet_requires_auth(client):
    r = client.post("/api/v1/andar-bahar/bet", json={
        "bet": "andar", "stake": 10, "client_seed": "x", "nonce": 1})
    assert r.status_code == 401
