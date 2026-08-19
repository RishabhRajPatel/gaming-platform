"""Integration test for the real-time game socket using Starlette's test client."""
from conftest import register_and_login
from tests.helpers import hand


def _drain(ws, want_event=None, max_msgs=12):
    """Read up to max_msgs, returning the list; stops early if want_event seen."""
    seen = []
    for _ in range(max_msgs):
        msg = ws.receive_json()
        seen.append(msg)
        if want_event and msg.get("type") == "event" and msg.get("event") == want_event:
            break
    return seen


def _recv_until(ws, predicate, max_tries=30):
    """Read messages, discarding ones that don't match, until `predicate` is true.

    Cross-socket broadcast timing/ordering in the test transport isn't worth pinning
    down exactly (every connect/join/action fans out state+hand to every socket) —
    scanning forward for the specific message we care about is far more robust than
    counting positions.
    """
    for _ in range(max_tries):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError(f"did not see expected message within {max_tries} reads")


def _make_table(client):
    tok = register_and_login(client, "host@example.com", "host")
    h = {"Authorization": f"Bearer {tok}"}
    tid = client.post("/api/v1/tables", json={
        "name": "WS", "mode": "free", "max_players": 2, "num_deals": 2,
    }, headers=h).json()["id"]
    return tid


def test_two_players_join_start_and_finish(client):
    tid = _make_table(client)
    t1 = register_and_login(client, "wsa@example.com", "wsa")
    t2 = register_and_login(client, "wsb@example.com", "wsb")

    with client.websocket_connect(f"/ws/game/{tid}?token={t1}") as ws1:
        _drain(ws1, want_event="joined")
        with client.websocket_connect(f"/ws/game/{tid}?token={t2}") as ws2:
            _drain(ws2, want_event="joined")
            # start the (single) deal
            ws1.send_json({"action": "start"})
            msgs = _drain(ws1, want_event="deal_started")
            assert any(m.get("event") == "deal_started" for m in msgs)

            # a player receives a private 13-card hand at some point
            got_hand = False
            for _ in range(8):
                m = ws1.receive_json()
                if m.get("type") == "hand" and len(m.get("cards", [])) == 13:
                    got_hand = True
                    break
            assert got_hand


def test_reject_without_token(client):
    tid = _make_table(client)
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/game/{tid}") as ws:
            ws.receive_json()


def test_full_turn_loop_draw_discard_declare_result(client):
    """Drives the whole 6->12 flow over the real websocket path: deal, several
    draw/discard turns alternating players, then a valid Declare that resolves to
    a settled result with the winner correctly identified."""
    from app.services.game_manager import game_manager

    host_tok = register_and_login(client, "loophost@example.com", "loophost")
    tid = client.post("/api/v1/tables", json={
        "name": "Loop", "mode": "free", "max_players": 2, "num_deals": 2,
    }, headers={"Authorization": f"Bearer {host_tok}"}).json()["id"]
    t1 = register_and_login(client, "loopa@example.com", "loopa")
    t2 = register_and_login(client, "loopb@example.com", "loopb")
    id1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).json()["id"]
    id2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]

    with client.websocket_connect(f"/ws/game/{tid}?token={t1}") as ws1:
        with client.websocket_connect(f"/ws/game/{tid}?token={t2}") as ws2:
            ws1.send_json({"action": "start"})
            _recv_until(ws1, lambda m: m.get("event") == "deal_started")

            game = game_manager.get(tid)
            sockets = {id1: ws1, id2: ws2}

            def current_ws():
                return sockets[game.current_player().id]

            # Steps 7-10, twice around: draw from stock, discard the drawn card, next player.
            for _ in range(4):
                ws = current_ws()
                ws.send_json({"action": "draw", "source": "stock"})
                hand_msg = _recv_until(
                    ws, lambda m: m.get("type") == "hand" and len(m.get("cards", [])) == 14
                )
                ws.send_json({"action": "discard", "card": hand_msg["cards"][-1]})
                ws.receive_json()  # sync barrier: server has applied the discard by now

            # Step 8 (arrange) + 11 (declare): rig the current player's hand to a
            # guaranteed-valid grouping so we can exercise the real declare() path
            # through the websocket without depending on the shuffle. Built entirely
            # from sequences with disjoint rank ranges (never sets, and no rank shared
            # by more than one group) so that whatever the deal's random wild rank
            # turns out to be, it can knock at most one card out of at most two of the
            # four groups — never enough to zero out a group's natural anchors or drop
            # below 2 sequences with >=1 pure. A set-based rigging (e.g. three 2s) is
            # NOT safe here: if the wild rank happens to equal that set's rank, every
            # card in it goes wild at once and the group becomes invalid outright.
            winner_id = game.current_player().id
            winner = game.current_player()
            winner.hand = hand("AH", "2H", "3H", "4H", "6S", "7S", "8S",
                                "10D", "JD", "QD", "2C", "3C", "4C")
            # Prevent the upcoming draw from coincidentally pulling a real card that
            # shares a code with one of the rigged ones above (duplicate codes would
            # break the code->card lookup declare() uses to build groups).
            rigged_codes = {c.code for c in winner.hand}
            game.shoe.stock = [c for c in game.shoe.stock if c.code not in rigged_codes]
            ws = sockets[winner_id]
            ws.send_json({"action": "draw", "source": "stock"})
            _recv_until(ws, lambda m: m.get("type") == "hand" and len(m.get("cards", [])) == 14)

            ws.send_json({"action": "declare", "groups": [
                ["AH0", "2H0", "3H0", "4H0"],
                ["6S0", "7S0", "8S0"],
                ["10D0", "JD0", "QD0"],
                ["2C0", "3C0", "4C0"],
            ]})
            declared = _recv_until(ws, lambda m: m.get("event") == "declared")
            assert declared["valid"] is True

    # deal 1 of 2 just finished via a valid Declare — this is exactly what step 12
    # (Result) needs: a settled deal with the winner correctly identified.
    assert game.phase.value == "deal_over"
    assert game.winner_id == winner_id


