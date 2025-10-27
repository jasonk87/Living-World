# tests/test_reputation.py
import pytest
from game.character import Character
from game.world import World
from game.rumor import Rumor
from game.time import Time
from game import config

@pytest.fixture
def base_world():
    """Provides a basic world instance for reputation tests."""
    world = World(grid_size=(10, 10))
    world.game_time = Time()
    char1 = Character(name="Alice", personality="Friendly", traits=["Kind"], skills={}, x=1, y=1)
    char2 = Character(name="Bob", personality="Stoic", traits=[], skills={}, x=2, y=1)
    world.add_character(char1)
    world.add_character(char2)
    return world

def test_reputation_initialization(base_world):
    alice = base_world.get_character_by_name("Alice")
    assert alice.reputation_score == 0
    assert alice.get_reputation_tier() == "Neutral"

def test_update_reputation_score(base_world):
    alice = base_world.get_character_by_name("Alice")
    alice.update_reputation(15, "Act of kindness")
    assert alice.reputation_score == 15
    alice.update_reputation(-20, "Minor transgression")
    assert alice.reputation_score == -5

def test_reputation_score_clamping(base_world):
    alice = base_world.get_character_by_name("Alice")

    # Test max clamping
    alice.reputation_score = 0
    alice.update_reputation(config.REPUTATION_SCORE_MAX + 50, "Major heroic act")
    assert alice.reputation_score == config.REPUTATION_SCORE_MAX

    # Test min clamping
    alice.reputation_score = 0
    alice.update_reputation(config.REPUTATION_SCORE_MIN - 50, "Heinous act")
    assert alice.reputation_score == config.REPUTATION_SCORE_MIN

def test_get_reputation_tier(base_world):
    alice = base_world.get_character_by_name("Alice")
    config.REPUTATION_TIERS = [
        ("Hero", 80),
        ("Respected", 30),
        ("Neutral", -30),
        ("Disliked", -70),
        ("Villain", -100),
    ]
    alice.reputation_score = 90
    assert alice.get_reputation_tier() == "Hero"
    alice.reputation_score = 50
    assert alice.get_reputation_tier() == "Respected"
    alice.reputation_score = 0
    assert alice.get_reputation_tier() == "Neutral"
    alice.reputation_score = -50
    assert alice.get_reputation_tier() == "Disliked"
    alice.reputation_score = -90
    assert alice.get_reputation_tier() == "Villain"

def test_rumor_generation_from_reputation_change(base_world):
    alice = base_world.get_character_by_name("Alice")
    world = base_world
    world.game_time.current_day = 1 # Set game time for rumor creation

    assert len(world.rumors) == 0
    # A small change should not generate a rumor
    alice.update_reputation(config.REPUTATION_FOR_RUMOR_THRESHOLD - 1, "Polite conversation", world=world)
    assert len(world.rumors) == 0

    # A large change should generate a rumor
    alice.update_reputation(config.REPUTATION_FOR_RUMOR_THRESHOLD + 5, "Saved a cat from a tree", world=world)
    assert len(world.rumors) == 1
    rumor = world.rumors[0]
    assert rumor.subject_char_id == "Alice"
    assert "saved_a_cat_from_a_tree" in rumor.content_key
    assert rumor.is_positive
    assert rumor.rumor_id in alice.known_rumor_ids

def test_rumor_daily_decay(base_world):
    world = base_world
    world.game_time.current_day = 1
    rumor = Rumor(
        subject_char_id="Alice",
        content_key="test_rumor_positive",
        initial_strength=10.0,
        creation_day=1,
        is_positive=True,
    )
    rumor.last_spread_day = 0 # Set last spread to a day in the past
    world.add_rumor(rumor)
    initial_strength = rumor.current_strength

    world.game_time.current_day = 2 # Advance time
    world.update_rumors_daily()

    assert rumor.current_strength < initial_strength

def test_rumor_propagation(base_world):
    world = base_world
    alice = world.get_character_by_name("Alice")
    bob = world.get_character_by_name("Bob")
    # Make characters known to each other for propagation to occur
    alice.known_characters.append("Bob")
    bob.known_characters.append("Alice")
    world.game_time.current_day = 1

    rumor = Rumor(
        subject_char_id="Charlie",
        content_key="found_gold_positive",
        initial_strength=config.MIN_RUMOR_STRENGTH_TO_SPREAD + 10, # Ensure it's strong enough
        creation_day=1,
        is_positive=True,
    )
    rumor.add_knower(alice.name)
    alice.known_rumor_ids.add(rumor.rumor_id)
    world.add_rumor(rumor)

    assert rumor.rumor_id in alice.known_rumor_ids
    assert rumor.rumor_id not in bob.known_rumor_ids

    # To make it deterministic, let's temporarily set the propagation attempts high
    original_attempts = config.DAILY_RUMOR_SPREAD_ATTEMPTS
    config.DAILY_RUMOR_SPREAD_ATTEMPTS = 100 # Ensure it runs

    world._propagate_rumors_daily()

    assert rumor.rumor_id in bob.known_rumor_ids
    assert rumor.is_known_by(bob.name)

    # Reset the config value
    config.DAILY_RUMOR_SPREAD_ATTEMPTS = original_attempts

def test_share_rumor_goal(base_world):
    world = base_world
    alice = world.get_character_by_name("Alice")
    bob = world.get_character_by_name("Bob")
    alice.known_characters.append("Bob")
    bob.known_characters.append("Alice")
    world.game_time.current_day = 1

    rumor = Rumor(
        subject_char_id="Charlie",
        content_key="secret_pie_recipe_positive",
        initial_strength=50,
        creation_day=1,
        is_positive=True,
    )
    world.add_rumor(rumor)
    alice.known_rumor_ids.add(rumor.rumor_id)

    assert rumor.rumor_id not in bob.known_rumor_ids

    from game.goal import Goal, GoalType
    alice.current_goal = Goal(
        GoalType.SHARE_RUMOR,
        assignee_id=alice.name,
        originator_id=alice.name,
        parameters={"target_char_name": "Bob", "rumor_id": rumor.rumor_id}
    )

    alice.decide_action(world)

    assert rumor.rumor_id in bob.known_rumor_ids
    # Check for social consequences
    assert "gossipy" in bob.opinions["Alice"]
