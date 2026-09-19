import json

from jpp import options, policy, symbols as S
from jpp.decode import decode
from jpp.goals import GOALS

import make_ram

GOAL = next(g for g in GOALS if g.name == "win_lab_rival")


def battle_state(with_potion=False):
    ram = make_ram.battle()
    if with_potion:
        ram[S.NUM_BAG_ITEMS] = 1
        ram[S.BAG_ITEMS], ram[S.BAG_ITEMS + 1] = options.POTION, 2
    return decode(bytes(ram)), bytes(ram)


def test_battle_options_are_intent_sentences_not_buttons():
    state, mem = battle_state()
    opts = options.battle_options(state, options.bag(mem))
    assert set(opts) == {
        "use_move_scratch",
        "use_move_growl",
        "use_move_ember",
        "switch_to_pidgey",
    }
    assert opts["use_move_ember"].startswith(
        "attack with EMBER, a Fire move, 25 of 25 PP left"
    )
    assert "not very effective against WATER" in opts["use_move_ember"]
    assert "the opponent gets a free turn" in opts["switch_to_pidgey"]
    assert not any(b in " ".join(opts.values()) for b in ("press", "button", "cursor"))


def test_a_move_with_no_pp_is_not_offered():
    ram = make_ram.battle()
    ram[S.BATTLE_MON + S.B_PP + 2] = 0  # EMBER runs dry
    opts = options.battle_options(decode(bytes(ram)))
    assert "use_move_ember" not in opts and "use_move_scratch" in opts


def test_a_potion_appears_only_when_the_bag_holds_one():
    state, mem = battle_state(with_potion=True)
    assert "use_item_potion" in options.battle_options(state, options.bag(mem))
    plain, plain_mem = battle_state()
    assert "use_item_potion" not in options.battle_options(
        plain, options.bag(plain_mem)
    )


def test_run_away_only_exists_in_a_wild_battle():
    ram = make_ram.battle()
    ram[S.IS_IN_BATTLE] = 1
    assert "run_away" in options.battle_options(decode(bytes(ram)))
    assert "run_away" not in options.battle_options(battle_state()[0])


def test_the_state_body_is_trimmed_to_the_branch():
    state, mem = battle_state()
    branch = options.battle_branch(state, GOAL, items=options.bag(mem), turn=3)
    assert set(branch.state) == {"goal", "battle", "party", "options"}
    assert branch.state["battle"]["turn"] == 3
    assert branch.state["goal"] == GOAL.sentence
    assert [m["species"] for m in branch.state["party"]] == [
        "PIDGEY"
    ]  # active trimmed out
    blob = json.dumps(branch.state)
    assert "badges" not in blob and "money" not in blob and "events" not in blob


def test_tie_and_dialogue_branches_send_only_their_own_fields():
    state, _ = battle_state()
    tie = options.tie_branch(state, GOAL, (12, 11), ["left", "down"])
    assert set(tie.state) == {"goal", "current_map", "position", "waypoint", "options"}
    assert set(tie.options) == {"step_left", "step_down"}
    talk = options.dialogue_branch(
        state, GOAL, "DO YOU WANT TO NICKNAME IT?", ["YES", "NO"]
    )
    assert set(talk.state) == {"goal", "visible_text", "options"}


def test_every_choice_carries_the_other_escape_hatch():
    state, _ = battle_state()
    for branch in (
        options.battle_branch(state, GOAL),
        options.tie_branch(state, GOAL, (1, 1), ["left", "right"]),
    ):
        criteria = policy.questions_for(branch)["next_action"]["criteria"]
        assert criteria["other"] is None
        assert set(criteria) == set(branch.options) | {"other"}


def test_buttons_drive_the_cursor_and_never_come_from_jev():
    state, _ = battle_state()
    branch = options.battle_branch(state, GOAL)
    assert options.buttons_for(state, branch, "use_move_scratch") == ["a", "a"]
    assert options.buttons_for(state, branch, "use_move_ember") == [
        "a",
        "down",
        "down",
        "a",
    ]
    assert options.buttons_for(state, branch, "switch_to_pidgey") == [
        "right",
        "a",
        "down",
        "a",
        "a",
    ]
    tie = options.tie_branch(state, GOAL, (1, 1), ["left", "right"])
    assert options.buttons_for(state, tie, "step_left") == ["left"]


def test_the_cursor_walks_from_where_the_game_left_it():
    """Gen 1 menus are sticky. Turn 2 does not start on FIGHT or on the first move."""
    ram = make_ram.battle()
    ram[S.BATTLE_SAVED_MENU_ITEM] = 3  # RUN, bottom right, from last turn
    ram[S.PLAYER_MOVE_LIST_INDEX] = 2  # EMBER was the last move picked
    state = decode(bytes(ram))
    branch = options.battle_branch(state, GOAL)
    assert options.buttons_for(state, branch, "use_move_scratch") == [
        "left",
        "up",
        "a",
        "up",
        "up",
        "a",
    ]
    assert options.buttons_for(state, branch, "use_move_ember") == [
        "left",
        "up",
        "a",
        "a",
    ]
    assert options.buttons_for(state, branch, "switch_to_pidgey") == [
        "up",
        "a",
        "down",
        "a",
        "a",
    ]


def test_the_move_row_is_the_move_slot_not_its_rank_among_the_legal_ones():
    """The menu lists every move the mon knows, PP or not."""
    ram = make_ram.battle()
    ram[S.BATTLE_MON + S.B_PP] = 0  # SCRATCH, slot 0, runs dry
    state = decode(bytes(ram))
    branch = options.battle_branch(state, GOAL)
    assert "use_move_scratch" not in branch.options
    assert options.buttons_for(state, branch, "use_move_ember") == [
        "a",
        "down",
        "down",
        "a",
    ]


def test_the_party_row_is_the_slot_even_with_a_fainted_member_above_it():
    ram = make_ram.battle()
    ram[S.PARTY_COUNT] = 3
    state = decode(bytes(ram))
    branch = options.battle_branch(state, GOAL)
    third = next(k for k in branch.options if k.startswith("switch_to_"))
    slot = next(m.slot for m in state.party if options._slug(m.species) in third)
    assert options.buttons_for(state, branch, third) == (
        ["right", "a"] + ["down"] * (slot - 1) + ["a", "a"]
    )


def test_answering_no_moves_the_cursor_off_yes():
    """A alone takes whatever the cursor sits on, which said YES to the nickname prompt
    and then mashed the keyboard into AAAAAAAAAAAA."""
    state = decode(bytes(make_ram.overworld()))
    branch = options.dialogue_branch(
        state, GOAL, "give a nickname to CHARMANDER?", ["YES", "NO"]
    )
    assert options.buttons_for(state, branch, "answer_yes") == ["a"]
    assert options.buttons_for(state, branch, "answer_no") == ["down", "a"]
