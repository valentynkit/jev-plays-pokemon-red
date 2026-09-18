# Session prompt: the demo, the clip, and the X post

Run this after `sessions/01-review.md` has landed and ideally after a ROM run exists.
Point a fresh Claude Code session at this file from inside `jev-plays-pokemon/`.

## Context to load first

`CLAUDE.md` ("Lab rules"), `CLAUDE.md`, `CONTEXT.md` sections 1, 7, 8 (pitch, README skeleton,
launch), `docs/SHARED.md` "The recipe every repo follows" and "Launch",
`docs/research/00a-virality-recipe.md` (what broke out and why), `docs/research/04` section 2
(recording pipeline, size limits, X media specs), `demo/README.md`, and `src/jpp/overlay.py`.

## What the clip must do

The tweet is watched muted, on a phone, for four seconds before the scroll decision. In
those four seconds it has to show: a Game Boy playing itself, probability bars moving
under each menu option, and a number that proves it is fast and cheap. The internals are
the hook, not the game: the viewer should see the state that was sent, the answers coming
back, and the calibration score ticking. Nobody else shows this.

## The job

1. **Design the frame.** Storyboard the overlay for a 1280x720 (or 1080x1080 square for X)
   capture: game feed left, Jev panel right. Decide what is always on screen (goal, bars,
   ticker), what pulses on each decision (the state JSON scrolling in, the chosen bar
   lighting up, the latency number), and what accumulates (Brier, decisions/sec, $ spent).
   Typography and color: dark background, one accent for the chosen action, dim for the
   rest, tabular numbers, big enough to read at phone width. Use the frontend-design
   sensibility even though it is pygame. Sketch three variants as ASCII mockups, pick one,
   say why.
2. **Tune `overlay.py` for the camera.** Bar animation timing, the state JSON reveal
   (typewriter or fade, under 300 ms), a "JEV" request pulse, a legible latency readout,
   the sparkline, and a `--demo` flag that slows replay to a watchable 1.5 decisions per
   second without touching measured numbers. Keep it under 300 lines. Verify with
   `SDL_VIDEODRIVER=dummy` and by dumping frames to PNG for review.
3. **Shot list.** Three clips: (a) 12 s, the lab rival battle, bars flipping as HP drops,
   `faints_this_turn` climbing; (b) 8 s, the overworld tie branch, the two directions and
   the pick; (c) 6 s, the ticker close-up: decisions/sec, $/hour, Brier with n. Plus three
   stills: mid-battle bars, the state JSON, the measure line as terminal text.
4. **Recording recipe.** QuickTime cropped to the window, then the ffmpeg two-pass palette
   command from `docs/research/04` section 2 for the README GIF (under 5 MB) and H.264 MP4 for X
   (1080p max, under 140 s). Write the exact commands into `demo/README.md`. If no ROM
   exists, record the replay of `fixtures/runs/sample.jsonl` and label the clip as a
   replay in the post; never pass it off as live.
5. **The post.** First line from CONTEXT.md section 8, then the number line from `measure`
   verbatim, then one sentence on what the bars are, then the repo link. Draft an X thread
   of three posts (hook clip, the internals still with the state JSON, the calibration
   caveat with the Wilson interval) and a Show HN title. Human voice, no hype words, no
   emoji, no em dashes. Credit Claude Plays Pokemon as the famous version and milanboers
   as the earlier Jev attempt.
6. **Awesome list entry.** One line for `~/Projects/mine/awesome-jev-typesafe` in that
   repo's format, ready to paste.

Every visual change ships with its check (`uv run pytest tests/test_overlay.py -q` plus a
frame dump). Commit locally; the user pushes and posts.
