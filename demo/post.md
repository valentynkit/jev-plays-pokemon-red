# Launch copy

Rewritten 2026-09-19, after the first cartridge runs. The old draft was written against
synthetic RAM and every number in it has been replaced.

## What is true now

The agent plays the opening of Pokemon Red unattended on a real ROM: out of the bedroom,
across Pallet Town, into Oak's lab, takes Charmander, and wins the rival battle. Code owns
the route, so nothing is asked between the bedroom and the lab. Jev is asked at branches:
every battle turn, and the menus.

Measured over the six calls that were answered before the free tier cut in:

```
479  496  563  679  867  1470 ms      median 621, mean 759
about 1.3 decisions/sec, $0.14/hour at ~725 input tokens a call
```

Still blocked: a Brier worth publishing. Five calls per rate-limit window is not a sample,
and the best run so far is n=5 labelled turns with an interval that covers everything.
**Do not post a calibration claim until that number exists.** The number is the differentiator;
posting a shrug instead is worse than waiting.

## The hook line is wrong in CONTEXT

Sections 1 and 8 say "about a hundred milliseconds". The median is 621 ms through the
gateway shim. Say "under a second". The speed story does not need the exaggeration when
the comparison is a model that deliberates for tens of seconds a move.

## X thread

**1, with `demo/clip-live-battle.mp4`**

```
I gave Pokemon Red to a model that cannot write a sentence.

It never sees the screen. Code reads the Game Boy's memory into a typed snapshot,
hands it a menu of the moves that are actually legal, and it returns a probability
for each one. The bars are those probabilities, live.

Median 621 ms a decision, $0.14/hour.
```

**2, with `demo/still-payload.png`**

```
Code owns everything that is not a branch. Text boxes, waypoints, cursor moves.
Between the bedroom and Oak's lab it is not asked anything at all.

Where it does get asked, the question is small. This is the whole request: the
goal sentence, the two Pokemon, and the legal options. No screenshots, no history,
no plan for next turn.
```

**3, the one I would push back on**

```
Two prompts, one route, and the answer has to differ:

  "do you want the fire POKeMON, CHARMANDER?"   -> yes, 0.61
  "give a nickname to CHARMANDER?"              -> no,  0.58

No fixed button survives both. Yes is wrong for the nickname, no is wrong for the
starter. The only thing separating them is the goal sentence in the state, which is
the entire argument for asking at a branch rather than scripting one.

<repo link>
```

**4, the caveat, once the Brier exists**

```
Calibration: Brier __ on "will my Pokemon faint this turn", n=__, 95% CI __ to __,
against a constant predictor at __. [If the interval covers it, say so plainly and
say the sample is too small.]

Prior art: Claude Plays Pokemon is the famous one. milanboers/jev-plays-pokemon got
there first with Jev and plays more of the game than this does.
```

## Show HN

```
Show HN: Pokemon Red played by a model that only outputs probabilities, with a published Brier score
```

Hold this one until the Brier is real. It is the only claim HN will actually check.

## Awesome list

For `~/Projects/mine/awesome-jev-typesafe`, under "Games, robotics and simulation", beside
the existing `JevPlaysPokemon` line:

```
- [<new name>](https://github.com/valentynkit/<new name>) - Pokémon Red on PyBoy where code owns the route and Jev is asked only at branches, with per-option probability bars over the live game and a Brier score on "faints this turn".
```

The repo name is still open. `jev-plays-pokemon` is taken by milanboers.
