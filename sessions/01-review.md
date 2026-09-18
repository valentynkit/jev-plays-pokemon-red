# Session prompt: brutal review, refinement, and the README

Paste or point a fresh Claude Code session at this file from inside `jev-plays-pokemon/`.

## Context to load first

1. `CLAUDE.md` ("Lab rules") (monorepo rules, real Jev access), then `CLAUDE.md` here ("Build state"
   and "Next session" sections carry what the first build left unverified).
2. `CONTEXT.md` in full, including the review responses at the end; `REVIEW-3.md` for the
   verdict. `docs/SHARED.md` for the contract every project follows.
3. `docs/research/04-quality-bar-and-launch.md` section 1 (the README skeleton and section
   order, taken from the five reference repos) and section 3 (measure line convention).
4. `docs/comparison.md` for what the incumbents already do. Prior art at
   `/tmp/prior-art/` (re-clone per `CLAUDE.md` if gone): milanboers_jev-plays-pokemon,
   PWhiddy_PokemonRedExperiments, fhshaik_typesafe-mario, pret_pokered.

## State on entry

First build, one session, zero second-pair review. 58 tests pass, 5 skip. No ROM has ever
run. Real Jev cassettes: 6 (rival battle turns 1 to 4 plus two run branches), recorded
through the gateway shim before it rate-limited. Everything else is fake or synthetic and
labeled so. README headline is `__`.

## The job

Run this with parallel subagents (at most 5 in flight; drafting on opus, reviewers and
readers on sonnet, never `model: inherit`). Treat every line of `src/jpp/` as suspect.

1. **Brutal review, file by file.** One reviewer per module pair. Hunt: wrong RAM
   addresses (walk `wram.asm` again, independently), off-by-one in the event-flag bit
   index, BCD money, the `wIsInBattle` latch racing the goal check, the readiness predicate
   (`loop.py`) being a guess, cursor choreography in `options.py` that has never touched a
   menu, waypoint coordinates in `route.py`, the 40-decision cap logic, option-id validation
   in `policy.py`, Brier and Wilson arithmetic in `measure.py`, overlay frame pacing and the
   replay clock. Each finding: file:line, failure scenario, severity, fix. Verify each
   finding before reporting it; adversarial second pass on the top ten.
2. **Fix what is real.** Tests first for every fix. Keep the stdlib-only, fewest-files
   shape. `ponytail:` markers stay until a cartridge settles them.
3. **With a ROM, if the user supplies one** (`--rom`, never in the repo): run task 2's
   probe, walk the route by hand, fix the waypoints and the readiness predicate from what
   the probe prints, run the smoke test, then a 50-decision headless run, then ten runs for
   the calibration corpus. With gateway credits: `fixtures/record.py` for the missing
   jaggedness cassettes, then `uv run measure runs/*.jsonl` for the real headline.
4. **The README, state of the art.** Follow `docs/research/04` section 1 exactly: measured
   number in the first sentence (or an honest `__` with the command that fills it), one
   paste-and-run command, MP4 or GIF above the fold, Why with the limit folded in, the
   speed and cost table against Claude Plays Pokemon and the two incumbents, Install with
   the bring-your-own-ROM line, How it works with the section 3 diagram and goal table,
   Known limits flat and honest, Development, License. Human voice: no em dashes, no
   "comprehensive, robust, seamlessly, leverage", no emoji, no AI cadence. Read
   `docs/comparison.md` and credit milanboers and NousResearch by name.
5. **Repo hygiene.** MIT `LICENSE` (exists), `CONTRIBUTING.md` (short: how to run tests,
   the no-ROM rule, the fake-first rule, how to record cassettes), `CHANGELOG.md` in Keep a
   Changelog form, `.env.example` with the required/optional table, a GitHub Actions
   workflow running `uv run pytest -q` with no key and no network, `SECURITY.md` only if
   there is something to say (there is not; skip it). Pick the new repo name (the incumbent
   already owns `jev-plays-pokemon`); verify it free with `gh search repos`.
6. **Close.** Every task ends with its runnable check and pasted output. Update
   `CLAUDE.md` "Build state" and CONTEXT.md in the same commit as any change of decision.
   Local commits only, one logical change per commit.

## Non-negotiables

No ROM bytes, save states, or RAM dumps from a running game in the repo. Unit tests never
touch the network. Jev only makes the agent stricter: any error path takes the code default.
Numbers come from `measure` or stay `__`.
