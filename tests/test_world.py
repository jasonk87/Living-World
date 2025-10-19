from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from game import config
from game.building import Building
from game.character import Character, Job
from game.data import Job
from game.stockpile import Stockpile
from game.time import Time
from game.world import World
from game.data import JOB_SALARIES


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
        functionality={
            "provides_shelter": capacity,
            "tags": ["residential"],
            "wealth_tier": "modest",
        },
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


def test_initial_landscape_has_resources_and_variety():
    game_time = Time(ticks_per_day=config.TICKS_PER_DAY)
    world = World(grid_size=(24, 24), game_time_ref=game_time, map_seed=1337)

    tile_counter: Counter[str] = Counter()
    for x in range(world.grid_size[0]):
        for y in range(world.grid_size[1]):
            tile_counter[world.grid[x][y]] += 1

    assert len([tile for tile, count in tile_counter.items() if count > 0]) > 1
    assert tile_counter.get("Grass", 0) < world.grid_size[0] * world.grid_size[1]

    resource_snapshot = world.get_resource_nodes_snapshot()
    resource_types = {node.get("resource") for node in resource_snapshot}
    for expected in {"Wood", "Stone", "Herbs", "Food"}:
        assert expected in resource_types

    landscape_profile = world.get_landscape_profile()
    assert landscape_profile.get("resources", {}).get("Wood", 0) >= 1
    assert landscape_profile.get("reserved", 0) > 0


def test_reserved_clearing_tiles_are_walkable():
    radius = getattr(config, "MAP_RESERVED_CLEARING_RADIUS", 0)
    if radius <= 0:
        pytest.skip("No reserved clearing configured")

    game_time = Time(ticks_per_day=config.TICKS_PER_DAY)
    world = World(grid_size=(20, 20), game_time_ref=game_time, map_seed=2024)
    center = (world.grid_size[0] // 2, world.grid_size[1] // 2)

    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x = center[0] + dx
            y = center[1] + dy
            if not (0 <= x < world.grid_size[0] and 0 <= y < world.grid_size[1]):
                continue
            assert world.grid[x][y] not in config.IMPASSABLE_TERRAINS


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


def test_healthcare_report_tracks_vitals_and_events():
    world, game_time = _make_world()
    patient_needs = _standard_needs()
    patient_needs.update({"Hunger": 20, "Thirst": 25, "Energy": 35, "Safety": 35})
    patient = Character(
        name="Orin",
        personality="Stoic",
        traits=[],
        skills={},
        needs=patient_needs, job=Job("Unemployed", None, 0)
    )
    world.add_character(patient)
    patient.health_profile["vitality"] = 48.0
    patient.health_profile["immune_resilience"] = 0.22

    with patch("random.random", side_effect=[0.0, 1.0]), patch("random.uniform", return_value=3.1):
        world.process_healthcare_daily()

    report = world.latest_healthcare_report
    assert report.get("health_events")
    assert any(evt.get("type") == "fell_ill" for evt in report.get("health_events", []))
    assert report.get("average_vitality") is not None
    assert report.get("new_cases")


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
        job=Job("Farmer", None, JOB_SALARIES.get("Farmer", 0)),
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
        job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)),
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


def test_building_tile_layout_used_for_map_tiles():
    world, _ = _make_world()
    layout = [["WoodWall", "Bedroll"], ["Hearth", "Bed"]]
    building = Building(
        structure_type="House",
        display_name="Layout House",
        location=(1, 2),
        size=(2, 2),
        required_resources={},
        functionality={"provides_shelter": 2, "tags": ["residential"], "wealth_tier": "modest"},
        required_skill={},
        tile_layout=layout,
    )
    building.is_operational = True
    world.add_building(building)

    assert world.get_tile(1, 2) == "WoodWall"
    assert world.get_tile(2, 2) == "Bedroll"
    assert world.get_tile(1, 3) == "Hearth"
    assert world.get_tile(2, 3) == "Bed"


def test_leadership_cycle_records_commendable_oversight():
    world, game_time = _make_world()
    game_time.current_day = 3

    mayor = Character(
        name="Alina",
        personality="Charismatic",
        traits=["Diligent"],
        skills={"Leadership": 3},
        job=Job("Mayor", None, JOB_SALARIES.get("Mayor", 0)),
        needs=_standard_needs(),
    )
    steward = Character(
        name="Bren",
        personality="Calm",
        traits=[],
        skills={},
        job=Job("Steward", None, JOB_SALARIES.get("Steward", 0)),
        needs=_standard_needs(),
        supervisor_name=mayor.name,
    )

    world.add_character(mayor)
    world.add_character(steward)
    mayor.subordinates_names.append(steward.name)
    mayor.relationships[steward.name] = 20

    mayor._record_management_activity(world, "rounds", 1.2)
    mayor._record_management_activity(world, "briefing", 0.8)

    world._process_leadership_management_cycle()

    assert len(world.leadership_oversight_report) >= 1
    mayor_entry = next((entry for entry in world.leadership_oversight_report if entry["leader"] == "Alina"), None)
    assert mayor_entry is not None
    assert mayor_entry["role"] == "Mayor"
    assert mayor_entry["actions"] == pytest.approx(2.0)
    assert "commendable" in mayor_entry["flags"]
    assert mayor.leadership_oversight_score == pytest.approx(mayor_entry["score"])
    assert mayor_entry.get("notes") == ["rounds", "briefing"]


