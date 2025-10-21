# tests/conftest.py
import pytest
from game.world import World
from game.time import Time

@pytest.fixture
def world():
    """Creates a new world for each test."""
    time = Time()
    return World(game_time_ref=time)
