from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class CountStockpileAction(Action):
    """
    An action for a character to count the items in a stockpile and record them in the ledger.
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        stockpile_name = self.character.current_goal.parameters.get("stockpile_name")
        if not stockpile_name:
            return ActionStatus.FAILED

        stockpile = world.get_stockpile_by_name(stockpile_name)
        if not stockpile:
            return ActionStatus.FAILED

        # Step 1: Move to the stockpile
        stockpile_pos = (stockpile.rect[0], stockpile.rect[1])
        if (self.character.x, self.character.y) != stockpile_pos:
            self.character.add_memory(f"Moving to {stockpile_name} to count its contents.")
            self.character.move_towards(stockpile_pos[0], stockpile_pos[1], world)
            return ActionStatus.RUNNING

        # Step 2: At the stockpile, perform the count
        self.character.add_memory(f"Counting items in {stockpile_name}.")

        # Simulate the counting process (takes one tick)
        counted_inventory = {}
        is_careless = "Careless" in self.character.traits

        for item, quantity in stockpile.inventory.items():
            final_quantity = quantity
            # If careless, there's a chance to miscount
            if is_careless and random.random() < config.CARELESS_TRAIT_MISHAP_CHANCE:
                # This logic now uses random.random() exclusively, making it mockable.
                miscount_direction = 1 if random.random() < 0.5 else -1
                miscount_amount = miscount_direction

                # Ensure count doesn't go below zero
                if quantity + miscount_amount < 0:
                    miscount_amount = -quantity # Will result in 0

                final_quantity += miscount_amount

                if final_quantity != quantity:
                    self.character.add_memory(f"Oops, miscounted {item}. Recorded {final_quantity} instead of {quantity}.")

            counted_inventory[item] = final_quantity

        # Step 3: Update the ledger with the counted amounts
        world.ledger.update_stockpile_record(stockpile_name, counted_inventory, world.game_time.current_day)
        self.character.add_memory(f"Finished counting {stockpile_name} and updated the ledger.")

        # This action is considered complete after one tick of counting.
        return ActionStatus.COMPLETED
