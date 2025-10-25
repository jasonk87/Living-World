import unittest
import random
from game.character import Character, Job
from game.world import World
from game.time import Time
from game.stockpile import Stockpile
from game.ledger import Ledger
from game.work_order import WorkOrder # For potential crafting tests
from game.data import JOB_TASK_DEFINITIONS, BLUEPRINTS, JOB_SALARIES
from game.goal import Goal, GoalType
from game import config
from game.crop import Crop


class TestCharacterTaskPerformance(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(20, 20), game_time_ref=self.time) # Larger world for tasks

        # Define some resources and tasks if not already in data
        if "Chop Wood" not in JOB_TASK_DEFINITIONS:
            JOB_TASK_DEFINITIONS["Chop Wood"] = {
                "required_tool_type": "Axe", "skill_used": "Woodcutting",
                "resource_produced": "Wood", "base_yield": 1, "base_time_per_yield": 3
            }
        if "Stone Axe" not in BLUEPRINTS:
            BLUEPRINTS["Stone Axe"] = {
                "required_resources": {"Stone": 2, "Wood": 1}, "required_skill": "Stonemasonry",
                "type": "Tool", "tool_type": "Axe", "max_durability": 50, "craft_time_per_unit": 8
            }
        if not self.world.get_resources("Wood"):
             self.world.add_resource("Wood", (0,0), tile_becomes="Forest")
             self.world.add_resource("Wood", (0,1), tile_becomes="Forest")

        # Allow all resources for this test stockpile for simplicity
        self.stockpile = Stockpile(name="TestSP", x=5, y=5, width=1, height=1, allowed_resources=None)
        self.world.add_stockpile(self.stockpile)
        # Pre-stock for bookkeeper tests
        self.stockpile.add_item("Logs", 10) # This should now work
        self.stockpile.add_item("Stones", 5)
        self.world.ledger.update_stockpile_record(self.stockpile.name, self.stockpile.inventory.copy(), self.time.current_day)


    def run_task_for_ticks(self, character, task_name, ticks, task_location=(0,0)):
        """Helper to run a generic task for a number of ticks."""
        character.current_goal = Goal(GoalType.GATHER_RESOURCE, assignee_id=character.name, parameters={"task_name": task_name})

        # Ensure character is at task location
        character.x, character.y = task_location

        for _ in range(ticks):
            if task_name in JOB_TASK_DEFINITIONS : # Generic gather task
                 character._execute_generic_task(self.world, task_name)


    def test_lazy_generic_task_slower_progress(self):
        lazy_char = Character(name="LazyTest", personality="slacker", traits=["Lazy"], skills={}, job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)))
        lazy_char.equip_tool("Stone Axe") # Assume Stone Axe blueprint exists and is an Axe
        self.world.add_character(lazy_char)

        # Base time for Chop Wood is 3. Lazy has 25% chance to do 0 progress.
        # Over many ticks, progress should be slower.
        # Let's run for enough ticks that 1 unit *should* be made by a normal char (e.g., 3 ticks for 1 wood)
        # And see if lazy char makes less or takes longer.

        ticks_to_run = JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"] * 2 # Enough for 2 units normally

        # Mock random.random to control laziness
        # We want to see at least one instance of laziness
        original_random = random.random

        # Test 1: Ensure laziness triggers (makes progress 0 for a tick)
        def lazy_random_once(): # First call lazy, then normal
            lazy_random_once.calls += 1
            if lazy_random_once.calls == 1: return 0.0 # Triggers lazy ( < 0.25)
            return 0.5 # Does not trigger lazy
        lazy_random_once.calls = 0
        random.random = lazy_random_once

        self.run_task_for_ticks(lazy_char, "Chop Wood", ticks_to_run)
        wood_yield = lazy_char.inventory.get("Wood", 0)
        # Expect less than 2 wood due to slacking. Base time 3. 6 ticks.
        # Tick 1: Lazy (0 prog). Total prog = 0
        # Tick 2: Work (1 prog). Total prog = 1
        # Tick 3: Work (1 prog). Total prog = 2
        # Tick 4: Work (1 prog). Total prog = 3 -> 1 Wood. Prog resets.
        # Tick 5: Work (1 prog). Total prog = 1
        # Tick 6: Work (1 prog). Total prog = 2
        # Expected: 1 wood
        self.assertEqual(wood_yield, 1, "Lazy character should produce less due to slacking.")
        self.assertTrue(any("Felt lazy and decided to slack off" in msg for msg in lazy_char.memory), "Lazy log not found.")
        random.random = original_random # Restore random

    def test_diligent_generic_task_faster_progress(self):
        diligent_char = Character(name="DiligentTest", personality="worker", traits=["Diligent"], skills={}, job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)))
        diligent_char.equip_tool("Stone Axe")
        self.world.add_character(diligent_char)

        ticks_to_run = JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"] # Enough for 1 unit normally

        original_random = random.random
        # Test: Ensure diligence triggers (makes progress +2 for a tick)
        def diligent_random_once():
            diligent_random_once.calls +=1
            if diligent_random_once.calls == 1: return 0.0 # Triggers diligent bonus ( < 0.25)
            return 0.5
        diligent_random_once.calls = 0
        random.random = diligent_random_once

        self.run_task_for_ticks(diligent_char, "Chop Wood", ticks_to_run) # 3 ticks
        # Tick 1: Diligent (+2 prog). Total prog = 2
        # Tick 2: Normal (+1 prog). Total prog = 3 -> 1 Wood. Prog resets.
        # Tick 3: Normal (+1 prog). Total prog = 1
        # Expected: 1 wood, but faster than normal if we measured sub-yield progress.
        # Since we only get yield at threshold, this test shows it completes within normal time even with a boost.
        # A better test would be to see if it produces *more* over a set number of ticks than normal.
        self.assertEqual(diligent_char.inventory.get("Wood", 0), 1)
        self.assertTrue(any("Worked with extra diligence" in msg for msg in diligent_char.memory), "Diligent log not found.")

        # Test for more yield over slightly more ticks
        diligent_char.memory = [] # Clear memory for next check
        diligent_char.inventory = {} # Reset
        diligent_char.task_work_progress = 0
        diligent_random_once.calls = 0 # Reset mock
        # Run for 4 ticks. Normal char = 1 wood. Diligent with one bonus:
        # T1: +2 (bonus) -> prog=2
        # T2: +1         -> prog=3 -> 1 Wood, prog=0
        # T3: +1         -> prog=1
        # T4: +1         -> prog=2
        # Still 1 wood. Let's try 6 ticks.
        # T5: +1         -> prog=3 -> 2nd Wood!
        # T6: +1         -> prog=1 (after 2nd wood)
        self.run_task_for_ticks(diligent_char, "Chop Wood", 6)
        self.assertEqual(diligent_char.inventory.get("Wood", 0), 2, "Diligent char should produce more over time.")

        random.random = original_random

    def test_focused_overrides_lazy_generic_task(self):
        focused_lazy_char = Character(name="FocusLazy", personality="focused", traits=["Focused", "Lazy"], skills={}, job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)))
        focused_lazy_char.equip_tool("Stone Axe")
        self.world.add_character(focused_lazy_char)

        ticks_to_run = JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"] # 3 ticks

        # Mock random.random to try and trigger lazy AND focused bonus
        original_random = random.random
        def focus_override_random():
            focus_override_random.calls += 1
            if focus_override_random.calls == 1: return 0.0 # Would trigger Lazy (if not Focused), also Focused bonus
            return 0.5
        focus_override_random.calls = 0
        random.random = focus_override_random

        self.run_task_for_ticks(focused_lazy_char, "Chop Wood", ticks_to_run)
        # Tick 1: Focused bonus (+2 prog). Prog = 2. Lazy is ignored.
        # Tick 2: Normal (+1 prog). Prog = 3 -> 1 Wood. Prog resets.
        # Tick 3: Normal (+1 prog). Prog = 1
        self.assertEqual(focused_lazy_char.inventory.get("Wood", 0), 1)
        self.assertNotIn("Felt lazy", "".join(focused_lazy_char.memory)) # Ensure "Felt lazy" is NOT in memory
        self.assertTrue(any("Remained focused" in msg for msg in focused_lazy_char.memory), "Focused log not found.")
        random.random = original_random

    def test_strong_trait_extra_yield_generic_task(self):
        strong_char = Character(name="StrongTest", personality="strong", traits=["Strong"], skills={}, job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)))
        strong_char.equip_tool("Stone Axe")
        self.world.add_character(strong_char)

        ticks_to_run = JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"] # 3 ticks for 1 base wood

        original_random = random.random
        # Mock random to ensure Strong bonus triggers
        def strong_bonus_random(): # For the 20% chance of +1 yield
            return 0.1 # < 0.20, triggers bonus
        random.random = strong_bonus_random

        self.run_task_for_ticks(strong_char, "Chop Wood", ticks_to_run)
        # Base yield 1. Strong bonus +1. Total 2.
        self.assertEqual(strong_char.inventory.get("Wood", 0), 2)
        self.assertTrue(any("Put my strength into" in msg for msg in strong_char.memory), "Strong log not found.")
        random.random = original_random

    def test_careless_trait_extra_tool_wear_generic_task(self):
        careless_char = Character(name="CarelessTest", personality="clumsy", traits=["Careless"], skills={}, job=Job("Woodcutter", None, JOB_SALARIES.get("Woodcutter", 0)))
        self.world.add_character(careless_char)

        # Equip a tool with known durability
        tool_name = "Stone Axe"
        original_durability = BLUEPRINTS[tool_name]["max_durability"]
        careless_char.equip_tool(tool_name)
        self.assertIsNotNone(careless_char.equipped_tool)
        self.assertEqual(careless_char.equipped_tool["durability"], original_durability)

        # Run task enough times to complete one yield (which triggers durability loss)
        ticks_to_run = JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"]

        original_random = random.random
        # Mock random to ensure Careless bonus wear triggers (25% chance for +1 extra)
        def careless_wear_random():
            return 0.1 # < 0.25, triggers bonus wear
        random.random = careless_wear_random

        self.run_task_for_ticks(careless_char, "Chop Wood", ticks_to_run)

        expected_durability = original_durability - 2 # 1 base wear + 1 careless wear
        self.assertEqual(careless_char.equipped_tool["durability"], expected_durability)
        self.assertTrue(any(f"Was a bit careless with my {tool_name}" in msg for msg in careless_char.memory), "Careless tool wear log not found.")
        random.random = original_random

    def run_craft_order_for_ticks(self, character, item_name, required_resources, craft_time, ticks):
        """Helper to run a craft order for a number of ticks."""
        wo_details = {"item_name": item_name, "quantity": 1, "required_resources": required_resources}
        if item_name not in BLUEPRINTS: # Ensure blueprint exists for test
            BLUEPRINTS[item_name] = {"required_resources": required_resources, "craft_time_per_unit": craft_time, "required_skill": "Crafting"}

        order = WorkOrder(order_type="CraftItem", details=wo_details, creation_day=self.time.current_day)
        self.world.add_work_order(order)
        order.status = "InProgress"
        order.assigned_to = character.name
        character.active_work_order_id = order.order_id
        goal = Goal(GoalType.EXECUTE_CRAFT_ORDER, assignee_id=character.name, parameters={"work_order_id": order.order_id})
        character.current_goal = goal


        # Assume materials are already gathered for simplicity in testing crafting speed
        character.materials_gathered_for_wo = True
        character.items_crafted_for_wo = False
        character.crafting_progress = 0
        for res, qty in required_resources.items(): # Give char the resources
            character.inventory[res] = character.inventory.get(res,0) + qty

        for _ in range(ticks):
            character._execute_craft_order(self.world)
            if character.items_crafted_for_wo: # Stop if item is finished
                break

    def test_lazy_crafter_slower_progress(self):
        lazy_crafter = Character(name="LazyCrafter", personality="slacker", traits=["Lazy"], skills={})
        self.world.add_character(lazy_crafter)
        item_name = "TestCraftLazy"
        res = {"Wood":1}; time = 3

        original_random = random.random
        lazy_random_once_calls = [0] # Use list to pass by reference for closure
        def lazy_random_once():
            lazy_random_once_calls[0] += 1
            if lazy_random_once_calls[0] == 1: return 0.0 # Trigger lazy on first crafting tick
            return 0.5
        random.random = lazy_random_once

        self.run_craft_order_for_ticks(lazy_crafter, item_name, res, time, time) # Run for base time
        # Expected: Tick 1=Lazy (0 prog), Tick 2=+1 prog, Tick 3=+1 prog. Total prog = 2. Item not finished.
        self.assertFalse(lazy_crafter.items_crafted_for_wo)
        self.assertEqual(lazy_crafter.crafting_progress, time -1) # Should be one less than time due to one lazy tick
        self.assertTrue(any(f"Felt lazy and slacked off while crafting {item_name}" in msg for msg in lazy_crafter.memory), "Lazy crafter log not found.")
        random.random = original_random

    def test_diligent_crafter_faster_progress(self):
        diligent_crafter = Character(name="DiligentCrafter", personality="worker", traits=["Diligent"], skills={})
        self.world.add_character(diligent_crafter)
        item_name = "TestCraftDiligent"
        res = {"Wood":1}; time = 3 # Base time 3

        original_random = random.random
        diligent_random_once_calls = [0]
        def diligent_random_once():
            diligent_random_once_calls[0] += 1
            if diligent_random_once_calls[0] == 1: return 0.0 # Trigger diligent bonus on first tick
            return 0.5
        random.random = diligent_random_once

        # Run for less than base time, expecting completion due to diligence
        # Tick 1: Diligent (+1.5 prog). Prog = 1.5
        # Tick 2: Normal (+1 prog). Prog = 2.5
        # Tick 3: Normal (+1 prog). Prog = 3.5 -> Item crafted!
        self.run_craft_order_for_ticks(diligent_crafter, item_name, res, time, time)
        self.assertTrue(diligent_crafter.items_crafted_for_wo, "Diligent crafter should have finished in base time with one bonus.")
        self.assertTrue(any(f"Worked with extra diligence crafting {item_name}" in msg for msg in diligent_crafter.memory), "Diligent crafter log not found.")
        random.random = original_random

    def test_careless_bookkeeper_miscounts(self):
        target_stockpile_name = "TestSP"
        stockpile_for_char = self.world.get_stockpile_by_name(target_stockpile_name)
        self.assertIsNotNone(stockpile_for_char, f"Stockpile {target_stockpile_name} not found in world setup.")

        stockpile_for_char.inventory = {"Logs": 10, "Stones": 5}
        self.world.ledger.update_stockpile_record(target_stockpile_name, stockpile_for_char.inventory.copy(), self.time.current_day)

        careless_bookie = Character(name="CarelessBookie", personality="distracted", traits=["Careless"], skills={}, job=Job("Bookkeeper", None, JOB_SALARIES.get("Bookkeeper", 0)))
        self.world.add_character(careless_bookie)
        careless_bookie.x, careless_bookie.y = stockpile_for_char.rect[0], stockpile_for_char.rect[1]

        goal = Goal(GoalType.COUNT_STOCKPILE, assignee_id=careless_bookie.name, parameters={"stockpile_name": target_stockpile_name})
        careless_bookie.current_goal = goal

        initial_logs = stockpile_for_char.inventory["Logs"]
        initial_stones = stockpile_for_char.inventory["Stones"]

        original_random = random.random
        original_choice = random.choice
        def careless_random():
            return 0.05 # < 0.10, triggers miscount
        def careless_choice(seq):
            return -1 # Always choose -1
        random.random = careless_random
        random.choice = careless_choice

        original_decide_action = careless_bookie.decide_action
        careless_bookie.decide_action = lambda world_param: None

        careless_bookie._execute_count_stockpile(self.world)

        careless_bookie.decide_action = original_decide_action
        random.random = original_random
        random.choice = original_choice

        # Check the ledger using the correct resource-keyed structure
        logs_in_ledger = self.world.ledger.get_resource_count_in_stockpile("Logs", target_stockpile_name)
        stones_in_ledger = self.world.ledger.get_resource_count_in_stockpile("Stones", target_stockpile_name)

        self.assertEqual(logs_in_ledger, initial_logs - 1)
        self.assertEqual(stones_in_ledger, initial_stones -1)

        self.assertTrue(any(f"Careless counting {target_stockpile_name}" in msg for msg in careless_bookie.memory), "Careless bookkeeper log not found.")
        self.assertTrue(any(f"Logs (actual: {initial_logs}, recorded: {initial_logs - 1})" in msg for msg in careless_bookie.memory), "Careless bookkeeper miscount detail not found.")


