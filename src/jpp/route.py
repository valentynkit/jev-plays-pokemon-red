"""The v0.1 route: one waypoint per map, axis-first stepping, a local sidestep.

Not a pathfinder. v0.1 walks six maps whose connections are static and public, so the
route is a hand-written list of tiles, most of them `warp_event` coordinates straight out
of `data/maps/objects/*.asm`. Anything past Viridian needs a real occupancy map with warp
edges, which is the v0.2 item in CONTEXT section 2.

The indoor tiles are exact: they are warp coordinates in the source. The outdoor legs were
guesses and both were wrong, which a cartridge settled on 2026-09-19.

Pallet Town, measured by walking every column: x=10 is the gap to Route 1 but only above
y=2, and from the lab door at y=12 that column is walled. Axis-first stepping closed x
first and parked against the wall forever. `_pallet_north` climbs x=9, which is clear from
y=12 to y=2, and crosses at the top. That leg now works end to end.

`ponytail:` Route 1 is still a straight line up x=10 and still wrong: the agent walks from
y=35 to y=28 and stops there. One waypoint per map cannot express a route around a ledge,
so this is the v0.2 occupancy map with warp edges from CONTEXT section 2, not another
hand-picked tile.
"""

from . import symbols as S

DIRECTIONS = ("up", "down", "left", "right")

# One target tile per map, per goal, or a function of the state where the game gates the
# leg on an event. (x, y) in map tile coordinates, the same units as wXCoord / wYCoord.
OAK_TRIGGER = (10, 1)  # any tile with wYCoord == 1: that is the whole condition
LAB_DOOR = (12, 11)
CHARMANDER_BALL = (6, 3)


def _pallet_town(state) -> tuple[int, int]:
    """North edge first, then the lab door.

    Walking straight to the lab is a dead end. `PalletTownDefaultScript`
    (scripts/PalletTown.asm) only fires when `wYCoord == 1` and
    EVENT_FOLLOWED_OAK_INTO_LAB is clear, and it is that script that sets
    EVENT_OAK_APPEARED_IN_PALLET. Without it `OaksLabDefaultScript` returns immediately,
    Oak never asks, and every poke ball answers "those are POKE BALLs" forever.
    """
    if not state.event(S.EVENT_FOLLOWED_OAK_INTO_LAB):
        return OAK_TRIGGER
    return LAB_DOOR


def _pallet_north(state) -> tuple[int, int]:
    """Two legs, because axis-first stepping cannot do this in one.

    Measured on a cartridge: x=10 is the gap to Route 1, but only above y=2. From the
    lab door at y=12 that column is walled, and closing x first parks the agent against
    it forever. x=9 is clear from y=12 up to y=2, so climb there and cross at the top.
    """
    return (9, 2) if state.y > 2 else (10, 0)


def _oaks_lab(state) -> tuple[int, int]:
    """Oak until he asks, then Charmander's ball.

    OaksLab.asm: object_event 6, 3 is the Charmander ball, object_event 5, 2 is Oak.
    Both are objects, so the tile stays blocked; walking into one turns the player to
    face it and `classify` presses A from there.
    """
    if state.event(S.EVENT_OAK_ASKED_TO_CHOOSE_MON):
        return CHARMANDER_BALL
    return (5, 3)


WAYPOINTS: dict[str, dict[int, object]] = {
    # RedsHouse2F.asm: warp_event 7, 1, REDS_HOUSE_1F, 3
    # RedsHouse1F.asm: warp_event 2, 7, LAST_MAP, 1
    "leave_house": {
        S.REDS_HOUSE_2F: (7, 1),
        S.REDS_HOUSE_1F: (2, 7),
    },
    "get_starter": {
        S.PALLET_TOWN: _pallet_town,
        S.OAKS_LAB: _oaks_lab,
    },
    # the rival does not challenge on the spot. He intercepts on the way out, so the
    # goal still has to walk: OaksLab.asm warp_event 4, 11 and 5, 11 are the door.
    "win_lab_rival": {
        S.OAKS_LAB: (5, 11),
    },
    "reach_viridian": {
        S.PALLET_TOWN: _pallet_north,
        S.ROUTE_1: (10, 0),
    },
}

# Where the player stands in the 20x18 tile grid `game_area_collision()` returns, and how
# many grid tiles one walking step covers. PyBoy builds that grid by testing each 2x2
# block against the tileset's walkable list and then doubling it
# (`game_wrapper_pokemon_gen1._get_screen_walkable_matrix`), so a block is two grid cells
# wide, the screen is 10x9 blocks, and the player is the middle one. 1 is walkable: the
# matrix is `np.isin(tiles, walkable_tiles_indexes)`, an inclusion test, matching
# `CanWalkOntoTile` in engine/overworld/movement.asm.
PLAYER_COL, PLAYER_ROW = 8, 9
STEP_TILES = 2
WALKABLE = 1

_DELTA = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def waypoint_for(goal, state) -> tuple[int, int] | None:
    """The tile to head for on the current map, or None if this map has no waypoint."""
    leg = WAYPOINTS.get(goal.name, {}).get(state.map_id)
    return leg(state) if callable(leg) else leg


def next_step(state, waypoint) -> str | None:
    """Axis-first greedy: close x, then y. None once the tile is reached."""
    if waypoint is None:
        return None
    dx = waypoint[0] - state.x
    dy = waypoint[1] - state.y
    if dx:
        return "right" if dx > 0 else "left"
    if dy:
        return "down" if dy > 0 else "up"
    return None


def distance(state, waypoint, direction=None) -> int:
    dx, dy = _DELTA.get(direction, (0, 0))
    return abs(waypoint[0] - (state.x + dx)) + abs(waypoint[1] - (state.y + dy))


def free_directions(collision) -> list[str]:
    """Which of the four neighbours the collision grid says are walkable."""
    free = []
    for name, (dx, dy) in _DELTA.items():
        col = PLAYER_COL + dx * STEP_TILES
        row = PLAYER_ROW + dy * STEP_TILES
        if 0 <= row < len(collision) and 0 <= col < len(collision[row]):
            if collision[row][col] == WALKABLE:
                free.append(name)
    return free


def sidesteps(state, collision, waypoint) -> list[str]:
    """Free neighbours that do not walk away from the waypoint.

    One survivor is a plain move. Two or more that are equally far is the tie Jev breaks,
    which is the only place the model touches the overworld.
    """
    if waypoint is None:
        return []
    free = free_directions(collision)
    if not free:
        return []
    best = min(distance(state, waypoint, d) for d in free)
    if best >= distance(state, waypoint):
        return []  # every free neighbour is a step backwards: nothing to choose between
    return [d for d in free if distance(state, waypoint, d) == best]
