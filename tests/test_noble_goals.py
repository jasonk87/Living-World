import unittest
from game.character import Character
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game.stockpile import Stockpile
from game import config

class TestNobleGoals(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)

        self.noble = Character(
            name="Lord Farquad",
            personality="Greedy",
            traits=["Ambitious"],
            job="Noble Lord",
            rank="Noble Lord",
            money=100,
            skills={}
        )
        self.world.add_character(self.noble)

        # Setup stockpiles with some valuable resources
        sp1 = Stockpile(name="SP1", x=2, y=2, width=1, height=1)
        sp1.add_item("Wood", 50) # 50 * 2 = 100
        sp1.add_item("Stone", 20) # 20 * 3 = 60
        self.world.add_stockpile(sp1)

        # Update ledger
        self.world.ledger.update_stockpile_record(sp1.name, sp1.inventory, self.time.current_day)

    def test_collect_revenue_from_domain(self):
        # Initial state
        initial_money = self.noble.money
        self.assertEqual(self.world.last_tax_collection_day, -1)

        # Calculate expected revenue
        # Wealth = (50 Wood * 2) + (20 Stone * 3) = 100 + 60 = 160
        # Tax = 160 * 0.02 = 3.2, which will be int(3.2) = 3
        total_wealth = self.world.calculate_total_wealth()
        self.assertEqual(total_wealth, 160)
        expected_tax = int(total_wealth * config.TAX_RATE)
        self.assertEqual(expected_tax, 3)

        # Assign and execute goal
        self.noble.current_goal = Goal(GoalType.COLLECT_REVENUE_FROM_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        # Assertions
        self.assertEqual(self.noble.money, initial_money + expected_tax)
        self.assertEqual(self.world.last_tax_collection_day, self.time.current_day)
        self.assertTrue(any(f"I have collected {expected_tax} in taxes" in m for m in self.noble.memory))

    def test_collect_revenue_already_collected_today(self):
        # First collection
        self.noble.current_goal = Goal(GoalType.COLLECT_REVENUE_FROM_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        money_after_first_collection = self.noble.money

        # Try to collect again on the same day
        self.noble.current_goal = Goal(GoalType.COLLECT_REVENUE_FROM_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        # Assertions
        self.assertEqual(self.noble.money, money_after_first_collection) # Money should not change
        self.assertTrue(any("Taxes have already been collected for the day." in m for m in self.noble.memory))

if __name__ == '__main__':
    unittest.main()
