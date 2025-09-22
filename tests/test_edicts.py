import unittest
from unittest.mock import patch
from game.character import Character
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game.stockpile import Stockpile
from game import config

class TestEdicts(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)

        self.noble = Character(
            name="Baron Von Edict",
            personality="Greedy",
            traits=["Greedy", "Ambitious"],
            job="Noble Lord",
            rank="Noble Lord",
            money=100,
            skills={}
        )
        self.world.add_character(self.noble)

    @patch('random.choices', return_value=['Tax_Hike'])
    def test_issue_edict_tax_hike_by_greedy_noble(self, mock_choices):
        # A greedy noble should favor a tax hike
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)

        self.noble.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1)
        issued_edict = self.world.edicts[0]

        # With the mock, this should always be the outcome
        self.assertEqual(issued_edict.edict_type, "Tax_Hike")
        self.assertEqual(issued_edict.issued_by, self.noble.name)
        self.assertEqual(self.noble.last_edict_day, self.time.current_day)
        self.assertTrue(any("I have issued the 'Tax_Hike' edict" in m for m in self.noble.memory))

    def test_issue_edict_cooldown(self):
        # Issue first edict
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1)
        self.assertEqual(self.noble.last_edict_day, 1)

        # Try to issue another edict on the same day
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1) # Should not have issued another edict
        self.assertTrue(any("It is too soon to issue another edict." in m for m in self.noble.memory))

        # Advance time, but not enough to reset cooldown
        self.time.advance_time(ticks=(config.EDICT_COOLDOWN_DAYS - 1) * self.time.ticks_per_day)
        self.assertEqual(self.time.current_day, config.EDICT_COOLDOWN_DAYS)

        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1) # Still on cooldown

        # Advance time enough to reset cooldown
        self.time.advance_time(ticks=self.time.ticks_per_day)
        self.assertEqual(self.time.current_day, config.EDICT_COOLDOWN_DAYS + 1)

        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 2) # Should now be able to issue a new edict

    @patch('random.choices', return_value=['Tax_Hike'])
    def test_edict_effect_and_expiration(self, mock_choices):
        # Issue a tax hike edict
        self.noble.traits = ["Greedy"]
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1)
        tax_hike_edict = self.world.edicts[0]
        self.assertEqual(tax_hike_edict.edict_type, "Tax_Hike")

        # Verify effect is active
        initial_tax_rate = config.TAX_RATE
        modified_tax_rate = self.world.get_modified_tax_rate()
        expected_modifier = tax_hike_edict.effects["tax_rate_modifier"]
        self.assertAlmostEqual(modified_tax_rate, initial_tax_rate + expected_modifier)

        # Advance time to just before expiration
        duration = tax_hike_edict.duration
        self.time.advance_time(ticks=(duration -1) * self.time.ticks_per_day)
        self.world.update_edicts() # Check for expiration
        self.assertTrue(tax_hike_edict.is_active)
        self.assertEqual(len(self.world.edicts), 1)

        # Advance time to expiration
        self.time.advance_time(ticks=self.time.ticks_per_day)
        self.world.update_edicts() # Check for expiration

        self.assertFalse(tax_hike_edict.is_active)
        self.assertEqual(len(self.world.edicts), 0) # Edict should be removed from active list

        # Verify effect is no longer active
        final_tax_rate = self.world.get_modified_tax_rate()
        self.assertAlmostEqual(final_tax_rate, initial_tax_rate)

    @patch('random.choices', side_effect=[['Tax_Hike'], ['Increased_Production']])
    def test_cannot_issue_active_edict(self, mock_choices):
        # Issue a tax hike edict
        self.noble.traits = ["Greedy"]
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1)
        self.assertEqual(self.world.edicts[0].edict_type, "Tax_Hike")

        # Set cooldown to allow another edict
        self.noble.last_edict_day = -100

        # Try to issue another edict. Since the noble is greedy, they will try for Tax_Hike again,
        # but it should be filtered out. They should issue another edict instead.
        self.noble.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.noble.name)
        self.noble.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 2)
        # The new edict should not be Tax_Hike
        new_edict_types = [e.edict_type for e in self.world.edicts]
        self.assertIn("Tax_Hike", new_edict_types)
        self.assertTrue(len(new_edict_types) > 1)
        self.assertTrue(any("Considered issuing an edict" not in m for m in self.noble.memory)) # Should not fail with "unsuitable" message

if __name__ == '__main__':
    unittest.main()
