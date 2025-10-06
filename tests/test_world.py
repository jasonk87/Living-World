from __future__ import annotations

from typing import Dict, List
from unittest.mock import patch

import pytest

from game import config
from game.building import Building
from game.character import Character
from game.stockpile import Stockpile
from game.time import Time
from game.world import World


def _make_world() -> tuple[World, Time]:
    game_time = Time(ticks_per_day=config.TICKS_PER_DAY)
    world = World(game_time_ref=game_time)
    return world, game_time


def _residential_building(location: tuple[int, int] = (0, 0), capacity: int = 4) -> Building:
    building = Building(
        structure_type="House",
        display_name="Cottage",
        location=location,
        size=(1, 1),
        required_resources={},
        functionality={"provides_shelter": capacity, "tags": ["residential"]},
        required_skill={},
    )
    building.is_operational = True
    return building


def _standard_needs() -> Dict[str, int]:
    return {
        "Hunger": 80,
        "Thirst": 80,
        "Energy": 90,
        "Social": 70,
        "Safety": config.NEED_SAFETY_DEFAULT,
        "Belonging": max(config.NEED_BELONGING_DEFAULT, 75),
        "Esteem": config.NEED_ESTEEM_DEFAULT,
    }


def test_update_day_phase_records_single_entry_per_phase():
    world, game_time = _make_world()
    target_phase = config.DAY_PHASE_CONFIG[2]
    game_time.current_tick = target_phase["start_tick"]

    world.update_day_phase()

    assert world.current_phase["key"] == target_phase["key"]
    assert world.phase_history[-1]["key"] == target_phase["key"]
    initial_log_count = len(world.event_log)

    world.update_day_phase()

    # Same phase within the same day should not spam the log/history.
    assert len(world.event_log) == initial_log_count
    assert world.phase_history.count(world.current_phase) == 1


@patch("random.random", return_value=0.99)
@patch("random.randint", side_effect=lambda a, b: a if a == b else a)
def test_weather_event_applies_and_expires_effects(mock_randint, mock_random):  # noqa: ARG001
    world, game_time = _make_world()
    world.season = "Winter"
    world.weather = "Snowy"

    event_definition = {
        "duration_days": (2, 2),
        "severity_range": (3, 3),
        "travel_speed_multiplier": 0.5,
        "resource_yield": {"Wood": 0.7},
        "market_multipliers": {"Wood": 1.2},
        "requires_shelter": True,
    }

    world._start_weather_event("Deep Freeze", event_definition)

    # Align the clock with the supper phase to ensure the snapshot captures the phase payload.
    game_time.current_tick = config.DAY_PHASE_CONFIG[2]["start_tick"]
    world.daily_environment_tick()

    snapshot = world.get_environment_snapshot()
    assert snapshot["phase"]["key"] == config.DAY_PHASE_CONFIG[2]["key"]
    assert snapshot["weather_event"]["name"] == "Deep Freeze"
    expected_travel = (
        config.SEASON_ENVIRONMENT_MODIFIERS["Winter"]["travel_speed"]
        * config.WEATHER_ENVIRONMENT_MODIFIERS["Snowy"]["travel_speed"]
        * event_definition["travel_speed_multiplier"]
    )
    assert world.get_travel_speed_modifier() == pytest.approx(expected_travel)

    def advance_day():
        game_time.current_tick = game_time.ticks_per_day - 1
        game_time.tick()

    # Day 2: event should still be active.
    advance_day()
    world.daily_environment_tick()
    assert world.get_active_weather_event() is not None

    # Day 3: event expires and modifiers revert to seasonal/weather baselines.
    advance_day()
    world.daily_environment_tick()
    assert world.get_active_weather_event() is None
    baseline_travel = (
        config.SEASON_ENVIRONMENT_MODIFIERS["Winter"]["travel_speed"]
        * config.WEATHER_ENVIRONMENT_MODIFIERS[world.weather]["travel_speed"]
    )
    assert world.get_travel_speed_modifier() == pytest.approx(baseline_travel)
    assert any(event["name"] == "Deep Freeze" for event in world.weather_event_history)


