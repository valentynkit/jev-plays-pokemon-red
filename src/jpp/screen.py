"""What is actually drawn, read out of `wTileMap`.

Every "is a menu up" byte in this game lies once you are on a cartridge: `wTextBoxID`
holds the last box forever, `wMaxMenuItem` keeps the name list's 3 from the intro, and
`wFontLoaded` is overworld-only so battle text leaves it at 0. The screen buffer does not
lie. `wTileMap` at $C3A0 is the 20x18 grid of what is on screen right now, in Gen 1
character codes, so a YES/NO menu is detected by the words YES and NO being visible.
"""

from . import symbols as S

WIDTH, HEIGHT = 20, 18

# charmap.asm. Only the printable run matters here; anything else reads as a space, which
# is right for a detector and honest for the prompt text the model is shown.
_CHARS = {0x7F: " ", 0xBA: "e", 0xE6: "?", 0xE7: ".", 0xE8: "!", 0xF4: ",", 0xE3: "-"}
for _i in range(26):
    _CHARS[0x80 + _i] = chr(ord("A") + _i)
    _CHARS[0xA0 + _i] = chr(ord("a") + _i)
for _i in range(10):
    _CHARS[0xF6 + _i] = chr(ord("0") + _i)


def text_lines(mem) -> list[str]:
    """The screen as 18 lines of text."""
    out = []
    for row in range(HEIGHT):
        base = S.TILE_MAP + row * WIDTH
        out.append("".join(_CHARS.get(mem[base + col], " ") for col in range(WIDTH)))
    return out


def yes_no_prompt(mem) -> tuple[str, list[str]] | None:
    """The question on screen and its choices, or None if no YES/NO menu is up.

    Both words have to be visible: "YES" alone shows up inside ordinary dialogue.
    """
    lines = text_lines(mem)
    words = [line.split() for line in lines]
    if not any("YES" in w for w in words) or not any("NO" in w for w in words):
        return None
    prompt = " ".join(
        " ".join(w for w in word_list if w not in ("YES", "NO")) for word_list in words
    ).split()
    return " ".join(prompt), ["YES", "NO"]
