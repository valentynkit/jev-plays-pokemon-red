"""The tick loop: advance the emulator, decode, classify, press or ask Jev.

The emulator is duck-typed. Anything with `memory`, `game_area_collision()`, `button()`
and `tick()` works, which is PyBoy and also the fake in `tests/test_loop.py`, so the whole
loop is testable without a ROM.
"""

import json
import time
from pathlib import Path

from . import goals, options, route, symbols as S
from .decode import decode
from .options import Branch
from .policy import Decision, Policy

FRAMES_PER_TICK = 8  # one decode per 8 frames, ~7.5 decodes a second at 60 fps
PRESS_FRAMES = 4
NO_PROGRESS_CAP = 40  # decisions per goal with no progress, CONTEXT section 3
BLOCKED_AFTER = 2  # presses of one direction from one tile before calling it a wall


def input_ready(state, button: str) -> bool:
    """Whether the game will honour *this* button this tick.

    Per button, because `wJoyIgnore` is a mask and not a flag: `_Joypad`
    (engine/joypad.asm) ANDs its complement into the held and pressed bytes, and scripted
    dialogue sets `PAD_SELECT | PAD_START | PAD_CTRL_PAD` precisely so that A still
    advances the text while walking is locked out. Waiting for the whole byte to clear
    deadlocks: the script is waiting for the A press, and the agent is waiting for the
    script. `wWalkCounter` is nonzero mid-step, which only blocks another step.

    Still to settle on a cartridge with `jpp probe --rom <path>`: whether any other byte
    has to be in the predicate. The mask semantics are not a guess.
    """
    if state.joy_ignore & S.BUTTON_BITS.get(button, 0):
        return False
    return button in ("a", "b") or state.walk_counter == 0


class BattleLatch:
    """`wBattleResult` only means anything just after a battle ends.

    So latch it on the tick `wIsInBattle` goes nonzero to zero, and never read it on a
    goal-check tick. The previous value (1 wild, 2 trainer, $FF lost) does not matter,
    only the flip to 0. Unset means "no battle has finished", so goal predicates that
    depend on it fail closed.

    `EndOfBattle` writes the result before it clears `wIsInBattle`, so reading both from
    one snapshot cannot race. The edge is sampled every 8 frames, so a battle that both
    starts and ends inside one gap is missed; v0.1's only latched goal is a multi-turn
    trainer battle, and a wild encounter that short would need the tick rate raised.
    """

    WIN, LOSE, DRAW = 0x00, 0x01, 0x02

    def __init__(self):
        self.previous = 0
        self.result: int | None = None
        self.count = 0

    def update(self, is_in_battle: int, battle_result: int) -> int | None:
        if self.previous != 0 and is_in_battle == 0:
            self.result = battle_result
            self.count += 1
        self.previous = is_in_battle
        return self.result


class Driver:
    """Emulator plus the decoded snapshot, one tick at a time."""

    def __init__(self, emulator):
        self.emu = emulator
        self.latch = BattleLatch()
        self.state = None
        self.turn = 0  # turns inside the current battle, reset when one ends
        # directions that have been pressed from this tile and moved nobody. Axis-first
        # stepping walks into a wall forever without this: the collision grid is the
        # screen's opinion, and an NPC or a ledge is not in it.
        self.stuck: dict[str, int] = {}

    def tick(self, frames: int = FRAMES_PER_TICK):
        self.emu.tick(frames)
        self.state = decode(self.emu.memory)
        before = self.latch.count
        self.latch.update(
            self.emu.memory[S.IS_IN_BATTLE], self.emu.memory[S.BATTLE_RESULT]
        )
        if self.latch.count != before:
            self.turn = 0
        return self.state

    def press(self, button: str):
        before = self._where()
        self.emu.button(button, PRESS_FRAMES)
        state = self.tick()
        if self._where() != before:
            self.stuck.clear()
        elif button in route.DIRECTIONS:
            self.stuck[button] = self.stuck.get(button, 0) + 1
        return state

    def _where(self):
        st = self.state
        return (st.map_id, st.x, st.y) if st else None

    def blocked(self, direction: str) -> bool:
        """One ignored press can be a timing miss; two from the same tile is a wall."""
        return self.stuck.get(direction, 0) >= BLOCKED_AFTER

    def collision(self):
        return self.emu.game_area_collision()


def probe(emulator, ticks: int, out=print, every: int = 8):
    """Print the decoded state and the input-readiness candidates once a second.

    Task 2's discovery tool: walk the route by hand while this runs, and read off both
    the waypoint tiles and which byte combination gates input.
    """
    driver = Driver(emulator)
    for i in range(ticks):
        st = driver.tick()
        if i % every:
            continue
        out(
            f"map={st.map_name}(${st.map_id:02X}) pos=({st.x},{st.y}) "
            f"battle={st.battle.kind} last_battle_result={driver.latch.result} "
            f"party={len(st.party)} | joy_ignore=${st.joy_ignore:02X} "
            f"walk_counter={st.walk_counter} text_box_id=${st.text_box_id:02X} "
            f"font_loaded={st.font_loaded} tile_in_front=${st.tile_in_front:02X} "
            f"menu={st.menu_item}/{st.max_menu_item} "
            f"battle_menu={st.battle_menu_item} move_index={st.move_list_index} "
            f"ready_a={input_ready(st, 'a')} ready_up={input_ready(st, 'up')}"
        )
    return driver


