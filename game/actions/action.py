from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.character import Character
    from game.world import World

class ActionStatus(Enum):
    """
    Represents the status of an action.
    """
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()

class Action:
    """
    Represents a base class for all actions a character can perform.
    """
    def __init__(self, character: Character):
        self.character = character

    def execute(self, world: World) -> ActionStatus:
        """
        Executes the action.

        This method should be overridden by subclasses to implement the specific
        logic for the action.

        :param world: The game world.
        :return: The status of the action after execution.
        """
        raise NotImplementedError("Subclasses must implement the execute method.")
