import unittest
import random
from game.character import Character
from game.world import World
from game.time import Time
from game.stockpile import Stockpile
from game.ledger import Ledger
from game.work_order import WorkOrder
from game.data import JOB_TASK_DEFINITIONS, BLUEPRINTS
from game import config
from game.goal import Goal, GoalType

class TestCharacterTaskPerformance(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(20, 20), game_time_ref=self.time)

        if "Chop Wood" not in JOB_TASK_DEFINITIONS:
            JOB_TASK_DEFINITIONS["Chop Wood"] = {
                "required_tool_type": "Axe", "skill_used": "Woodcutting",
                "resource_produced": "Wood", "base_yield": 1, "base_time_per_yield": 3
            }
        if "Stone Axe" not in BLUEPRINTS:
            BLUEPRINTS["Stone Axe"] = {
                "required_resources": {"Stone": 2, "Wood": 1}, "job_skill_needed": "Stonemasonry",
                "type": "Tool", "tool_type": "Axe", "max_durability": 50, "craft_time_per_unit": 8
            }
        if "Wood" not in self.world.resources:
             self.world.add_resource("Wood", (0,0), tile_becomes="Forest")
             self.world.add_resource("Wood", (0,1), tile_becomes="Forest")

        self.stockpile = Stockpile(name="TestSP", x=5, y=5, width=1, height=1, allowed_resources=None)
        self.world.add_stockpile(self.stockpile)
        self.stockpile.add_item("Logs", 10)
        self.stockpile.add_item("Stones", 5)
        self.world.ledger.update_stockpile_record(self.stockpile.name, self.stockpile.inventory.copy(), self.time.current_day)

    def run_task_for_ticks(self, character, task_name, ticks, task_location=(0,0)):
        character.current_goal = Goal(GoalType.GATHER_RESOURCE, assignee_id=character.name, parameters={"task_name": task_name, "resource_name": "Wood"})
        character.x, character.y = task_location
        for _ in range(ticks):
            character.decide_action(self.world)

    def test_lazy_generic_task_slower_progress(self):
        lazy_char = Character(name="LazyTest", personality="slacker", traits=["Lazy"], skills={}, job="Woodcutter")
        self.world.add_character(lazy_char)
        self.stockpile.add_item("Stone Axe", 1)
        lazy_char.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=lazy_char.name, parameters={"tool_type": "Axe"})
        lazy_char.decide_action(self.world)

        original_random = random.random
        def lazy_random_once():
            lazy_random_once.calls += 1
            if lazy_random_once.calls == 1: return 0.0
            return 0.5
        lazy_random_once.calls = 0
        random.random = lazy_random_once

        self.run_task_for_ticks(lazy_char, "Chop Wood", JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"] * 2)
        wood_yield = lazy_char.inventory.get("Wood", 0)
        self.assertEqual(wood_yield, 1, "Lazy character should produce less due to slacking.")
        random.random = original_random

    def test_diligent_generic_task_faster_progress(self):
        diligent_char = Character(name="DiligentTest", personality="worker", traits=["Diligent"], skills={}, job="Woodcutter")
        self.world.add_character(diligent_char)
        self.stockpile.add_item("Stone Axe", 1)
        diligent_char.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=diligent_char.name, parameters={"tool_type": "Axe"})
        diligent_char.decide_action(self.world)

        original_random = random.random
        def diligent_random_once():
            diligent_random_once.calls +=1
            if diligent_random_once.calls == 1: return 0.0
            return 0.5
        diligent_random_once.calls = 0
        random.random = diligent_random_once

        self.run_task_for_ticks(diligent_char, "Chop Wood", 5)
        self.assertEqual(diligent_char.inventory.get("Wood", 0), 2, "Diligent char should produce more over time.")
        random.random = original_random

    def test_focused_overrides_lazy_generic_task(self):
        focused_lazy_char = Character(name="FocusLazy", personality="focused", traits=["Focused", "Lazy"], skills={}, job="Woodcutter")
        self.world.add_character(focused_lazy_char)
        self.stockpile.add_item("Stone Axe", 1)
        focused_lazy_char.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=focused_lazy_char.name, parameters={"tool_type": "Axe"})
        focused_lazy_char.decide_action(self.world)

        original_random = random.random
        def focus_override_random():
            focus_override_random.calls += 1
            if focus_override_random.calls == 1: return 0.0
            return 0.5
        focus_override_random.calls = 0
        random.random = focus_override_random

        self.run_task_for_ticks(focused_lazy_char, "Chop Wood", JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"])
        self.assertEqual(focused_lazy_char.inventory.get("Wood", 0), 1)
        random.random = original_random

    def test_strong_trait_extra_yield_generic_task(self):
        strong_char = Character(name="StrongTest", personality="strong", traits=["Strong"], skills={}, job="Woodcutter")
        self.world.add_character(strong_char)
        self.stockpile.add_item("Stone Axe", 1)
        strong_char.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=strong_char.name, parameters={"tool_type": "Axe"})
        strong_char.decide_action(self.world)

        original_random = random.random
        def strong_bonus_random():
            return 0.1
        random.random = strong_bonus_random

        self.run_task_for_ticks(strong_char, "Chop Wood", JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"])
        self.assertEqual(strong_char.inventory.get("Wood", 0), 2)
        random.random = original_random

    def test_careless_trait_extra_tool_wear_generic_task(self):
        careless_char = Character(name="CarelessTest", personality="clumsy", traits=["Careless"], skills={}, job="Woodcutter")
        self.world.add_character(careless_char)
        self.stockpile.add_item("Stone Axe", 1)
        careless_char.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=careless_char.name, parameters={"tool_type": "Axe"})
        careless_char.decide_action(self.world)

        original_durability = BLUEPRINTS["Stone Axe"]["max_durability"]

        original_random = random.random
        def careless_wear_random():
            return 0.1
        random.random = careless_wear_random

        self.run_task_for_ticks(careless_char, "Chop Wood", JOB_TASK_DEFINITIONS["Chop Wood"]["base_time_per_yield"])

        expected_durability = original_durability - 2
        self.assertEqual(careless_char.equipped_tool["durability"], expected_durability)
        random.random = original_random

    def run_craft_order_for_ticks(self, character, item_name, required_resources, craft_time, ticks):
        wo_details = {"item_name": item_name, "quantity": 1, "required_resources": required_resources}
        if item_name not in BLUEPRINTS:
            BLUEPRINTS[item_name] = {"required_resources": required_resources, "craft_time_per_unit": craft_time, "job_skill_needed": "Crafting"}
        order = WorkOrder(order_type="CraftItem", details=wo_details, creation_day=self.time.current_day)
        self.world.add_work_order(order)
        order.status = "InProgress"
        order.assigned_to = character.name
        character.active_work_order_id = order.order_id
        character.materials_gathered_for_wo = True
        character.items_crafted_for_wo = False
        character.crafting_progress = 0
        for res, qty in required_resources.items():
            character.inventory[res] = character.inventory.get(res,0) + qty
        character.current_goal = Goal(GoalType.EXECUTE_CRAFT_ORDER, assignee_id=character.name)
        for _ in range(ticks):
            character.decide_action(self.world)
            if character.items_crafted_for_wo:
                break

    def test_lazy_crafter_slower_progress(self):
        lazy_crafter = Character(name="LazyCrafter", personality="slacker", traits=["Lazy"], skills={})
        self.world.add_character(lazy_crafter)
        item_name = "TestCraftLazy"
        res = {"Wood":1}; time = 3

        original_random = random.random
        lazy_random_once_calls = [0]
        def lazy_random_once():
            lazy_random_once_calls[0] += 1
            if lazy_random_once_calls[0] == 1: return 0.0
            return 0.5
        random.random = lazy_random_once

        self.run_craft_order_for_ticks(lazy_crafter, item_name, res, time, time)
        self.assertFalse(lazy_crafter.items_crafted_for_wo)
        random.random = original_random

    def test_diligent_crafter_faster_progress(self):
        diligent_crafter = Character(name="DiligentCrafter", personality="worker", traits=["Diligent"], skills={})
        self.world.add_character(diligent_crafter)
        item_name = "TestCraftDiligent"
        res = {"Wood":1}; time = 3

        original_random = random.random
        diligent_random_once_calls = [0]
        def diligent_random_once():
            diligent_random_once_calls[0] += 1
            if diligent_random_once_calls[0] == 1: return 0.0
            return 0.5
        random.random = diligent_random_once

        self.run_craft_order_for_ticks(diligent_crafter, item_name, res, time, time -1)
        self.assertTrue(diligent_crafter.items_crafted_for_wo)
        random.random = original_random

    def test_careless_bookkeeper_miscounts(self):
        target_stockpile_name = "TestSP"
        stockpile_for_char = self.world.get_stockpile_by_name(target_stockpile_name)
        self.assertIsNotNone(stockpile_for_char)

        stockpile_for_char.inventory = {}
        stockpile_for_char.add_item("Logs", 10)
        stockpile_for_char.add_item("Stones", 5)
        self.world.ledger.update_stockpile_record(target_stockpile_name, stockpile_for_char.inventory.copy(), self.time.current_day)

        careless_bookie = Character(name="CarelessBookie", personality="distracted", traits=["Careless"], skills={}, job="Bookkeeper")
        self.world.add_character(careless_bookie)
        careless_bookie.x, careless_bookie.y = stockpile_for_char.rect[0], stockpile_for_char.rect[1]
        careless_bookie.current_goal = Goal(GoalType.COUNT_STOCKPILE, assignee_id=careless_bookie.name, parameters={"stockpile_name": target_stockpile_name})

        initial_logs = stockpile_for_char.inventory["Logs"]
        initial_stones = stockpile_for_char.inventory["Stones"]

        original_random = random.random
        miscount_triggers = [0.05, 0.5]
        def miscount_random():
            return miscount_triggers.pop(0) if miscount_triggers else 0.5
        random.random = miscount_random

        careless_bookie.decide_action(self.world)

        logs_in_ledger = self.world.ledger.get_resource_count_in_stockpile("Logs", target_stockpile_name)
        stones_in_ledger = self.world.ledger.get_resource_count_in_stockpile("Stones", target_stockpile_name)

        self.assertNotEqual(logs_in_ledger, initial_logs)
        self.assertEqual(stones_in_ledger, initial_stones)

        random.random = original_random

if __name__ == '__main__':
    unittest.main()