def test_duplicate_action_id_does_not_double_apply(client):
    """A retried draw with the same action_id (double-click, dropped-ack retry) must
    not draw a second card — the second copy should be a no-op resync."""
    from app.services.game_manager import game_manager

    host_tok = register_and_login(client, "idemphost@example.com", "idemphost")
    tid = client.post("/api/v1/tables", json={
        "name": "Idem", "mode": "free", "max_players": 2, "num_deals": 2,
    }, headers={"Authorization": f"Bearer {host_tok}"}).json()["id"]
    t1 = register_and_login(client, "idempa@example.com", "idempa")
    t2 = register_and_login(client, "idempb@example.com", "idempb")
    id1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).json()["id"]
    id2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]

    with client.websocket_connect(f"/ws/game/{tid}?token={t1}") as ws1:
        with client.websocket_connect(f"/ws/game/{tid}?token={t2}") as ws2:
            ws1.send_json({"action": "start"})
            _recv_until(ws1, lambda m: m.get("event") == "deal_started")

            game = game_manager.get(tid)
            sockets = {id1: ws1, id2: ws2}
            cur_id = game.current_player().id
            ws = sockets[cur_id]

            ws.send_json({"action": "draw", "source": "stock", "action_id": "dup-draw-1"})
            hand_msg = _recv_until(
                ws, lambda m: m.get("type") == "hand" and len(m.get("cards", [])) == 14
            )
            assert len(hand_msg["cards"]) == 14

            # Retry with the SAME action_id — must not draw a second card.
            ws.send_json({"action": "draw", "source": "stock", "action_id": "dup-draw-1"})
            state_msg = _recv_until(ws, lambda m: m.get("type") == "state")
            player = next(p for p in state_msg["state"]["players"] if p["id"] == cur_id)
            assert player["hand_count"] == 14  # not 15

            # A genuinely new action_id for the same logical action is NOT deduped —
            # only exact retries are. Discarding for real should still work afterward.
            ws.send_json({"action": "discard", "card": hand_msg["cards"][-1], "action_id": "discard-1"})
            state_msg2 = _recv_until(ws, lambda m: m.get("type") == "state")
            player2 = next(p for p in state_msg2["state"]["players"] if p["id"] == cur_id)
            assert player2["hand_count"] == 13


def test_reconnect_preserves_hand_not_reset(client):
    """Disconnecting and reconnecting mid-deal must return the SAME hand — the deal
    must not restart or reshuffle just because a socket dropped."""
    tid = _make_table(client)
    t1 = register_and_login(client, "recona@example.com", "recona")
    t2 = register_and_login(client, "reconb@example.com", "reconb")

    original_hand = None
    with client.websocket_connect(f"/ws/game/{tid}?token={t1}") as ws1:
        with client.websocket_connect(f"/ws/game/{tid}?token={t2}"):
            ws1.send_json({"action": "start"})
            hand_msg = _recv_until(
                ws1, lambda m: m.get("type") == "hand" and len(m.get("cards", [])) == 13
            )
            original_hand = set(hand_msg["cards"])
        # player 2's socket context exits here — they disconnect, player 1 stays connected.

    # ws1's context now also exits (player 1 disconnects too). Reconnect as player 1:
    with client.websocket_connect(f"/ws/game/{tid}?token={t1}") as ws1b:
        hand_msg2 = _recv_until(ws1b, lambda m: m.get("type") == "hand")
        assert set(hand_msg2["cards"]) == original_hand
