"""`uv run measure runs/*.jsonl`: the two headline lines, and a measure.json beside them.

A decision is one Jev call. Wall clock runs from a run's first call to its last and is
summed across runs, so idle emulation between branches counts against us. The calibration
target is `faints_this_turn`, labelled from the RAM on the next decision of the same
battle, and it is always printed next to the base rate and the constant predictor. If ours
is not lower, this says so.
"""

import json
import math
import sys
from pathlib import Path

from .policy import cost_usd

NOUL = "faints_this_turn"


def load(paths) -> list[list[dict]]:
    runs = []
    for path in paths:
        records = [
            json.loads(line)
            for line in Path(path).read_text().splitlines()
            if line.strip()
        ]
        if records:
            runs.append(records)
    return runs


def pairs(run: list[dict]) -> list[tuple[float, int]]:
    """(predicted, outcome) for every turn whose next turn in the same battle is known.

    A row tagged `"source": "fake"` never counts: a stand-in probability is not a model
    answer and scoring it would say nothing about calibration.
    """
    out = []
    for i, record in enumerate(run[:-1]):
        if record.get("source") == "fake":
            continue
        probability = (record.get("nouls") or {}).get(NOUL)
        if probability is None:
            continue
        outcome = _fainted(run, i)
        if outcome is None:
            continue
        out.append((probability, outcome))
    return out


def _fainted(run: list[dict], i: int) -> int | None:
    """Did the mon judged on row `i` go down before it got another decision?

    The next decision of the same battle answers it. Two ways to read that row, because
    a mon that faints never gets another decision of its own:

    - same slot still out: it survived unless its HP is zero.
    - a different slot is out, and this row did not choose to switch: the game forced the
      switch, which in Gen 1 only happens on a faint.

    Rows are scanned forward rather than taking `i + 1`, so an overworld or dialogue row
    logged inside the same battle does not drop the turn. Runs recorded before the slot
    was logged fall back to the HP alone.
    """
    slot = run[i].get("active_slot")
    for following in run[i + 1 :]:
        if following.get("battle_index") != run[i].get("battle_index"):
            return None
        hp = following.get("active_hp_fraction")
        if hp is None:
            continue
        next_slot = following.get("active_slot")
        if slot is None or next_slot is None or next_slot == slot:
            return int(hp == 0)
        chose_to_switch = str(run[i].get("choice") or "").startswith("switch_to_")
        return 0 if chose_to_switch else 1
    return None


def brier(labelled) -> float:
    return sum((p - y) ** 2 for p, y in labelled) / len(labelled)


def brier_ci(labelled) -> tuple[float, float]:
    """Normal 95% interval on the mean squared error; wide at these sample sizes."""
    n = len(labelled)
    mean = brier(labelled)
    if n < 2:
        return (0.0, 1.0)
    variance = sum(((p - y) ** 2 - mean) ** 2 for p, y in labelled) / (n - 1)
    half = 1.96 * math.sqrt(variance / n)
    return (max(0.0, mean - half), min(1.0, mean + half))


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, center - half), min(1.0, center + half))


