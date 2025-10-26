# tests/test_ambition.py

import pytest
from game.character import Character
from game.ambition import Ambition, AmbitionType
from game.goal import Goal, GoalType
from game.world import World
from game.data import AMBITIONS
from .test_world import _make_world, _standard_needs
from game.job import Job


def test_ambition_selection():
    """Tests that a character selects an ambition."""
    char = Character(
        name="Test Character",
        personality="Ambitious",
        traits=["Ambitious", "Gregarious"],
        skills={"Leadership": 2, "Construction": 5, "Crafting": 5},
        money=200,
        age=35,
        job=Job("Unemployed", None, 0),
        needs=_standard_needs(),
    )
    char.reputation_score = 60
    world, game_time = _make_world()
    world.characters.append(char)
    char._evaluate_ambition(world)
    assert char.ambition is not None
    assert char.ambition.type.name in AMBITIONS

def test_become_master_artisan_ambition():
    """Tests the BECOME_MASTER_ARTISAN ambition."""
    char = Character(
        name="Artisan Character",
        personality="Creative",
        traits=["Focused", "Patient"],
        skills={"Crafting": 5},
        job=Job("Crafter", None, 0),
        needs=_standard_needs(),
    )
    ambition_data = AMBITIONS["BECOME_MASTER_ARTISAN"]
    char.ambition = Ambition(AmbitionType.BECOME_MASTER_ARTISAN, ambition_data)
    world, game_time = _make_world()
    world.characters.append(char)

    assert char.current_goal.priority >= 6

    char.decide_action(world)

    assert char.current_goal.type in [GoalType.IMPROVE_SKILL, GoalType.EXECUTE_CRAFT_ORDER, GoalType.IDLE]
    assert char.current_goal.priority >= 6

def test_accumulate_wealth_ambition():
    """Tests the ACCUMULATE_WEALTH ambition."""
    char = Character(
        name="Wealthy Character",
        personality="Greedy",
        traits=["Ambitious"],
        skills={},
        money=100,
        job=Job("Unemployed", None, 0),
        needs=_standard_needs(),
    )
    ambition_data = AMBITIONS["ACCUMULATE_WEALTH"]
    char.ambition = Ambition(AmbitionType.ACCUMULATE_WEALTH, ambition_data)
    world, game_time = _make_world()
    world.characters.append(char)

    assert char.current_goal.priority >= 6

    char.decide_action(world)

    assert char.current_goal.type in [GoalType.EARN_MONEY, GoalType.EXECUTE_CRAFT_ORDER, GoalType.GATHER_RESOURCE, GoalType.IDLE]
    assert char.current_goal.priority >= 6

def test_become_town_leader_ambition():
    """Tests the BECOME_TOWN_LEADER ambition."""
    char = Character(
        name="Leader Character",
        personality="Ambitious",
        traits=["Leader", "Ambitious", "Gregarious"],
        skills={"Leadership": 2},
        age=35,
        job=Job("Unemployed", None, 0),
        needs=_standard_needs(),
    )
    char.reputation_score = 60
    world, game_time = _make_world()
    world.characters.append(char)

    ambition_data = AMBITIONS["BECOME_TOWN_LEADER"]
    char.ambition = Ambition(AmbitionType.BECOME_TOWN_LEADER, ambition_data)

    assert char.current_goal.priority >= 6

    char.decide_action(world)

    assert char.current_goal.type in [GoalType.INCREASE_REPUTATION, GoalType.GIVE_SPEECH, GoalType.CAMPAIGN_SPEECH, GoalType.IDLE]
    assert char.current_goal.priority >= 6

def test_build_a_house_ambition():
    """Tests the BUILD_A_HOUSE ambition."""
    char = Character(
        name="Builder Character",
        personality="Practical",
        traits=["Hardworking"],
        skills={"Construction": 5},
        money=200,
        job=Job("Builder", None, 0),
        needs=_standard_needs(),
    )
    world, game_time = _make_world()
    world.characters.append(char)

    ambition_data = AMBITIONS["BUILD_A_HOUSE"]
    char.ambition = Ambition(AmbitionType.BUILD_A_HOUSE, ambition_data)

    assert char.current_goal.priority >= 6

    char.decide_action(world)

    assert char.current_goal.type in [GoalType.GATHER_RESOURCE, GoalType.EXECUTE_BUILD_ORDER, GoalType.IDLE]
    assert char.current_goal.priority >= 6

def test_ambition_goal_stickiness():
    """
    Tests that an ambition-driven goal persists across multiple ticks
    and is not immediately replaced by a lower-priority default goal.
    """
    # 1. Setup
    char = Character(
        name="Leader Character",
        personality="Ambitious",
        traits=["Leader", "Ambitious", "Gregarious"],
        skills={"Leadership": 2},
        age=35,
        job=Job("Unemployed", None, 0),
        needs=_standard_needs(),
    )
    char.reputation_score = 60
    world, game_time = _make_world()
    world.characters.append(char)

    # 2. Assign Ambition
    ambition_data = AMBITIONS["BECOME_TOWN_LEADER"]
    char.ambition = Ambition(AmbitionType.BECOME_TOWN_LEADER, ambition_data)

    initial_goal = char.current_goal
    assert initial_goal.priority >= 6

    # 3. First Tick: Ambition goal should be chosen
    char.decide_action(world)

    first_tick_goal = char.current_goal
    assert first_tick_goal.type in [GoalType.INCREASE_REPUTATION, GoalType.GIVE_SPEECH, GoalType.CAMPAIGN_SPEECH, GoalType.IDLE]
    assert first_tick_goal.priority >= 6

    # 4. Second Tick: Ambition goal should persist
    world.game_time.tick()
    char.decide_action(world)

    second_tick_goal = char.current_goal
    assert second_tick_goal.type in [GoalType.INCREASE_REPUTATION, GoalType.GIVE_SPEECH, GoalType.CAMPAIGN_SPEECH, GoalType.IDLE]
    assert second_tick_goal.priority >= 6

    # 5. Third Tick: Just to be sure
    world.game_time.tick()
    char.decide_action(world)
    third_tick_goal = char.current_goal
    assert third_tick_goal.type in [GoalType.INCREASE_REPUTATION, GoalType.GIVE_SPEECH, GoalType.CAMPAIGN_SPEECH, GoalType.IDLE]
    assert third_tick_goal.priority >= 6
