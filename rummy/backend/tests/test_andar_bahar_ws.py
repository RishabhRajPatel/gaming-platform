"""Integration tests for the real-time Andar Bahar socket using Starlette's test client."""
import app.websocket.andar_bahar_ws as abws
from conftest import register_and_login

# Speed the table lifecycle up for tests. The REST schema enforces betting_seconds
# >= 10, so instead of shrinking it via the payload, wrap _load_config to override
# just the timing (mode/max_players still come from the real DB row) — same
# "patch the process-wide constant/function once at import" approach used for
# Teen Patti's WS tests.
_orig_load_config = abws._load_config


def _fast_load_config(table_id):
    config, mode = _orig_load_config(table_id)
    config.betting_seconds = 1
    return config, mode


abws._load_config = _fast_load_config
abws._SETTLE_PAUSE_SECONDS = 1


def _recv_until(ws, predicate, max_tries=60):
    for _ in range(max_tries):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError(f"did not see expected message within {max_tries} reads")


def _make_table(client, tok, **overrides):
    payload = {"name": "WS AB", "mode": "virtual", "max_players": 8,
               "betting_seconds": 10}
    payload.update(overrides)
    r = client.post("/api/v1/andar-bahar/tables", json=payload,
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201
    return r.json()["id"]


def test_table_create_list_and_get(client):
    tok = register_and_login(client, "abtbl@example.com", "abtbluser")
    tid = _make_table(client, tok)
    got = client.get(f"/api/v1/andar-bahar/tables/{tid}").json()
    assert got["id"] == tid
    assert got["mode"] == "virtual"
    listed = client.get("/api/v1/andar-bahar/tables").json()
    assert any(t["id"] == tid for t in listed)


def test_reject_without_token(client):
    tok = register_and_login(client, "abnotok@example.com", "abnotokuser")
    tid = _make_table(client, tok)
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/andar-bahar/{tid}") as ws:
            ws.receive_json()


def test_solo_player_bet_resolves_round_and_settles_wallet(client):
    from app.services.wallet import credit
    from app.models.wallet import TxnType, WalletKind
    from app.db.session import SessionLocal

    tok = register_and_login(client, "absolo@example.com", "absolouser")
    tid = _make_table(client, tok)

    uid = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["id"]
    with SessionLocal() as db:
        credit(db, user_id=uid, amount_paise=1000, txn_type=TxnType.BONUS,
               idempotency_key=f"test_seed_{uid}", kind=WalletKind.VIRTUAL, reference="test")
        db.commit()

    with client.websocket_connect(f"/ws/andar-bahar/{tid}?token={tok}") as ws:
        _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "joined")
        state_msg = _recv_until(ws, lambda m: m.get("type") == "state" and m["state"]["phase"] == "betting")
        assert state_msg["state"]["round_number"] == 1

        ws.send_json({"action": "bet", "side": "andar", "stake": 50, "action_id": "bet-1"})
        state_after_bet = _recv_until(
            ws, lambda m: m.get("type") == "state" and len(m["state"]["bets"]) == 1
        )
        assert state_after_bet["state"]["bets"][0]["side"] == "andar"
        assert state_after_bet["state"]["bets"][0]["stake"] == 50

        settled = _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "round_settled")
        assert settled["winner"] in ("andar", "bahar")

    balance = client.get("/api/v1/wallet", headers={"Authorization": f"Bearer {tok}"}).json()
    # Started with 1000, staked 50 — win or lose, the round must have settled
    # (never just left the stake untouched).
    assert balance["virtual_chips"] != 1000


def test_two_players_opposite_sides_exactly_one_wins(client):
    from app.services.wallet import credit
    from app.models.wallet import TxnType, WalletKind
    from app.db.session import SessionLocal

    t1 = register_and_login(client, "ab2a@example.com", "ab2a")
    t2 = register_and_login(client, "ab2b@example.com", "ab2b")
    id1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).json()["id"]
    id2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]

    # Give both players starting chips directly (no REST /bet welcome-grant path
    # exercised here) so both bets can actually be covered.
    with SessionLocal() as db:
        credit(db, user_id=id1, amount_paise=1000, txn_type=TxnType.BONUS,
               idempotency_key=f"test_seed_{id1}", kind=WalletKind.VIRTUAL, reference="test")
        credit(db, user_id=id2, amount_paise=1000, txn_type=TxnType.BONUS,
               idempotency_key=f"test_seed_{id2}", kind=WalletKind.VIRTUAL, reference="test")
        db.commit()

    tid = _make_table(client, t1)

    with client.websocket_connect(f"/ws/andar-bahar/{tid}?token={t1}") as ws1:
        with client.websocket_connect(f"/ws/andar-bahar/{tid}?token={t2}") as ws2:
            _recv_until(ws1, lambda m: m.get("type") == "state" and m["state"]["phase"] == "betting")
            ws1.send_json({"action": "bet", "side": "andar", "stake": 50, "action_id": "p1-bet"})
            ws2.send_json({"action": "bet", "side": "bahar", "stake": 50, "action_id": "p2-bet"})

            settled = _recv_until(ws1, lambda m: m.get("type") == "event" and m.get("event") == "round_settled")
            winner = settled["winner"]

    winner_tok = t1 if winner == "andar" else t2
    loser_tok = t2 if winner == "andar" else t1
    winner_balance = client.get("/api/v1/wallet", headers={"Authorization": f"Bearer {winner_tok}"}).json()
    loser_balance = client.get("/api/v1/wallet", headers={"Authorization": f"Bearer {loser_tok}"}).json()
    assert winner_balance["virtual_chips"] > loser_balance["virtual_chips"]


def test_bet_over_balance_is_rejected_not_silently_dropped(client):
    """A brand-new account has 0 chips here (no REST /bet welcome-grant path
    exercised). Betting should be rejected up front with an error, not accepted
    into the round and then silently vanish at settlement."""
    tok = register_and_login(client, "abpoor@example.com", "abpooruser")
    tid = _make_table(client, tok)

    with client.websocket_connect(f"/ws/andar-bahar/{tid}?token={tok}") as ws:
        _recv_until(ws, lambda m: m.get("type") == "state" and m["state"]["phase"] == "betting")
        ws.send_json({"action": "bet", "side": "andar", "stake": 50, "action_id": "poor-bet"})
        err = _recv_until(ws, lambda m: m.get("type") == "error")
        assert "insufficient" in err["message"].lower()

    balance = client.get("/api/v1/wallet", headers={"Authorization": f"Bearer {tok}"}).json()
    assert balance["virtual_chips"] == 0


def test_second_round_starts_automatically(client):
    """Regression check mirroring the Teen Patti bug: after a round settles, the
    table must reopen betting for round 2 on its own, not just sit in 'settled'."""
    tok = register_and_login(client, "abnext@example.com", "abnextuser")
    tid = _make_table(client, tok)

    with client.websocket_connect(f"/ws/andar-bahar/{tid}?token={tok}") as ws:
        _recv_until(ws, lambda m: m.get("type") == "state" and m["state"]["phase"] == "betting")
        ws.send_json({"action": "bet", "side": "andar", "stake": 10, "action_id": "r1-bet"})
        _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "round_settled")

        reopened = _recv_until(
            ws, lambda m: m.get("type") == "state" and m["state"]["phase"] == "betting"
            and m["state"]["round_number"] == 2,
        )
        assert reopened["state"]["round_number"] == 2
        assert reopened["state"]["bets"] == []
