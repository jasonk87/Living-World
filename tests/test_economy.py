# tests/test_economy.py

import pytest
from game.character import Character
from game.world import World
from game.data import Job, BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from game.stockpile import Stockpile
from game.building import Building

@pytest.fixture(autouse=True)
def setup_blueprints(monkeypatch):
    # Add a basic Hammer blueprint for the blacksmith test
    test_blueprints = BLUEPRINTS.copy()
    test_blueprints["Hammer"] = {
        "type": "Tool",
        "tool_type": "Hammer",
        "max_durability": 100,
        "description": "A basic hammer for smithing and construction.",
    }
    monkeypatch.setattr("game.character.BLUEPRINTS", test_blueprints)
    monkeypatch.setattr("game.character.JOB_TASK_DEFINITIONS", JOB_TASK_DEFINITIONS)

def advance_simulation(world, ticks):
    """Helper to advance the simulation by a number of ticks."""
    for _ in range(ticks):
        new_day = world.game_time.tick()
        for character in list(world.characters):
            if character in world.characters:
                character.decide_action(world)
        if new_day:
            if hasattr(world, 'daily_environment_tick'):
                world.daily_environment_tick()
            if hasattr(world, 'process_daily_economy'):
                world.process_daily_economy()


class TestEconomy:
    def test_miner_job(self, world):
        miner = Character(
            name="Test Miner",
            personality="Hardworking",
            traits=["Strong"],
            skills={"Mining": 5},
            job=Job("Miner", None, 0)
        )
        world.add_character(miner)
        world.add_resource("Iron Ore", (5, 5))

        # Simulate to allow the miner to work
        advance_simulation(world, 30)

        # Check if the miner has gathered Iron Ore and deposited it
        assert world.stockpiles[0].inventory.get("Iron Ore", 0) > 0

    def test_smelter_job(self, world):
        smelter = Character(
            name="Test Smelter",
            personality="Focused",
            traits=[],
            skills={"Smelting": 5},
            job=Job("Smelter", None, 0)
        )
        world.add_character(smelter)

        # Add a workshop for the smelter
        workshop_bp = STRUCTURE_BLUEPRINTS["small_workshop"]
        workshop = Building(
            structure_type="small_workshop",
            display_name="Test Workshop",
            location=(3, 3),
            size=workshop_bp["size"],
            required_resources={},
            functionality=workshop_bp["functionality"],
            required_skill={},
        )
        workshop.is_operational = True # Pre-build it for the test
        world.add_building(workshop)

        stockpile = world.stockpiles[0]
        stockpile.add_item("Iron Ore", 10)

        # Simulate to allow the smelter to work
        advance_simulation(world, 500)

        # Check if the smelter has produced Iron Ingots
        assert stockpile.inventory.get("Iron Ingot", 0) > 0

    def test_blacksmith_job(self, world):
        blacksmith = Character(
            name="Test Blacksmith",
            personality="Creative",
            traits=[],
            skills={"Blacksmithing": 5},
            job=Job("Blacksmith", None, 0)
        )
        # Give the blacksmith a hammer
        blacksmith.inventory["Hammer"] = 1
        blacksmith.equip_tool("Hammer")
        world.add_character(blacksmith)

        # Add a workshop for the blacksmith
        workshop_bp = STRUCTURE_BLUEPRINTS["small_workshop"]
        workshop = Building(
            structure_type="small_workshop",
            display_name="Test Workshop",
            location=(3, 3),
            size=workshop_bp["size"],
            required_resources={},
            functionality=workshop_bp["functionality"],
            required_skill={},
        )
        workshop.is_operational = True # Pre-build it for the test
        world.add_building(workshop)

        stockpile = world.stockpiles[0]
        stockpile.add_item("Iron Ingot", 10)
        stockpile.add_item("Wood", 10)

        # Simulate to allow the blacksmith to work
        advance_simulation(world, 500)

        # Check if the blacksmith has produced Iron Axes
        assert stockpile.inventory.get("Iron Axe", 0) > 0

    def test_farmer_job(self, world):
        farmer = Character(
            name="Test Farmer",
            personality="Patient",
            traits=["Diligent"],
            skills={"Farming": 5},
            job=Job("Farmer", None, 0)
        )
        world.add_character(farmer)
        world.add_resource("Food", (10, 10), tile_becomes="Fields")

        # Simulate to allow the farmer to work
        advance_simulation(world, 30)

        # Check if the farmer has gathered Food and deposited it
        assert world.stockpiles[0].inventory.get("Food", 0) > 0
