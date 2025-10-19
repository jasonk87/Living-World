import unittest
import random
from game.character import Character, Job
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game import config
from game.work_order import WorkOrder
from game.data import BLUEPRINTS, JOB_SALARIES

class TestNeedsAndGoals(unittest.TestCase):
    def setUp(self):
        self.time = Time()
        self.world = World(game_time_ref=self.time)

        # Ensure blueprints for testing exist
        if "Wooden Sword" not in BLUEPRINTS:
            BLUEPRINTS["Wooden Sword"] = {
                "required_resources": {"Wood": 2},
                "type": "Weapon",
                "craft_time_per_unit": 5
            }

    def test_low_esteem_generates_seek_recognition_goal(self):
        # Setup character with low esteem
        low_esteem_char = Character(name="LowEsteem", personality="Insecure", traits=[], skills={}, job=Job("Crafter", None, JOB_SALARIES.get("Crafter", 0)))
        low_esteem_char.needs['Esteem'] = config.NEED_ESTEEM_CRITICAL_THRESHOLD - 1
        self.world.add_character(low_esteem_char)

        # Mock random to ensure the goal is generated
        original_random = random.random
        random.random = lambda: 0.0 # Will pass the < 0.1 check

        # Run decide_action, which should trigger the need-driven goal consideration
        low_esteem_char.decide_action(self.world)

        # Assert
        self.assertEqual(low_esteem_char.current_goal.type, GoalType.SEEK_RECOGNITION)
        self.assertTrue(any("Feeling a deep need for recognition" in msg for msg in low_esteem_char.memory))

        # Restore random
        random.random = original_random

    def test_praise_interaction_boosts_esteem(self):
        # Setup characters
        crafter = Character(name="Crafter", personality="Focused", traits=[], skills={"Crafting": 5}, job=Job("Master Craftsman", None, JOB_SALARIES.get("Master Craftsman", 0)), x=0, y=0)
        witness = Character(name="Witness", personality="Friendly", traits=[], skills={}, job=Job("Unemployed", None, JOB_SALARIES.get("Unemployed", 0)), x=1, y=0)
        self.world.add_character(crafter)
        self.world.add_character(witness)

        # Give crafter the resources and a work order
        crafter.inventory["Wood"] = 2
        order = WorkOrder(order_type="CraftItem", details={"item_name": "Wooden Sword", "quantity": 1})
        self.world.add_work_order(order)
        order.status = "InProgress"
        order.assigned_to = crafter.name
        crafter.active_work_order_id = order.order_id
        crafter.current_goal = Goal(GoalType.EXECUTE_CRAFT_ORDER, assignee_id=crafter.name)
        crafter.materials_gathered_for_wo = True # Skip gathering
        crafter.crafting_progress = 0 # Explicitly reset for test isolation

        initial_esteem = crafter.needs.get('Esteem', 50)
        initial_relationship = witness.get_relationship_score(crafter.name)

        # Mock random to ensure the praise is triggered
        original_random = random.random
        random.random = lambda: 0.0 # Will pass the < 0.2 check for witness to be impressed

        # Run crafter's action for enough ticks to complete the item
        craft_time = BLUEPRINTS["Wooden Sword"]["craft_time_per_unit"]
        for _ in range(craft_time + 1): # Add one extra tick for safety
            crafter.decide_action(self.world)
            if crafter.items_crafted_for_wo:
                break

        self.assertTrue(crafter.items_crafted_for_wo, "Crafter should have finished the item.")

        # At this point, the witness's goal should be to praise the crafter
        self.assertEqual(witness.current_goal.type, GoalType.PRAISE_CHARACTER)
        self.assertEqual(witness.current_goal.parameters["target_char_name"], crafter.name)

        # Now, run the witness's action to execute the praise
        witness.decide_action(self.world) # This will call _execute_praise_character

        # Assertions
        final_esteem = crafter.needs.get('Esteem', 50)
        final_relationship = witness.get_relationship_score(crafter.name)

        self.assertGreater(final_esteem, initial_esteem, "Crafter's esteem should have increased after being praised.")
        self.assertGreater(final_relationship, initial_relationship, "Witness's relationship with crafter should improve.")
        self.assertTrue(any(f"I was praised by {witness.name}" in msg for msg in crafter.memory))
        self.assertTrue(any(f"I praised {crafter.name}" in msg for msg in witness.memory))

        # Restore random
        random.random = original_random

if __name__ == '__main__':
    unittest.main()