@patch("random.random", return_value=0.0)
def test_leadership_cycle_flags_neglect_and_records_incident(mock_random):  # noqa: ARG001
    world, game_time = _make_world()
    game_time.current_day = 6

    steward = Character(
        name="Garrick",
        personality="Lenient",
        traits=["Lazy", "Careless"],
        skills={},
        job=Job("Steward", None, JOB_SALARIES.get("Steward", 0)),
        needs=_standard_needs(),
    )
    worker = Character(
        name="Hale",
        personality="Rebellious",
        traits=["Greedy"],
        skills={},
        job=Job("Laborer", None, JOB_SALARIES.get("Laborer", 0)),
        needs=_standard_needs(),
        supervisor_name=steward.name,
        money=0,
    )

    world.add_character(steward)
    world.add_character(worker)
    steward.subordinates_names.append(worker.name)
    steward.relationships[worker.name] = -80

    world._process_leadership_management_cycle()

    assert len(world.leadership_oversight_report) == 1
    entry = world.leadership_oversight_report[0]
    assert entry["leader"] == "Garrick"
    assert "neglect" in entry["flags"]
    assert "incident" in entry["flags"]
    assert entry.get("incidents")
    assert any(crime.get("suspect") == worker.name for crime in world.pending_crimes)
    assert worker.supervisor_oversight == pytest.approx(entry["score"])
    assert worker.money > 0


@patch("random.choice", side_effect=lambda options: options[0])
def test_household_evening_generates_story_and_bonuses(mock_choice):  # noqa: ARG001
    world, game_time = _make_world()
    game_time.current_day = 5
    layout = [["WoodWall", "Bedroll"], ["Hearth", "Bed"]]
    building = Building(
        structure_type="House",
        display_name="Hearthstead",
        location=(2, 2),
        size=(2, 2),
        required_resources={},
        functionality={"provides_shelter": 2, "tags": ["residential"], "wealth_tier": "modest"},
        required_skill={},
        tile_layout=layout,
        household_style="hearthfire",
    )
    building.is_operational = True
    world.add_building(building)

    resident = Character(
        name="Rhea",
        personality="Warm",
        traits=["Compassionate"],
        skills={},
        needs=_standard_needs(),
        job=Job("Farmer", None, JOB_SALARIES.get("Farmer", 0)),
    )
    world.add_character(resident)
    building.add_occupant(resident.name)
    resident.home_location = building.location

    baseline_mood = resident.mood_score
    baseline_belonging = resident.needs.get("Belonging", 0)

    snapshot = world.get_housing_snapshot()
    report: Dict[str, Any] = {}
    world._resolve_household_evenings(snapshot, report)

    assert world._latest_household_vignettes, "Expected a household vignette to be recorded."
    story = world._latest_household_vignettes[0]
    assert story["building"] == "Hearthstead"
    assert resident.mood_score > baseline_mood
    assert resident.needs["Belonging"] >= baseline_belonging
    assert "housing_highlights" in report


def test_household_comfort_cycle_consumes_resources_and_updates_mood():
    world, game_time = _make_world()
    stockpile = Stockpile(
        name="CentralStore",
        x=0,
        y=0,
        width=1,
        height=1,
        allowed_resources=None,
        total_capacity=200,
    )
    stockpile.add_item("Wood", 12)
    stockpile.add_item("Furniture", 4)
    world.add_stockpile(stockpile)

    cottage = _residential_building(location=(2, 2), capacity=2)
    cottage.household_style = "hearthfire"
    cottage.amenities = ["Shared hearth"]
    world.add_building(cottage)

    resident = Character(
        name="June",
        personality="Cheerful",
        traits=[],
        skills={},
        needs=_standard_needs(),
    )
    world.add_character(resident)
    world.claim_residential_spot(resident)

    resident.mood_score = config.MOOD_SCORE_NEUTRAL_START
    initial_mood = resident.mood_score
    game_time.current_day = 1

    report: Dict[str, Any] = {}
    updates = world._maintain_household_comforts(report)

    hearth_events = [entry for entry in updates if entry.get("rule") == "hearth_fire"]
    assert hearth_events, "Expected hearth comfort routine to resolve."
    hearth_event = hearth_events[0]
    assert 0 < hearth_event["withdrawn"] <= hearth_event["required"]
    assert resident.mood_score > initial_mood
    assert cottage.comfort_score > 0
    assert report["household_comfort_summary"]["satisfied"] >= 1
    assert stockpile.inventory.get("Wood", 0) < 12
    assert any("warm hearth" in memory.lower() for memory in resident.memory)

    stockpile.inventory["Wood"] = 0
    previous_mood = resident.mood_score
    game_time.current_day += 1

    report_shortage: Dict[str, Any] = {}
    updates_shortage = world._maintain_household_comforts(report_shortage)
    hearth_follow_up = [entry for entry in updates_shortage if entry.get("rule") == "hearth_fire"]
    assert hearth_follow_up, "Expected hearth comfort routine to be evaluated again."
    outcome = hearth_follow_up[0]["outcome"]
    assert outcome in {"partial", "missed"}
    assert resident.mood_score <= previous_mood
    summary = report_shortage["household_comfort_summary"]
    assert summary["partial"] + summary["missed"] >= 1


