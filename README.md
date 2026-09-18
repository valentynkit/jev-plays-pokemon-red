# jev-plays-pokemon

Pokemon Red, played at __ decisions per second for $__ an hour, with the model's
calibration measured instead of assumed.

    uv run jpp play --rom /path/to/your/red.gb --overlay

<!-- MP4 of the overlay goes here; "Watch it live" lands in the same slot in v0.2 -->

The two numbers above are blank on purpose. They get filled by `uv run measure` on a real
playthrough, and until one exists this README will not print a guess.

## Why

Claude Plays Pokemon is a large model deliberating tens of seconds a move. Jev answers a
closed-set question in about 100 ms with free output tokens, so the emulator becomes the
bottleneck instead of the model.

The catch, up front: Jev cannot plan. It never sees more than the current decision. Every
route, every threshold, every piece of arithmetic is ordinary Python, and the model only
picks among actions the code already proved legal. It is also not asked very often. Code
handles the routine ticks (a text box with no cursor, a step toward the next waypoint, a
cursor move) and only calls Jev where the game actually branches: which battle action,
which way when the tile ahead is blocked and the sidesteps tie, which menu option in a
dialogue.

Then it scores itself. Every battle turn carries a `faints_this_turn` noul, labelled from
what the RAM says happened on the next turn, and `measure` prints the Brier next to the
base rate and a constant predictor. If the model's confidence means nothing, the number
says so.

## Speed and cost

| | decisions/sec | $/hour | calibration published |
|---|---|---|---|
| this repo | __ | __ | yes, Brier on `faints_this_turn` |
| `milanboers/jev-plays-pokemon` | not run (no ROM here) | not run | no |
| Claude Plays Pokemon | not published | not published | no |

Units matter more than the numbers: we ask Jev once per branch, the incumbent asks once per
turn over eight action nouls plus a goal choice. `docs/comparison.md` has the details.

## Install

```
uv sync
cp .env.example .env
```

| variable | required | purpose |
|---|---|---|
| `POKEMON_ROM` | to play | path to your own Pokemon Red dump |
| `TYPESAFE_API_KEY` | to call real Jev | direct API auth |
| `JEV_BASE_URL` | no | point at a gateway shim, a recording proxy, or the local fake |

Bring your own ROM. This repo contains no game data and will not help you find any. Save
states hold copyrighted memory, so they stay out of git.

## Use

```
uv run jpp play --rom red.gb --headless --max-decisions 50   # writes runs/run.jsonl
uv run jpp probe --rom red.gb                                # watch the decoded state
uv run jpp state --ram fixtures/ram_battle.bin               # the exact request body
uv run jpp overlay --replay fixtures/runs/sample.jsonl       # the window, no ROM needed
uv run measure fixtures/runs/sample.jsonl                    # the headline numbers
```

## How it works

```
PyBoy --ram bytes--> decode.py --> GameState --> goals.py (active goal)
                                       |
                                       +-> route.py (waypoints + local dodge)
                                       +-> facts.py (HP fractions, type chart, PP)
                                       +-> options.py (legal actions + intent text)
                                                |
                                   situation classifier
                                   |- routine  --> code presses buttons
                                   +- branch   --> policy.py --> Jev
                                                        |
                                                 overlay.py + runs/*.jsonl
```

| goal | done when |
|---|---|
| `leave_house` | `wCurMap` is neither house map |
| `get_starter` | `wPartyCount >= 1` and `EVENT_GOT_STARTER` |
| `win_lab_rival` | `EVENT_BATTLED_RIVAL_IN_OAKS_LAB`, and the latched `wBattleResult` is a win |
| `reach_viridian` | `wCurMap == $01` |

Addresses come from walking pret/pokered's `ram/wram.asm` from the WRAM0 origin and summing
the struct macros, not from copying hex. Nine of them (`wCurMap`, `wYCoord`, `wXCoord`,
`wPartyCount`, `wObtainedBadges`, `wEventFlags`, `wPlayerMoney`, `wIsInBattle`, and the
party HP/level/max-HP columns) match the independently published values byte for byte,
which is what makes the rest of the table trustworthy.

## Known limits

- One turn of lookahead. No strategy, no team building.
- v0.1 goes as far as Viridian City on a hardcoded route. It cannot find its own way
  anywhere else.
- The RAM fixtures are synthetic, so the tests cannot catch a wrong address. The ROM smoke
  test is what catches that, and it only runs locally.
- The battle-menu button choreography and the two outdoor waypoints are written from the
  game's own source data, not measured on a running cartridge. `jpp probe` settles both.
- Brier is on per-turn fainting, printed next to the base rate and an interval. At v0.1's
  length it is preliminary, not a published calibration claim.
- `fixtures/runs/sample.jsonl` is a fixture, not a playthrough: synthetic RAM, no emulator.
  Five of its forty rows carry real Jev answers; the rest are deterministic stand-ins
  tagged `"source": "fake"`, and `measure` excludes those from the calibration and says how
  many there were. The endpoint used to build it was rate-limited, so no row is timed and
  decisions/sec reads "not measured".
- decisions/sec is measured headless and unthrottled. The overlay is slower on purpose.

## Development

```
uv run pytest -q
uv run python fixtures/make_ram.py      # regenerate the synthetic RAM fixtures
```

Tests run offline against `fixtures/fake_jev.py` and the recorded answers in
`fixtures/recorded/`. No key, no network, no ROM.

Three checks need a cartridge and are coded but unrun here. Run them yourself:

```
uv run pytest tests/test_smoke_rom.py -q          # POKEMON_ROM, and POKEMON_STATE for
                                                  # the save state that starts in the bedroom
uv run jpp probe --rom /path/to/red.gb
uv run jpp play --rom /path/to/red.gb --headless --max-decisions 50
```

`probe` is also the tool that settles the two things a ROM-less build has to guess: walk
out of the house by hand and watch `map` go `$26` to `$25` to `$00` while noting the
waypoint tiles, lose a wild battle on purpose and watch `last_battle_result` latch once and
hold, and press buttons while watching `joy_ignore` / `walk_counter` to confirm the
`input_ready()` predicate in `src/jpp/loop.py`.

## License

MIT.
