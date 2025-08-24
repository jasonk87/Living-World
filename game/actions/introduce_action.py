from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class IntroduceAction(Action):
    """An action for a character to introduce themselves to a stranger."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            self.character.add_memory(f"Wanted to introduce myself to {self.target_name}, but they could not be found.")
            return ActionStatus.FAILED

        if self.target_name in self.character.known_characters:
            self.character.add_memory(f"Wanted to introduce to {self.target_name}, but I already know them. Switching to greet.")
            self.character.current_goal = Goal(GoalType.GREET_CHARACTER, assignee_id=self.character.name, originator_id=self.character.name, parameters={"target_char_name": self.target_name})
            return ActionStatus.COMPLETED

        distance = abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y)
        if distance > 2:
            self.character.add_memory(f"Trying to introduce myself to {self.target_name}, moving closer.")
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        self.character.add_memory(f"Approached {self.target_name} to introduce myself.")

        self.character.known_characters.append(self.target_name)
        if self.character.name not in target_char.known_characters:
            target_char.known_characters.append(self.character.name)

        initiator_friendly = "Friendly" in self.character.traits
        target_friendly = "Friendly" in target_char.traits

        rel_change = 1
        if initiator_friendly and target_friendly: rel_change = 3
        elif initiator_friendly: rel_change = 2

        self.character.modify_relationship(self.target_name, rel_change, world, reason=f"Introduced myself to {self.target_name}.")
        target_char.modify_relationship(self.character.name, rel_change, world, reason=f"{self.character.name} introduced themselves.")

        dialogue_line_self = f"Hello, I'm {self.character.name}."
        dialogue_line_target = f"A pleasure to meet you, {self.character.name}! I'm {self.target_name}."

        dialogue_entry = {
            "type": "introduction",
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

        fulfillment = config.SOCIAL_FULFILLMENT_GREET_INTRODUCE
        self.character.needs['Social'] = min(100, self.character.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)

        return ActionStatus.COMPLETED
