from __future__ import annotations
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..data import JOB_TASK_DEFINITIONS
from ..goal import Goal, GoalType

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class GatherResourceAction(Action):
    """An action for a character to gather a resource."""
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        resource_name = self.character.current_goal.parameters.get("resource_name")
        task_name = self.character.current_goal.parameters.get("task_name")
        quota = self.character.current_goal.parameters.get("quota", float('inf'))

        if not resource_name or not task_name:
            return ActionStatus.FAILED

        task_loc = self.character.find_task_location(task_name, world)
        if not task_loc:
            return ActionStatus.FAILED

        if (self.character.x, self.character.y) != task_loc:
            self.character.move_towards(task_loc[0], task_loc[1], world)
            return ActionStatus.RUNNING

        if not self._execute_generic_task(world, task_name):
            return ActionStatus.RUNNING # Switched to Fetch Tool

        inv_val = self.character.inventory.get(resource_name, 0)
        if self.character.get_inventory_load() >= self.character.max_inventory_items or inv_val >= quota:
            return ActionStatus.COMPLETED

        return ActionStatus.RUNNING

    def _execute_generic_task(self, world: 'World', task_name: str) -> bool:
        task_def = JOB_TASK_DEFINITIONS[task_name]
        tool_type = task_def.get("required_tool_type")
        if tool_type and (not self.character.equipped_tool or self.character.equipped_tool.get("tool_type") != tool_type):
            if not self.character.goal_before_fetching_tool:
                self.character.goal_before_fetching_tool = self.character.current_goal
            self.character.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=self.character.name, originator_id=self.character.name, parameters={"tool_type": tool_type})
            self.character.tool_to_fetch_type = tool_type
            self.character.task_work_progress = 0
            return False

        # ... (rest of the logic from the old _execute_generic_task)
        # This will be filled in a later step if needed. For now, assume it works.
        self.character.task_work_progress += 1
        if self.character.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            if res_prod:
                self.character.inventory[res_prod] = self.character.inventory.get(res_prod, 0) + 1
            self.character.task_work_progress = 0

        return True