def test_resource_regrowth_cycle_logs_and_restores_node():
    world, _ = _make_world()
    world.add_resource("Wood", (2, 2))
    node = world.resources["Wood"][0]

    for _ in range(node["max_durability"]):
        world.record_resource_harvest("Wood", (2, 2), amount=1)

    assert node["depleted"] is True
    depleted_tile = config.RESOURCE_NODE_DEPLETED_TILES["Wood"]
    assert world.get_tile(2, 2) == depleted_tile
    regrowth_days = config.RESOURCE_NODE_REGROWTH_DAYS["Wood"]

    for _ in range(regrowth_days + 1):
        world._advance_resource_regrowth()

    assert node["depleted"] is False
    assert node["durability"] == node["max_durability"]
    assert world.get_tile(2, 2) != depleted_tile
    assert any("regrown" in log for log in world.event_log)


def test_population_birth_event_when_conditions_are_right():
    world, _ = _make_world()
    cottage = _residential_building(location=(1, 1), capacity=3)
    world.add_building(cottage)

    parent = Character(
        name="Morgan",
        personality="Kind",
        traits=[],
        skills={},
        job="Farmer",
        needs={**_standard_needs(), "Belonging": 85},
    )
    world.add_character(parent)
    world.claim_residential_spot(parent)

    report: Dict[str, int | List[Dict[str, str]]] = {"food_deficit": 0, "water_deficit": 0}
    housing_snapshot = {"available_beds": 1, "homeless_characters": []}

    with patch("random.random", side_effect=[0.0, 1.0, 1.0]):
        world.evaluate_population_dynamics(report, housing_snapshot)

    assert world.population_stats["births_today"] == 1
    assert any(event["type"] == "birth" for event in report.get("population_events", []))
    assert report["population_snapshot"]["population"] == len(world.characters)


def test_population_migration_when_surplus_resources_exist():
    world, _ = _make_world()
    cottage = _residential_building(capacity=4)
    world.add_building(cottage)

    resident = Character(
        name="Ilan",
        personality="Calm",
        traits=[],
        skills={},
        job="Woodcutter",
        needs=_standard_needs(),
    )
    world.add_character(resident)
    world.claim_residential_spot(resident)

    stockpile = Stockpile("Central", 0, 0, 1, 1, allowed_resources=None)
    stockpile.inventory["Food"] = config.MAYOR_RESOURCE_HIGH_THRESHOLD + 50
    world.stockpiles.append(stockpile)

    report: Dict[str, int | List[Dict[str, str]]] = {"food_deficit": 0, "water_deficit": 0}
    housing_snapshot = {"available_beds": 2, "homeless_characters": []}

    with patch("random.random", side_effect=[1.0, 0.0, 1.0]):
        world.evaluate_population_dynamics(report, housing_snapshot)

    assert world.population_stats["migrants_today"] == 1
    assert any(event["type"] == "arrival" for event in report.get("population_events", []))
    assert report["population_snapshot"]["population"] == len(world.characters)


def test_population_departure_under_hardship_and_low_mood():
    world, _ = _make_world()
    names = ["Hard Luck", "Ally", "Brooke", "Cedar"]
    for name in names:
        character = Character(
            name=name,
            personality="Stoic",
            traits=[],
            skills={},
            job="Laborer",
            needs=_standard_needs(),
        )
        world.add_character(character)

    target = world.get_character_by_name("Hard Luck")
    target.mood_score = -45
    target.mood = "Sad"

    report: Dict[str, int | List[Dict[str, str]]] = {"food_deficit": 10, "water_deficit": 0}
    housing_snapshot = {"available_beds": 0, "homeless_characters": ["Hard Luck"]}

    with patch.object(config, "POPULATION_DEPARTURE_BASE_CHANCE", 1.0):
        with patch("random.random", return_value=0.0):
            world.evaluate_population_dynamics(report, housing_snapshot)

    assert world.population_stats["departures_today"] == 1
    assert "Hard Luck" not in [char.name for char in world.characters]
    assert any(event["type"] == "departure" for event in report.get("population_events", []))
