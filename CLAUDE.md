# jev-plays-pokemon

Pokemon Red on PyBoy: code decodes RAM into a symbolic state, owns the goal stack and
waypoint movement, Jev picks among legal actions at branches. Live probability overlay.
Read the "Lab rules" section below for the monorepo rules, then `CONTEXT.md` here in full.

Verdict after three review rounds: **ready to build**. The run starts in Red's house 2F
(`$26`); the input-readiness predicate is discovered with `jpp probe` in task 2, not assumed.

## Build state (2026-09-18, after the review session)

All nine CONTEXT.md tasks are coded and reviewed. `uv run pytest -q` gives 78 passed, 6
skipped. The skips are the ROM tests (3, one of which also wants `POKEMON_STATE`) and the
three jaggedness assertions that need recorded real answers.

Five reviewers went over `src/jpp/` file by file against pret/pokered and the installed
PyBoy. Six real findings, all fixed, all listed in CONTEXT.md "Review round 4": the
readiness predicate deadlocked on scripted dialogue, the battle cursor is sticky so every
button sequence after turn 1 was wrong, the sidestep and tie branch were unreachable,
`get_starter` skipped the trigger that arms the whole starter sequence, the collision grid
was read inverted, and `measure` divided all rows' cost by only the timed rows' clock. The
decoder came out clean: 30 addresses, both struct layouts, event bit order, BCD, endianness,
species and move tables and all 82 type-chart entries re-derived and matched.

What ran for real and what did not:
- Tasks 1, 3, 4, 5, 6, 8, 9: checks pass on synthetic RAM and the fake Jev.
- Tasks 2 and 7: coded (`loop.py`, readiness predicate, battle latch, `jpp probe`,
  `jpp play`), unit-tested against a fake emulator object. Never run on a cartridge. The ROM
  commands are written verbatim in README "Development".
- Real Jev: 6 cassettes in `fixtures/recorded/` (four rival-battle turns, two run branches)
  came from the gateway shim before its free tier rate-limited the rest. Padded-state,
  labels-vs-raw-numbers, and injection cases are NOT recorded. `fixtures/runs/sample.jsonl`
  is 40 rows, 5 real and 35 tagged `"source": "fake"`; measure excludes the fakes and says
  so. No row carries a latency, so decisions/sec prints "not measured". README headline
  stays `__`.
- Overlay: rebuilt for the camera in the demo session as 1080x1350 (four to five, phone
  aspect), verified by dumping frames with `--frames` under `SDL_VIDEODRIVER=dummy`. The
  ticker's decisions/sec now comes from recorded call latency, never the replay clock, so
  `--demo` pacing cannot print itself as a measurement.

CONTEXT.md changes made by the build (all in the file already):
1. `wBattleResult` is a plain `db` at `$CF0B`, not a WRAM union; the latch stays.
2. `leave_house` is now "not in either house map", since `wCurMap == $00` un-completes
   itself when `get_starter` enters the lab.
