# tests/test_economy.py
import pytest
import threading
import time
import urllib.request
import json
from game.character import Character
from game.item import Item
from game.building import Building
from game.world import World
from game.stockpile import Stockpile
from game.time import Time
from game.main import advance_simulation_one_tick, run_server as start_server
from game.data import STRUCTURE_BLUEPRINTS

# Test for Miner
def test_miner_job(world):
    miner = Character(name="Test Miner", personality="test", traits=[], skills={}, job="Miner", x=0, y=0)
    miner.inventory["Iron Pickaxe"] = 1
    miner.equip_tool("Iron Pickaxe")
    world.add_character(miner)
    world.add_resource("Iron Ore", (5, 5))
    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Iron Ore"])
    world.stockpiles.append(stockpile)

    # Simulate enough ticks for the miner to gather ore and deposit it
    for _ in range(100):
        advance_simulation_one_tick(world)

    assert stockpile.inventory.get("Iron Ore", 0) > 0, "Miner should have deposited Iron Ore in the stockpile"

# Test for Smelter
def test_smelter_job(world):
    smelter = Character(name="Test Smelter", personality="test", traits=[], skills={}, job="Smelter", x=0, y=0)
    world.add_character(smelter)
    blueprint = STRUCTURE_BLUEPRINTS["small_workshop"]
    world.add_building(Building(structure_type="smelter_workshop", location=(6, 6), **blueprint))

    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Iron Ore", "Iron Ingot"])
    stockpile.add_item("Iron Ore", 10)
    world.stockpiles.append(stockpile)

    for _ in range(150):
        advance_simulation_one_tick(world)

    assert stockpile.inventory.get("Iron Ingot", 0) > 0, "Smelter should have produced Iron Ingots"

# Test for Blacksmith
def test_blacksmith_job(world):
    blacksmith = Character(name="Test Blacksmith", personality="test", traits=[], skills={}, job="Blacksmith", x=0, y=0)
    blacksmith.inventory["Hammer"] = 1
    blacksmith.equip_tool("Hammer")
    world.add_character(blacksmith)
    blueprint = STRUCTURE_BLUEPRINTS["small_workshop"]
    world.add_building(Building(structure_type="blacksmith_workshop", location=(7, 7), **blueprint))

    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Iron Ingot", "Wood", "Iron Axe", "Iron Pickaxe"])
    stockpile.add_item("Iron Ingot", 10)
    stockpile.add_item("Wood", 10)
    world.stockpiles.append(stockpile)

    # Simulate to produce at least one tool
    for _ in range(200):
        advance_simulation_one_tick(world)

    assert stockpile.inventory.get("Iron Axe", 0) > 0 or stockpile.inventory.get("Iron Pickaxe", 0) > 0, "Blacksmith should have produced an Iron Axe or Pickaxe"

# Test for Sawyer
def test_sawyer_job(world):
    sawyer = Character(name="Test Sawyer", personality="test", traits=[], skills={}, job="Sawyer", x=0, y=0)
    sawyer.inventory["Saw"] = 1
    sawyer.equip_tool("Saw")
    world.add_character(sawyer)
    blueprint = STRUCTURE_BLUEPRINTS["sawmill"]
    world.add_building(Building(structure_type="sawmill", location=(8, 8), **blueprint))

    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Wood", "Lumber"])
    stockpile.add_item("Wood", 10)
    world.stockpiles.append(stockpile)

    for _ in range(150):
        advance_simulation_one_tick(world)

    assert stockpile.inventory.get("Lumber", 0) > 0, "Sawyer should have produced Lumber"