@patch("random.choice", side_effect=lambda options: options[0])
def test_neighborhood_gathering_records_story(mock_choice):  # noqa: ARG001
    world, game_time = _make_world()
    game_time.current_day = 9

    names = ["Caro", "Devi", "Eamon"]
    baseline_moods = {}
    buildings: List[Building] = []

    for idx, name in enumerate(names):
        building = Building(
            structure_type="House",
            display_name=f"Lane Home {idx + 1}",
            location=(idx * 2, 3),
            size=(2, 2),
            required_resources={},
            functionality={"provides_shelter": 2, "tags": ["residential"], "wealth_tier": "modest"},
            required_skill={},
            tile_layout=[["WoodWall", "Bedroll"], ["Hearth", "Bed"]],
        )
        building.is_operational = True
        world.add_building(building)
        buildings.append(building)

        resident = Character(
            name=name,
            personality="Cheerful",
            traits=[],
            skills={},
            job=Job("Laborer", None, JOB_SALARIES.get("Laborer", 0)),
            needs=_standard_needs(),
        )
        resident.net_worth = 50 + (len(names) - idx) * 5
        world.add_character(resident)
        building.add_occupant(resident.name)
        resident.home_location = building.location
        baseline_moods[name] = resident.mood_score

    snapshot = world.get_housing_snapshot()
    report: Dict[str, Any] = {}
    baseline_spirit = world.community_spirit

    with patch.object(config, "NEIGHBORHOOD_GATHERING_BASE_CHANCE", 1.0), patch(
        "random.random", return_value=0.0
    ):
        gatherings = world._resolve_neighborhood_gatherings(snapshot, report)

    assert gatherings, "Expected a neighborhood gathering to be recorded."
    story = gatherings[0]
    assert story["host"] in {building.display_name for building in buildings}
    assert len(story["attendees"]) == len(names)
    assert snapshot["neighborhood_gatherings"], "Snapshot should include neighborhood gatherings"
    assert world._latest_neighborhood_gatherings, "World should track recent neighborhood gatherings"
    assert "neighborhood_gatherings" in report

    for name in names:
        character = world.get_character_by_name(name)
        assert character is not None
        assert character.mood_score >= baseline_moods[name]

    assert world.community_spirit >= baseline_spirit


def test_population_departure_under_hardship_and_low_mood():
    world, _ = _make_world()
    names = ["Hard Luck", "Ally", "Brooke", "Cedar"]
    for name in names:
        character = Character(
            name=name,
            personality="Stoic",
            traits=[],
            skills={},
            job=Job("Laborer", None, JOB_SALARIES.get("Laborer", 0)),
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


def test_estate_allocation_matches_wealth_tiers():
    world, _ = _make_world()

    comfortable = Character(
        name="Clara",
        personality="Pragmatic",
        traits=[],
        skills={},
        job=Job("Craftswoman", None, JOB_SALARIES.get("Craftswoman", 0)),
        needs=_standard_needs(),
    )
    comfortable.wealth_status = "comfortable"

    prosperous = Character(
        name="Merin",
        personality="Ambitious",
        traits=[],
        skills={},
        job=Job("Merchant", None, JOB_SALARIES.get("Merchant", 0)),
        needs=_standard_needs(),
    )
    prosperous.wealth_status = "prosperous"

    noble = Character(
        name="Lord Bren",
        personality="Stoic",
        traits=[],
        skills={},
        job=Job("Noble", None, JOB_SALARIES.get("Noble", 0)),
        needs=_standard_needs(),
        rank="Noble Lord",
    )
    noble.wealth_status = "prosperous"

    world.add_character(comfortable)
    world.add_character(prosperous)
    world.add_character(noble)

    report: Dict[str, Any] = {"food_deficit": 0, "water_deficit": 0}
    world._evaluate_housing_daily(report)

    assignments = report["housing"]["assignments"]
    assert assignments[comfortable.name].startswith("Stone Cottage")
    assert assignments[prosperous.name].startswith("Merchant Manor")
    assert assignments[noble.name].startswith("Noble Estate")

    tiers = {
        building.functionality.get("wealth_tier")
        for building in world.buildings
        if world._is_residential(building)
    }
    assert {"comfortable", "prosperous", "noble"}.issubset(tiers)


def test_cultural_snapshot_lists_upcoming_events():
    world, _ = _make_world()

    world.daily_environment_tick()

    snapshot = world.get_cultural_snapshot()
    assert 0.0 <= snapshot["community_spirit"] <= 1.0
    assert snapshot["upcoming_events"], "Expected cultural calendar to provide upcoming events"
    for event in snapshot["upcoming_events"]:
        assert "name" in event and "day" in event
        assert event["day"] >= world.game_time.current_day


def test_cultural_event_boosts_characters_and_spirit():
    world, _ = _make_world()
    celebrant = Character(
        name="Aela",
        personality="Cheerful",
        traits=["Empath"],
        skills={},
        needs={
            "Hunger": 70,
            "Thirst": 70,
            "Energy": 80,
            "Social": 60,
            "Belonging": 50,
            "Esteem": 45,
        }, job=Job("Unemployed", None, 0)
    )
    world.add_character(celebrant)

    world.daily_environment_tick()

    assert world.cultural_calendar, "Cultural calendar should populate after the first daily tick"
    first_event = world.cultural_calendar[0]

    pre_spirit = world.community_spirit
    pre_belonging = celebrant.needs["Belonging"]

    world.game_time.current_day = first_event["day"]
    world.daily_environment_tick()

    assert world.active_cultural_event is not None
    assert celebrant.needs["Belonging"] >= pre_belonging
    assert world.community_spirit > pre_spirit

    env_snapshot = world.get_environment_snapshot()
    assert env_snapshot["cultural_event"]
    assert env_snapshot["cultural_event"]["name"] == world.active_cultural_event["name"]

    end_day = first_event["day"] + max(1, int(first_event.get("duration", 1))) - 1
    for day in range(first_event["day"] + 1, end_day + 2):
        world.game_time.current_day = day
        world.daily_environment_tick()

    assert world.active_cultural_event is None
    assert not any(key for key in world.active_world_effects if str(key).startswith("cultural_event"))


def test_training_sessions_launch_and_award_experience():
    world, game_time = _make_world()

    instructor = Character(
        name="Maris Foreman",
        personality="Pragmatic",
        traits=["Diligent"],
        skills={"Construction": 4},
        job=Job("Master Craftsman", None, JOB_SALARIES.get("Master Craftsman", 0)),
        needs=_standard_needs(),
    )
    apprentice_one = Character(
        name="Toma Mason",
        personality="Studious",
        traits=["Curious"],
        skills={"Construction": 0},
        job=Job("Builder", None, JOB_SALARIES.get("Builder", 0)),
        needs=_standard_needs(),
    )
    apprentice_two = Character(
        name="Ren Brick",
        personality="Steadfast",
        traits=["Patient"],
        skills={"Construction": 0},
        job=Job("Builder", None, JOB_SALARIES.get("Builder", 0)),
        needs=_standard_needs(),
    )

    world.add_character(instructor)
    world.add_character(apprentice_one)
    world.add_character(apprentice_two)

    economy_payload: Dict[str, Dict[str, object]] = {}
    day_one_report = world.process_training_daily(economy_payload)

    assert economy_payload.get("training") == day_one_report
    assert len(world.active_training_sessions) == 1
    session = world.active_training_sessions[0]
    assert session["instructor"] == instructor.name
    assert set(session["trainees"]) == {apprentice_one.name, apprentice_two.name}

    apprentice_experience = apprentice_one.skills["Construction"]["experience"]
    assert apprentice_experience > 0
    expected_esteem = min(
        config.NEED_SCORE_MAX,
        config.NEED_ESTEEM_DEFAULT + config.TRAINING_ESTEEM_BOOST,
    )
    assert apprentice_one.needs["Esteem"] == expected_esteem

    game_time.current_tick = game_time.ticks_per_day - 1
    game_time.tick()

    followup_payload: Dict[str, Dict[str, object]] = {}
    day_two_report = world.process_training_daily(followup_payload)

    assert len(world.active_training_sessions) == 0
    assert day_two_report.get("concluded_sessions")
    conclusion = day_two_report["concluded_sessions"][0]
    assert conclusion["reason"] == "completed"
    assert any(outcome["name"] == apprentice_one.name for outcome in conclusion["outcomes"])
    assert apprentice_one.skills["Construction"]["experience"] >= apprentice_experience


def test_workforce_crews_deliver_resources_and_queue_backlog():
    world, _ = _make_world()

    stockpile = Stockpile("Central Stockpile", 0, 0, 2, 2, allowed_resources=None, capacity_per_resource=8)
    world.add_stockpile(stockpile)

    woodcutter = Character(
        name="Darin", 
        personality="Stoic",
        traits=[],
        skills={"Woodcutting": 2},
        job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)),
        needs=_standard_needs(),
    )
    hauler = Character(
        name="Mira",
        personality="Helpful",
        traits=[],
        skills={},
        job=Job("Builder", None, JOB_SALARIES.get("Builder", 0)),
        needs=_standard_needs(),
    )

    world.add_character(woodcutter)
    world.add_character(hauler)

    world.work_shift_definitions = {
        "logging": {
            "title": "Logging Crews",
            "jobs": ["Woodcutter"],
            "task": "Chop Wood",
            "resource": "Wood",
            "skill": "Woodcutting",
            "shift_ticks": 6,
            "carry_capacity_per_worker": 3,
            "hauler_jobs": ["Builder"],
            "hauler_capacity": 4,
            "skill_yield_bonus": 0.0,
            "preferred_stockpiles": ["Central Stockpile"],
        }
    }
    world.work_shift_backlog = {"logging": 0.0}

    daily_report: Dict[str, Any] = {}
    report_one = world.process_workforce_daily(daily_report)

    assert daily_report.get("workforce") == report_one
    assert report_one["gathered_total"] >= 1
    assert report_one["delivered_total"] == stockpile.inventory.get("Wood", 0)

    logging_entry = report_one["crews"][0]
    assert logging_entry["key"] == "logging"
    assert logging_entry["delivered"] == report_one["delivered_total"]
    assert logging_entry["backlog"] >= 0

    previous_backlog = logging_entry["backlog"]

    # Saturate the stockpile so new deliveries cannot be stored.
    current_wood = stockpile.inventory.get("Wood", 0)
    stockpile.capacity_per_resource = current_wood
    stockpile.total_capacity = current_wood

    world.game_time.current_day += 1

    follow_report = world.process_workforce_daily({})
    follow_entry = follow_report["crews"][0]

    assert follow_report["gathered_total"] >= report_one["gathered_total"]
    assert follow_entry["backlog"] >= previous_backlog
    assert follow_report["backlog_total"] >= follow_entry["backlog"]
    assert follow_report["delivered_total"] <= stockpile.capacity_per_resource


