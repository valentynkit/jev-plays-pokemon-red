"""The tick loop against a fake emulator, so the whole driver runs without a ROM.

The fake exposes exactly what `loop.Driver` uses: `memory`, `button`, `tick` and
`game_area_collision`. PyBoy satisfies the same four.
"""

import json

import pytest

import fake_jev
import make_ram
from jpp import goals, loop, options, policy, route, symbols as S
from jpp.decode import decode

WALK = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}


class FakeEmulator:
    """Directions move the player, everything else is recorded and ignored."""

    def __init__(self, ram, walls=(), warps=None, on_press=None):
        self.memory = bytearray(ram)
        self.pressed = []
        self.ticks = 0
        self.walls = set(walls)
        self.warps = warps or {}
        self.on_press = on_press

    def tick(self, frames=1):
        self.ticks += frames

    def button(self, name, frames=1):
        self.pressed.append(name)
        if name in WALK:
            dx, dy = WALK[name]
            target = (self.memory[S.X_COORD] + dx, self.memory[S.Y_COORD] + dy)
            if target not in self.walls:
                self.memory[S.X_COORD], self.memory[S.Y_COORD] = target
        here = (self.memory[S.CUR_MAP], self.memory[S.X_COORD], self.memory[S.Y_COORD])
        if here in self.warps:
            self.memory[S.CUR_MAP], self.memory[S.X_COORD], self.memory[S.Y_COORD] = (
                self.warps[here]
            )
        if self.on_press:
            self.on_press(self, name)

    def game_area_collision(self):
        return [[route.WALKABLE] * 20 for _ in range(18)]


def goal(name):
    return next(g for g in goals.GOALS if g.name == name)


def test_input_ready_is_per_button_because_joy_ignore_is_a_mask():
    ram = make_ram.overworld()
    assert loop.input_ready(decode(bytes(ram)), "a")
    assert loop.input_ready(decode(bytes(ram)), "up")

    # what scripted dialogue sets: movement locked, A deliberately left open so the text
    # can be advanced. Waiting for the whole byte to clear deadlocks against the script.
    ram[S.JOY_IGNORE] = S.PAD_SELECT | S.PAD_START | S.PAD_CTRL_PAD
    assert loop.input_ready(decode(bytes(ram)), "a")
    assert not loop.input_ready(decode(bytes(ram)), "up")

    ram[S.JOY_IGNORE] = 0xFF
    assert not loop.input_ready(decode(bytes(ram)), "a")

    ram[S.JOY_IGNORE] = 0
    ram[S.WALK_COUNTER] = 3  # mid-step: another step is refused, A is not
    assert not loop.input_ready(decode(bytes(ram)), "up")
    assert loop.input_ready(decode(bytes(ram)), "a")


def test_a_text_box_still_gets_its_a_press_while_the_script_owns_the_pad():
    """The regression that would hang every run: Oak's speech never advances."""
    ram = make_ram.overworld()
    ram[S.FONT_LOADED] = 0x01
    ram[S.JOY_IGNORE] = S.PAD_SELECT | S.PAD_START | S.PAD_CTRL_PAD
    driver = loop.Driver(FakeEmulator(ram))
    driver.tick()
    assert loop.classify(driver, goal("get_starter"), (12, 11)) == ("press", "a")


def test_a_tick_that_is_not_ready_makes_no_decision():
    ram = make_ram.overworld()
    ram[S.WALK_COUNTER] = 2
    driver = loop.Driver(FakeEmulator(ram))
    driver.tick()
    assert loop.classify(driver, goal("get_starter"), (12, 11)) == ("wait", None)


def test_a_direction_that_never_moves_stops_being_pressed():
    """Axis-first stepping walks into a wall forever without this."""
    ram = make_ram.overworld()
    ram[S.CUR_MAP], ram[S.X_COORD], ram[S.Y_COORD] = S.PALLET_TOWN, 10, 8
    emu = FakeEmulator(ram, walls={(11, 8)})
    driver = loop.Driver(emu)
    driver.tick()
    waypoint = (12, 11)
    for _ in range(loop.BLOCKED_AFTER):
        assert loop.classify(driver, goal("reach_viridian"), waypoint) == (
            "press",
            "right",
        )
        driver.press("right")
    assert driver.blocked("right")
    action, payload = loop.classify(driver, goal("reach_viridian"), waypoint)
    assert (action, payload) == ("press", "down")  # the only free step still closing in


def test_an_object_one_tile_away_is_talked_to_not_walked_into():
    ram = make_ram.overworld()
    ram[S.CUR_MAP], ram[S.X_COORD], ram[S.Y_COORD] = S.OAKS_LAB, 5, 3
    emu = FakeEmulator(ram, walls={(6, 3)})  # Charmander's poke ball
    driver = loop.Driver(emu)
    driver.tick()
    for _ in range(loop.BLOCKED_AFTER):
        driver.press("right")
    assert loop.classify(driver, goal("get_starter"), route.CHARMANDER_BALL) == (
        "press",
        "a",
    )