class TestCharacterFarming(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)
        self.farmer = Character(name="Farmer", personality="hardworking", traits=[], skills={"Farming": 1}, job=Job("Farmer", None, 0))
        self.world.add_character(self.farmer)

    def test_farmer_prioritizes_harvest(self):
        # Setup: ripe crop, tilled soil, and grass nearby
        self.world.set_tile_type(1, 1, "Tilled Soil")
        self.world.set_tile_type(1, 2, "Grass")
        ripe_crop = Crop("Wheat", 1, 0)
        ripe_crop.growth = 1.0
        self.world.crops.append(ripe_crop)
        self.farmer.x, self.farmer.y = 1, 1

        self.farmer.current_goal = Goal(GoalType.PERFORM_FARMER_DUTIES, assignee_id=self.farmer.name)
        self.farmer.decide_action(self.world)

        self.assertEqual(self.farmer.current_goal.type, GoalType.HARVEST_CROP)
        self.assertEqual(self.farmer.current_goal.parameters["target_location"], (1, 0))

    def test_farmer_prioritizes_plant(self):
        # Setup: tilled soil and grass nearby, no ripe crops
        self.world.set_tile_type(1, 1, "Tilled Soil")
        self.world.set_tile_type(1, 2, "Grass")
        self.farmer.x, self.farmer.y = 1, 0

        self.farmer.current_goal = Goal(GoalType.PERFORM_FARMER_DUTIES, assignee_id=self.farmer.name)
        self.farmer.decide_action(self.world)

        self.assertEqual(self.farmer.current_goal.type, GoalType.PLANT_SEEDS)
        self.assertEqual(self.farmer.current_goal.parameters["target_location"], (1, 1))

    def test_farmer_tills_when_no_other_tasks(self):
        # Clear the area of grass first
        for x in range(self.world.grid_size[0]):
            for y in range(self.world.grid_size[1]):
                self.world.set_tile_type(x, y, "Dirt")

        # Setup: only one grass tile nearby
        self.world.set_tile_type(1, 1, "Grass")
        self.farmer.x, self.farmer.y = 1, 0

        self.farmer.current_goal = Goal(GoalType.PERFORM_FARMER_DUTIES, assignee_id=self.farmer.name)
        self.farmer.decide_action(self.world)

        self.assertEqual(self.farmer.current_goal.type, GoalType.TILL_SOIL)
        self.assertEqual(self.farmer.current_goal.parameters["target_location"], (1, 1))

    def test_farmer_full_cycle(self):
        # Till
        self.world.set_tile_type(1, 1, "Grass")
        self.farmer.x, self.farmer.y = 1, 1 # Move farmer to the spot to till
        self.farmer.current_goal = Goal(GoalType.TILL_SOIL, assignee_id=self.farmer.name, parameters={"target_location": (1, 1)})
        self.farmer.decide_action(self.world)
        self.assertEqual(self.world.grid[1][1], "Tilled Soil")

        # Plant
        self.farmer.x, self.farmer.y = 1, 1 # Ensure farmer is at the spot to plant
        self.farmer.current_goal = Goal(GoalType.PLANT_SEEDS, assignee_id=self.farmer.name, parameters={"target_location": (1, 1)})
        self.farmer.decide_action(self.world)
        crop = self.world.get_crop_at(1, 1)
        self.assertIsNotNone(crop)
        self.assertEqual(crop.crop_type, "Wheat")

        # Harvest
        crop.growth = 1.0 # Make the crop ready for harvest
        self.farmer.x, self.farmer.y = 1, 1 # Ensure farmer is at the spot to harvest
        self.farmer.current_goal = Goal(GoalType.HARVEST_CROP, assignee_id=self.farmer.name, parameters={"target_location": (1, 1)})
        self.farmer.decide_action(self.world)
        self.assertIsNone(self.world.get_crop_at(1, 1))
        self.assertEqual(self.farmer.inventory.get("Wheat"), 1)


