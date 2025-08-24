from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class SmallTalkAction(Action):
    """An action for a character to engage in small talk."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            return ActionStatus.FAILED

        if self.target_name not in self.character.known_characters:
            return ActionStatus.FAILED

        if abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y) > 2:
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        dialogue_line_self = "The weather's been something else lately, hasn't it?"
        dialogue_line_target = "Indeed it has."

        dialogue_entry = {
            "type": "small_talk",
            "initiator": self.character.name,
            "target": self.target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.character.name, "line": dialogue_line_self},
                {"speaker": self.target_name, "line": dialogue_line_target}
            ]
        }
        self.character.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        fulfillment = config.SOCIAL_FULFILLMENT_SMALL_TALK
        self.character.needs['Social'] = min(100, self.character.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)

        return ActionStatus.COMPLETED