def test_manufacturing_crews_transform_inputs_into_outputs():
    world, _ = _make_world()

    stockpile = Stockpile(
        "Central Stockpile",
        0,
        0,
        2,
        2,
        allowed_resources=None,
        capacity_per_resource=50,
    )
    world.add_stockpile(stockpile)
    added = stockpile.add_item("Wood", 20)
    assert added == (True, 20)

    sawyer = Character(
        name="Rhea",
        personality="Focused",
        traits=[],
        skills={"Carpentry": 2},
        job=Job("Sawyer", None, JOB_SALARIES.get("Sawyer", 0)),
        needs=_standard_needs(),
    )
    carpenter = Character(
        name="Orrin",
        personality="Patient",
        traits=[],
        skills={"Carpentry": 3},
        job=Job("Carpenter", None, JOB_SALARIES.get("Carpenter", 0)),
        needs=_standard_needs(),
    )
    hauler = Character(
        name="Jess",
        personality="Helpful",
        traits=[],
        skills={},
        job=Job("Builder", None, JOB_SALARIES.get("Builder", 0)),
        needs=_standard_needs(),
    )

    for character in (sawyer, carpenter, hauler):
        world.add_character(character)

    world.work_shift_definitions = {
        "sawmill": {
            "title": "Sawmill Crew",
            "jobs": ["Sawyer"],
            "task": "Saw Lumber",
            "resource": "Lumber",
            "skill": "Carpentry",
            "shift_ticks": 6,
            "carry_capacity_per_worker": 4,
            "hauler_jobs": ["Builder"],
            "hauler_capacity": 6,
            "skill_yield_bonus": 0.1,
            "inputs": {"Wood": 2},
            "preferred_stockpiles": ["Central Stockpile"],
            "discrete_output": True,
        },
        "carpentry": {
            "title": "Carpenter's Shop",
            "jobs": ["Carpenter"],
            "task": "Assemble Furniture",
            "resource": "Furniture",
            "skill": "Carpentry",
            "shift_ticks": 6,
            "carry_capacity_per_worker": 3,
            "hauler_jobs": ["Builder"],
            "hauler_capacity": 6,
            "skill_yield_bonus": 0.12,
            "inputs": {"Lumber": 2},
            "preferred_stockpiles": ["Central Stockpile"],
            "discrete_output": True,
        },
    }
    world.work_shift_backlog = {"sawmill": 0.0, "carpentry": 0.0}

    daily_report: Dict[str, Any] = {}
    report = world.process_workforce_daily(daily_report)

    assert daily_report.get("workforce") == report
    assert report["alerts"] and any("Carpenter's Shop" in alert for alert in report["alerts"])

    sawmill_entry = next(entry for entry in report["crews"] if entry["key"] == "sawmill")
    carpentry_entry = next(entry for entry in report["crews"] if entry["key"] == "carpentry")

    assert sawmill_entry["delivered"] >= 1
    sawmill_inputs = sawmill_entry.get("inputs_consumed", {})
    assert sawmill_inputs.get("Wood", 0) == sawmill_entry["gathered"] * 2
    lumber_used = carpentry_entry.get("inputs_consumed", {}).get("Lumber", 0)
    if carpentry_entry["delivered"]:
        assert lumber_used == carpentry_entry["delivered"] * 2

    starting_wood = 20
    remaining_wood = stockpile.inventory.get("Wood", 0)
    assert remaining_wood == starting_wood - sawmill_inputs.get("Wood", 0)
    assert stockpile.inventory.get("Furniture", 0) == carpentry_entry["delivered"]


