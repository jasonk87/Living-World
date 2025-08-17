from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.character import Character

class Component:
    """
    A base class for components that can be attached to a character.
    """
    def __init__(self, character: Character):
        self.character = character
