import unittest
from unittest.mock import patch
from game.character import Character
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game.stockpile import Stockpile
from game.edict import EdictStatus
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

    @patch('random.random', return_value=0.5)
    def test_oversee_domain_diligent_noble(self, mock_random):
        self.noble.traits = ["Diligent"]
        self.noble.current_goal = Goal(GoalType.OVERSEE_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(self.noble.current_goal.type, GoalType.PATROL_AREA)
        self.assertTrue(any("diligent noble, I will patrol" in m for m in self.noble.memory))

    @patch('random.random', return_value=0.5)
    def test_oversee_domain_greedy_noble(self, mock_random):
        self.noble.traits = ["Greedy"]
        self.noble.current_goal = Goal(GoalType.OVERSEE_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(self.noble.current_goal.type, GoalType.COLLECT_REVENUE_FROM_DOMAIN)
        self.assertTrue(any("greedy noble, I will assess the wealth" in m for m in self.noble.memory))

    @patch('random.random', return_value=0.5)
    def test_oversee_domain_sociable_noble(self, mock_random):
        self.noble.traits = ["Sociable"]
        self.noble.current_goal = Goal(GoalType.OVERSEE_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(self.noble.current_goal.type, GoalType.WANDER)
        self.assertEqual(self.noble.current_goal.parameters.get("reason"), "socializing")
        self.assertTrue(any("sociable noble, I will wander" in m for m in self.noble.memory))

    @patch('random.random', return_value=0.5)
    def test_oversee_domain_lazy_noble(self, mock_random):
        self.noble.traits = ["Lazy"]
        self.noble.current_goal = Goal(GoalType.OVERSEE_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(self.noble.current_goal.type, GoalType.IDLE)
        self.assertTrue(any("lazy noble, I will find a comfortable spot" in m for m in self.noble.memory))

    @patch('random.random', return_value=0.5)
    def test_oversee_domain_default_noble(self, mock_random):
        self.noble.traits = ["Average"] # A neutral trait
        self.noble.current_goal = Goal(GoalType.OVERSEE_DOMAIN, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(self.noble.current_goal.type, GoalType.WANDER)
        self.assertNotIn("reason", self.noble.current_goal.parameters) # Should not have a specific reason
        self.assertTrue(any("wander my domain, observing" in m for m in self.noble.memory))


if __name__ == '__main__':
    unittest.main()

class TestEdictReviewProcess(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)

        self.mayor = Character(
            name="Mayor McCheese",
            personality="Kind",
            traits=["Kind", "Diplomatic"],
            job="Mayor",
            rank="Mayor",
            money=500,
            skills={}
        )
        self.world.add_character(self.mayor)

        self.sheriff = Character(
            name="Sheriff of Nottingham",
            personality="Strict",
            traits=["Strict"],
            job="Sheriff",
            rank="Sheriff",
            money=50,
            skills={}
        )
        self.world.add_character(self.sheriff)

        # Establish relationship
        self.mayor.relationships[self.sheriff.name] = 20
        self.sheriff.relationships[self.mayor.name] = 20

    def test_sheriff_issues_edict_it_becomes_pending(self):
        # Sheriff issues an edict
        self.sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.sheriff.name)
        self.sheriff.decide_action(self.world)

        # Check that an edict was created and is pending
        self.assertEqual(len(self.world.edicts), 1)
        edict = self.world.edicts[0]
        self.assertEqual(edict.issued_by, self.sheriff.name)
        self.assertEqual(edict.status, EdictStatus.PENDING)

    def test_mayor_chooses_to_review_pending_edicts(self):
        # Sheriff issues a pending edict first
        self.sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.sheriff.name)
        self.sheriff.decide_action(self.world)
        self.assertEqual(self.world.edicts[0].status, EdictStatus.PENDING)

        # Mayor's turn to act, should see the pending edict
        self.mayor.current_goal = Goal(GoalType.OVERSEE_SETTLEMENT, assignee_id=self.mayor.name)
        with patch('random.random', return_value=0.1): # Ensure the 50% chance passes
            self.mayor.decide_action(self.world)

        # Check if the mayor's goal is now to review edicts
        self.assertEqual(self.mayor.current_goal.type, GoalType.REVIEW_PENDING_EDICTS)
        self.assertTrue(any("pending edicts that require my attention" in m for m in self.mayor.memory))

    def test_mayor_approves_edict(self):
        # Sheriff issues a pending edict
        self.sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.sheriff.name)
        self.sheriff.decide_action(self.world)
        edict = self.world.edicts[0]
        self.assertEqual(edict.status, EdictStatus.PENDING)

        initial_relationship = self.mayor.get_relationship_score(self.sheriff.name)

        # Mayor reviews and approves the edict
        self.mayor.current_goal = Goal(GoalType.REVIEW_PENDING_EDICTS, assignee_id=self.mayor.name)
        with patch('random.random', return_value=0.1): # Ensure approval
            self.mayor.decide_action(self.world)

        # Check edict status and relationship
        self.assertEqual(edict.status, EdictStatus.ACTIVE)
        self.assertGreater(self.mayor.get_relationship_score(self.sheriff.name), initial_relationship)
        self.assertTrue(any(f"approved the '{edict.edict_type}' edict" in m for m in self.mayor.memory))

    def test_mayor_rejects_edict(self):
        # Sheriff issues a pending edict
        self.sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.sheriff.name)
        self.sheriff.decide_action(self.world)
        edict = self.world.edicts[0]
        self.assertEqual(edict.status, EdictStatus.PENDING)

        initial_relationship = self.mayor.get_relationship_score(self.sheriff.name)

        # Mayor reviews and rejects the edict
        self.mayor.current_goal = Goal(GoalType.REVIEW_PENDING_EDICTS, assignee_id=self.mayor.name)
        with patch('random.random', return_value=0.9): # Ensure rejection
            self.mayor.decide_action(self.world)

        # Check edict status and relationship
        self.assertEqual(edict.status, EdictStatus.REJECTED)
        self.assertLess(self.mayor.get_relationship_score(self.sheriff.name), initial_relationship)
        self.assertTrue(any(f"rejected the '{edict.edict_type}' edict" in m for m in self.mayor.memory))