def summarise(runs: list[list[dict]]) -> dict:
    decisions = [r for run in runs for r in run]
    # a fallback never reached the model: its latency is the failed attempt, which
    # under a rate limit is seconds of retry. Counting those printed 0.23 dec/s for
    # a run whose five real calls averaged 700 ms.
    timed = [
        r for r in decisions if r.get("latency_ms") and not r.get("fell_back")
    ]
    # A real run's clock is wall time from its first Jev call to its last, so idle
    # emulation counts against us. A ROM-less fixture run has no emulator at all, so it
    # can only report the call economy: its own latency, and it says so.
    call_only = any(r.get("mode") == "call-latency-only" for r in decisions)
    if call_only:
        seconds = sum(r["latency_ms"] for r in timed) / 1000
        counted = len(timed)
    else:
        clocked = [
            run for run in runs if len(run) > 1 and run[0].get("t") and run[-1].get("t")
        ]
        seconds = sum(run[-1]["t"] - run[0]["t"] for run in clocked)
        counted = sum(len(run) for run in clocked)
    # cost and clock have to cover the same rows, or a replayed cassette's tokens get
    # divided by a time only the live calls were measured over
    tokens = sum(
        r.get("input_tokens") or 0 for r in (timed if call_only else decisions)
    )
    labelled = [pair for run in runs for pair in pairs(run)]
    positives = sum(y for _, y in labelled)
    base = positives / len(labelled) if labelled else 0.0
    out = {
        "runs": len(runs),
        "decisions": len(decisions),
        "seconds": round(seconds, 2),
        "decisions_per_second": round(counted / seconds, 2) if seconds else None,
        "call_latency_only": call_only,
        "input_tokens": tokens,
        "usd_per_hour": round(cost_usd(tokens) / seconds * 3600, 4)
        if seconds
        else None,
        "latency_p50_ms": _percentile(
            [r["latency_ms"] for r in timed], 50
        ),
        "fell_back": sum(1 for r in decisions if r.get("fell_back")),
        "stand_in_rows": sum(1 for r in decisions if r.get("source") == "fake"),
        "labelled_turns": len(labelled),
        "base_rate": round(base, 3),
    }
    if labelled:
        out["brier"] = round(brier(labelled), 4)
        out["brier_ci_95"] = [round(v, 4) for v in brier_ci(labelled)]
        out["constant_predictor_brier"] = round(
            brier([(base, y) for _, y in labelled]), 4
        )
        out["base_rate_ci_95"] = [round(v, 3) for v in wilson(positives, len(labelled))]
        out["beats_constant_predictor"] = out["brier"] < out["constant_predictor_brier"]
    return out


def _percentile(values, pct):
    values = sorted(v for v in values if v)
    if not values:
        return None
    return round(values[min(len(values) - 1, int(len(values) * pct / 100))], 1)


def lines(s: dict, note: str) -> list[str]:
    n = f"n={s['decisions']} Jev calls over {s['runs']} run{'s' if s['runs'] > 1 else ''}"
    if s["stand_in_rows"]:
        # a stand-in never hit the network, so it is not a Jev call and the headline
        # cannot quietly count it as one
        n += f", {s['stand_in_rows']} of them stand-ins"
    if s["fell_back"]:
        # on a real run the clock is wall time, so a rate limit's retry stalls land in
        # the rate and make the agent look slow for someone else's reason
        n += f", {s['fell_back']} fell back, so the clock includes their retries"
    if s["decisions_per_second"] is None:
        first = (
            f"decisions/sec and $/hour: not measured, no timed call in this run ({n})"
        )
    else:
        first = (
            f"{s['decisions_per_second']} decisions/sec, ${s['usd_per_hour']}/hour "
            f"({n}, {note})"
        )
    if "brier" not in s:
        excluded = (
            f"; {s['stand_in_rows']} of {s['decisions']} rows are stand-ins, not model answers"
            if s["stand_in_rows"]
            else ""
        )
        return [
            first,
            f"Brier on {NOUL}: not enough labelled turns (n={s['labelled_turns']}{excluded})",
        ]
    low, high = s["brier_ci_95"]
    verdict = (
        "" if s["beats_constant_predictor"] else " -- worse than the constant predictor"
    )
    return [
        first,
        f"Brier {s['brier']} on {NOUL} (n={s['labelled_turns']} turns, "
        f"base {s['base_rate']}, constant-predictor {s['constant_predictor_brier']}, "
        f"95% CI {low}-{high}){verdict}",
    ]


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    paths = [a for a in argv if not a.startswith("-")]
    if not paths:
        print("usage: measure <run.jsonl> [run.jsonl ...]", file=sys.stderr)
        return 2
    runs = load(paths)
    if not runs:
        print("no decisions in those files", file=sys.stderr)
        return 1
    summary = summarise(runs)
    synthetic = any("fixtures/runs" in p for p in paths) or summary["stand_in_rows"]
    note = (
        "synthetic RAM, call latency only, no emulator"
        if summary["call_latency_only"]
        else "headless, unthrottled PyBoy"
    )
    summary["method"] = note
    for line in lines(summary, note):
        print(line)
    if synthetic:
        print(
            "This run is a fixture: synthetic RAM, no emulator, and a rate-limited "
            "endpoint. Shape, not score."
        )
    Path("measure.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("wrote measure.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
