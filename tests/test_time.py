from game import config
from game.time import Time


def test_time_tick_rolls_over_day_and_counts_election_cycle():
    time = Time(ticks_per_day=4)

    # Exhaust a full day of ticks.
    for _ in range(3):
        assert time.tick() is False

    # The final tick should roll to a new day and decrement the election counter.
    starting_election_timer = time.days_until_election
    assert time.tick() is True
    assert time.current_day == 2
    assert time.current_tick == 0
    assert time.days_until_election == max(0, starting_election_timer - 1)


def test_time_uses_configured_phase_schedule_for_phase_lookup():
    time = Time(ticks_per_day=config.TICKS_PER_DAY)

    # Ensure each configured phase is returned when we are at or after its start tick.
    for phase in config.DAY_PHASE_CONFIG:
        time.current_tick = phase["start_tick"]
        resolved_phase = time.get_phase()
        assert resolved_phase["key"] == phase["key"]
        assert resolved_phase["name"] == phase["name"]

    # Verify that in-between ticks use the most recent phase definition.
    time.current_tick = config.DAY_PHASE_CONFIG[1]["start_tick"] + 1
    resolved_phase = time.get_phase()
    assert resolved_phase["key"] == config.DAY_PHASE_CONFIG[1]["key"]
