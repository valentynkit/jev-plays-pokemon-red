# The clip

The frame is 1080x1350, four to five, because the tweet is watched muted on a phone. The
Game Boy is on top at 5x, the bars are the middle third, and the ticker is one line of
42px tabular mono at the bottom. Nothing in the frame moves except the game, the bars,
the request ring beside the REPLAY badge, and the payload card typing itself in.

No screen recorder is involved. `--frames` walks the same draw calls on a fake clock and
writes one PNG per frame, so a clip is exactly as long as it says, has no cursor in it,
and re-renders identically after a code change.

## Render

```
SDL_VIDEODRIVER=dummy uv run jpp overlay --replay fixtures/runs/sample.jsonl \
  --demo --frames /tmp/frames --seconds 12
```

`--demo` paces the replay at 1.5 decisions a second, which is watchable. It does not touch
the ticker: `dec/s` and `$/hr` come from the recorded call latencies, so the playback speed
can never print itself as a measurement. A run with no timed rows shows `dec/s not
measured` rather than a number.

`--skip N` starts at decision N, which is how the three clips below are cut.

## Encode

X, H.264, plays inline:

```
ffmpeg -y -framerate 30 -i /tmp/frames/f%05d.png -c:v libx264 -preset slow -crf 23 \
  -pix_fmt yuv420p -an -movflags +faststart demo/overlay.mp4
```

README GIF, two-pass palette, half size:

```
ffmpeg -y -framerate 30 -i /tmp/frames/f%05d.png \
  -vf "fps=15,scale=540:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -framerate 30 -i /tmp/frames/f%05d.png -i /tmp/pal.png \
  -lavfi "fps=15,scale=540:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  demo/overlay.gif
```

The three clips below came out at 409 KB, 259 KB and 118 KB, and the GIF at 522 KB. The
5 MB ceiling is not close. Raise `-crf` only if a longer cut needs it.

## Stand-in rows never reach a frame

A bar drawn from a hash looks exactly like a bar drawn from an answer, and nothing on
screen tells them apart, so rows tagged `"source": "fake"` are dropped before rendering.
`--include-stand-ins` puts them back and must never be used for a clip. The current run is
40 rows, 20 of them real, so the master is 20 decisions and 13.3 seconds.

Publish the number from the same rows the clip shows, or the tweet and the video disagree:

```
uv run python -c 'import json; rows=[json.loads(l) for l in open("fixtures/runs/sample.jsonl")]; \
  open("/tmp/real.jsonl","w").write("".join(json.dumps(r)+chr(10) for r in rows if r.get("source")!="fake"))'
uv run measure /tmp/real.jsonl
```

## Shot list

With a ROM, the clip is the live game, not a replay. `jpp play --frames` draws the
overlay over the running emulator and dumps a PNG per captured frame, `--every 2` for
30 fps.

```
uv run python fixtures/make_state.py red-bedroom.state        # drives the intro
SDL_VIDEODRIVER=dummy JEV_BASE_URL=http://127.0.0.1:4322 uv run jpp play \
  --rom "$POKEMON_ROM" --state rival-battle.state \
  --frames /tmp/final --every 2 --max-decisions 10 --out runs/final.jsonl
```

Save a state at the branch you want to film first, or the clip opens with a minute of
walking: the route is code-owned, so nothing is asked between the bedroom and the lab.

Cut the clip to the decisions that were actually answered. Under the free tier that is
about the first five, and a fallback draws its options greyed with NO ANSWER over them,
which is honest but is not the shot.

Stills come straight out of the frame dump.

## Before any of this is posted

- `demo/clip-live-battle.mp4` is 10 seconds because only one decision in that capture was
  answered before the free tier cut in. The full battle, won, needs a window with five or
  more calls in it.
- The gateway free tier rate-limits `typesafe-ai/jev` after about five requests regardless
  of credit balance, and the window refills over hours. A 40 row run costs roughly half its
  rows to stand-ins. Paid credits, re-run `fixtures/make_run.py`, re-render.
- Label the clip a replay in the post whenever the feed panel is empty. Never imply live.
