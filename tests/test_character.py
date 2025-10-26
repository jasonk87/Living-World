from collections import deque
from unittest.mock import patch

from game import config
from game.character import Character
from game.goal import Goal, GoalType, create_goal_from_job
from game.building import Building
from game.time import Time
from game.world import World


def _make_world_with_time() -> tuple[World, Time]:
    game_time = Time(ticks_per_day=config.TICKS_PER_DAY)
    world = World(game_time_ref=game_time)
    return world, game_time


def _basic_needs() -> dict[str, int]:
    return {
        "Hunger": 80,
        "Thirst": 80,
        "Energy": 95,
        "Social": 70,
        "Safety": config.NEED_SAFETY_DEFAULT,
        "Belonging": config.NEED_BELONGING_DEFAULT,
        "Esteem": config.NEED_ESTEEM_DEFAULT,
    }


@patch("random.random", return_value=0.99)
def test_character_shifts_to_job_goal_during_work_phase(mock_random):  # noqa: ARG001
    world, game_time = _make_world_with_time()
    worker = Character(
        name="Avery",
        personality="Calm",
        traits=[],
        skills={},
        job="Farmer",
        needs=_basic_needs(),
        current_goal_obj=Goal(GoalType.IDLE, assignee_id="Avery", originator_id="Test"),
    )
    world.add_character(worker)

    phase_info = config.DAY_PHASE_CONFIG[1]
    with patch.object(worker, "get_default_goal", return_value=create_goal_from_job(worker.job, worker.name)):
        worker._apply_phase_behavior(world, phase_info)

    assert worker.current_goal.type == GoalType.PERFORM_FARMER_DUTIES


@patch("random.random", return_value=0.99)
def test_character_prioritizes_meal_during_supper(mock_random):  # noqa: ARG001
    world, _ = _make_world_with_time()
    diner = Character(
        name="Bryn",
        personality="Cheerful",
        traits=[],
        skills={},
        job="Unemployed",
        needs=_basic_needs(),
        current_goal_obj=Goal(GoalType.WANDER, assignee_id="Bryn", originator_id="Test", priority=6),
    )
    diner.inventory["Food"] = 1
    world.add_character(diner)

    phase_info = config.DAY_PHASE_CONFIG[2]
    diner._apply_phase_behavior(world, phase_info)

    assert diner.current_goal.type == GoalType.EAT_FOOD


@patch("random.random", return_value=0.99)
def test_character_forced_to_rest_during_night(mock_random):  # noqa: ARG001
    world, _ = _make_world_with_time()
    cottage = Building(
        structure_type="House",
        display_name="Hearthstead",
        location=(1, 1),
        size=(1, 1),
        required_resources={},
        functionality={"provides_shelter": 2, "tags": ["residential"]},
        required_skill={},
    )
    cottage.is_operational = True
    world.add_building(cottage)

    worker = Character(
        name="Caro",
        personality="Calm",
        traits=[],
        skills={},
        job="Farmer",
        needs=_basic_needs(),
        current_goal_obj=Goal(GoalType.PERFORM_FARMER_DUTIES, assignee_id="Caro", originator_id="Test", priority=4),
    )
    worker.x = worker.y = 1
    world.add_character(worker)
    phase_info = config.DAY_PHASE_CONFIG[-1]
    with patch.object(worker, "_ensure_home_assignment", return_value=cottage):
        worker._apply_phase_behavior(world, phase_info)

    assert worker.current_goal.type == GoalType.REST_AT_HOME
    assert worker.current_goal.parameters.get("building_location") == cottage.location


def test_decision_profile_blends_memory_relationships():
    world, _ = _make_world_with_time()
    thinker = Character(
        name="Mira",
        personality="Cautious",
        traits=["Generous", "Empathetic"],
        skills={},
        job="Builder",
        needs=_basic_needs(),
    )
    thinker.job_satisfaction = 0.8
    thinker.relationships["Ally"] = 80
    thinker.relationships["Rival"] = -50
    thinker.memory.extend([
        "Completed a major workshop project today.",
        "Earned a fair wage from the guild.",
        "Offered comfort to a grieving neighbour.",
        "Still feeling unsafe after the last storm.",
    ])

    profile = thinker._build_decision_profile(world)

    assert profile["work_focus"] > 1.0
    assert profile["social_focus"] > 1.0
    assert profile["risk_modifier"] < 1.0
    assert profile["ask_for_help_multiplier"] > 1.0
    assert profile["rest_threshold_adjustment"] > 0
    assert profile["relationship_summary"] == {"positive": 1, "negative": 1}
    assert profile["memory_summary"].get("entries_considered") == len(thinker.memory)


@patch("random.random", return_value=0.99)
def test_decision_profile_adjusts_rest_threshold(mock_random):  # noqa: ARG001
    world, _ = _make_world_with_time()
    cottage = Building(
        structure_type="House",
        display_name="Evenfall",
        location=(2, 2),
        size=(1, 1),
        required_resources={},
        functionality={"provides_shelter": 2, "tags": ["residential"]},
        required_skill={},
    )
    cottage.is_operational = True
    world.add_building(cottage)

    sleeper_needs = _basic_needs()
    sleeper_needs["Energy"] = 45
    reflective = Character(
        name="Dara",
        personality="Cautious",
        traits=["Lazy"],
        skills={},
        job="Farmer",
        needs=sleeper_needs,
        current_goal_obj=Goal(GoalType.WANDER, assignee_id="Dara", originator_id="Test"),
    )
    reflective.job_satisfaction = 0.2
    reflective.memory.extend([
        "Injured in an accident while working the fields.",
        "Feeling unsafe walking home after dusk.",
    ])
    world.add_character(reflective)

    with patch.object(reflective, "_ensure_home_assignment", return_value=cottage):
        reflective.decide_action(world)

    assert reflective.current_goal.type == GoalType.REST_AT_HOME
    assert reflective.current_goal.parameters.get("building_location") == cottage.location


