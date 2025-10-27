# tests/conftest.py
import pytest
import threading
import time
from game.world import World
from game.time import Time
from game import main as game_main

@pytest.fixture
def world():
    """
    Creates a new world for each test and ensures that map generation is disabled.
    """
    # Disable landscape generation for tests to ensure a clean slate
    from game import config
    original_map_gen_disabled = getattr(config, "MAP_GENERATION_DISABLED", False)
    config.MAP_GENERATION_DISABLED = True

    test_time = Time()
    test_world = World(game_time_ref=test_time)

    yield test_world

    # Teardown: Restore original config value
    config.MAP_GENERATION_DISABLED = original_map_gen_disabled