def classify(driver: Driver, goal, waypoint) -> tuple[str, object]:
    """Code decides what kind of tick this is. Only two answers reach Jev.

    Returns (action, payload): ("wait", None), ("press", button), or ("branch", Branch).
    """
    st = driver.state
    if st.in_battle:
        if st.max_menu_item > 0 or st.menu_item > 0:
            if st.joy_ignore & (S.PAD_A | S.PAD_CTRL_PAD):
                return "wait", None  # the menu is up but the script still owns the pad
            branch = options.battle_branch(
                st, goal, items=options.bag(driver.emu.memory), turn=driver.turn
            )
            return "branch", branch
        return _press(st, "a")
    if st.text_box_id:
        return _press(st, "a")  # a text box with no cursor: A costs nothing
    step = route.next_step(st, waypoint)
    if step and not driver.blocked(step):
        return _press(st, step)
    if step and route.distance(st, waypoint) == 1:
        # the waypoint is the next tile and it will not be walked onto: it is an object,
        # Oak or a poke ball. Walking into it already turned the player to face it.
        return _press(st, "a")
    free = [
        d
        for d in route.sidesteps(st, driver.collision(), waypoint)
        if not driver.blocked(d)
    ]
    if len(free) == 1:
        return _press(st, free[0])
    if len(free) > 1:
        return "branch", options.tie_branch(st, goal, waypoint, free)
    return _press(st, "a")


def _press(state, button: str) -> tuple[str, object]:
    return ("press", button) if input_ready(state, button) else ("wait", None)


def play(
    emulator,
    policy: Policy,
    max_decisions: int,
    log_path: Path | None = None,
    on_decision=None,
    max_ticks: int = 200_000,
) -> list[dict]:
    """Run until the goal stack empties or `max_decisions` Jev calls have happened."""
    driver = Driver(emulator)
    stack = goals.GoalStack()
    records: list[dict] = []
    log = log_path.open("a") if log_path else None
    stale, on_goal, where = 0, None, None
    try:
        for _ in range(max_ticks):
            if len(records) >= max_decisions or stack.done:
                break
            driver.tick()
            stack.advance(driver.state, driver.latch)
            goal = stack.current
            if goal is None:
                break
            here = _progress(driver)
            if goal is not on_goal or here != where:
                stale = 0
            on_goal, where = goal, here
            waypoint = route.waypoint_for(goal, driver.state)
            action, payload = classify(driver, goal, waypoint)
            if action == "wait":
                continue
            if action == "press":
                driver.press(payload)
                continue
            forced = stale >= NO_PROGRESS_CAP
            decision = policy.decide(payload, forced=forced)
            if payload.kind == "battle":
                driver.turn += 1
            # the row's HP is the HP the decision was taken on, not what the buttons then
            # did to it: `measure` labels turn n from the HP row n+1 carries
            asked_on = driver.state
            for button in options.buttons_for(driver.state, payload, decision.option):
                driver.press(button)
            record = _record(goal, payload, decision, driver, asked_on)
            records.append(record)
            if log:
                log.write(json.dumps(record) + "\n")
                log.flush()
            if on_decision:
                on_decision(record)
            stale += 1
    finally:
        if log:
            log.close()
    return records


def _progress(driver: Driver) -> tuple:
    """What "getting somewhere" means, for the no-progress cap.

    A tile, a finished battle, or a dent in the opponent. A long battle that is being won
    is not stuck, and the cap should not fire on it.
    """
    st = driver.state
    foe = st.battle.opponent
    return (st.map_id, st.x, st.y, driver.latch.count, foe.hp if foe else None)


def _record(goal, branch: Branch, decision: Decision, driver: Driver, st) -> dict:
    return {
        "t": time.time(),
        "goal": goal.name,
        "battle_index": driver.latch.count,
        "kind": branch.kind,
        "state": branch.state,
        "options": branch.options,
        "choice": decision.option,
        "probabilities": decision.probabilities,
        "nouls": decision.nouls,
        "fell_back": decision.fell_back,
        "latency_ms": decision.latency_ms,
        "input_tokens": decision.input_tokens,
        "active_hp_fraction": st.battle.active.hp_fraction
        if st.battle.active
        else None,
        # the party slot that was judged. A fainted mon never gets another decision of
        # its own, so the faint shows up as the next decision being a different slot.
        "active_slot": st.active_slot if st.battle.active else None,
    }
