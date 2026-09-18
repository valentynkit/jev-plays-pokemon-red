"""`jpp state | probe | play | overlay`."""

import argparse
import json
import sys
from pathlib import Path

from . import goals, options, policy
from .decode import decode

RUNS = Path("runs")


def _goal(name, state, latch=None):
    if name:
        return next(g for g in goals.GOALS if g.name == name)
    stack = goals.GoalStack()
    stack.advance(state, latch or _EmptyLatch())
    return stack.current or goals.GOALS[-1]


class _EmptyLatch:
    result = None
    WIN = 0x00


def _file(path: str) -> Path:
    """argparse-level existence check, so a typo is one line and not a traceback."""
    where = Path(path).expanduser()
    if not where.is_file():
        raise argparse.ArgumentTypeError(f"no such file: {where}")
    return where


def _pyboy(rom: Path, headless: bool):
    from pyboy import PyBoy

    emu = PyBoy(str(rom), window="null" if headless else "SDL2")
    if headless:
        emu.set_emulation_speed(
            0
        )  # unthrottled: the decisions/sec number is taken here
    return emu


def cmd_state(args):
    """Build the exact request body a branch would send, from a RAM image."""
    mem = args.ram.read_bytes()
    state = decode(mem)
    goal = _goal(args.goal, state)
    if state.in_battle:
        branch = options.battle_branch(
            state, goal, items=options.bag(mem), turn=args.turn
        )
    else:
        waypoint = (state.x + 2, state.y + 3)
        branch = options.tie_branch(state, goal, waypoint, ["left", "right"])
    print(
        json.dumps(
            {
                "model": policy.MODEL,
                "state": branch.state,
                "questions": policy.questions_for(branch),
            },
            indent=1,
        )
    )


def cmd_probe(args):
    from .loop import probe

    emu = _pyboy(args.rom, headless=False)
    try:
        probe(emu, ticks=args.ticks)
    finally:
        emu.stop(save=False)


def cmd_play(args):
    from .loop import play

    RUNS.mkdir(exist_ok=True)
    log = Path(args.out) if args.out else RUNS / "run.jsonl"
    emu = _pyboy(args.rom, headless=args.headless and not args.overlay)
    client = policy.JevClient(replay_dir=args.replay)
    on_decision = _overlay_feed(emu) if args.overlay else None
    try:
        records = play(
            emu,
            policy.Policy(client, enabled=not args.no_jev),
            max_decisions=args.max_decisions,
            log_path=log,
            on_decision=on_decision,
        )
    finally:
        emu.stop(save=False)
    print(f"{len(records)} decisions -> {log}")


def _overlay_feed(emu):
    """The bars beside the game, one repaint per decision.

    The overlay caps at 60 fps and the headline number is never taken here; the measure
    line names the mode, CONTEXT section 5.
    """
    from .overlay import Overlay

    overlay = Overlay("jev plays pokemon")
    labelled: list[dict] = []

    def feed(record):
        from . import measure

        labelled.append(record)
        overlay.feed(record, labelled=measure.pairs(labelled))
        overlay.draw(emu.screen.ndarray)

    return feed


def cmd_overlay(args):
    from .overlay import run_replay

    run_replay(args.replay, rate=args.rate)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="jpp")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("state", help="print the Jev request for a RAM image")
    p.add_argument("--ram", required=True, type=_file)
    p.add_argument("--goal", choices=[g.name for g in goals.GOALS])
    p.add_argument("--turn", type=int, default=None)
    p.set_defaults(func=cmd_state)

    p = sub.add_parser(
        "probe", help="walk the route by hand and watch the decoded state"
    )
    p.add_argument("--rom", required=True, type=_file)
    p.add_argument("--ticks", type=int, default=100_000)
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("play", help="run the agent")
    p.add_argument("--rom", required=True, type=_file)
    p.add_argument("--headless", action="store_true")
    p.add_argument(
        "--overlay",
        action="store_true",
        help="the 1280x720 window beside the game; slower on purpose, never the headline",
    )
    p.add_argument("--max-decisions", type=int, default=50)
    p.add_argument("--out")
    p.add_argument(
        "--replay", help="answer from recorded fixtures instead of the network"
    )
    p.add_argument(
        "--no-jev", action="store_true", help="code defaults only, for a baseline"
    )
    p.set_defaults(func=cmd_play)

    p = sub.add_parser(
        "overlay", help="the 1280x720 window, live or replaying a run file"
    )
    p.add_argument("--replay", required=True, type=_file)
    p.add_argument("--rate", type=float, default=2.0, help="decisions per second")
    p.set_defaults(func=cmd_overlay)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
