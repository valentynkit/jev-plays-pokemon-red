# Recording the demo

1. `uv run jpp overlay --replay fixtures/runs/sample.jsonl` (or `jpp play --overlay` with a ROM).
2. QuickTime, New Screen Recording, drag a box tight around the 1280x720 window only.
3. Stop, save as `demo/recording.mov`, then:

```
ffmpeg -i demo/recording.mov -vf "fps=30,scale=1280:-2:flags=lanczos" \
  -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -an -movflags +faststart demo/overlay.mp4
```

Check the size with `ls -lh demo/overlay.mp4`; raise `-crf` toward 30 until it is under
5 MB. Keep it MP4 for X, which re-encodes GIFs to muted video anyway. For a README GIF
instead, use the two-pass palette command in `docs/research/04` section 2.
