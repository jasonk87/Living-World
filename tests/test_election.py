import unittest
from unittest.mock import patch
from game.character import Character
from game.world import World
from game.time import Time
from game.goal import Goal, GoalType
from game import config

class TestElectionProcess(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.world = World(grid_size=(10, 10), game_time_ref=self.time)

        self.mayor = Character(
            name="Mayor",
            personality="Kind",
            traits=["Kind"],
            job="Mayor",
            rank="Mayor",
            skills={"Leadership": 5}
        )
        self.mayor.reputation_score = 50
        self.world.add_character(self.mayor)

        self.candidate1 = Character(
            name="Candidate1",
            personality="Ambitious",
            traits=["Ambitious"],
            job="Noble",
            rank="Noble",
            skills={"Leadership": 4}
        )
        self.candidate1.reputation_score = 30
        self.world.add_character(self.candidate1)

        self.candidate2 = Character(
            name="Candidate2",
            personality="Wise",
            traits=["Intelligent", "Ambitious"],
            job="Noble",
            rank="Noble",
            skills={"Leadership": 6}
        )
        self.candidate2.reputation_score = 40
        self.world.add_character(self.candidate2)

        self.voter1 = Character(name="Voter1", personality="Neutral", traits=[], job="Worker", rank="Worker", skills={})
        self.world.add_character(self.voter1)
        self.voter2 = Character(name="Voter2", personality="Rebellious", traits=["Rebellious"], job="Worker", rank="Worker", skills={})
        self.world.add_character(self.voter2)

    def test_election_starts_and_candidates_are_selected(self):
        # Set election day
        self.world.game_time.days_until_election = 0

        self.world.handle_election()

        self.assertTrue(self.world.is_election_active)
        self.assertIn("Candidate1", self.world.candidates)
        self.assertIn("Candidate2", self.world.candidates)
        self.assertIn("Mayor", self.world.candidates)

        # Check if candidates have the correct goal
        self.assertEqual(self.candidate1.current_goal.type, GoalType.CAMPAIGN_FOR_ELECTION)
        self.assertEqual(self.candidate2.current_goal.type, GoalType.CAMPAIGN_FOR_ELECTION)

    def test_voting_logic(self):
        # Start an election
        self.world.is_election_active = True
        self.world.candidates = ["Mayor", "Candidate1", "Candidate2"]

        # Set relationships to influence vote
        self.voter1.relationships[self.candidate2.name] = 50 # Voter1 likes Candidate2
        self.voter2.relationships[self.mayor.name] = -50 # Voter2 dislikes the mayor

        # Cast votes
        self.voter1._cast_vote(self.world)
        self.voter2._cast_vote(self.world)

        # Check ballots
        self.assertEqual(self.world.ballots[self.voter1.name], self.candidate2.name)
        # Voter2 is rebellious and dislikes the mayor, should not vote for them
        self.assertNotEqual(self.world.ballots[self.voter2.name], self.mayor.name)

    @patch('random.choice', lambda x: x[0]) # Mock random.choice to be deterministic
    @patch('game.character.Character._cast_vote')
    def test_power_transfer(self, mock_cast_vote):
        # Rig the election for Candidate2
        self.world.is_election_active = True
        self.world.candidates = ["Mayor", "Candidate1", "Candidate2"]
        self.world.ballots = {
            "Voter1": "Candidate2",
            "Voter2": "Candidate2",
            "Mayor": "Mayor",
            "Candidate1": "Candidate1"
        }

        self.world.handle_election()

        # Check that Candidate2 is the new mayor
        self.assertEqual(self.candidate2.job, "Mayor")
        self.assertEqual(self.candidate2.rank, "Mayor")
        self.assertGreater(self.candidate2.reputation_score, 40)

        # Check that the old mayor was deposed
        self.assertEqual(self.mayor.job, "Noble")
        self.assertLess(self.mayor.reputation_score, 50)

        # Check that the election state is reset
        self.assertFalse(self.world.is_election_active)
        self.assertEqual(self.world.game_time.days_until_election, config.ELECTION_CYCLE_DAYS)

if __name__ == '__main__':
    unittest.main()
