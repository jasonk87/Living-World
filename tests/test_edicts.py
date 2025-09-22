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
        self.world.add_edict = lambda edict: self.world.edicts.append(edict)


        self.mayor = Character(
            name="Mayor McCheese",
            personality="Greedy",
            traits=["Greedy", "Ambitious"],
            job="Mayor",
            rank="Mayor",
            money=100,
            skills={}
        )
        self.world.add_character(self.mayor)

    @patch('random.choices', return_value=['Tax_Hike'])
    def test_issue_edict_tax_hike_by_greedy_mayor(self, mock_choices):
        # A greedy mayor should favor a tax hike
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)

        self.mayor.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1)
        issued_edict = self.world.edicts[0]

        # With the mock, this should always be the outcome
        self.assertEqual(issued_edict.edict_type, "Tax_Hike")
        self.assertEqual(issued_edict.issued_by, self.mayor.name)
        self.assertEqual(self.mayor.last_edict_day, self.time.current_day)
        self.assertTrue(any("I have issued the 'Tax_Hike' edict" in m for m in self.mayor.memory))

    def test_issue_edict_cooldown(self):
        # Issue first edict
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1)
        self.assertEqual(self.mayor.last_edict_day, 1)

        # Try to issue another edict on the same day
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1) # Should not have issued another edict
        self.assertTrue(any("It is too soon to issue another edict." in m for m in self.mayor.memory))

        # Advance time, but not enough to reset cooldown
        for _ in range((config.EDICT_COOLDOWN_DAYS - 1) * self.time.ticks_per_day):
            self.time.tick()
        self.assertEqual(self.time.current_day, config.EDICT_COOLDOWN_DAYS)

        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1) # Still on cooldown

        # Advance time enough to reset cooldown
        for _ in range(self.time.ticks_per_day):
            self.time.tick()
        self.assertEqual(self.time.current_day, config.EDICT_COOLDOWN_DAYS + 1)

        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 2) # Should now be able to issue a new edict

    @patch('random.choices', return_value=['Tax_Hike'])
    def test_edict_effect_and_expiration(self, mock_choices):
        # Issue a tax hike edict
        self.mayor.traits = ["Greedy"]
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)

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
        for _ in range((duration -1) * self.time.ticks_per_day):
            self.time.tick()
        self.world.update_edicts() # Check for expiration
        self.assertTrue(tax_hike_edict.is_active)
        self.assertEqual(len(self.world.edicts), 1)

        # Advance time to expiration
        for _ in range(self.time.ticks_per_day):
            self.time.tick()
        self.world.update_edicts() # Check for expiration

        self.assertEqual(len(self.world.edicts), 0) # Edict should be removed from active list

        # Verify effect is no longer active
        final_tax_rate = self.world.get_modified_tax_rate()
        self.assertAlmostEqual(final_tax_rate, initial_tax_rate)

    @patch('random.choices', side_effect=[['Tax_Hike'], ['Increased_Production']])
    def test_cannot_issue_active_edict(self, mock_choices):
        # Issue a tax hike edict
        self.mayor.traits = ["Greedy"]
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)
        self.assertEqual(len(self.world.edicts), 1)
        self.assertEqual(self.world.edicts[0].edict_type, "Tax_Hike")

        # Set cooldown to allow another edict
        self.mayor.last_edict_day = -100

        # Try to issue another edict. Since the mayor is greedy, they will try for Tax_Hike again,
        # but it should be filtered out. They should issue another edict instead.
        self.mayor.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=self.mayor.name)
        self.mayor.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 2)
        # The new edict should not be Tax_Hike
        new_edict_types = [e.edict_type for e in self.world.edicts]
        self.assertIn("Tax_Hike", new_edict_types)
        self.assertIn("Increased_Production", new_edict_types)
        self.assertTrue(any("Considered issuing an edict" not in m for m in self.mayor.memory)) # Should not fail with "unsuitable" message

    @patch('random.choices', return_value=['Curfew'])
    def test_sheriff_can_issue_curfew(self, mock_choices):
        sheriff = Character(name="Sheriff", personality="Strict", traits=["Strict"], job="Sheriff", rank="Sheriff", skills={}, money=50)
        self.world.add_character(sheriff)

        sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=sheriff.name)
        sheriff.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1)
        self.assertEqual(self.world.edicts[0].edict_type, "Curfew")
        self.assertTrue(any("I have issued the 'Curfew' edict" in m for m in sheriff.memory))

    def test_sheriff_cannot_issue_tax_hike(self):
        sheriff = Character(name="Sheriff", personality="Strict", traits=["Strict"], job="Sheriff", rank="Sheriff", skills={}, money=50)
        self.world.add_character(sheriff)

        sheriff.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=sheriff.name)
        sheriff.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 1)
        # The only edicts a sheriff can issue are Conscription and Curfew. It should not be Tax_Hike.
        self.assertNotEqual(self.world.edicts[0].edict_type, "Tax_Hike")

    def test_character_with_no_edict_permissions(self):
        # A character with a job not in ROLE_EDICTS
        crafter = Character(name="Crafter", personality="Neutral", traits=[], job="Master Craftsman", rank="Worker", skills={}, money=20)
        self.world.add_character(crafter)

        crafter.current_goal = Goal(GoalType.ISSUE_DOMAIN_EDICT, assignee_id=crafter.name)
        crafter.decide_action(self.world)

        self.assertEqual(len(self.world.edicts), 0)
        self.assertTrue(any("My role does not permit me to issue any edicts." in m for m in crafter.memory))


if __name__ == '__main__':
    unittest.main()