def test_manufacturing_crews_surface_shortages():
    world, _ = _make_world()

    stockpile = Stockpile(
        "Central Stockpile",
        0,
        0,
        2,
        2,
        allowed_resources=None,
        capacity_per_resource=10,
    )
    world.add_stockpile(stockpile)

    carpenter = Character(
        name="Lysa",
        personality="Stubborn",
        traits=[],
        skills={"Carpentry": 2},
        job=Job("Carpenter", None, JOB_SALARIES.get("Carpenter", 0)),
        needs=_standard_needs(),
    )
    world.add_character(carpenter)

    world.work_shift_definitions = {
        "carpentry": {
            "title": "Carpenter's Shop",
            "jobs": ["Carpenter"],
            "task": "Assemble Furniture",
            "resource": "Furniture",
            "skill": "Carpentry",
            "shift_ticks": 6,
            "carry_capacity_per_worker": 3,
            "hauler_jobs": ["Builder"],
            "hauler_capacity": 6,
            "skill_yield_bonus": 0.12,
            "inputs": {"Lumber": 2},
            "preferred_stockpiles": ["Central Stockpile"],
            "discrete_output": True,
        }
    }
    world.work_shift_backlog = {"carpentry": 0.0}

    report = world.process_workforce_daily({})

    carpentry_entry = report["crews"][0]

    assert carpentry_entry["gathered"] == 0
    assert "notes" in carpentry_entry and any("Awaiting inputs" in note for note in carpentry_entry["notes"])
    assert report["alerts"] and any("Lumber" in alert for alert in report["alerts"])
    assert "inputs_consumed" not in carpentry_entry or not carpentry_entry["inputs_consumed"]


def test_business_industry_consumes_inputs_and_reports():
    world, _ = _make_world()

    stockpile = Stockpile(
        "Central",
        0,
        0,
        2,
        2,
        allowed_resources=None,
    )
    world.add_stockpile(stockpile)
    stockpile.add_item("Wood", 12)

    owner = Character(
        name="Mae",
        personality="Driven",
        traits=[],
        skills={"Woodcutting": 2, "Carpentry": 3},
        job=Job("Sawyer", None, JOB_SALARIES.get("Sawyer", 0)),
        needs=_standard_needs(),
    )
    owner.money = 100
    world.add_character(owner)

    template = {
        "key": "test_lumber",
        "display_name": "Test Lumberyard",
        "industry": "lumberworks",
        "startup_cost": 0,
        "base_capital": 10,
        "revenue_range": (0, 0),
    }
    business = world.launch_business(owner, template=template)
    assert business is not None

    report: Dict[str, Any] = {}
    events = world._update_businesses(report)
    assert events
    event = next(evt for evt in events if evt["id"] == business["id"])
    industry_report = event.get("industry_report")
    assert industry_report
    assert industry_report.get("cycles", 0) >= 1
    assert industry_report.get("inputs_consumed", {}).get("Wood", 0) > 0
    assert industry_report.get("outputs_created", {}).get("Lumber", 0) >= 1
    assert stockpile.inventory.get("Wood", 0) < 12
    assert not report.get("business_supply_alerts")


def test_business_industry_shortage_creates_alert():
    world, _ = _make_world()

    owner = Character(
        name="Darin",
        personality="Steady",
        traits=[],
        skills={"Woodcutting": 1},
        job=Job("Sawyer", None, JOB_SALARIES.get("Sawyer", 0)),
        needs=_standard_needs(),
    )
    owner.money = 50
    world.add_character(owner)

    template = {
        "key": "test_lumber",
        "display_name": "Test Lumberyard",
        "industry": "lumberworks",
        "startup_cost": 0,
        "base_capital": 5,
        "revenue_range": (0, 0),
    }
    business = world.launch_business(owner, template=template)
    assert business is not None

    report: Dict[str, Any] = {}
    events = world._update_businesses(report)
    assert events
    event = next(evt for evt in events if evt["id"] == business["id"])
    industry_report = event.get("industry_report")
    assert industry_report
    assert industry_report.get("cycles", 0) == 0
    alerts = report.get("business_supply_alerts")
    assert alerts
    alert = next(alert for alert in alerts if alert["id"] == business["id"])
    assert alert["shortages"].get("Wood", 0) > 0
    assert any("Awaiting" in note for note in industry_report.get("notes", []))


