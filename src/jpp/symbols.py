"""WRAM addresses, taken from pret/pokered `ram/wram.asm`.

Every address here was computed by walking `ram/wram.asm` from the WRAM0 origin
($C000, with "Sprite State Data" at $C100 per `layout.link`) and summing `db`, `dw`,
`ds`, `flag_array` and the struct macros in `macros/ram.asm`, honouring UNION/NEXTU/ENDU.
The nine addresses that are independently published (wCurMap, wYCoord, wXCoord,
wPartyCount, wObtainedBadges, wEventFlags, wPlayerMoney, wIsInBattle, and the party HP /
level / max-HP columns) came out of that walk byte-exact, which is what makes the rest of
the table trustworthy. Each entry names its `wram.asm` label.
"""

# --- overworld position and map (SECTION "Main Data") ---
CUR_MAP = 0xD35E  # wCurMap
Y_COORD = 0xD361  # wYCoord
X_COORD = 0xD362  # wXCoord
LAST_MAP = 0xD365  # wLastMap
CUR_MAP_HEIGHT = 0xD368  # wCurMapHeight, in blocks
CUR_MAP_WIDTH = 0xD369  # wCurMapWidth, in blocks

# --- player inventory-ish facts we only read for the overlay ---
NUM_BAG_ITEMS = 0xD31D  # wNumBagItems
BAG_ITEMS = 0xD31E  # wBagItems, (item id, quantity) pairs, $FF terminated
PLAYER_MONEY = 0xD347  # wPlayerMoney, 3 bytes BCD
OBTAINED_BADGES = 0xD356  # wObtainedBadges, flag_array NUM_BADGES
EVENT_FLAGS = 0xD747  # wEventFlags, flag_array NUM_EVENTS ($A00 bits = 320 bytes)
EVENT_FLAGS_LEN = 0xA00 // 8

# --- party (SECTION "Party Data") ---
PARTY_COUNT = 0xD163  # wPartyCount
PARTY_SPECIES = 0xD164  # wPartySpecies, PARTY_LENGTH + 1 terminated list
PARTY_MONS = 0xD16B  # wPartyMons, 6 x party_struct
PARTY_STRUCT_LEN = 44  # PARTYMON_STRUCT_LENGTH

# party_struct field offsets, from `box_struct` + `party_struct` in macros/ram.asm
P_SPECIES = 0
P_HP = 1  # dw
P_STATUS = 4
P_TYPE1 = 5
P_TYPE2 = 6
P_MOVES = 8  # ds NUM_MOVES
P_PP = 29  # ds NUM_MOVES
P_LEVEL = 33
P_MAX_HP = 34  # dw

# --- battle (SECTION "WRAM") ---
IS_IN_BATTLE = 0xD057  # wIsInBattle: -1 lost, 0 none, 1 wild, 2 trainer
CUR_OPPONENT = 0xD059  # wCurOpponent
BATTLE_TYPE = 0xD05A  # wBattleType: 0 normal, 1 old man, 2 safari
BATTLE_RESULT = 0xCF0B  # wBattleResult: $00 win, $01 lose, $02 draw

# battle_struct blocks. wram.asm orders them wEnemyMonNick, wEnemyMon, ...,
# wBattleMonNick, wBattleMon, so the enemy block sits below the player's; the field
# offsets below are the same macro for both and match that order.
BATTLE_MON = 0xD014  # wBattleMon (player's active)
ENEMY_MON = 0xCFE5  # wEnemyMon
BATTLE_MON_NICK = 0xD009  # wBattleMonNick, ds NAME_LENGTH
ENEMY_MON_NICK = 0xCFDA  # wEnemyMonNick

# battle_struct field offsets, from `battle_struct` in macros/ram.asm
B_SPECIES = 0
B_HP = 1  # dw
B_STATUS = 4
B_TYPE1 = 5
B_TYPE2 = 6
B_MOVES = 8  # ds NUM_MOVES
B_LEVEL = 14
B_MAX_HP = 15  # dw
B_PP = 25  # ds NUM_MOVES

