from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class GreetAction(Action):
    """An action for a character to greet another character."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            self.character.add_memory(f"Wanted to greet {self.target_name}, but they could not be found.")
            return ActionStatus.FAILED

        distance = abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y)
        if distance > 2:
            self.character.add_memory(f"Trying to greet {self.target_name}, but they are too far away. Moving closer.")
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        # --- At Greeting Distance ---
        self.character.add_memory(f"Approached {target_char.name} to greet them.")

        if self.target_name not in self.character.known_characters:
            self.character.known_characters.append(self.target_name)
        if self.character.name not in target_char.known_characters:
            target_char.known_characters.append(self.character.name)

        initiator_friendly = "Friendly" in self.character.traits
        initiator_grumpy = "Grumpy" in self.character.traits
        target_friendly = "Friendly" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        base_rel_change_initiator_to_target = 0
        if self.target_name not in self.character.relationships:
            if initiator_friendly and target_friendly: base_rel_change_initiator_to_target = 3
            elif initiator_friendly and not target_grumpy: base_rel_change_initiator_to_target = 2
            self.character.modify_relationship(self.target_name, base_rel_change_initiator_to_target, world, reason=f"First impression of {self.target_name}.")

        if self.character.name not in target_char.relationships:
            base_rel_change_target_to_initiator = 1
            if target_friendly and initiator_friendly: base_rel_change_target_to_initiator = 3
            target_char.modify_relationship(self.character.name, base_rel_change_target_to_initiator, world, reason=f"First impression of {self.character.name}.")

        if initiator_friendly:
            dialogue_line_self = f"Well hello there, {self.target_name}!"
        elif initiator_grumpy:
            dialogue_line_self = f"{self.target_name}."
        else:
            dialogue_line_self = f"Hello, {self.target_name}."

        if target_friendly:
            dialogue_line_target = f"And a good day to you too, {self.character.name}!"
        elif target_grumpy:
            dialogue_line_target = "Hmph."
        else:
            dialogue_line_target = f"Hello, {self.character.name}."

        dialogue_entry = {
            "type": "greeting",
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

        self.character.add_memory(f"Greeted {self.target_name}. Said: '{dialogue_line_self}'.")
        target_char.add_memory(f"Was greeted by {self.character.name}. They said: '{dialogue_line_self}'. I replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.character.name} greeted {self.target_name}.")

        fulfillment = config.SOCIAL_FULFILLMENT_GREET_INTRODUCE
        self.character.needs['Social'] = min(100, self.character.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)

        return ActionStatus.COMPLETED
