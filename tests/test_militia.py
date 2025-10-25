import unittest
from unittest.mock import MagicMock, patch
from game.character import Character
from game.world import World
from game.goal import Goal, GoalType
from game.building import Building
from game.data import STRUCTURE_BLUEPRINTS
from game.stockpile import Stockpile
import game.config as config

class TestMilitiaSystem(unittest.TestCase):

    def setUp(self):
        self.world = World(grid_size=(10, 10))
        self.world.game_time = MagicMock()
        self.world.game_time.current_day = 1

        self.world.add_stockpile(Stockpile("Main Stockpile", 0, 0, 2, 2))

        self.commander = Character(name="Commander", personality="Brave", traits=["Leader"], skills={"Leadership": 5, "Security": 3}, x=5, y=5, needs={})
        self.world.add_character(self.commander)
        self.commander.job = MagicMock()
        self.commander.job.title = "Militia Commander"
        # Mock leadership oversight score for deterministic readiness calculation
        self.commander.leadership_oversight_score = 0.8


        self.soldier1 = Character(name="Soldier1", personality="Loyal", traits=[], skills={"Security": 5}, x=5, y=6, needs={})
        self.world.add_character(self.soldier1)
        self.soldier1.job = MagicMock()
        self.soldier1.job.title = "Militia Soldier"

        self.soldier2 = Character(name="Soldier2", personality="Cautious", traits=[], skills={"Security": 4}, x=6, y=5, needs={})
        self.world.add_character(self.soldier2)
        self.soldier2.job = MagicMock()
        self.soldier2.job.title = "Militia Soldier"

    def test_militia_commander_assigns_training(self):
        # Set readiness to a low value to trigger training
        self.world.military_structure["readiness"] = 0.1
        self.commander.decide_action(self.world)

        # Commander should assign a training goal to the soldiers
        # This depends on the commander's AI logic for assigning goals.
        # Assuming commander assigns goals to nearby soldiers.
        nearby_soldiers = self.world.get_nearby_characters(self.commander, radius=2)

        # Check that soldiers have been assigned training goals
        for soldier in nearby_soldiers:
            if soldier.job.title == "Militia Soldier":
                self.assertIsNotNone(soldier.current_goal)
                self.assertEqual(soldier.current_goal.type, GoalType.TRAIN_COMBAT)

    def test_militia_commander_assigns_patrols(self):
        # Set readiness to a high value to trigger patrols
        self.world.military_structure["readiness"] = 0.8
        self.commander.decide_action(self.world)

        nearby_soldiers = self.world.get_nearby_characters(self.commander, radius=2)

        # Check that soldiers have been assigned guard/patrol goals
        for soldier in nearby_soldiers:
            if soldier.job.title == "Militia Soldier":
                self.assertIsNotNone(soldier.current_goal)
                self.assertEqual(soldier.current_goal.type, GoalType.GUARD_LOCATION)

    def test_soldier_training_increases_security_skill(self):
        training_yard_blueprint = STRUCTURE_BLUEPRINTS["training_yard"]
        training_yard = Building(
            structure_type="training_yard",
            display_name="Training Yard",
            location=(3, 3),
            size=training_yard_blueprint['size'],
            functionality=training_yard_blueprint['functionality'],
            required_resources=training_yard_blueprint['required_resources'],
            required_skill=training_yard_blueprint.get('required_skill')
        )
        training_yard.is_operational = True
        self.world.add_building(training_yard)

        self.soldier2.skills['Security'] = {'level': 1, 'experience': 0.0, 'exp_to_next_level': 10.0}
        initial_exp = self.soldier2.skills["Security"].get("experience", 0)

        # Set soldier's goal and position
        self.soldier2.x, self.soldier2.y = 3,3
        self.soldier2.current_goal = Goal(GoalType.TRAIN_COMBAT, self.soldier2.name, "Commander")

        # Execute training action
        self.soldier2.decide_action(self.world)

        final_exp = self.soldier2.skills["Security"].get("experience", 0)
        self.assertGreater(final_exp, initial_exp)

    def test_raid_breaches_defenses_without_watchtower(self):
        # Mock a raid scenario
        with patch.dict(config.ENEMY_RAID_PROFILE, {
            "base_chance": 1.0, "readiness_factor": 0.5, "difficulty": 0.35,
            "severity_weights": {"skirmish": 1.0}, "severity_difficulty": {"skirmish": 1.0},
            "resource_targets": ["Food"], "losses": {"skirmish": (2, 5)}, "max_log_entries": 6
            }):
            with patch.object(self.world, '_military_rng', new_callable=MagicMock) as mock_rng:
                mock_rng.random.return_value = 0.0 # Ensure raid triggers
                mock_rng.uniform.return_value = 0.0 # Ensure skirmish severity
                mock_rng.randint.return_value = 3 # loss_amount

                # Run military daily process without a watchtower
                self.world.process_military_daily()

                raid_entry = self.world.military_structure["enemy_activity"][0]
                self.assertEqual(raid_entry["outcome"], "breached")

    def test_raid_repelled_with_watchtower(self):
        # Add a watchtower
        watchtower_blueprint = STRUCTURE_BLUEPRINTS["watchtower"]
        watchtower = Building(
            structure_type="watchtower",
            display_name="Watchtower",
            location=(1, 1),
            size=watchtower_blueprint['size'],
            functionality=watchtower_blueprint['functionality'],
            required_resources=watchtower_blueprint['required_resources'],
            required_skill=watchtower_blueprint.get('required_skill')
        )
        watchtower.is_operational = True
        self.world.add_building(watchtower)

        # Mock a raid scenario
        with patch.dict(config.ENEMY_RAID_PROFILE, {
            "base_chance": 1.0, "readiness_factor": 0.5, "difficulty": 0.35,
            "severity_weights": {"skirmish": 1.0}, "severity_difficulty": {"skirmish": 1.0},
            "resource_targets": ["Food"], "losses": {"skirmish": (2, 5)}, "max_log_entries": 6
            }):
            with patch.object(self.world, '_military_rng', new_callable=MagicMock) as mock_rng:
                mock_rng.random.return_value = 0.0 # Ensure raid triggers
                mock_rng.uniform.return_value = 0.0 # Ensure skirmish severity
                mock_rng.randint.return_value = 3 # loss_amount

                # Run military daily process
                self.world.process_military_daily()

                raid_entry = self.world.military_structure["enemy_activity"][0]
                self.assertEqual(raid_entry["outcome"], "repelled")


if __name__ == '__main__':
    unittest.main()
