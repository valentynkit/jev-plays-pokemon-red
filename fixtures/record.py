"""Record real Jev answers once, so the tests can replay them free and offline.

The VCR pattern from research/01 section 4: each request is keyed by
`sha256(state + questions)` and its answers land in `fixtures/recorded/`. Run it against a
real endpoint (`JEV_BASE_URL`, plus `TYPESAFE_API_KEY` for the direct API), commit what it
writes, and never run it again unless the fixtures change.

    JEV_BASE_URL=http://127.0.0.1:4322 uv run python fixtures/record.py
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import jaggedness  # noqa: E402
import make_ram  # noqa: E402

from jpp import options, policy  # noqa: E402
from jpp.decode import decode  # noqa: E402

HERE = Path(__file__).parent
RECORDED = HERE / "recorded"
# the free gateway tier rate-limits hard; recording is a one-off, so it can crawl
GAP = float(os.environ.get("JEV_GAP_S", "5"))


def battle_turns():
    return {
        f"battle_turn_{n}": options.battle_branch(
            decode(bytes(make_ram.battle_turn(n))), jaggedness.BATTLE_GOAL, turn=n
        )
        for n in range(1, len(make_ram.RIVAL_TURNS) + 1)
    }


def main():
    # a cold gateway hop is slower than the in-loop budget; recording is not timed
    client = policy.JevClient(record_dir=RECORDED, timeout=60.0)
    branches = battle_turns() | {
        name: build() for name, build in jaggedness.CASES.items()
    }
    (HERE / "battle_turns.json").write_text(
        json.dumps({n: b.state for n, b in battle_turns().items()}, indent=1) + "\n"
    )
    summary = {}
    for name, branch in branches.items():
        questions = policy.questions_for(branch)
        key = policy.cache_key(branch.state, questions)
        cassette = RECORDED / f"{key}.json"
        started = None
        if cassette.exists():  # already paid for; never send the same body twice
            payload = json.loads(cassette.read_text())
        else:
            try:
                time.sleep(GAP)  # before the clock starts: the gap is ours, not Jev's
                started = time.monotonic()
                payload = client.ask(branch.state, questions)
            except Exception as e:
                print(f"{name:28} FAILED {type(e).__name__}: {e}", flush=True)
                continue
        answers = payload["answers"]
        choice = answers["next_action"]
        summary[name] = {
            "key": key,
            "choice": choice["choice"],
            "confidence": choice.get("confidence"),
            "probabilities": choice.get("probabilities", {}),
            "nouls": {
                k: v["noul"] for k, v in answers.items() if v.get("type") == "noul"
            },
            "latency_ms": round((time.monotonic() - started) * 1000, 1)
            if started
            else None,
            "input_tokens": (payload.get("usage") or {}).get("input_tokens"),
            "model": payload.get("model"),
        }
        print(
            f"{name:28} {choice['choice']:20} conf={choice.get('confidence')}",
            flush=True,
        )
    (HERE / "recorded_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"\n{len(summary)} answers -> {RECORDED}")


if __name__ == "__main__":
    main()
