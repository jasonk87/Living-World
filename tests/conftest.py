# tests/conftest.py

import pytest
from game.world import World
from game.time import Time
from game.stockpile import Stockpile

@pytest.fixture
def world():
    """Provides a clean World instance for each test."""
    game_time = Time(ticks_per_day=10)
    test_world = World(grid_size=(20, 20), game_time_ref=game_time)

    # Add a default stockpile for tests that need to deposit items.
    # It allows all resources by default for simplicity.
    default_stockpile = Stockpile("Default Stockpile", 0, 0, 3, 3, allowed_resources=None)
    test_world.add_stockpile(default_stockpile)

    return test_world
