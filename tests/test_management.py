import unittest
from game.character import Character
from game.world import World
from game.time import Time
from game.ledger import Ledger
from game.stockpile import Stockpile
from game.work_order import WorkOrder
from game.data import BLUEPRINTS
from game import config
from game.goal import Goal, GoalType
from game.events import EventBus

class TestManagement(unittest.TestCase):
    def setUp(self):
        self.time = Time(ticks_per_day=10)
        self.event_bus = EventBus()
        self.world = World(grid_size=(10, 10), game_time_ref=self.time, event_bus_ref=self.event_bus)

        default_personality = "neutral"
        default_traits = ["average"]

        self.supervisor = Character(name="Supervisor", personality=default_personality, traits=default_traits,
                                    job="Manager", rank="Baron", x=0, y=0, skills={})
        self.subordinate = Character(name="Subordinate", personality=default_personality, traits=default_traits,
                                     job="Bookkeeper", rank="Worker", x=1, y=0, skills={})

        self.world.add_character(self.supervisor)
        self.world.add_character(self.subordinate)

        self.supervisor.subordinates_names.append(self.subordinate.name)
        self.subordinate.supervisor_name = self.supervisor.name

        self.stockpile1 = Stockpile(name="SP1", x=2,y=2,width=1,height=1)
        self.world.add_stockpile(self.stockpile1)
        self.world.ledger.update_stockpile_record(self.stockpile1.name, {}, self.time.current_day)

    def test_performance_review_bookkeeper_good(self):
        self.world.ledger.update_stockpile_record(self.stockpile1.name, {"Wood": 10}, self.time.current_day)
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.performance_rating, "Good")

    def test_performance_review_bookkeeper_stale_ledger(self):
        self.world.ledger.update_stockpile_record(self.stockpile1.name, {"Wood": 10}, self.time.current_day - (config.STALE_THRESHOLD_DAYS + 3))
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.performance_rating, "Needs Improvement")

    def test_performance_review_resets_warnings_if_not_poor(self):
        self.subordinate.warning_count = 2
        self.subordinate.performance_rating = "Needs Improvement"
        self.world.ledger.update_stockpile_record(self.stockpile1.name, {"Wood": 10}, self.time.current_day)
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.warning_count, 0)

    def test_issue_warning(self):
        initial_warnings = self.subordinate.warning_count
        self.subordinate.performance_rating = "Poor"
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.warning_count, initial_warnings + 1)

    def test_fire_subordinate(self):
        self.subordinate.warning_count = config.FIRING_WARNING_THRESHOLD
        self.subordinate.performance_rating = "Poor"
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.job, "Unemployed")

    def test_fire_subordinate_with_active_work_order(self):
        if "Wooden Chair" not in BLUEPRINTS:
            BLUEPRINTS["Wooden Chair"] = {
                "required_resources": {"Wood": 5}, "job_skill_needed": "Carpentry",
                "type": "Furniture", "craft_time_per_unit": 5
            }
        wo_details = {"item_name": "Wooden Chair", "quantity": 1, "required_resources": BLUEPRINTS["Wooden Chair"]["required_resources"]}
        work_order_obj = WorkOrder(order_type="CraftItem", details=wo_details, creation_day=self.time.current_day)
        self.world.add_work_order(work_order_obj)
        work_order_obj.status = "InProgress"
        work_order_obj.assigned_to = self.subordinate.name
        self.subordinate.active_work_order_id = work_order_obj.order_id
        self.subordinate.job = "Master Craftsman"
        self.subordinate.warning_count = config.FIRING_WARNING_THRESHOLD
        self.subordinate.performance_rating = "Poor"
        self.supervisor.current_goal = Goal(GoalType.MANAGE_SUBORDINATES, assignee_id=self.supervisor.name)
        self.supervisor.decide_action(self.world)
        self.assertEqual(self.subordinate.job, "Unemployed")
        self.assertIsNone(self.subordinate.active_work_order_id)
        original_wo_in_world = self.world.get_work_order_by_id(work_order_obj.order_id)
        self.assertEqual(original_wo_in_world.status, "Pending")

if __name__ == '__main__':
    unittest.main()
