"""The overlay renders headlessly, so the layout is checked without a display."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from jpp import overlay  # noqa: E402

RECORD = {
    "t": 0.0,
    "goal": "win_lab_rival",
    "kind": "battle",
    "battle_index": 1,
    "state": {"goal": "Win the rival battle in Oak's lab.", "battle": {"turn": 3}},
    "options": {"use_move_scratch": "...", "use_move_ember": "..."},
    "choice": "use_move_ember",
    "probabilities": {"use_move_ember": 0.71, "use_move_scratch": 0.18, "other": 0.11},
    "nouls": {"faints_this_turn": 0.23},
    "latency_ms": 104.0,
    "input_tokens": 420,
    "active_hp_fraction": 0.42,
}


def test_bars_animate_from_the_previous_values_to_the_new():
    view = overlay.Overlay()
    try:
        view.feed(RECORD)
        assert view.shown["use_move_ember"] == 0.0
        for _ in range(3):
            assert view.draw(None)
        assert 0.0 < view.shown["use_move_ember"] <= 0.71
        for _ in range(40):
            view.draw(None)
        assert abs(view.shown["use_move_ember"] - 0.71) < 0.01
    finally:
        pygame.quit()


def test_it_draws_every_option_and_survives_a_missing_frame():
    view = overlay.Overlay()
    try:
        view.feed(RECORD)
        assert view.draw(None)
        assert set(view.target) == set(RECORD["probabilities"])
        assert view.latencies == [104.0]
    finally:
        pygame.quit()


def test_long_state_is_scrolled_rather_than_clipped():
    big = {f"key_{i}": i for i in range(200)}
    rows = overlay.state_lines(big, 78, 20)
    assert len(rows) == 20 and rows[2].strip() == "..."


def test_json_tinting_separates_keys_strings_and_numbers():
    assert overlay.tint('  "species":') == overlay.KEY
    assert overlay.tint('  "CHARMANDER",') == overlay.STRING
    assert overlay.tint("  0.42,") == overlay.NUMBER


def test_the_ticker_rate_comes_from_call_latency_not_the_replay_clock():
    assert overlay.measured_rate([]) is None
    assert overlay.measured_rate([0.0, 0.0]) is None  # untimed rows are not a zero rate
    assert abs(overlay.measured_rate([1000.0, 1000.0]) - 1.0) < 1e-9
    assert abs(overlay.measured_rate([836.0]) - 1.196) < 0.001


def test_render_frames_writes_one_png_per_frame(tmp_path):
    run = tmp_path / "run.jsonl"
    run.write_text(json.dumps(RECORD) + "\n")
    out = tmp_path / "frames"
    assert overlay.render_frames(run, out, fps=10, rate=2.0, seconds=1) == 10
    assert sorted(p.name for p in out.glob("*.png"))[:2] == ["f00000.png", "f00001.png"]


def test_bar_width_depends_on_elapsed_time_not_on_how_often_draw_ran():
    """A still grabbed from a 30 fps dump must match one from a 60 fps window."""
    widths = []
    for draws in (2, 20):
        view = overlay.Overlay()
        try:
            view.now = 0.0
            view.feed(RECORD)
            for i in range(draws):
                view.now = 0.15 * (i + 1) / draws
                view.draw(None)
            widths.append(view.shown["use_move_ember"])
        finally:
            pygame.quit()
    assert abs(widths[0] - widths[1]) < 1e-9


def test_stand_in_rows_never_reach_a_frame_unless_asked_for(tmp_path):
    run = tmp_path / "run.jsonl"
    run.write_text(
        json.dumps(RECORD | {"source": "jev"})
        + "\n"
        + json.dumps(RECORD | {"source": "fake"})
        + "\n"
    )
    assert len(overlay._replay_source(run)[0]) == 1
    assert len(overlay._replay_source(run, include_stand_ins=True)[0]) == 2


def test_a_fallback_row_is_not_priced_as_a_jev_call():
    """Its latency is a failed attempt, seconds of retry under a rate limit."""
    view = overlay.Overlay()
    try:
        view.feed(RECORD | {"latency_ms": 4000.0, "fell_back": True})
        assert overlay.measured_rate(view.latencies) is None
        view.feed(RECORD | {"latency_ms": 500.0, "fell_back": False})
        assert abs(overlay.measured_rate(view.latencies) - 2.0) < 1e-9
    finally:
        pygame.quit()


def test_a_fallback_still_draws_its_options():
    """Blanking the panel reads as broken; the options were real, nothing answered."""
    view = overlay.Overlay()
    try:
        view.feed(RECORD | {"probabilities": {}, "fell_back": True})
        assert set(view.target) == set(RECORD["options"])
        assert all(v == 0.0 for v in view.target.values())
        assert view.draw(None)
    finally:
        pygame.quit()
