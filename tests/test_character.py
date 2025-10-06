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