def test_character_initializes_personal_pursuits():
    character = Character(
        name="Iris",
        personality="Gregarious",
        traits=["Generous"],
        skills={},
        needs=_basic_needs(),
    )

    assert character.personal_pursuits
    assert 0 < len(character.personal_pursuits) <= config.PERSONAL_PURSUIT_SLOTS
    for pursuit in character.personal_pursuits:
        assert "key" in pursuit
        assert "progress" in pursuit
        assert pursuit.get("level", 0) == 0


def test_health_profile_initializes_with_defaults():
    citizen = Character(
        name="Lyra",
        personality="Calm",
        traits=[],
        skills={},
        needs=_basic_needs(),
    )

    snapshot = citizen.get_health_snapshot()
    assert "vitality" in snapshot
    assert "immune_resilience" in snapshot
    assert "stress" in snapshot
    assert isinstance(snapshot.get("recent_events"), list)
    assert isinstance(citizen.health_profile.get("recent_events"), deque)


def test_daily_health_evaluation_flags_new_sickness():
    world, _ = _make_world_with_time()
    patient_needs = _basic_needs()
    patient_needs.update({"Hunger": 30, "Thirst": 35, "Energy": 40, "Safety": 40})
    patient = Character(
        name="Milo",
        personality="Stoic",
        traits=[],
        skills={},
        needs=patient_needs,
    )
    world.add_character(patient)
    patient.health_profile["vitality"] = 50.0
    patient.health_profile["immune_resilience"] = 0.25

    with patch("random.random", side_effect=[0.0, 1.0]), patch("random.uniform", return_value=3.2):
        events = patient.evaluate_daily_health(world)

    assert patient.is_sick
    assert any(evt.get("type") == "fell_ill" for evt in events)
    assert any(evt.get("type") == "fell_ill" for evt in patient.health_profile["recent_events"])


def test_record_health_event_tracks_life_event_logging():
    world, _ = _make_world_with_time()
    patient = Character(
        name="Sal", personality="Stoic", traits=[], skills={}, needs=_basic_needs()
    )

    result = patient.record_health_event(
        world,
        "fell_ill",
        "Sal was struck by a sudden fever.",
        severity=3.5,
        tags=["fever"],
    )

    assert result["life_event_logged"] is True
    history_entry = patient.health_profile["condition_history"][-1]
    assert history_entry.get("life_event_logged") is True
    assert "life_event_error" not in result


def test_record_health_event_notes_failure_and_logs():
    world, _ = _make_world_with_time()
    patient = Character(
        name="Reva", personality="Calm", traits=[], skills={}, needs=_basic_needs()
    )

    with patch.object(patient, "record_life_event", side_effect=RuntimeError("Ledger locked")):
        result = patient.record_health_event(
            world,
            "injured",
            "Reva slipped in the workshop.",
            severity=2.1,
        )

    assert result["life_event_logged"] is False
    assert "life_event_error" in result
    assert any("Failed to log health life event" in msg for msg in world.event_log)
    history_entry = patient.health_profile["condition_history"][-1]
    assert history_entry.get("life_event_logged") is False


def test_daily_health_evaluation_recovers_patient():
    world, _ = _make_world_with_time()
    patient = Character(
        name="Nora",
        personality="Cheerful",
        traits=[],
        skills={},
        needs=_basic_needs(),
    )
    world.add_character(patient)
    patient.is_sick = True
    patient.sickness_severity = 1.0
    patient.health_profile["vitality"] = 88.0
    patient.health_profile["immune_resilience"] = 0.82

    with patch("random.random", side_effect=[1.0, 1.0]):
        events = patient.evaluate_daily_health(world)

    assert not patient.is_sick
    assert patient.sickness_severity == 0
    assert any(evt.get("type") == "recovered" for evt in events)


def test_personal_pursuits_progress_and_log_entries():
    world, game_time = _make_world_with_time()
    citizen = Character(
        name="Elio",
        personality="Ambitious",
        traits=["Organized"],
        skills={},
        needs=_basic_needs(),
    )
    world.add_character(citizen)
    assert citizen.personal_pursuits

    pursuit = citizen.personal_pursuits[0]
    progress_threshold = getattr(config, "PERSONAL_PURSUIT_LIFE_EVENT_PROGRESS", 1.0)
    pursuit["progress"] = progress_threshold - 0.1
    pursuit["progress_per_day"] = progress_threshold
    pursuit["affinity"] = 2.0
    pursuit["need_focus"] = "Esteem"
    citizen.needs["Esteem"] = max(config.NEED_SCORE_MIN, config.NEED_ESTEEM_DEFAULT - 20)

    events = citizen.evaluate_personal_pursuits_daily(world)

    assert events
    assert any(event.get("type") == "pursuit_engaged" for event in events)
    assert citizen.personal_pursuit_log
    assert pursuit.get("last_day") == game_time.current_day
    assert citizen.needs["Esteem"] >= config.NEED_ESTEEM_DEFAULT - 20
    assert citizen.active_personal_project == pursuit["key"]

    milestone_events = [event for event in events if event.get("type") == "pursuit_milestone"]
    assert milestone_events
    assert pursuit.get("level", 0) >= 1
    assert any(evt.get("type") == "pursuit_milestone" for evt in citizen.life_history)
