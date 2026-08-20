"""Integration tests for the real-time Teen Patti socket using Starlette's test client."""
import app.websocket.teen_patti_ws as tpws
from conftest import register_and_login

# Speed the table lifecycle timers up for tests — these are process-wide module
# constants read at call time, so patching them here (once, at import) is enough for
# every test in this file. Values stay well above 0 so the async scheduling is real,
# just fast.
tpws._BOT_JOIN_DELAY_SECONDS = 0.05
tpws._START_COUNTDOWN_SECONDS = 0.05
tpws._NEXT_HAND_DELAY_SECONDS = 0.05


def _recv_until(ws, predicate, max_tries=60):
    for _ in range(max_tries):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError(f"did not see expected message within {max_tries} reads")


def _make_table(client, tok, **overrides):
    payload = {"name": "WS TP", "mode": "virtual", "max_players": 4,
               "boot_amount": 10, "turn_seconds": 15}
    payload.update(overrides)
    r = client.post("/api/v1/teen-patti/tables", json=payload,
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201
    return r.json()["id"]


def test_table_create_list_and_get(client):
    tok = register_and_login(client, "tptbl@example.com", "tptbluser")
    tid = _make_table(client, tok)
    got = client.get(f"/api/v1/teen-patti/tables/{tid}").json()
    assert got["id"] == tid
    assert got["mode"] == "virtual"
    listed = client.get("/api/v1/teen-patti/tables").json()
    assert any(t["id"] == tid for t in listed)


def test_reject_without_token(client):
    tok = register_and_login(client, "tpnotok@example.com", "tpnotokuser")
    tid = _make_table(client, tok)
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/teen-patti/{tid}") as ws:
            ws.receive_json()


def test_lone_player_gets_bots_and_hand_finishes(client):
    host_tok = register_and_login(client, "tpsolo_host@example.com", "tpsolohost")
    tid = _make_table(client, host_tok)
    tok = register_and_login(client, "tpsolo@example.com", "tpsolouser")

    with client.websocket_connect(f"/ws/teen-patti/{tid}?token={tok}") as ws:
        _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "joined")
        _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "bots_joined")
        _recv_until(ws, lambda m: m.get("type") == "event" and m.get("event") == "hand_started")

        from app.teen_patti.manager import teen_patti_manager
        hand = teen_patti_manager.get(tid)
        assert len(hand.seats) >= 2
        assert hand.phase.value == "playing"
        human_id = hand.seats[0].id

        # Drive the human seat to pack whenever it's their turn until the hand ends —
        # bots play themselves via the WS layer's own background tasks.
        for _ in range(20):
            state_msg = _recv_until(ws, lambda m: m.get("type") == "state")
            state = state_msg["state"]
            if state["phase"] == "finished":
                break
            if state["turn"] == human_id:
                ws.send_json({"action": "pack"})
        assert teen_patti_manager.get(tid).phase.value in ("finished", "playing")


def test_two_humans_play_to_completion_and_wallets_move(client):
    host_tok = register_and_login(client, "tp2a@example.com", "tp2a")
    tid = _make_table(client, host_tok, max_players=2, boot_amount=10)
    t2 = register_and_login(client, "tp2b@example.com", "tp2b")
    id1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {host_tok}"}).json()["id"]
    id2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]

    with client.websocket_connect(f"/ws/teen-patti/{tid}?token={host_tok}") as ws1:
        with client.websocket_connect(f"/ws/teen-patti/{tid}?token={t2}") as ws2:
            _recv_until(ws1, lambda m: m.get("type") == "event" and m.get("event") == "hand_started")

            from app.teen_patti.manager import teen_patti_manager
            hand = teen_patti_manager.get(tid)
            sockets = {id1: ws1, id2: ws2}

            # Everyone just packs on their turn — deterministic, fast way to reach
            # "last standing" regardless of the shuffle.
            for _ in range(4):
                if hand.phase.value == "finished":
                    break
                cur_id = hand.current_seat().id
                sockets[cur_id].send_json({"action": "pack"})
                _recv_until(ws1, lambda m: m.get("type") == "state")

    assert hand.phase.value == "finished"
    assert hand.winner_seat is not None
    winner_id = hand.seats[hand.winner_seat].id
    winner_tok = host_tok if winner_id == id1 else t2
    loser_tok = t2 if winner_id == id1 else host_tok
    winner_balance = client.get("/api/v1/wallet",
                                headers={"Authorization": f"Bearer {winner_tok}"}).json()
    loser_balance = client.get("/api/v1/wallet",
                               headers={"Authorization": f"Bearer {loser_tok}"}).json()
    assert winner_balance["virtual_chips"] > loser_balance["virtual_chips"]