def test_family_arrival_event_and_profile():
    world, _ = _make_world()
    alice = Character(
        name="Alice",
        personality="Brave",
        traits=[],
        skills={},
        family_members=["Bryn"], job=Job("Unemployed", None, 0)
    )
    bryn = Character(
        name="Bryn",
        personality="Calm",
        traits=[],
        skills={},
        family_members=["Alice"], job=Job("Unemployed", None, 0)
    )

    world.add_character(alice)
    world.add_character(bryn)

    profile = world.get_family_profile_for_character("Alice")
    assert profile
    assert sorted(profile["members"]) == ["Alice", "Bryn"]

    arrival_event = next((evt for evt in alice.life_history if evt.get("type") == "arrival"), None)
    assert arrival_event is not None
    assert arrival_event.get("significance", 0) >= 3

    echoed = next((evt for evt in bryn.life_history if evt.get("is_family_echo")), None)
    assert echoed is not None
    assert "Alice" in echoed.get("summary", "")


def test_record_birth_creates_family_links_and_events():
    world, _ = _make_world()

    parent = Character(
        name="Elena",
        personality="Caring",
        traits=["Compassionate"],
        skills={}, job=Job("Unemployed", None, 0)
    )
    partner = Character(
        name="Garrin",
        personality="Steadfast",
        traits=["Diligent"],
        skills={}, job=Job("Unemployed", None, 0)
    )

    world.add_character(parent)
    world.add_character(partner)

    assert world.register_union("Elena", "Garrin", ceremony_name="Harvest vows") is True

    child = world.record_birth("Elena", other_parent="Garrin")
    assert child is not None

    assert child.name in parent.family_members
    assert child.name in partner.family_members
    assert parent.name in child.family_members

    parent_event = next((evt for evt in parent.life_history if evt.get("type") == "welcomed_child"), None)
    assert parent_event is not None
    assert child.name in parent_event.get("summary", "")

    child_event = next((evt for evt in child.life_history if evt.get("type") == "birth"), None)
    assert child_event is not None
    assert "Elena" in child_event.get("summary", "")

    profile = world.get_family_profile_for_character("Elena")
    assert child.name in profile["lineage"].get("Elena", {}).get("children", [])
    child_profile = world.get_family_profile_for_character(child.name)
    assert "Elena" in child_profile["lineage"].get(child.name, {}).get("parents", [])


def test_medical_events_populate_life_history():
    world, _ = _make_world()
    patient = Character(
        name="Mae",
        personality="Patient",
        traits=[],
        skills={},
        family_members=["Nox"], job=Job("Unemployed", None, 0)
    )
    kin = Character(
        name="Nox",
        personality="Guarded",
        traits=[],
        skills={},
        family_members=["Mae"], job=Job("Unemployed", None, 0)
    )

    world.add_character(patient)
    world.add_character(kin)

    case, created = world.register_medical_case("Mae", "injury", 4.5, reporter="Nox", cause="Logging accident")
    assert created is True
    case_id = case["case_id"]

    open_event = next(
        evt
        for evt in patient.life_history
        if evt.get("type") == "medical_case_opened" and evt.get("details", {}).get("case_id") == case_id
    )
    assert "injury" in open_event.get("summary", "")

    kin_echo = next((evt for evt in kin.life_history if evt.get("is_family_echo") and "injury" in evt.get("summary", "")), None)
    assert kin_echo is not None

    world.resolve_medical_case(case_id, "recovered", notes="Nox stitched the wound.")

    outcome_event = next(
        evt
        for evt in patient.life_history
        if evt.get("type") == "medical_case_resolved" and evt.get("details", {}).get("case_id") == case_id
    )
    assert outcome_event.get("details", {}).get("outcome") == "recovered"


def test_register_union_logs_history_and_lineage():
    world, _ = _make_world()

    rowan = Character(name="Rowan", personality="Curious", traits=[], skills={}, job=Job("Unemployed", None, 0))
    sera = Character(name="Sera", personality="Cheerful", traits=[], skills={}, job=Job("Unemployed", None, 0))
    witness = Character(name="Bryn", personality="Calm", traits=[], skills={}, job=Job("Unemployed", None, 0))

    world.add_character(rowan)
    world.add_character(sera)
    world.add_character(witness)

    assert world.register_union("Rowan", "Sera", ceremony_name="Moonlit vows", witnesses=["Bryn"]) is True

    marriage_event = next((evt for evt in rowan.life_history if evt.get("type") == "marriage"), None)
    assert marriage_event is not None
    assert "Sera" in marriage_event.get("summary", "")

    witness_event = next((evt for evt in witness.life_history if evt.get("type") == "witnessed_union"), None)
    assert witness_event is not None
    assert "Rowan" in witness_event.get("summary", "")

    profile = world.get_family_profile_for_character("Rowan")
    assert profile["lineage"].get("Rowan", {}).get("partners") == ["Sera"]


def test_relationship_tier_change_creates_life_event():
    world, _ = _make_world()
    iris = Character(name="Iris", personality="Bold", traits=[], skills={}, job=Job("Unemployed", None, 0))
    oren = Character(name="Oren", personality="Calm", traits=[], skills={}, job=Job("Unemployed", None, 0))

    world.add_character(iris)
    world.add_character(oren)

    iris.modify_relationship("Oren", 50, world, reason="Worked side by side")

    tier_event = next((evt for evt in iris.life_history if evt.get("type") == "relationship_tier_change"), None)
    assert tier_event is not None
    assert "Oren" in tier_event.get("summary", "")
    assert tier_event.get("details", {}).get("new_tier") in {"Friend", "Friendly Acquaintance", "Close Friend", "Soulmate"}