def test_the_overworld_walks_toward_the_waypoint_without_asking():
    ram = make_ram.bedroom()
    emu = FakeEmulator(ram, warps={(S.REDS_HOUSE_2F, 7, 1): (S.REDS_HOUSE_1F, 7, 1)})
    driver = loop.Driver(emu)
    driver.tick()
    for _ in range(20):
        action, payload = loop.classify(
            driver,
            goal("leave_house"),
            route.waypoint_for(goal("leave_house"), driver.state),
        )
        if action == "press":
            driver.press(payload)
    assert driver.state.map_id == S.REDS_HOUSE_1F
    assert set(emu.pressed) <= set(WALK) | {"a"}


def test_a_battle_menu_is_a_branch_and_carries_the_legal_options():
    ram = make_ram.battle()
    ram[S.MAX_MENU_ITEM] = 3
    driver = loop.Driver(FakeEmulator(ram))
    driver.tick()
    action, branch = loop.classify(driver, goal("win_lab_rival"), None)
    assert action == "branch" and branch.kind == "battle"
    assert "use_move_ember" in branch.options


def test_a_text_box_with_no_cursor_costs_one_a_press():
    ram = make_ram.overworld()
    ram[S.FONT_LOADED] = 0x01
    driver = loop.Driver(FakeEmulator(ram))
    driver.tick()
    assert loop.classify(driver, goal("get_starter"), (12, 11)) == ("press", "a")


def test_the_latch_runs_through_the_driver():
    ram = make_ram.battle()
    ram[S.BATTLE_RESULT] = loop.BattleLatch.WIN

    def end_the_battle(emu, name):
        emu.memory[S.IS_IN_BATTLE] = 0

    driver = loop.Driver(FakeEmulator(ram, on_press=end_the_battle))
    driver.tick()
    assert driver.latch.result is None
    driver.press("a")
    assert driver.latch.result == loop.BattleLatch.WIN


def test_play_logs_one_jsonl_record_per_decision(tmp_path):
    url, shutdown = fake_jev.serve()
    ram = make_ram.battle()
    ram[S.MAX_MENU_ITEM] = 3
    log = tmp_path / "run.jsonl"
    try:
        records = loop.play(
            FakeEmulator(ram),
            policy.Policy(policy.JevClient(base_url=url, api_key="test")),
            max_decisions=3,
            log_path=log,
        )
    finally:
        shutdown()
    assert len(records) == 3
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(lines) == 3
    assert lines[0]["choice"] == "use_move_ember"
    assert lines[0]["nouls"]["faints_this_turn"] == 0.23
    assert lines[0]["goal"] == "win_lab_rival"
    assert lines[0]["latency_ms"] > 0


def test_play_stops_when_the_goal_stack_empties():
    ram = make_ram.bedroom()
    ram[S.CUR_MAP] = S.VIRIDIAN_CITY
    ram.event(S.EVENT_GOT_STARTER)
    ram.event(S.EVENT_BATTLED_RIVAL_IN_OAKS_LAB)
    ram[S.PARTY_COUNT] = 1
    ram[S.BATTLE_RESULT] = loop.BattleLatch.WIN
    emu = FakeEmulator(ram)
    driver = loop.Driver(emu)
    driver.tick()
    driver.latch.update(2, loop.BattleLatch.WIN)
    driver.latch.update(0, loop.BattleLatch.WIN)
    stack = goals.GoalStack()
    stack.advance(driver.state, driver.latch)
    assert stack.done


@pytest.mark.parametrize("kind", ["tie", "dialogue"])
def test_buttons_for_a_non_battle_branch_never_touch_the_battle_menu(kind):
    state = decode(bytes(make_ram.overworld()))
    g = goal("get_starter")
    branch = (
        options.tie_branch(state, g, (12, 11), ["left", "down"])
        if kind == "tie"
        else options.dialogue_branch(state, g, "YES or NO?", ["YES", "NO"])
    )
    for option in branch.options:
        assert options.buttons_for(state, branch, option)


def test_a_stale_text_box_id_does_not_freeze_the_walk():
    """On a cartridge wTextBoxID reads 1 from the intro onward and never clears, so
    treating it as "a box is open" pressed A forever and the agent never left the house."""
    ram = make_ram.overworld()
    ram[S.TEXT_BOX_ID] = 0x01
    ram[S.FONT_LOADED] = 0x00
    driver = loop.Driver(FakeEmulator(ram))
    driver.tick()
    action, payload = loop.classify(driver, goal("get_starter"), (12, 11))
    assert (action, payload) != ("press", "a")
