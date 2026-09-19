"""The emulator switches, which only ever run when a ROM exists."""

import sys
import types

from jpp import cli


def _fake_pyboy(monkeypatch):
    seen = {}

    class FakePyBoy:
        def __init__(self, rom, window):
            seen["window"] = window
            seen["speed"] = None

        def set_emulation_speed(self, n):
            seen["speed"] = n

    monkeypatch.setitem(sys.modules, "pyboy", types.SimpleNamespace(PyBoy=FakePyBoy))
    return seen


def test_the_overlay_never_lets_pyboy_open_its_own_window(monkeypatch, tmp_path):
    """pygame and pyboy ship different SDL2 builds; two windows crashes the process."""
    seen = _fake_pyboy(monkeypatch)
    cli._pyboy(tmp_path, window=False, unthrottled=False)
    assert seen == {"window": "null", "speed": None}


def test_headless_is_unthrottled_because_that_is_where_the_number_is_taken(
    monkeypatch, tmp_path
):
    seen = _fake_pyboy(monkeypatch)
    cli._pyboy(tmp_path, window=False, unthrottled=True)
    assert seen == {"window": "null", "speed": 0}


def test_probe_gets_a_real_window_at_real_speed(monkeypatch, tmp_path):
    seen = _fake_pyboy(monkeypatch)
    cli._pyboy(tmp_path, window=True, unthrottled=False)
    assert seen == {"window": "SDL2", "speed": None}
