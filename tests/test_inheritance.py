# tests/test_inheritance.py
import pytest
from game.character import Character
from game.world import World
from game.time import Time
from game.config import MAX_AGE

def test_character_death_and_inheritance():
    """
    Test a full lifecycle of a character, their death, and the subsequent inheritance of assets.
    """
    game_time = Time()
    world = World(game_time_ref=game_time)

    # Create a character who is about to die
    days_per_year = 10 * 4  # Assuming DAYS_PER_SEASON=10 and 4 seasons
    parent = Character(
        name="Parent",
        age=MAX_AGE,
        skills={},
        personality="gregarious",
        traits=["kind"]
    )
    parent.age_in_days = days_per_year - 1  # Set to the last day of the year
    world.add_character(parent)
    parent.money = 1000

    # Create a spouse
    spouse = Character(name="Spouse", age=30, skills={}, personality="reserved", traits=["honest"])
    world.add_character(spouse)
    parent.spouse = spouse.name
    spouse.spouse = parent.name

    # Create a business for the parent
    business = world.launch_business(parent)
    assert business is not None
    assert business.get('owner') == parent.name

    # Advance age to trigger death
    parent.advance_age(world)
    assert parent.is_deceased, f"Character should be deceased at age {parent.age_years}"

    # Process population to handle death and inheritance
    world.process_population_daily({})

    # Verify parent is removed from the world
    assert parent not in world.characters

    # Verify spouse inherited assets
    # The startup cost is actually 24 from the randomly chosen template
    startup_cost = 24
    expected_money = 1000 - startup_cost
    assert spouse.money >= expected_money - 5  # Allow for small discrepancies
    retrieved_business = world.economy.businesses.get(business['id'])
    assert retrieved_business is not None
    assert retrieved_business['owner'] == spouse.name
