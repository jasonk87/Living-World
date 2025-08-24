from __future__ import annotations
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class HaulResourceAction(Action):
    """An action for a character to haul a resource to a stockpile."""
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        params = self.character.current_goal.parameters
        sp_name = params.get("target_stockpile_name")
        res = params.get("resource")

        if not sp_name or not res or self.character.inventory.get(res, 0) == 0:
            return ActionStatus.FAILED

        sp_obj = world.get_stockpile_by_name(sp_name)
        if not sp_obj:
            return ActionStatus.FAILED

        spot = sp_obj.deposit_tiles[0] if sp_obj.deposit_tiles else (sp_obj.rect[0], sp_obj.rect[1])
        if not spot:
            return ActionStatus.FAILED

        if (self.character.x, self.character.y) == spot:
            qty_dep = self.character.inventory.get(res, 0)
            s_success, qty_add = sp_obj.add_item(res, qty_dep)
            if s_success and qty_add > 0:
                self.character.inventory[res] -= qty_add
                if self.character.inventory.get(res, 0) <= 0:
                    del self.character.inventory[res]

            is_crafted_item_haul = params.get("is_crafted_item", False)
            for_wo_id = params.get("for_wo_id")
            if is_crafted_item_haul and self.character.inventory.get(res, 0) == 0 and for_wo_id:
                order = world.get_work_order_by_id(for_wo_id)
                if order and order.assigned_to == self.character.name and order.status == "InProgress":
                    order.status = "Completed"
                self.character._reset_crafting_state()

            return ActionStatus.COMPLETED
        else:
            self.character.move_towards(spot[0], spot[1], world)
            return ActionStatus.RUNNING