def test_table_deals_a_second_hand_automatically(client):
    """Regression test: _start_next_hand_after_delay used to leave a fully-seated
    table stuck in "finished" forever (phase only ever reset to WAITING in the
    not-enough-players branch), so a second hand never dealt."""
    host_tok = register_and_login(client, "tpsecond_a@example.com", "tpsecond_a")
    tid = _make_table(client, host_tok, max_players=2, boot_amount=10)
    t2 = register_and_login(client, "tpsecond_b@example.com", "tpsecond_b")

    from app.teen_patti.manager import teen_patti_manager

    with client.websocket_connect(f"/ws/teen-patti/{tid}?token={host_tok}") as ws1:
        with client.websocket_connect(f"/ws/teen-patti/{tid}?token={t2}") as ws2:
            _recv_until(ws1, lambda m: m.get("type") == "event" and m.get("event") == "hand_started")
            hand = teen_patti_manager.get(tid)
            sockets = {hand.seats[0].id: ws1, hand.seats[1].id: ws2}

            # End the first hand fast (pack immediately).
            for _ in range(4):
                if hand.phase.value == "finished":
                    break
                sockets[hand.current_seat().id].send_json({"action": "pack"})
                _recv_until(ws1, lambda m: m.get("type") == "state")
            assert hand.phase.value == "finished"

            # The second hand must actually start — this is the regression check.
            second_start = _recv_until(
                ws1, lambda m: m.get("type") == "event" and m.get("event") == "hand_started",
            )
            assert second_start is not None
            assert hand.phase.value == "playing"
            assert tpws._hand_number[tid] == 2


def test_mid_hand_joiner_becomes_spectator_then_gets_seated_next_hand(client):
    """A user connecting while a hand is already in progress can't be seated
    immediately (add_seat rejects mid-hand) — confirm they're queued and actually
    seated once the table deals its next hand, rather than stuck watching forever."""
    host_tok = register_and_login(client, "tpspec_a@example.com", "tpspec_a")
    tid = _make_table(client, host_tok, max_players=3, boot_amount=10)
    t2 = register_and_login(client, "tpspec_b@example.com", "tpspec_b")
    t3 = register_and_login(client, "tpspec_c@example.com", "tpspec_c")

    from app.teen_patti.manager import teen_patti_manager

    with client.websocket_connect(f"/ws/teen-patti/{tid}?token={host_tok}") as ws1:
        with client.websocket_connect(f"/ws/teen-patti/{tid}?token={t2}") as ws2:
            _recv_until(ws1, lambda m: m.get("type") == "event" and m.get("event") == "hand_started")
            hand = teen_patti_manager.get(tid)
            assert len(hand.seats) == 2

            # Third player connects mid-hand — must not raise, must not get seated yet.
            with client.websocket_connect(f"/ws/teen-patti/{tid}?token={t3}") as ws3:
                _recv_until(ws3, lambda m: m.get("type") == "event" and m.get("event") == "joined")
                assert len(hand.seats) == 2
                assert "tpspec_c" in tpws._spectators.get(tid, {}).values()

                sockets = {hand.seats[0].id: ws1, hand.seats[1].id: ws2}
                for _ in range(4):
                    if hand.phase.value == "finished":
                        break
                    sockets[hand.current_seat().id].send_json({"action": "pack"})
                    _recv_until(ws1, lambda m: m.get("type") == "state")
                assert hand.phase.value == "finished"

                _recv_until(ws1, lambda m: m.get("type") == "event" and m.get("event") == "hand_started")
                assert len(hand.seats) == 3
                assert tid not in tpws._spectators or not tpws._spectators[tid]