# Test for Carpenter
def test_carpenter_job(world):
    carpenter = Character(name="Test Carpenter", personality="test", traits=[], skills={}, job="Carpenter", x=0, y=0)
    carpenter.inventory["Hammer"] = 1
    carpenter.equip_tool("Hammer")
    world.add_character(carpenter)
    blueprint = STRUCTURE_BLUEPRINTS["carpenters_shop"]
    world.add_building(Building(structure_type="carpenters_shop", location=(9, 9), **blueprint))

    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Lumber", "Iron Ingot", "Furniture"])
    stockpile.add_item("Lumber", 10)
    stockpile.add_item("Iron Ingot", 10)
    world.stockpiles.append(stockpile)

    for _ in range(200):
        advance_simulation_one_tick(world)

    assert stockpile.inventory.get("Furniture", 0) > 0, "Carpenter should have produced Furniture"

def test_work_order_creation_and_assignment(world):
    from game.work_order import WorkOrder
    # Add a Carpenter to the world
    carpenter = Character(name="Test Carpenter", personality="test", traits=[], skills={}, job="Carpenter", x=0, y=0)
    carpenter.inventory["Hammer"] = 1
    carpenter.equip_tool("Hammer")
    world.add_character(carpenter)

    # Add a Carpenter's shop
    blueprint = STRUCTURE_BLUEPRINTS["carpenters_shop"]
    world.add_building(Building(structure_type="carpenters_shop", location=(9, 9), **blueprint))

    # Add a stockpile with the necessary resources
    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Lumber", "Iron Ingot", "Furniture"])
    stockpile.add_item("Lumber", 10)
    stockpile.add_item("Iron Ingot", 10)
    world.stockpiles.append(stockpile)

    # Create and add a work order
    work_order = WorkOrder(order_type="CraftItem", details={"item_name": "Furniture", "quantity": 1})
    work_order.status = "Approved"
    world.add_work_order(work_order)

    # Simulate for a few ticks to allow the character to be assigned the work order
    for _ in range(10):
        advance_simulation_one_tick(world)

    # Check that the Carpenter has been assigned the work order
    assert carpenter.active_work_order_id == work_order.order_id, "Carpenter should have been assigned the work order"
def test_end_to_end_work_order_creation_and_completion(world):
    from game.work_order import WorkOrder
    # Add a Manager, Carpenter, and necessary buildings/resources
    manager = Character(name="Test Manager", personality="test", traits=[], skills={}, job="Manager", x=0, y=0)
    world.add_character(manager)
    carpenter = Character(name="Test Carpenter", personality="test", traits=[], skills={}, job="Carpenter", x=0, y=0)
    carpenter.inventory["Hammer"] = 1
    carpenter.equip_tool("Hammer")
    world.add_character(carpenter)
    manager.add_subordinate(carpenter.name)
    carpenter.set_supervisor(manager.name)
    blueprint = STRUCTURE_BLUEPRINTS["carpenters_shop"]
    world.add_building(Building(structure_type="carpenters_shop", location=(9, 9), **blueprint))
    stockpile = Stockpile("main_stockpile", 2, 2, 1, 1, allowed_resources=["Lumber", "Iron Ingot", "Furniture"])
    stockpile.add_item("Lumber", 10)
    stockpile.add_item("Iron Ingot", 10)
    world.stockpiles.append(stockpile)

    # Manually update the ledger to reflect the initial stockpile state,
    # as there's no Bookkeeper in this test to do it automatically.
    world.ledger.update_stockpile_record("main_stockpile", stockpile.inventory, world.game_time.current_day)

    # Manually create and add a work order (simulating an API call's effect)
    work_order = WorkOrder(order_type="CraftItem", details={"item_name": "Furniture", "quantity": 1})
    world.add_work_order(work_order)

    # Simulate until the order is approved and assigned
    for _ in range(50):
        advance_simulation_one_tick(world)
        if carpenter.active_work_order_id == work_order.order_id:
            break

    assert carpenter.active_work_order_id == work_order.order_id, "Carpenter should have been assigned the work order"

    # Continue simulation until the order is completed
    for _ in range(200):
        advance_simulation_one_tick(world)
        if work_order.status == "Completed":
            break

    assert work_order.status == "Completed", "Work order should be completed"
