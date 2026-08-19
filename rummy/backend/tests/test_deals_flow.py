from app.game_engine.deals_rummy import DealsRummyGame, GameConfig, Phase


def _new_game(num_players=2, num_deals=2):
    g = DealsRummyGame("t1", GameConfig(num_deals=num_deals, starting_chips=160))
    for i in range(num_players):
        g.add_player(f"p{i}", f"Player {i}")
    return g


def test_deal_setup_deterministic():
    g = _new_game()
    g.start_deal(seed=42)
    assert g.phase == Phase.AWAIT_DRAW
    assert g.deal_number == 1
    for p in g.players:
        assert len(p.hand) == 13
    assert g.wild_joker is not None
    assert g.shoe.top_discard() is not None


def test_turn_draw_discard_cycle():
    g = _new_game()
    g.start_deal(seed=1)
    cur = g.current_player()
    g.draw(cur.id, "stock")
    assert g.phase == Phase.AWAIT_DISCARD
    assert len(cur.hand) == 14
    discard_code = cur.hand[0].code
    g.discard(cur.id, discard_code)
    assert g.phase == Phase.AWAIT_DRAW
    assert g.current_player().id != cur.id  # turn advanced


def test_cannot_act_out_of_turn():
    g = _new_game()
    g.start_deal(seed=1)
    other = g.players[(g.turn_index + 1) % 2]
    import pytest
    with pytest.raises(Exception):
        g.draw(other.id, "stock")


def test_first_drop_scores_twenty_and_settles():
    g = _new_game(num_players=2, num_deals=1)
    g.start_deal(seed=7)
    cur = g.current_player()
    pts = g.drop(cur.id)
    assert pts == 20
    # opponent is last standing -> deal settles, game over (1 deal)
    assert g.phase == Phase.GAME_OVER
    dropper = next(p for p in g.players if p.id == cur.id)
    assert dropper.chips == 160 - 20
    winner = next(p for p in g.players if p.id != cur.id)
    assert winner.chips == 160 + 20
    # regression: attrition wins (everyone else drops) must set winner_id too,
    # not just explicit declare() wins — this drives both the frontend result
    # screen and real-money wallet settlement.
    assert g.winner_id == winner.id


def test_zero_sum_chips_over_deal():
    g = _new_game(num_players=3, num_deals=1)
    g.start_deal(seed=3)
    total_before = sum(p.chips for p in g.players)
    # two players first-drop; last wins by attrition
    # drop the current player, then whoever is current next
    g.drop(g.current_player().id)
    if g.phase not in (Phase.GAME_OVER,):
        g.drop(g.current_player().id)
    total_after = sum(p.chips for p in g.players)
    assert total_before == total_after  # zero-sum
    assert g.phase == Phase.GAME_OVER


def test_full_two_deal_game_completes():
    g = _new_game(num_players=2, num_deals=2)
    for _ in range(2):
        g.start_deal(seed=11)
        # both deals resolved by an immediate drop
        g.drop(g.current_player().id)
    assert g.phase == Phase.GAME_OVER
    assert g.winner_id is not None


# ---- Pool Rummy: open-ended deals + elimination at a cumulative point limit -----------

def test_pool_rummy_ignores_num_deals_and_continues_until_one_remains():
    g = DealsRummyGame("t1", GameConfig(pool_limit=45, starting_chips=160))
    g.add_player("p0", "P0")
    g.add_player("p1", "P1")

    deals_played = 0
    while g.phase != Phase.GAME_OVER and deals_played < 10:
        g.start_deal(seed=deals_played)
        # First drop every deal = 20 points to whoever is up; a single drop can never
        # cross a 45-point limit, so this must take at least two deals.
        g.drop(g.current_player().id)
        deals_played += 1

    assert g.phase == Phase.GAME_OVER
    assert deals_played >= 2
    eliminated = [p for p in g.players if p.eliminated]
    live = [p for p in g.players if not p.eliminated]
    assert len(eliminated) == 1
    assert eliminated[0].total_score >= 45
    assert len(live) == 1
    assert g.winner_id == live[0].id


def test_pool_rummy_eliminated_player_excluded_from_next_deal():
    g = DealsRummyGame("t1", GameConfig(pool_limit=25, starting_chips=160))
    for i in range(3):
        g.add_player(f"p{i}", f"P{i}")
    g.start_deal(seed=2)
    g.drop(g.current_player().id)  # first drop = 20 (< 25, survives)
    cur = g.current_player().id
    g.draw(cur, "stock")  # must draw first, or this would also score as a first-drop
    g.drop(cur)  # middle drop = 40 (>= 25, eliminated)
    assert g.phase == Phase.DEAL_OVER  # 2 of 3 live -> pool continues, not game over

    eliminated = [p for p in g.players if p.eliminated]
    assert len(eliminated) == 1
    assert eliminated[0].deal_points == 40
    assert len([p for p in g.players if not p.eliminated]) == 2

    g.start_deal(seed=9)
    for p in g.players:
        if p.eliminated:
            assert len(p.hand) == 0
        else:
            assert len(p.hand) == 13


def test_pool_rummy_exact_101_boundary_eliminates():
    g = DealsRummyGame("t1", GameConfig(pool_limit=101, starting_chips=160))
    g.add_player("p0", "P0")
    g.add_player("p1", "P1")
    g.start_deal(seed=1)
    dropper = g.current_player()
    dropper.total_score = 81  # a 20-point first-drop lands exactly on 101
    g.drop(dropper.id)
    after = next(p for p in g.players if p.id == dropper.id)
    assert after.total_score == 101
    assert after.eliminated is True  # >= is inclusive of the exact boundary


def test_pool_rummy_one_point_under_101_survives():
    g = DealsRummyGame("t1", GameConfig(pool_limit=101, starting_chips=160))
    g.add_player("p0", "P0")
    g.add_player("p1", "P1")
    g.start_deal(seed=1)
    dropper = g.current_player()
    dropper.total_score = 80  # lands on 100, one under the limit
    g.drop(dropper.id)
    after = next(p for p in g.players if p.id == dropper.id)
    assert after.total_score == 100
    assert after.eliminated is False


def test_pool_rummy_exact_201_boundary_eliminates():
    g = DealsRummyGame("t1", GameConfig(pool_limit=201, starting_chips=160))
    g.add_player("p0", "P0")
    g.add_player("p1", "P1")
    g.start_deal(seed=1)
    dropper = g.current_player()
    dropper.total_score = 181  # lands exactly on 201
    g.drop(dropper.id)
    after = next(p for p in g.players if p.id == dropper.id)
    assert after.total_score == 201
    assert after.eliminated is True


def test_pool_rummy_multiple_players_eliminated_in_same_deal():
    g = DealsRummyGame("t1", GameConfig(pool_limit=101, starting_chips=160))
    for i in range(4):
        g.add_player(f"p{i}", f"P{i}")
    g.start_deal(seed=4)
    for p in g.players:
        p.total_score = 85  # a 20-point first-drop pushes any dropper to 105 (>= 101)
    for _ in range(3):  # 3 of 4 drop -> deal settles by attrition, 1 winner remains
        g.drop(g.current_player().id)

    eliminated = [p for p in g.players if p.eliminated]
    live = [p for p in g.players if not p.eliminated]
    assert len(eliminated) == 3
    assert all(p.total_score == 105 for p in eliminated)
    assert len(live) == 1
    assert g.phase == Phase.GAME_OVER
    assert g.winner_id == live[0].id
