from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class ShareSecretAction(Action):
    """An action for a character to share a secret with another."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            return ActionStatus.FAILED

        relationship_tier = self.character.get_relationship_tier(self.target_name)
        allowed_tiers = [config.RELATIONSHIP_TIER_FAMILY, "Close Friend", "Soulmate"]
        if relationship_tier not in allowed_tiers:
            return ActionStatus.FAILED

        if abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y) > 1:
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        secret_content = random.choice(["a hidden stash of berries", "a funny dream I had"])

        dialogue_entry = {
            "type": "share_secret", "initiator": self.character.name, "target": self.target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.character.name, "line": f"(Whispering) Psst, {self.target_name}, can I tell you something?"},
                {"speaker": self.target_name, "line": "(Leans in) Of course, what is it?"}
            ]
        }
        self.character.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        self.character.modify_relationship(self.target_name, 15, world, reason="Shared a secret, building trust.")
        target_char.modify_relationship(self.character.name, 15, world, reason="Was trusted with a secret.")

        self.character.update_mood_score(10, f"Shared a secret with {self.target_name}")
        target_char.update_mood_score(10, f"Was trusted with a secret by {self.character.name}")

        belonging_increase = 15
        self.character.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.character.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)

        return ActionStatus.COMPLETED