def test_fatal_medical_case_creates_bereavement_events():
    world, _ = _make_world()

    patient = Character(name="Calla", personality="Stoic", traits=[], skills={}, family_members=["Ivor"], job=Job("Unemployed", None, 0))
    kin = Character(name="Ivor", personality="Loyal", traits=[], skills={}, family_members=["Calla"], job=Job("Unemployed", None, 0))
    medic = Character(name="Mae", personality="Patient", traits=[], skills={}, job=Job("Unemployed", None, 0))

    world.add_character(patient)
    world.add_character(kin)
    world.add_character(medic)

    case, created = world.register_medical_case("Calla", "illness", 5.0, reporter="Ivor")
    assert created is True

    world.record_medical_treatment(case["case_id"], "Mae", severity_after=5.0, success=False)
    world.resolve_medical_case(case["case_id"], "deceased", notes="Condition worsened overnight.")

    kin_event = next((evt for evt in kin.life_history if evt.get("type") == "family_loss"), None)
    assert kin_event is not None
    assert "Calla" in kin_event.get("summary", "")

    medic_event = next((evt for evt in medic.life_history if evt.get("type") == "witnessed_tragedy"), None)
    assert medic_event is not None
    assert "Calla" in medic_event.get("summary", "")


def test_governance_generates_petitions_from_crime_history():
    world, game_time = _make_world()
    game_time.current_day = 6

    for day in range(3):
        incident = {
            "id": f"crime_{day}",
            "type": "theft",
            "reported_day": game_time.current_day - day - 1,
            "resolved_day": game_time.current_day - day - 1,
            "status": "resolved",
        }
        world._record_crime_history(incident)

    world.process_governance_daily()

    petitions = [p for p in world.law_petitions if p.get("issue_type") == "theft"]
    assert petitions
    assert petitions[0]["incident_count"] >= 3


def test_enacted_law_applies_to_case_and_queues_interviews():
    world, _ = _make_world()

    mayor = Character(name="Elena", personality="Resolute", traits=[], skills={"Leadership": 6}, job=Job("Mayor", None, JOB_SALARIES.get("Mayor", 0)))
    sheriff = Character(name="Rogan", personality="Stoic", traits=[], skills={"Security": 5}, job=Job("Sheriff", None, JOB_SALARIES.get("Sheriff", 0)))
    suspect = Character(name="Vail", personality="Impulsive", traits=[], skills={}, job=Job("Laborer", None, JOB_SALARIES.get("Laborer", 0)))
    witness = Character(name="Mira", personality="Calm", traits=[], skills={}, job=Job("Farmer", None, JOB_SALARIES.get("Farmer", 0)))
    mayor = Character(name="Elena", personality="Resolute", traits=[], skills={"Leadership": 6}, job=Job("Mayor", None, JOB_SALARIES.get("Mayor", 0)))
    sheriff = Character(name="Rogan", personality="Stoic", traits=[], skills={"Security": 5}, job=Job("Sheriff", None, JOB_SALARIES.get("Sheriff", 0)))
    suspect = Character(name="Vail", personality="Impulsive", traits=[], skills={}, job=Job("Laborer", None, JOB_SALARIES.get("Laborer", 0)))
    witness = Character(name="Mira", personality="Calm", traits=[], skills={}, job=Job("Farmer", None, JOB_SALARIES.get("Farmer", 0)))

    for char in (mayor, sheriff, suspect, witness):
        world.add_character(char)

    petition = world.register_law_petition("theft", "Merchants seek tighter safeguards", "Guild", incident_count=4, severity=3)
    law = world.draft_law_from_petition(petition["id"], mayor.name)
    assert law is not None
    enacted = world.enact_law(law["id"], mayor.name)
    assert enacted is not None

    crime = {
        "id": "crime_test",
        "type": "theft",
        "suspect": suspect.name,
        "description": "Caught removing goods from stockpile",
    }

    case = world.schedule_trial_for_crime(crime, sheriff.name, 0.4)
    assert case is not None
    assert case["law_id"] == law["id"]
    assert case["requires_interviews"] is True
    assert case["interview_plan"]
    assert world.pending_interviews


def test_interview_result_boosts_case_evidence():
    world, _ = _make_world()

    mayor = Character(name="Elena", personality="Resolute", traits=[], skills={"Leadership": 6}, job="Mayor")
    sheriff = Character(name="Rogan", personality="Stoic", traits=[], skills={"Security": 5}, job="Sheriff")
    suspect = Character(name="Vail", personality="Impulsive", traits=[], skills={}, job="Laborer")
    witness = Character(name="Mira", personality="Calm", traits=[], skills={}, job="Farmer")

    for char in (mayor, sheriff, suspect, witness):
        world.add_character(char)

    petition = world.register_law_petition("theft", "Merchants seek tighter safeguards", "Guild", incident_count=4, severity=3)
    law = world.draft_law_from_petition(petition["id"], mayor.name)
    world.enact_law(law["id"], mayor.name)

    crime = {
        "id": "crime_case",
        "type": "theft",
        "suspect": suspect.name,
        "description": "Lifted tools from workshop",
    }

    case = world.schedule_trial_for_crime(crime, sheriff.name, 0.3)
    base_strength = case["evidence_strength"]

    assignment = world.assign_investigative_interview(sheriff.name)
    assert assignment is not None

    world.record_interview_result(assignment["id"], sheriff.name, 0.8, "Witness corroborated the theft.")
    updated = world.get_case_by_id(case["case_id"])

    assert updated["evidence_strength"] > base_strength
    assert updated["interview_statements"]


