from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class ManageSubordinatesAction(Action):
    """
    An action for a manager to manage their subordinates.
    This involves reviewing performance, issuing warnings, and potentially firing.
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        if not (self.character.job == "Manager" or self.character.rank in ["Noble Lord", "Baron"]) or not self.character.subordinates_names:
            return ActionStatus.FAILED

        if self.character.job == "Manager":
            self._execute_manage_work_orders_as_part_of_supervision(world)

        if not world.game_time:
            return ActionStatus.RUNNING

        for sub_name in self.character.subordinates_names:
            subordinate: Character | None = world.get_character_by_name(sub_name)
            if not subordinate or subordinate.performance_rating == "Fired":
                continue

            # In a single tick, a manager can take one significant action per subordinate.
            # The order of operations should be:
            # 1. Check for most severe action (firing).
            # 2. Check for less severe action (warning).
            # 3. If no action is taken, conduct a routine review if it's due.

            # Check for firing condition
            if subordinate.performance_rating == "Poor" and subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD:
                relationship_to_sub = self.character.get_relationship_score(subordinate.name)
                firing_chance = 0.5 # Base chance
                if "Ruthless" in self.character.traits: firing_chance += 0.25
                if "Compassionate" in self.character.traits: firing_chance -= 0.25
                if relationship_to_sub < -50: firing_chance += 0.20
                # For tests, we assume random() will be mocked to succeed.
                if random.random() < firing_chance:
                    self.character.fire_subordinate(subordinate.name, world)
                    return ActionStatus.COMPLETED # Action taken for this tick.

            # If not fired, check for warning condition
            if subordinate.performance_rating == "Poor":
                relationship_to_sub = self.character.get_relationship_score(subordinate.name)
                warning_chance = 0.3 # Base chance
                if "Strict" in self.character.traits: warning_chance += 0.2
                if "Forgiving" in self.character.traits: warning_chance -= 0.2
                if random.random() < warning_chance:
                    self.character.issue_warning(subordinate.name, world, "Poor performance.")
                    return ActionStatus.COMPLETED # Action taken for this tick.

            # If no disciplinary action was taken, check if a routine review is due.
            review_due_day = subordinate.last_performance_review_day is None or \
                             (world.game_time.current_day - subordinate.last_performance_review_day >= config.MANAGEMENT_REVIEW_INTERVAL_DAYS)
            if review_due_day:
                self.character.conduct_performance_review(subordinate.name, world)
                return ActionStatus.COMPLETED # Action taken for this tick.

        return ActionStatus.COMPLETED

    def _execute_manage_work_orders_as_part_of_supervision(self, world: 'World'):
        pending_orders = world.get_pending_work_orders()
        if not pending_orders: return
        order_to_process = pending_orders[0]
        # ... (rest of the logic from the old method)
        order_to_process.status = "Approved"
        order_to_process.approved_by = self.character.name
        order_to_process.approval_day = world.game_time.current_day
