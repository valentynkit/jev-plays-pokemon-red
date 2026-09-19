"""Drive the new-game intro and save a state the agent can actually start from.

`test_the_loop_gets_out_of_the_house` needs a save state in Red's bedroom, and the only
documented way to get one was for a human to sit through the intro. This does it headless.

    POKEMON_ROM=/path/to/red.gb uv run python fixtures/make_state.py

Two things make the intro resist a plain A-mash. `wCurMap` reads $26 while Oak is still
talking, because the game loads the destination map before it hands over control, so it
cannot be used to detect arrival. And A on the NAME list picks NEW NAME, which opens the
keyboard and mashes letters forever; the preset is one DOWN away. `wMaxMenuItem` is set a
frame or so before the menu is drawn, so the DOWN has to wait for the menu to appear.
"""

import os
import sys
from pathlib import Path

from pyboy import PyBoy

from jpp.decode import decode

NAME_LIST = 3  # NEW NAME / RED / ASH / JACK, so wMaxMenuItem is 3
SETTLE = 60  # frames between wMaxMenuItem changing and the menu being on screen


def tap(emu, button, hold=5, then=15):
    emu.button(button, hold)
    emu.tick(hold + then)


def mash_to_name_list(emu, budget):
    """A until the NAME list arms. Two lists appear, the player's then the rival's, and
    they are indistinguishable in RAM, so the caller separates them by taking the first
    one before mashing on."""
    for _ in range(budget):
        if decode(emu.memory).max_menu_item == NAME_LIST:
            return True
        emu.button("a", 4)
        emu.tick(12)
    return False


def take_preset_name(emu):
    """DOWN then A. A alone picks NEW NAME and mashes letters on the keyboard forever,
    and the DOWN has to wait for the menu to be drawn, not just for wMaxMenuItem."""
    emu.tick(SETTLE)
    emu.button("down", 6)
    emu.tick(40)
    if decode(emu.memory).menu_item != 1:
        raise SystemExit("cursor did not land on the preset name")
    emu.button("a", 6)
    emu.tick(40)


def in_control(emu) -> bool:
    """The only honest test that the script let go: press a direction and look.

    Not gated on wMaxMenuItem. That byte keeps the name list's 3 forever, because nothing
    resets it once the menu closes, so any check built on it never passes.
    """
    before = decode(emu.memory)
    for i in range(48):
        if i % 16 == 0:
            emu.button("down", 4)
        emu.tick()
    now = decode(emu.memory)
    return (now.x, now.y) != (before.x, before.y)


def play_intro(emu, budget=6000):
    """The NAME list appears twice, for the player then the rival, and wMaxMenuItem reads
    3 continuously across both: there is no gap to wait for. What does change is the
    cursor. A fresh list opens on NEW NAME at wCurrentMenuItem 0, and our own DOWN leaves
    it at 1, so "cursor is home on a name list" fires exactly twice.
    """
    taken = 0
    for step in range(budget):
        state = decode(emu.memory)
        if state.max_menu_item == NAME_LIST and state.menu_item == 0 and taken < 2:
            take_preset_name(emu)
            taken += 1
            print(f"took preset name {taken} of 2")
            continue
        if taken == 2:
            # the player lands facing the TV, and more A just reopens its text box
            for _ in range(30):
                emu.button("a", 4)
                emu.tick(12)
            for _ in range(40):
                if in_control(emu):
                    return step
                emu.button("b", 4)
                emu.tick(12)
            raise SystemExit("names taken but the player never moved")
        emu.button("a", 4)
        emu.tick(12)
    raise SystemExit(f"intro unfinished: {taken} of 2 names taken")


def main():
    rom = os.environ.get("POKEMON_ROM")
    if not rom:
        raise SystemExit("set POKEMON_ROM to a Pokemon Red ROM")
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "red-bedroom.state")
    emu = PyBoy(rom, window="null")
    emu.set_emulation_speed(0)
    try:
        step = play_intro(emu)
        state = decode(emu.memory)
        print(
            f"in control after {step} steps: map=0x{state.map_id:02X} "
            f"({state.map_name}) pos=({state.x},{state.y}) party={len(state.party)}"
        )
        with out.open("wb") as f:
            emu.save_state(f)
        print(f"wrote {out}")
    finally:
        emu.stop(save=False)


if __name__ == "__main__":
    main()
