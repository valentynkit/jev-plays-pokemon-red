"""Reading what is drawn, because every "is a menu up" byte lies on a cartridge."""

from jpp import screen, symbols as S

CODES = {" ": 0x7F, "?": 0xE6, ",": 0xF4}


def _write(mem, row, col, text):
    for i, ch in enumerate(text):
        code = CODES.get(ch)
        if code is None:
            code = 0x80 + ord(ch) - ord("A") if ch.isupper() else 0xA0 + ord(ch) - ord("a")
        mem[S.TILE_MAP + row * screen.WIDTH + col + i] = code


def _blank():
    mem = bytearray(0x10000)
    for i in range(screen.WIDTH * screen.HEIGHT):
        mem[S.TILE_MAP + i] = 0x7F
    return mem


def test_the_screen_buffer_decodes_to_the_words_on_it():
    mem = _blank()
    _write(mem, 16, 1, "CHARMANDER?")
    assert screen.text_lines(mem)[16].strip() == "CHARMANDER?"


def test_a_yes_no_menu_is_read_off_the_screen_with_its_question():
    mem = _blank()
    _write(mem, 8, 16, "YES")
    _write(mem, 10, 16, "NO")
    _write(mem, 14, 1, "give a nickname to")
    _write(mem, 16, 1, "CHARMANDER?")
    prompt, choices = screen.yes_no_prompt(mem)
    assert choices == ["YES", "NO"]
    assert prompt == "give a nickname to CHARMANDER?"


def test_yes_inside_ordinary_dialogue_is_not_a_menu():
    """Both words have to be visible, or narration trips the detector."""
    mem = _blank()
    _write(mem, 14, 1, "YES I remember")
    assert screen.yes_no_prompt(mem) is None