# --- menus and input plumbing ---
CURRENT_MENU_ITEM = 0xCC26  # wCurrentMenuItem
MAX_MENU_ITEM = 0xCC28  # wMaxMenuItem
TOP_MENU_ITEM_Y = 0xCC24  # wTopMenuItemY
TOP_MENU_ITEM_X = 0xCC25  # wTopMenuItemX

# Gen 1 menus remember where the cursor was. All three are zeroed by
# InitBattleVariables, so turn 1 starts at FIGHT / move 1 / party slot 1 and every later
# turn does not. options.buttons_for navigates from these, not from an assumed corner.
PARTY_SAVED_MENU_ITEM = 0xCC2B  # wPartyAndBillsPCSavedMenuItem
BATTLE_SAVED_MENU_ITEM = 0xCC2D  # wBattleAndStartSavedMenuItem
PLAYER_MOVE_LIST_INDEX = 0xCC2E  # wPlayerMoveListIndex, the last move picked
PLAYER_MON_NUMBER = 0xCC2F  # wPlayerMonNumber, party index of the active mon
TEXT_BOX_ID = 0xD125  # wTextBoxID
TILE_MAP = 0xC3A0  # wTileMap, the 20x18 screen buffer in charmap codes
JOY_IGNORE = 0xCD6B  # wJoyIgnore, "Set buttons are ignored"

# wJoyIgnore is a per-button mask, not a boolean: `_Joypad` in engine/joypad.asm ANDs its
# complement against the held and pressed bytes. Scripted dialogue sets
# PAD_SELECT | PAD_START | PAD_CTRL_PAD, which locks movement and deliberately leaves A
# open so the text can be advanced. Bit order from constants/hardware.inc.
PAD_A = 0x01
PAD_B = 0x02
PAD_SELECT = 0x04
PAD_START = 0x08
PAD_RIGHT = 0x10
PAD_LEFT = 0x20
PAD_UP = 0x40
PAD_DOWN = 0x80
PAD_CTRL_PAD = 0xF0
BUTTON_BITS = {
    "a": PAD_A,
    "b": PAD_B,
    "up": PAD_UP,
    "down": PAD_DOWN,
    "left": PAD_LEFT,
    "right": PAD_RIGHT,
}
WALK_COUNTER = 0xCFC5  # wWalkCounter, "walk animation counter"
FONT_LOADED = 0xCFC4  # wFontLoaded, bit 0 set while a text box owns the walk tiles
TILE_IN_FRONT = 0xCFC6  # wTileInFrontOfPlayer

# --- map ids, from constants/map_constants.asm ---
PALLET_TOWN = 0x00
VIRIDIAN_CITY = 0x01
ROUTE_1 = 0x0C
REDS_HOUSE_1F = 0x25
REDS_HOUSE_2F = 0x26
OAKS_LAB = 0x28

MAP_NAMES = {
    PALLET_TOWN: "PALLET_TOWN",
    VIRIDIAN_CITY: "VIRIDIAN_CITY",
    ROUTE_1: "ROUTE_1",
    REDS_HOUSE_1F: "REDS_HOUSE_1F",
    REDS_HOUSE_2F: "REDS_HOUSE_2F",
    OAKS_LAB: "OAKS_LAB",
}

# --- event bits, counted through constants/event_constants.asm (const_skip included) ---
EVENT_FOLLOWED_OAK_INTO_LAB = 0
EVENT_OAK_ASKED_TO_CHOOSE_MON = 33
EVENT_GOT_STARTER = 34
EVENT_BATTLED_RIVAL_IN_OAKS_LAB = 35
EVENT_GOT_POKEBALLS_FROM_OAK = 36
EVENT_GOT_POKEDEX = 37

# status byte bits, from constants/battle_constants.asm (SLP_MASK is the low 3 bits)
STATUS_NAMES = ((3, "poison"), (4, "burn"), (5, "freeze"), (6, "paralysis"))


def event_address(bit: int) -> tuple[int, int]:
    """Byte address and bit index inside wEventFlags for an event constant."""
    return EVENT_FLAGS + bit // 8, bit % 8
