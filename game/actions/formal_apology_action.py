from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config
from ..rumor import Rumor

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class FormalApologyAction(Action):
    """An action for a character to formally apologize to another."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            return ActionStatus.FAILED

        if abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y) > 2:
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        base_acceptance_chance = 0.4
        if "Forgiving" in target_char.traits: base_acceptance_chance += 0.25
        if "Grumpy" in target_char.traits or "Stern" in target_char.personality: base_acceptance_chance -= 0.2

        target_relationship_tier = target_char.get_relationship_tier(self.character.name)
        if target_relationship_tier in ["Friend", "Close Friend", "Family", "Soulmate"]: base_acceptance_chance += 0.2
        elif target_relationship_tier in ["Rival", "Archenemy"]: base_acceptance_chance -= 0.3

        target_mood_effect = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(target_char.mood, 0.0)
        final_acceptance_chance = base_acceptance_chance - target_mood_effect
        final_acceptance_chance = max(0.05, min(0.95, final_acceptance_chance))

        dialogue_line_self = f"I've been thinking, {self.target_name}, and I wanted to sincerely apologize for my behavior earlier."

        if random.random() < final_acceptance_chance:
            dialogue_line_target = random.choice([f"Thank you, {self.character.name}. I appreciate that.", "It takes courage to apologize. Accepted."])
            relationship_change = 10 + (5 if "Forgiving" in target_char.traits else 0)
            self.character.update_mood_score(8, f"Apology accepted by {self.target_name}")
            target_char.update_mood_score(5, f"Accepted apology from {self.character.name}")
            self.character.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.character.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5)
            self.character.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.character.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + 7)
            target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + 5)
            self.character.update_reputation(config.REPUTATION_CHANGE_APOLOGY_ACCEPTED, f"Successfully apologized to {self.target_name}")
        else:
            dialogue_line_target = random.choice([f"I hear you, {self.character.name}, but I need some more time.", "Words are easy. Let's see if your actions change."])
            relationship_change = 2
            self.character.update_mood_score(-2, f"Apology to {self.target_name} was met with skepticism.")
            target_char.update_mood_score(1, f"{self.character.name} apologized, I'm considering it.")
            self.character.needs['Belonging'] = max(config.NEED_SCORE_MIN, self.character.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 3)

        self.character.modify_relationship(self.target_name, relationship_change, world, reason="Formal apology offered.")
        target_char.modify_relationship(self.character.name, relationship_change // 2, world, reason=f"{self.character.name} offered an apology.")

        return ActionStatus.COMPLETED
