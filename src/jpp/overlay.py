"""The 1080x1350 window: the Game Boy on top, what Jev was asked and answered below.

Four-to-five aspect because the clip is watched on a phone, muted, for four seconds. Runs
live over PyBoy, or with `--replay <run.jsonl>` over a recorded run. Bars animate from the
previous probabilities to the new ones so the eye can follow which option moved, and
`render_frames` walks the same draw calls on a fake clock so ffmpeg gets an exact-length
video without anyone pointing a screen recorder at a window.
"""

import json
import time
from pathlib import Path

import pygame

from . import measure
from .policy import cost_usd

W, H = 1080, 1350
GAME_W, GAME_H = 160, 144
SCALE = 5
MARGIN = 60
FEED = pygame.Rect((W - GAME_W * SCALE) // 2, 86, GAME_W * SCALE, GAME_H * SCALE)
GOAL_Y = 830
BAR_TOP, BAR_H, BAR_GAP, BAR_MAX = 896, 44, 12, 5
FOOT_Y = 1172
TICKER_Y = 1258
ANIMATION_MS = 140
PULSE_MS = 420
REVEAL_MS = 260

BG = (22, 22, 29)
CARD = (31, 31, 40)
EDGE = (42, 42, 54)
FG = (220, 215, 186)
MUTED = (114, 113, 140)
KEY = (126, 156, 216)
STRING = (152, 187, 108)
NUMBER = (210, 126, 153)
ACCENT = (255, 160, 102)
BAR = (58, 62, 84)


def _font(size, bold=False):
    return pygame.font.SysFont("Menlo,Monaco,monospace", size, bold=bold)


def _sans(size, bold=False):
    return pygame.font.SysFont("Helvetica Neue,Helvetica,Arial", size, bold=bold)


def tint(token: str):
    stripped = token.strip().rstrip(",")
    if stripped.endswith(":"):
        return KEY
    if stripped.startswith('"'):
        return STRING
    try:
        float(stripped)
        return NUMBER
    except ValueError:
        return FG if stripped in "{}[]" else MUTED


def pretty(option: str) -> str:
    """`use_move_scratch` reads as SCRATCH at arm's length; the card shows the raw id."""
    for prefix in ("use_move_", "use_item_", "switch_to_", "go_", "walk_", "say_"):
        option = option.removeprefix(prefix)
    return option.replace("_", " ").upper()


def state_lines(state: dict, width: int, height: int) -> list[str]:
    """Pretty-printed and scrolled to fit: the tail is where the options live."""
    text = json.dumps(state, indent=1).splitlines()
    text = [line if len(line) <= width else line[: width - 3] + "..." for line in text]
    return text if len(text) <= height else text[:2] + ["  ..."] + text[-(height - 3) :]


def measured_rate(latencies) -> float | None:
    """Decisions per second from call latency alone, or None if nothing was timed.

    Deliberately not derived from wall clock: `--demo` pacing is a camera choice and
    would otherwise print itself as a measurement.
    """
    timed = [ms for ms in latencies if ms]
    return 1000 / (sum(timed) / len(timed)) if timed else None


def fit(font, text: str, width: int) -> str:
    while text and font.size(text)[0] > width:
        text = text[:-2] + "."
    return text


class Overlay:
    def __init__(self, caption="jev plays pokemon", live=True):
        pygame.init()
        pygame.display.set_caption(caption)
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.live = live
        self.mono = _font(15)
        self.small = _sans(20)
        self.head = _sans(34, bold=True)
        self.goal_font = _sans(30, bold=True)
        self.label = _sans(26, bold=True)
        self.value = _font(28, bold=True)
        self.ticker = _font(38, bold=True)
        self.noul = _font(24)
        self.shown: dict[str, float] = {}
        self.previous: dict[str, float] = {}
        self.target: dict[str, float] = {}
        self.changed_at = 0.0
        self.now = None  # set by render_frames to walk a fake clock
        self.record = None
        self.latencies: list[float] = []
        self.decisions = 0
        self.tokens = 0
        self.labelled: list[tuple[float, int]] = []

    def _clock(self) -> float:
        return time.monotonic() if self.now is None else self.now

    def feed(self, record: dict, labelled=None):
        self.record = record
        # a fallback has no probabilities, and blanking the panel reads as broken rather
        # than as what it is: the options are still real, nothing answered about them
        self.target = dict(record.get("probabilities") or {}) or {
            k: 0.0 for k in (record.get("options") or {})
        }
        # keep only the options this decision offered: a move from a previous battle
        # would otherwise sit at zero in the bar list for the rest of the run
        self.shown = {k: self.shown.get(k, 0.0) for k in self.target}
        self.previous = dict(self.shown)  # bars lerp from here, not from themselves
        self.changed_at = self._clock()
        self.decisions += 1
        self.tokens += record.get("input_tokens") or 0
        # a fallback row carries the time the failed attempt took, which on a rate limit
        # is seconds of retry. It is not a Jev call and must not price one: counting it
        # printed 0.5 dec/s and $0.03/hr off four rows that never reached the model
        timed = 0.0 if record.get("fell_back") else (record.get("latency_ms") or 0.0)
        self.latencies = (self.latencies + [timed])[-60:]
        if labelled is not None:
            self.labelled = labelled

    def _since(self) -> float:
        return (self._clock() - self.changed_at) * 1000

    def draw(self, frame=None):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_ESCAPE, pygame.K_q)
            ):
                return False
        self.screen.fill(BG)
        self._draw_header()
        self._draw_feed(frame)
        if self.record:
            self._draw_goal()
            self._draw_bars()
            self._draw_nouls()
            self._draw_state()
        self._draw_ticker()
        pygame.display.flip()
        if self.now is None:
            self.clock.tick(60)
        return True

    def _draw_header(self):
        self.screen.blit(self.head.render("JEV PLAYS POKEMON", True, FG), (MARGIN, 38))
        badge = "LIVE" if self.live else "REPLAY"
        text = self.small.render(badge, True, MUTED)
        x = W - MARGIN - text.get_width()
        self.screen.blit(text, (x, 46))
        self._draw_pulse(x - 26, 56)

    def _draw_pulse(self, x, y):
        """The ring that fires the moment a request leaves for Jev."""
        progress = min(1.0, self._since() / PULSE_MS) if self.record else 1.0
        pygame.draw.circle(self.screen, ACCENT if progress < 1 else MUTED, (x, y), 6)
        if progress < 1.0:
            pygame.draw.circle(self.screen, ACCENT, (x, y), int(6 + 16 * progress), 2)

    def _draw_feed(self, frame):
        pygame.draw.rect(self.screen, CARD, FEED.inflate(20, 20), border_radius=10)
        if frame is not None:
            surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1)[:, :, :3])
            self.screen.blit(pygame.transform.scale(surface, FEED.size), FEED)
        else:
            pygame.draw.rect(self.screen, BG, FEED, border_radius=6)
            for i, line in enumerate(
                ("replaying a recorded run", "live feed needs  jpp play --rom")
            ):
                note = self.small.render(line, True, MUTED)
                self.screen.blit(
                    note, note.get_rect(center=(FEED.centerx, FEED.centery + i * 30))
                )

    def _draw_goal(self):
        goal = self.record["state"].get("goal", self.record["goal"])
        self.screen.blit(self.small.render("GOAL", True, MUTED), (MARGIN, GOAL_Y + 6))
        self.screen.blit(
            self.goal_font.render(
                fit(self.goal_font, goal, W - 2 * MARGIN - 90), True, ACCENT
            ),
            (MARGIN + 90, GOAL_Y),
        )

    def _draw_bars(self):
        # lerp from where the bar was when this decision arrived, so the drawn width
        # depends on elapsed time and not on how many times draw() happened to run
        progress = min(1.0, self._since() / ANIMATION_MS)
        eased = 1 - (1 - progress) ** 3
        for key in self.shown:
            start = self.previous.get(key, 0.0)
            self.shown[key] = start + (self.target.get(key, 0.0) - start) * eased
        label_w, value_w = 300, 96
        track_x = MARGIN + label_w
        track_w = W - 2 * MARGIN - label_w - value_w
        chosen = self.record.get("choice")
        if self.record.get("fell_back"):
            self.screen.blit(
                self.small.render(
                    "NO ANSWER: RATE LIMITED, CODE DEFAULT", True, MUTED
                ),
                (MARGIN, BAR_TOP - 26),
            )
        ordered = sorted(
            self.shown.items(), key=lambda kv: -self.target.get(kv[0], 0.0)
        )
        for i, (key, value) in enumerate(ordered[:BAR_MAX]):
            y = BAR_TOP + i * (BAR_H + BAR_GAP)
            picked = key == chosen and not self.record.get("fell_back")
            name = fit(self.label, pretty(key), label_w - 16)
            self.screen.blit(
                self.label.render(name, True, FG if picked else MUTED),
                (MARGIN, y + (BAR_H - self.label.get_height()) // 2),
            )
            pygame.draw.rect(
                self.screen, CARD, (track_x, y, track_w, BAR_H), border_radius=6
            )
            filled = max(3, int(track_w * max(0.0, min(1.0, value))))
            pygame.draw.rect(
                self.screen,
                ACCENT if picked else BAR,
                (track_x, y, filled, BAR_H),
                border_radius=6,
            )
            number = self.value.render(
                f"{self.target.get(key, 0.0):.2f}", True, FG if picked else MUTED
            )
            self.screen.blit(
                number,
                (
                    W - MARGIN - number.get_width(),
                    y + (BAR_H - number.get_height()) // 2,
                ),
            )
        extra = len(ordered) - BAR_MAX
        if extra > 0:
            y = BAR_TOP + BAR_MAX * (BAR_H + BAR_GAP)
            self.screen.blit(
                self.small.render(f"+{extra} more below 0.01", True, MUTED), (MARGIN, y)
            )

    def _draw_nouls(self):
        """The side questions that rode along in the same request, for the same price."""
        nouls = self.record.get("nouls") or {}
        if not nouls:
            return
        self.screen.blit(
            self.small.render("SAME REQUEST, NO EXTRA CALL", True, MUTED),
            (MARGIN, FOOT_Y),
        )
        for i, (name, value) in enumerate(list(nouls.items())[:2]):
            line = self.noul.render(f"{name} {value:.2f}", True, FG)
            self.screen.blit(line, (MARGIN, FOOT_Y + 26 + i * 28))

    def _draw_state(self):
        """The raw payload, typing itself in on each decision. Texture, not a document."""
        box = pygame.Rect(W // 2 + 10, FOOT_Y, W // 2 - MARGIN - 10, 74)
        pygame.draw.rect(self.screen, CARD, box, border_radius=8)
        pygame.draw.rect(self.screen, EDGE, box, width=1, border_radius=8)
        columns = (box.width - 24) // self.mono.size("0")[0]
        flat = json.dumps(self.record["state"])
        wrapped = [flat[i : i + columns] for i in range(0, len(flat), columns)][:4]
        revealed = int(len("".join(wrapped)) * min(1.0, self._since() / REVEAL_MS))
        used = 0
        for i, line in enumerate(wrapped):
            if used >= revealed:
                break
            self.screen.blit(
                self.mono.render(line[: revealed - used], True, STRING),
                (box.x + 12, box.y + 8 + i * 17),
            )
            used += len(line)

    def _draw_ticker(self):
        timed = [ms for ms in self.latencies if ms]
        rate = measured_rate(self.latencies)
        brier = (
            f"Brier {measure.brier(self.labelled):.3f} n={len(self.labelled)}"
            if self.labelled
            else "Brier pending"
        )
        answered = sum(1 for ms in self.latencies if ms) or 1
        if rate:
            per_hour = cost_usd(self.tokens) / answered * rate * 3600
            text = f"{rate:.1f} dec/s    ${per_hour:.2f}/hr    {brier}"
        else:
            text = f"dec/s not measured    {brier}"
        # fit, not clip: n grows through the run and silently ate its own digits
        text = fit(self.ticker, text, W - 2 * MARGIN)
        self.screen.blit(self.ticker.render(text, True, FG), (MARGIN, TICKER_Y))
        last = timed[-1] if timed else 0.0
        note = (
            f"call latency only    last call {last:.0f} ms"
            if last
            else "no row in this run carries a latency"
        )
        self.screen.blit(self.small.render(note, True, MUTED), (MARGIN, TICKER_Y + 52))
        self._draw_sparkline(
            pygame.Rect(W // 2 + 10, TICKER_Y + 58, W // 2 - MARGIN - 10, 24)
        )

    def _draw_sparkline(self, box):
        timed = [ms for ms in self.latencies if ms]
        if len(timed) < 2:
            return
        top = max(timed)
        step = box.width / (len(timed) - 1)
        points = [
            (box.x + i * step, box.bottom - (v / top) * box.height)
            for i, v in enumerate(timed)
        ]
        pygame.draw.lines(self.screen, ACCENT, False, points, 2)


def _replay_source(path: Path, include_stand_ins=False):
    """Stand-in rows are dropped by default: a bar drawn from a hash looks exactly like
    a bar drawn from an answer, and nothing on screen tells them apart."""
    records = measure.load([path])[0]
    if not include_stand_ins:
        records = [r for r in records if r.get("source") != "fake"]
    return records, measure.pairs(records)


def run_replay(path: Path, rate: float = 2.0, include_stand_ins=False):
    """Play a run file back so the clip can be recorded with no ROM in sight."""
    records, labelled = _replay_source(path, include_stand_ins)
    overlay = Overlay(f"jev-plays-pokemon: {path.name}", live=False)
    index, next_at = 0, 0.0
    running = True
    while running:
        if index < len(records) and time.monotonic() >= next_at:
            overlay.feed(records[index], labelled=labelled[: max(0, index - 1)])
            index += 1
            next_at = time.monotonic() + 1.0 / rate
        running = overlay.draw()
        if index >= len(records) and time.monotonic() > next_at + 3:
            running = False
    pygame.quit()


def render_frames(
    path: Path, out: Path, fps=30, rate=1.5, seconds=None, skip=0,
    include_stand_ins=False,
):
    """Walk the same draw calls on a fake clock and dump one PNG per frame.

    Deterministic, so a clip is exactly as long as it says and ffmpeg can encode it
    without a screen recorder, a cursor, or window chrome in the shot.
    """
    records, labelled = _replay_source(path, include_stand_ins)
    records = records[skip:]
    seconds = seconds if seconds is not None else len(records) / rate
    out.mkdir(parents=True, exist_ok=True)
    overlay = Overlay(live=False)
    index = 0
    for n in range(int(fps * seconds)):
        t = n / fps
        overlay.now = t
        while index < len(records) and index / rate <= t:
            overlay.feed(records[index], labelled=labelled[skip : skip + index])
            index += 1
        overlay.draw(None)
        pygame.image.save(overlay.screen, str(out / f"f{n:05d}.png"))
    pygame.quit()
    return int(fps * seconds)