3. Section 1 differentiator rewritten: milanboers/jev-plays-pokemon (MIT, 4k lines, vendors
   NousResearch/pokemon-agent's RAM reader) already plays the whole v0.1 route and already
   uses this name. Our claims are the branches-only question economy, the published
   calibration number, and the overlay. Same facts in `docs/comparison.md`. The user must
   pick a new repo name at launch.

Address table: derived by walking `ram/wram.asm` with struct and UNION handling; nine
independently published addresses matched byte-exact (`wCurMap $D35E`, `wPartyCount $D163`,
`wEventFlags $D747`, `wIsInBattle $D057`, party HP/level at `$D16C`/`$D18C`), which is the
evidence for the battle block (`wBattleMon $D014`, `wEnemyMon $CFE5`).

`ponytail:` markers left, both needing a cartridge: the outdoor waypoint columns
(`route.py`, Pallet Town and Route 1 are still a straight line up x=10) and the bag row for
a second item (`options.py`). The battle-menu choreography and the player's cell in the
collision grid are no longer guesses; both were settled from pret/pokered and the installed
PyBoy in review round 4.

The cassettes in `fixtures/recorded/` are keyed on the state body and the state body
changed in round 4, so they have to be recorded again before `make_run.py` can build a
sample out of real answers.

Blocked on the user: a Pokemon Red ROM path (`--rom`), and Vercel AI Gateway paid credits
for the remaining recordings (see the "Lab rules" section below, "Real Jev access").

## Next sessions

Two prompts are checked in: `sessions/01-review.md` (brutal review, fixes, the README,
repo hygiene, the new name) and `sessions/02-demo.md` (overlay tuned for the camera, shot
list, recording recipe, the X thread). Run them in that order, each in its own session.

### Review targets

Start with: `decode.py` against `wram.asm` for any address not in the nine verified ones;
the readiness predicate and latch in `loop.py` (never exercised on real frames);
`options.py` cursor choreography; `policy.py` option-id validation and the 40-decision cap;
`overlay.py` frame pacing; `measure.py` Brier and Wilson math. Then, with a ROM: task 2's
probe, waypoints, the smoke test, a 50-decision headless run, re-record with
`fixtures/record.py` once credits exist.

Project-specific rules:
- The ROM is never in the repo. `ROM_PATH` env, user supplied. Save states are gitignored.
  RAM fixtures are synthesized (`fixtures/make_ram.py`), never dumped from a running game.
- RAM addresses come from pret/pokered `ram/wram.asm` symbols, not hex from a wiki.
- HP fractions, type effectiveness, PP, and all arithmetic are computed in code and handed
  to Jev as labeled facts. Jev never plans more than one turn.
- `uv run measure` replays a recorded run; it prints the base rate and the constant
  predictor's Brier next to ours, always.
- Launch gate: a recorded run (stream or MP4) exists before anything is posted.

## Lab rules (from the jev-lab monorepo this repo was split from)

This project was designed and first built inside `valentynkit/jev-lab` (research reports,
the shared contract, the gateway shim). `docs/SHARED.md` and `docs/research/` are copies
taken at the split on 2026-09-18; the lab repo is canonical for them.

## Hard rules (also in docs/SHARED.md)

- No network and no key by default. Tests run against the project's fake Jev. Real calls
  only through `JEV_BASE_URL` set to the gateway shim or the direct API.
- Jev only makes a system stricter, never looser. Every error path fails open or falls
  back to the tool's no-Jev behavior.
- Every task ends with its runnable check from CONTEXT.md passing; paste the output before
  calling it done.
- Local commits only, one project per commit where possible, human voice, no
  Co-Authored-By, no em dashes. The user pushes and creates GitHub repos.
- Fewest files that work. Mark deliberate shortcuts with `ponytail:` naming the ceiling.
- The user's own transcripts (jev-belay corpus) never leave `corpus/`, which is gitignored.

## Prior-art clones

`/tmp/prior-art/<owner>_<repo>/` held shallow clones during design. If gone, re-clone the
ones CONTEXT.md cites: `git clone -q --depth 1 https://github.com/<owner>/<repo> /tmp/prior-art/<owner>_<repo>`.

## Real Jev access (2026-09-18)

No TypeSafe key yet. Real answers come through Vercel AI Gateway: the key sits in
`~/.config/jev-lab/env` (`AI_GATEWAY_API_KEY`, $5 budget cap), and `tools/jev-proxy` in the jev-lab repo (`~/Projects/mine/jev-lab/tools/jev-proxy`) turns
the direct wire format into gateway evaluate calls on `127.0.0.1:4322`. Start it, then set
`JEV_BASE_URL=http://127.0.0.1:4322` for record and measure steps only. Never loop against
it; unit tests stay on the fakes. Numbers measured this way carry the "via gateway shim"
footnote until re-measured on the direct API against a pinned `jev-1.13.0`.

**The balance is not the gate.** `GET https://ai-gateway.vercel.sh/v1/credits` read
`4.970921048` while every call past the fifth still came back 429 with
`"Free tier requests on this model are rate-limited. Upgrade to paid credits"`, and it was
still 429 after eight retries at 12 second spacing. Granted credits do not lift the
per-model free-tier limit; only a card top-up does. Check the 429 body before concluding
anything about a rate limit, and budget about five calls per session until then.

Measured 2026-09-18 over four fresh cassettes: 923.9, 885.8, 674.7, 861.1 ms, mean 836 ms,
1.2 decisions/sec, $0.17/hour at ~920 input tokens. The "about a hundred milliseconds" hook
in CONTEXT sections 1 and 8 is eight times off and must not be posted as written.
