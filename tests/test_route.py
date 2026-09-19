from jpp import route, symbols as S
from jpp.decode import decode
from jpp.goals import GOALS

import make_ram

# PyBoy's collision matrix is `np.isin(tiles, walkable_tiles_indexes)`, so 1 is walkable.
# Written out rather than taken from route.WALKABLE: a test that reads the constant it is
# checking passes whichever way the constant is wrong.
FREE, BLOCKED = 1, 0


def test_the_grid_says_one_for_walkable():
    assert route.WALKABLE == FREE


def grid(*free_directions):
    """A 20x18 collision grid where only the named neighbours are walkable."""
    g = [[BLOCKED] * 20 for _ in range(18)]
    for d in free_directions:
        dx, dy = route._DELTA[d]
        g[route.PLAYER_ROW + dy * route.STEP_TILES][
            route.PLAYER_COL + dx * route.STEP_TILES
        ] = FREE
    return g


def state_at(map_id, x, y, events=()):
    ram = make_ram.overworld()
    ram[S.CUR_MAP] = map_id
    ram[S.X_COORD], ram[S.Y_COORD] = x, y
    for bit in events:
        addr, offset = S.event_address(bit)
        ram[addr] |= 1 << offset
    return decode(bytes(ram))


def goal(name):
    return next(g for g in GOALS if g.name == name)


def test_every_goal_with_walking_has_a_waypoint_on_every_map_it_crosses():
    # RedsHouse2F.asm and RedsHouse1F.asm warps
    assert route.WAYPOINTS["leave_house"][S.REDS_HOUSE_2F] == (7, 1)
    assert route.WAYPOINTS["leave_house"][S.REDS_HOUSE_1F] == (2, 7)
    # the rival does not challenge on the spot: on a cartridge the agent stood in the lab
    # pressing A forever. He intercepts on the way out, so the goal walks to the door.
    assert route.WAYPOINTS["win_lab_rival"] == {S.OAKS_LAB: (5, 11)}
    assert set(route.WAYPOINTS) == {g.name for g in GOALS}


def test_pallet_town_goes_to_the_north_edge_before_the_lab():
    """Oak only intercepts at wYCoord == 1, and nothing in the lab arms until he does."""
    st = state_at(S.PALLET_TOWN, 5, 5)
    assert route.waypoint_for(goal("get_starter"), st) == route.OAK_TRIGGER
    assert route.OAK_TRIGGER[1] == 1

    followed = state_at(S.PALLET_TOWN, 5, 5, events={S.EVENT_FOLLOWED_OAK_INTO_LAB})
    assert route.waypoint_for(goal("get_starter"), followed) == route.LAB_DOOR


def test_the_lab_waypoint_is_a_poke_ball_only_once_oak_has_asked():
    st = state_at(S.OAKS_LAB, 5, 6)
    assert route.waypoint_for(goal("get_starter"), st) == (5, 3)  # Oak

    asked = state_at(S.OAKS_LAB, 5, 6, events={S.EVENT_OAK_ASKED_TO_CHOOSE_MON})
    assert route.waypoint_for(goal("get_starter"), asked) == route.CHARMANDER_BALL


def test_waypoint_for_returns_none_off_route():
    st = state_at(S.VIRIDIAN_CITY, 1, 1)
    assert route.waypoint_for(goal("get_starter"), st) is None


def test_stepping_closes_x_then_y():
    waypoint = (12, 11)
    assert route.next_step(state_at(S.PALLET_TOWN, 10, 8), waypoint) == "right"
    assert route.next_step(state_at(S.PALLET_TOWN, 14, 8), waypoint) == "left"
    assert route.next_step(state_at(S.PALLET_TOWN, 12, 8), waypoint) == "down"
    assert route.next_step(state_at(S.PALLET_TOWN, 12, 14), waypoint) == "up"
    assert route.next_step(state_at(S.PALLET_TOWN, 12, 11), waypoint) is None


def test_one_free_sidestep_resolves_in_code():
    st = state_at(S.PALLET_TOWN, 10, 8)
    free = route.sidesteps(st, grid("right", "up"), (12, 11))
    assert free == ["right"]  # up does not shorten the walk, right does


def test_two_equally_good_sidesteps_are_the_tie_jev_breaks():
    st = state_at(S.PALLET_TOWN, 10, 8)
    free = route.sidesteps(st, grid("right", "down"), (12, 11))
    assert sorted(free) == ["down", "right"]  # both cut one tile off the distance


def test_a_dead_end_is_not_a_branch():
    st = state_at(S.PALLET_TOWN, 10, 8)
    assert route.sidesteps(st, grid("left", "up"), (12, 11)) == []
    assert route.sidesteps(st, grid(), (12, 11)) == []


def test_free_directions_reads_the_grid_and_stays_in_bounds():
    assert sorted(route.free_directions(grid("up", "left"))) == ["left", "up"]
    assert route.free_directions([[FREE] * 2] * 2) == []


def test_pallet_town_climbs_the_clear_column_before_crossing_to_the_gap():
    """Measured on a cartridge: x=10 is the gap to Route 1 but only above y=2, and from
    the lab door at y=12 it is walled. Closing x first parks against that wall."""
    ram = make_ram.overworld()
    ram[S.X_COORD], ram[S.Y_COORD] = 12, 12
    ram[S.CUR_MAP] = S.PALLET_TOWN
    goal = next(g for g in GOALS if g.name == "reach_viridian")
    low = decode(bytes(ram))
    assert route.waypoint_for(goal, low) == (9, 2)

    ram[S.X_COORD], ram[S.Y_COORD] = 9, 2
    assert route.waypoint_for(goal, decode(bytes(ram))) == (10, 0)