class TestCharacterHunting(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)
        self.hunter = Character(name="Hunter", personality="adventurous", traits=[], skills={}, job=Job("Hunter", None, 0))
        self.world.add_character(self.hunter)
        self.world.add_animal("Deer", 5, 5)
        self.stockpile = Stockpile(name="MainStockpile", x=0, y=0, width=1, height=1)
        self.world.add_stockpile(self.stockpile)

    def test_hunter_job_hunts_animal(self):
        original_random = random.random
        def successful_hunt():
            return 0.1 # < 0.7, guarantees success
        random.random = successful_hunt

        self.hunter.current_goal = Goal(GoalType.PERFORM_HUNTER_DUTIES, assignee_id=self.hunter.name)
        self.hunter.decide_action(self.world) # Should decide to hunt
        self.assertEqual(self.hunter.current_goal.type, GoalType.HUNT)

        target_animal = self.hunter.current_goal.parameters.get("target_animal")
        self.assertIsNotNone(target_animal)

        # Move hunter next to animal
        self.hunter.x = target_animal.x - 1
        self.hunter.y = target_animal.y

        # Execute hunt
        self.hunter.decide_action(self.world)

        self.assertNotIn(target_animal, self.world.animals)
        self.assertGreater(self.hunter.inventory.get("Raw Meat", 0), 0)

        random.random = original_random

    def test_hunter_job_hauls_when_full(self):
        # Fill hunter's inventory
        self.hunter.inventory["Raw Meat"] = self.hunter.max_inventory_items

        self.hunter.current_goal = Goal(GoalType.PERFORM_HUNTER_DUTIES, assignee_id=self.hunter.name)
        self.hunter.decide_action(self.world) # Should decide to haul

        self.assertEqual(self.hunter.current_goal.type, GoalType.INITIATE_HAULING)

if __name__ == '__main__':
    unittest.main()
