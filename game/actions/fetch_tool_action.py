from __future__ import annotations
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..data import BLUEPRINTS

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class FetchToolAction(Action):
    """
    An action for a character to fetch a required tool from a stockpile.
    """
    def __init__(self, character: Character):
        super().__init__(character)
        self.target_stockpile = None

    def execute(self, world: World) -> ActionStatus:
        tool_type = self.character.current_goal.parameters.get("tool_type")
        if not tool_type:
            return ActionStatus.FAILED

        # Step 1: Find a stockpile with the required tool if not already targeted
        if self.target_stockpile is None:
            for stockpile in world.stockpiles:
                for item_name, quantity in stockpile.inventory.items():
                    blueprint = BLUEPRINTS.get(item_name)
                    if blueprint and blueprint.get("type") == "Tool" and blueprint.get("tool_type") == tool_type and quantity > 0:
                        self.target_stockpile = stockpile
                        break
                if self.target_stockpile:
                    break

        if not self.target_stockpile:
            self.character.add_memory(f"Cannot find a {tool_type} in any stockpile.")
            return ActionStatus.FAILED # No tool found anywhere

        # Step 2: Move to the stockpile
        stockpile_pos = (self.target_stockpile.rect[0], self.target_stockpile.rect[1])
        if (self.character.x, self.character.y) != stockpile_pos:
            self.character.add_memory(f"Moving to {self.target_stockpile.name} to get a {tool_type}.")
            self.character.move_towards(stockpile_pos[0], stockpile_pos[1], world)
            return ActionStatus.RUNNING

        # Step 3: At the stockpile, take the tool
        tool_to_take = None
        for item_name, quantity in self.target_stockpile.inventory.items():
            blueprint = BLUEPRINTS.get(item_name)
            if blueprint and blueprint.get("type") == "Tool" and blueprint.get("tool_type") == tool_type and quantity > 0:
                tool_to_take = item_name
                break

        if not tool_to_take:
            # Tool might have been taken by someone else
            self.character.add_memory(f"Arrived at {self.target_stockpile.name}, but the {tool_type} is gone.")
            self.target_stockpile = None # Reset to find a new stockpile next tick
            return ActionStatus.RUNNING

        # Take the tool from the stockpile
        success, qty_taken = self.target_stockpile.remove_item(tool_to_take, 1)
        if success and qty_taken > 0:
            # Equip the tool
            self.character.equipped_tool = {
                "name": tool_to_take,
                "durability": BLUEPRINTS[tool_to_take]["max_durability"]
            }
            self.character.add_memory(f"Equipped a {tool_to_take}.")

            # Restore the original goal if one was saved
            if self.character.goal_before_fetching_tool:
                self.character.current_goal = self.character.goal_before_fetching_tool
                self.character.goal_before_fetching_tool = None

            return ActionStatus.COMPLETED
        else:
            # Failed to take the tool for some reason
            self.character.add_memory(f"Failed to take the {tool_type} from {self.target_stockpile.name}.")
            self.target_stockpile = None
            return ActionStatus.FAILED
