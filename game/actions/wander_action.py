from __future__ import annotations
import random
from typing import TYPE_CHECKING
from game.actions.action import Action, ActionStatus

if TYPE_CHECKING:
    from game.character import Character
    from game.world import World

class WanderAction(Action):
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        """
        Executes the wander action.

        The character will move to a random adjacent tile if possible.
        """
        moves = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            tx, ty = self.character.x + dx, self.character.y + dy
            if 0 <= tx < world.grid_size[0] and 0 <= ty < world.grid_size[1] and \
               world.get_tile(tx, ty) not in ["Water", "Mountain", "Forest", "Rocks", "SP_Mai", "SP_Woo", "SP_Sto"] and \
               not world.get_characters_at_location(tx, ty):
                moves.append((dx, dy))

        if moves:
            choice = random.choice(moves)
            self.character.move(choice[0], choice[1], world)

        return ActionStatus.COMPLETED
