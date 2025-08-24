from __future__ import annotations
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class MaintainLedgerAction(Action):
    """
    An action for a bookkeeper to maintain the ledger.
    This involves finding the most outdated stockpile and counting it.
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        if self.character.job != "Bookkeeper":
            return ActionStatus.FAILED

        stockpiles_to_check = world.stockpiles
        if not stockpiles_to_check:
            return ActionStatus.COMPLETED # No work to do

        target_sp = None
        min_day = float('inf')
        for sp_obj in stockpiles_to_check:
            day = world.ledger.get_stockpile_last_update_day(sp_obj.name)
            if day is None:
                target_sp = sp_obj
                break
            if day < world.game_time.current_day and day < min_day:
                min_day = day
                target_sp = sp_obj

        if target_sp is None:
            return ActionStatus.COMPLETED # Everything is up to date

        self.character.current_goal = Goal(GoalType.COUNT_STOCKPILE, assignee_id=self.character.name, originator_id=self.character.name, parameters={"stockpile_name": target_sp.name})
        return ActionStatus.COMPLETED # Let the new goal be handled
