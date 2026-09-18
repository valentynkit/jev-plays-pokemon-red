"""The published-number path: Brier, the constant predictor, the clock, the cost."""

from jpp import measure


def row(**kw):
    base = {"battle_index": 0, "nouls": {}, "active_hp_fraction": 1.0}
    return base | kw


def test_brier_is_the_mean_squared_error_against_the_label():
    assert measure.brier([(1.0, 1), (0.0, 0)]) == 0.0
    assert measure.brier([(1.0, 0), (0.0, 1)]) == 1.0
    assert measure.brier([(0.5, 1), (0.5, 0)]) == 0.25


def test_the_constant_predictor_is_the_base_rate_on_the_same_rows():
    run = [
        row(nouls={"faints_this_turn": 0.9}, active_hp_fraction=0.5),
        row(nouls={"faints_this_turn": 0.1}, active_hp_fraction=0.0),
        row(active_hp_fraction=0.3),
    ]
    s = measure.summarise([run])
    assert s["labelled_turns"] == 2
    assert s["base_rate"] == 0.5
    # p(1-p) at the base rate, the number ours has to beat
    assert s["constant_predictor_brier"] == 0.25
    assert s["brier"] == 0.01  # both calls landed on the right side
    assert s["beats_constant_predictor"] is True


def test_stand_in_rows_never_score():
    run = [
        row(source="fake", nouls={"faints_this_turn": 1.0}),
        row(active_hp_fraction=0.0),
    ]
    s = measure.summarise([run])
    assert s["labelled_turns"] == 0
    assert "brier" not in s
    assert s["stand_in_rows"] == 1
    assert "not enough labelled turns" in measure.lines(s, "note")[1]


def test_a_turn_is_still_labelled_across_a_row_with_no_hp():
    """An overworld row logged inside the same battle must not drop the turn."""
    run = [
        row(nouls={"faints_this_turn": 0.8}),
        row(active_hp_fraction=None),
        row(active_hp_fraction=0.0),
    ]
    assert measure.pairs(run) == [(0.8, 1)]


def test_a_forced_switch_counts_as_the_faint_it_was():
    """A fainted mon never gets another decision, so its own HP row never shows zero."""
    judged = row(
        nouls={"faints_this_turn": 0.7}, active_slot=0, choice="use_move_ember"
    )
    after = row(active_slot=1, active_hp_fraction=1.0)
    assert measure.pairs([judged, after]) == [(0.7, 1)]


def test_switching_on_purpose_is_not_a_faint():
    judged = row(
        nouls={"faints_this_turn": 0.7}, active_slot=0, choice="switch_to_pidgey"
    )
    after = row(active_slot=1, active_hp_fraction=1.0)
    assert measure.pairs([judged, after]) == [(0.7, 0)]


def test_a_run_recorded_before_the_slot_was_logged_still_scores():
    judged = row(nouls={"faints_this_turn": 0.7})
    assert measure.pairs([judged, row(active_hp_fraction=0.0)]) == [(0.7, 1)]


def test_a_label_never_crosses_a_battle():
    run = [
        row(nouls={"faints_this_turn": 0.8}),
        row(battle_index=1, active_hp_fraction=0.0),
    ]
    assert measure.pairs(run) == []


def test_cost_and_clock_cover_the_same_rows():
    """A replayed cassette carries tokens and no latency; it must not inflate $/hour."""
    run = [
        row(mode="call-latency-only", latency_ms=1000, input_tokens=100),
        row(mode="call-latency-only", latency_ms=None, input_tokens=1000),
    ]
    s = measure.summarise([run])
    assert s["seconds"] == 1.0
    assert s["input_tokens"] == 100
    assert s["usd_per_hour"] == round(100 * 0.042 / 1e6 * 3600, 4)


def test_an_untimed_run_says_so_instead_of_printing_a_zero():
    s = measure.summarise([[row(latency_ms=None), row(latency_ms=None)]])
    assert s["decisions_per_second"] is None
    assert "not measured" in measure.lines(s, "note")[0]


def test_wilson_edges():
    assert measure.wilson(0, 0) == (0.0, 1.0)
    low, high = measure.wilson(0, 10)
    assert low == 0.0 and 0.0 < high < 0.35
    low, high = measure.wilson(10, 10)
    assert high == 1.0 and 0.65 < low < 1.0
