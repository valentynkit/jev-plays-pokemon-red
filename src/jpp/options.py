"""Legal actions, described by intent, plus one state builder per branch kind.

Two rules do the work here. Jev picks from a deck the code already proved legal, so it
cannot name a button or an option that does not exist. And each branch kind builds its own
state: sending the whole world is CONTEXT section 4's first jaggedness risk, and a padded
state measurably moves the answer.
"""

from dataclasses import dataclass

from . import facts, symbols as S


@dataclass(frozen=True)
class Branch:
    """What the classifier hands to Jev: a kind, a state body, the legal options."""

    kind: str
    state: dict
    options: dict


POTION = 0x14  # constants/item_constants.asm
ITEM_NAMES = {POTION: "Potion"}
POTION_HEAL = 20


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def bag(mem) -> dict[int, int]:
    """item id -> quantity, from wNumBagItems / wBagItems."""
    count = min(mem[S.NUM_BAG_ITEMS], 20)
    return {
        mem[S.BAG_ITEMS + i * 2]: mem[S.BAG_ITEMS + i * 2 + 1] for i in range(count)
    }


def bench(state) -> list:
    """Party members that can be switched in: not fainted, not the one already out.

    The one already out is the slot wPlayerMonNumber names, not "the one with the same
    species": two of a species would otherwise hide each other.
    """
    return [m for m in state.party if not m.fainted and m.slot - 1 != state.active_slot]


def battle_options(state, items: dict[int, int] | None = None) -> dict[str, str]:
    """Moves with PP left, healthy bench members, and a Potion if one is in the bag."""
    active, foe = state.battle.active, state.battle.opponent
    out: dict[str, str] = {}
    for name, pp in zip(active.moves, active.pp):
        if pp > 0:
            out[f"use_move_{_slug(name)}"] = facts.describe_move(name, pp, foe.types)
    for mon in bench(state):
        out[f"switch_to_{_slug(mon.species)}"] = facts.describe_switch(mon)
    missing = active.max_hp - active.hp
    if items and items.get(POTION) and missing:
        out["use_item_potion"] = (
            f"use a Potion, restores {POTION_HEAL} HP of {missing} missing"
        )
    if state.battle.kind == "wild":
        out["run_away"] = "run away from this wild Pokemon and keep walking the route"
    return out


def battle_branch(state, goal, items=None, turn=None) -> Branch:
    active, foe = state.battle.active, state.battle.opponent
    body = {
        "goal": goal.sentence,
        "battle": {
            "kind": state.battle.kind,
            "active": facts.battle_summary(active),
            "opponent": facts.battle_summary(foe),
        },
        "party": [facts.battle_summary(m) | {"slot": m.slot} for m in bench(state)],
    }
    if turn is not None:
        body["battle"]["turn"] = turn
    opts = battle_options(state, items)
    body["options"] = opts
    return Branch("battle", body, opts)


def tie_branch(state, goal, waypoint, free: list[str]) -> Branch:
    """The overworld tie: blocked, and two sidesteps are equally good."""
    opts = {
        f"step_{d}": f"take one step {d} and try again from there" for d in sorted(free)
    }
    body = {
        "goal": goal.sentence,
        "current_map": state.map_name,
        "position": {"x": state.x, "y": state.y},
        "waypoint": {"x": waypoint[0], "y": waypoint[1]},
        "options": opts,
    }
    return Branch("tie", body, opts)


VISIBLE_TEXT_CHARS = 180  # two text box lines and a bit, CONTEXT section 4 risk 3


def dialogue_branch(state, goal, visible_text: str, choices: list[str]) -> Branch:
    """A menu with a cursor in the overworld, read off the screen by `screen.py`.

    The truncation is deliberate: NPC text is full of imperatives and the model does not
    treat state as untrusted.
    """
    opts = {f"answer_{_slug(c)}": f"answer {c}" for c in choices}
    body = {
        "goal": goal.sentence,
        "visible_text": visible_text[:VISIBLE_TEXT_CHARS],
        "options": opts,
    }
    return Branch("dialogue", body, opts)


# --- turning a chosen option back into button presses ---
# The Gen 1 battle menu is two columns, ids 0 and 1 down the left, 2 and 3 down the right
# (`DisplayBattleMenu`, engine/battle/core.asm: "sub 2 ; check if the cursor is in the
# left column", and +2 again on the A press):
#
#     FIGHT (0)   PKMN (2)
#     ITEM  (1)   RUN  (3)
#
# Every one of these menus remembers its cursor. The battle menu restores
# wBattleAndStartSavedMenuItem, the move list starts on wPlayerMoveListIndex, the party
# list on wPartyAndBillsPCSavedMenuItem. So the sequence is a delta from where the cursor
# actually is, never a path from an assumed corner: on turn 2 onwards the corner is wrong
# and a blind sequence confirms the wrong item.
ROOT_CELL = {"fight": (0, 0), "item": (0, 1), "pkmn": (1, 0), "run": (1, 1)}


def _root_path(state, entry: str) -> list[str]:
    saved = state.battle_menu_item & 0b11
    return _walk((saved // 2, saved % 2), ROOT_CELL[entry])


def _walk(current: tuple[int, int], target: tuple[int, int]) -> list[str]:
    (c0, r0), (c1, r1) = current, target
    across = ["right"] * (c1 - c0) if c1 > c0 else ["left"] * (c0 - c1)
    down = ["down"] * (r1 - r0) if r1 > r0 else ["up"] * (r0 - r1)
    return across + down


def _list_path(current: int, target: int) -> list[str]:
    return (
        ["down"] * (target - current)
        if target > current
        else ["up"] * (current - target)
    )


def buttons_for(state, branch: Branch, option: str) -> list[str]:
    if branch.kind in ("tie", "dialogue"):
        if option.startswith("step_"):
            return [option[len("step_") :]]
        if option.startswith("answer_"):
            # the cursor sits on one of the choices already; A alone always takes the
            # one it is on, which answered YES to every prompt including the nickname
            wanted = option[len("answer_") :]
            names = [k[len("answer_") :] for k in branch.options]
            if wanted in names:
                return _list_path(state.menu_item, names.index(wanted)) + ["a"]
        return ["a"]
    active = state.battle.active
    if option.startswith("use_move_"):
        # the menu lists every move the mon knows, PP or not, so the row is the move's
        # own slot and not its position among the legal ones
        wanted = option[len("use_move_") :]
        index = next(i for i, n in enumerate(active.moves) if _slug(n) == wanted)
        return (
            _root_path(state, "fight")
            + ["a"]
            + _list_path(state.move_list_index, index)
            + ["a"]
        )
    if option.startswith("switch_to_"):
        # likewise the party list shows fainted members; the row is the slot
        wanted = option[len("switch_to_") :]
        slot = next(m.slot for m in state.party if _slug(m.species) == wanted)
        return (
            _root_path(state, "pkmn")
            + ["a"]
            + _list_path(state.party_menu_item, slot - 1)
            + ["a", "a"]
        )
    if option == "use_item_potion":
        # ponytail: the bag holds one Potion at this point in the game, so the item row is
        # row 0 and wBagSavedMenuItem cannot have moved. A second item needs the same
        # delta treatment as the two lists above.
        return _root_path(state, "item") + ["a", "a", "a"]
    if option == "run_away":
        return _root_path(state, "run") + ["a"]
    return ["a"]