def test_dissolve_union_tracks_ex_partners():
    world, _ = _make_world()
    alice = Character(
        name="Alice",
        personality="Romantic",
        traits=["Affectionate"],
        skills={},
        job=Job("Tailor", None, JOB_SALARIES.get("Tailor", 0)),
        needs=_standard_needs(),
    )
    borin = Character(
        name="Borin",
        personality="Stoic",
        traits=["Loyal"],
        skills={},
        job=Job("Smith", None, JOB_SALARIES.get("Smith", 0)),
        needs=_standard_needs(),
    )
    world.add_character(alice)
    world.add_character(borin)

    assert world.register_union(alice.name, borin.name)
    assert borin.name in alice.romantic_partners
    assert alice.name in borin.romantic_partners

    world.dissolve_union(alice.name, borin.name, reason="irreconcilable", divorce=True)

    assert borin.name not in alice.get_romantic_partners()
    assert alice.name not in borin.get_romantic_partners()
    assert borin.name in alice.ex_partners
    assert alice.name in borin.ex_partners
    assert not alice.family_roles.get("partners")
    assert not borin.family_roles.get("partners")


def test_process_family_dynamics_starts_romance():
    world, _ = _make_world()
    aisling = Character(
        name="Aisling",
        personality="Romantic",
        traits=["Charming"],
        skills={},
        job=Job("Baker", None, JOB_SALARIES.get("Baker", 0)),
        needs=_standard_needs(),
    )
    borin = Character(
        name="Borin",
        personality="Dreamer",
        traits=["Loyal"],
        skills={},
        job=Job("Farmer", None, JOB_SALARIES.get("Farmer", 0)),
        needs=_standard_needs(),
    )
    world.add_character(aisling)
    world.add_character(borin)

    aisling.relationships[borin.name] = 80
    borin.relationships[aisling.name] = 78

    with patch("random.random", return_value=0.0):
        family_events = world.process_family_dynamics_daily()

    assert any(event.get("type") == "romance_started" for event in family_events)
    assert borin.name in aisling.active_romances
    assert aisling.name in borin.active_romances


def test_world_daily_report_includes_personal_pursuits():
    world, _ = _make_world()
    resident = Character(
        name="Caro",
        personality="Curious",
        traits=["Resourceful"],
        skills={},
        needs=_standard_needs(), job=Job("Unemployed", None, 0)
    )
    world.add_character(resident)

    assert resident.personal_pursuits

    pursuit = resident.personal_pursuits[0]
    threshold = getattr(config, "PERSONAL_PURSUIT_LIFE_EVENT_PROGRESS", 1.0)
    pursuit["progress"] = threshold - 0.05
    pursuit["progress_per_day"] = threshold
    pursuit["affinity"] = 2.0

    world.process_daily_economy()

    report = world.last_daily_economic_report
    assert "personal_pursuits" in report
    assert world.latest_personal_pursuit_events
    assert any(event.get("type") == "pursuit_engaged" for event in report["personal_pursuits"])


def test_military_process_builds_chain_and_readiness():
    world, game_time = _make_world()
    game_time.current_day = 4

    commander = Character(
        name="Darin",
        personality="Resolute",
        traits=[],
        skills={"Leadership": 5, "Security": 3},
        job=Job("Militia Commander", None, JOB_SALARIES.get("Militia Commander", 0)),
    )
    captain = Character(
        name="Lysa",
        personality="Calm",
        traits=[],
        skills={"Leadership": 4, "Security": 4},
        job=Job("Militia Captain", None, JOB_SALARIES.get("Militia Captain", 0)),
    )
    soldier = Character(
        name="Holt",
        personality="Stoic",
        traits=[],
        skills={"Security": 3},
        job=Job("Militia Soldier", None, JOB_SALARIES.get("Militia Soldier", 0)),
    )
    scout = Character(
        name="Risa",
        personality="Bold",
        traits=[],
        skills={"Security": 2},
        job=Job("Scout", None, JOB_SALARIES.get("Scout", 0)),
    )

    for character in (commander, captain, soldier, scout):
        world.add_character(character)

    commander.leadership_oversight_score = 0.6
    captain.leadership_oversight_score = 0.52

    world.process_military_daily()
    snapshot = world.get_military_snapshot()

    assert snapshot["commander"]["name"] == commander.name
    captain_names = [entry["name"] for entry in snapshot["captains"]]
    assert captain.name in captain_names
    assert snapshot["squads"], "Expected at least one squad to be formed"
    assert snapshot["readiness"] > 0
    assert any(squad["size"] >= 1 for squad in snapshot["squads"])


def test_enemy_raid_logs_activity_when_forced(monkeypatch):
    world, game_time = _make_world()
    game_time.current_day = 7

    commander = Character(
        name="Serra",
        personality="Resolute",
        traits=[],
        skills={"Leadership": 3, "Security": 2},
        job=Job("Militia Commander", None, JOB_SALARIES.get("Militia Commander", 0)),
    )
    captain = Character(
        name="Bryn",
        personality="Stoic",
        traits=[],
        skills={"Leadership": 2, "Security": 3},
        job=Job("Militia Captain", None, JOB_SALARIES.get("Militia Captain", 0)),
    )
    soldier = Character(
        name="Olan",
        personality="Steady",
        traits=[],
        skills={"Security": 3},
        job=Job("Militia Soldier", None, JOB_SALARIES.get("Militia Soldier", 0)),
    )

    for character in (commander, captain, soldier):
        world.add_character(character)

    forced_profile = deepcopy(config.ENEMY_RAID_PROFILE)
    forced_profile["base_chance"] = 1.0
    forced_profile["readiness_factor"] = 0.0
    forced_profile["severity_weights"] = {"raid": 1.0}
    forced_profile["losses"] = {"raid": (1, 1)}
    monkeypatch.setattr(config, "ENEMY_RAID_PROFILE", forced_profile, raising=False)

    world.process_military_daily()
    snapshot = world.get_military_snapshot()

    assert snapshot["enemy_activity"], "Enemy activity should be recorded when raids are forced"
    entry = snapshot["enemy_activity"][0]
    assert entry["severity"] == "raid"
