import unittest
import random
from game.character import Character, Job
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game import config
from game.work_order import WorkOrder
from game.data import BLUEPRINTS, JOB_SALARIES
from game.building import Building

def _basic_needs() -> dict[str, int]:
    return {
        "Hunger": 80,
        "Thirst": 80,
        "Energy": 95,
        "Social": 70,
        "Safety": config.NEED_SAFETY_DEFAULT,
        "Belonging": config.NEED_BELONGING_DEFAULT,
        "Esteem": config.NEED_ESTEEM_DEFAULT,
    }

class TestNeedsAndGoals(unittest.TestCase):
    def setUp(self):
        self.time = Time()
        self.world = World(game_time_ref=self.time)

        # Ensure blueprints for testing exist
        if "Wooden Sword" not in BLUEPRINTS:
            BLUEPRINTS["Wooden Sword"] = {
                "required_resources": {"Wood": 2},
                "type": "Weapon",
                "craft_time_per_unit": 5,
                "required_skill": "Woodworking"
            }

        # Add a workshop for the test
        carpentry_shop = Building(
            structure_type='carpenters_shop',
            display_name="Carpenter's Shop",
            location=(0, 1),
            size=(3, 2),
            functionality={"allows_crafting_category": ["carpentry"], "tags": ["indoor", "workshop", "woodworking"]},
            required_resources={},
            required_skill=None
        )
        carpentry_shop.is_operational = True
        self.world.add_building(carpentry_shop)

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
        crafter = Character(name="Crafter", personality="Focused", traits=[], skills={"Woodworking": 5}, job=Job("Carpenter", None, JOB_SALARIES.get("Carpenter", 0)), x=0, y=0)
        witness = Character(name="Witness", personality="Friendly", traits=[], skills={}, job=Job("Unemployed", None, JOB_SALARIES.get("Unemployed", 0)), x=1, y=0)
        self.world.add_character(crafter)
        self.world.add_character(witness)

        # Give crafter the resources and a work order
        crafter.inventory["Wood"] = 2
        crafter.inventory["Saw"] = 1
        crafter.equip_tool("Saw")
        order = WorkOrder(order_type="CraftItem", details={"item_name": "Wooden Sword", "quantity": 1})
        self.world.add_work_order(order)
        order.status = "Approved"
        crafter.materials_gathered_for_wo = True # Skip gathering
        crafter.crafting_progress = 0 # Explicitly reset for test isolation

        initial_esteem = crafter.needs.get('Esteem', 50)
        initial_relationship = witness.get_relationship_score(crafter.name)

        # Mock random to ensure the praise is triggered
        original_random = random.random
        random.random = lambda: 0.0 # Will pass the < 0.2 check for witness to be impressed

        # Assign the craft order goal to the crafter
        crafter.active_work_order_id = order.order_id
        crafter.current_goal = Goal(GoalType.EXECUTE_CRAFT_ORDER, assignee_id=crafter.name, originator_id="Test", parameters={"order_id": order.order_id})

        # Run the crafter's action until the item is crafted and witness's goal changes
        craft_time = BLUEPRINTS["Wooden Sword"]["craft_time_per_unit"]
        for _ in range(craft_time + 5):  # Add extra ticks for safety
            crafter.decide_action(self.world)
            if witness.current_goal.type == GoalType.PRAISE_CHARACTER:
                break

        # 1. Assert that the crafter finished and the witness's goal is correctly set
        self.assertTrue(crafter.items_crafted_for_wo, "Crafter should have finished the item.")
        self.assertEqual(witness.current_goal.type, GoalType.PRAISE_CHARACTER, "Witness's goal should be to praise the crafter.")
        self.assertEqual(witness.current_goal.parameters["target_char_name"], crafter.name)

        # 2. Now, execute the witness's action to perform the praise
        witness.decide_action(self.world)

        # 3. Assert the effects of the praise
        final_esteem = crafter.needs.get('Esteem', 50)
        final_relationship = witness.get_relationship_score(crafter.name)

        self.assertGreater(final_esteem, initial_esteem, "Crafter's esteem should have increased after being praised.")
        self.assertGreater(final_relationship, initial_relationship, "Witness's relationship with crafter should improve.")
        self.assertTrue(any(f"I was praised by {witness.name}" in msg for msg in crafter.memory), "Crafter memory should contain praise event.")
        self.assertTrue(any(f"I praised {crafter.name}" in msg for msg in witness.memory), "Witness memory should contain praise event.")

        # Restore random
        random.random = original_random

if __name__ == '__main__':
    unittest.main()
