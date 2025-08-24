from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config
from ..rumor import Rumor

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class AskForHelpAction(Action):
    """An action for a character to ask another for help."""
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        params = self.character.current_goal.parameters
        target_name = params.get("target_char_name")
        if not target_name:
            self.character.add_memory("Wanted to ask for help, but no target specified.")
            return ActionStatus.FAILED

        target_char = world.get_character_by_name(target_name)
        if not target_char:
            self.character.add_memory(f"Wanted to ask {target_name} for help, but they could not be found.")
            return ActionStatus.FAILED

        if target_name not in self.character.known_characters:
            self.character.add_memory(f"Wanted to ask {target_name} for help, but I don't know them.")
            return ActionStatus.FAILED

        distance = abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y)
        if distance > 2:
            self.character.add_memory(f"Trying to ask {target_name} for help, moving closer.")
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        help_type = params.get("help_type", "general")
        item_name_needed = params.get("item_name")
        quantity_needed = params.get("quantity", 1)

        self.character.add_memory(f"Approaching {target_name} to ask for {help_type} help" + (f" with {item_name_needed}" if item_name_needed else "") + ".")

        can_help = False
        willing_to_help = False

        base_willingness_chance = 0.2
        if "Generous" in target_char.traits or "Kind" in target_char.traits: base_willingness_chance = 0.7
        elif "Selfish" in target_char.traits or "Grumpy" in target_char.traits: base_willingness_chance = 0.05

        target_relationship_tier_to_initiator = target_char.get_relationship_tier(self.character.name)
        tier_modifier = config.RELATIONSHIP_ASK_FOR_HELP_MODIFIERS.get(target_relationship_tier_to_initiator, 0.0)
        base_willingness_chance += tier_modifier

        initiator_mood_social_modifier = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(self.character.mood, 0.0)
        final_willingness_chance = base_willingness_chance + initiator_mood_social_modifier

        initiator_reputation_modifier = self.character.reputation_score * config.REPUTATION_EFFECT_ON_WILLINGNESS_TO_HELP
        final_willingness_chance += initiator_reputation_modifier
        if initiator_reputation_modifier != 0:
            target_char.add_memory(f"My willingness to help {self.character.name} is slightly affected by their reputation ({self.character.reputation_score:.0f} -> {initiator_reputation_modifier:+.2f} chance).")

        final_willingness_chance = max(0.0, min(1.0, final_willingness_chance))
        willing_to_help = random.random() < final_willingness_chance

        if "Selfish" in target_char.traits and target_relationship_tier_to_initiator not in ["Family", "Soulmate", "Close Friend"]:
            if random.random() > 0.05:
                 willing_to_help = False

        dialogue_line_self = f"Excuse me, {target_name}, I was wondering if you could help me?"
        if help_type == "resource" and item_name_needed:
            dialogue_line_self = f"{target_name}, I'm in a bit of a bind. Could you spare {quantity_needed} {item_name_needed}?"
            if target_char.inventory.get(item_name_needed, 0) >= quantity_needed:
                can_help = True

        outcome_message = ""
        if willing_to_help and can_help:
            if help_type == "resource" and item_name_needed:
                target_char.inventory[item_name_needed] -= quantity_needed
                if target_char.inventory[item_name_needed] <= 0: del target_char.inventory[item_name_needed]
                self.character.inventory[item_name_needed] = self.character.inventory.get(item_name_needed, 0) + quantity_needed
                outcome_message = f"{target_name} gave {quantity_needed} {item_name_needed} to {self.character.name}."
                dialogue_line_target = f"Of course, {self.character.name}. Here you go."

            self.character.modify_relationship(target_name, 5, world, reason="They helped me when I asked.")
            target_char.modify_relationship(self.character.name, 3, world, reason="I helped them out.")
            self.character.update_mood_score(config.MOOD_CHANGE_NEED_FULFILLED_FROM_CRITICAL, f"Received help from {target_name}")
            target_char.update_mood_score(config.MOOD_CHANGE_POSITIVE_SOCIAL, f"Helped {self.character.name}")

            rep_change_reason = f"Helped {self.character.name} with {item_name_needed or help_type}"
            target_char.update_reputation(config.REPUTATION_CHANGE_HELPED_OTHER, rep_change_reason)
            if abs(config.REPUTATION_CHANGE_HELPED_OTHER) >= config.REPUTATION_FOR_RUMOR_THRESHOLD and world.game_time:
                new_rumor = Rumor(
                    subject_char_id=target_char.name,
                    content_key="helped_someone_positive",
                    initial_strength=config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT,
                    creation_day=world.game_time.current_day,
                    is_positive=True,
                    original_source_char_id=self.character.name
                )
                world.add_rumor(new_rumor)
                target_char.known_rumor_ids.add(new_rumor.rumor_id)
                self.character.known_rumor_ids.add(new_rumor.rumor_id)
        elif willing_to_help and not can_help:
            outcome_message = f"{target_name} was willing but unable to help {self.character.name}."
            dialogue_line_target = f"I'd like to help, {self.character.name}, but I don't have any {item_name_needed} to spare." if item_name_needed else f"I wish I could help, {self.character.name}, but I'm not able to."
            self.character.modify_relationship(target_name, 1, world, reason="They were willing to help, even if they couldn't.")
            self.character.update_mood_score(config.MOOD_CHANGE_NEGATIVE_SOCIAL // 2, f"Was unable to get help from {target_name}, but they were willing.")
        else:
            outcome_message = f"{target_name} declined to help {self.character.name}."
            dialogue_line_target = f"Sorry, {self.character.name}, I can't help you with that right now."
            if "Grumpy" in target_char.traits: dialogue_line_target = f"Not my problem, {self.character.name}."
            elif "Selfish" in target_char.traits: dialogue_line_target = f"I need to look out for myself, {self.character.name}."
            self.character.modify_relationship(target_name, -3, world, reason="They wouldn't help when I asked.")
            self.character.update_mood_score(config.MOOD_CHANGE_NEGATIVE_SOCIAL, f"Denied help by {target_name}")

        world.add_event_log_message(outcome_message)
        return ActionStatus.COMPLETED
