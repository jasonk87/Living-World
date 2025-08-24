from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class ArgueAction(Action):
    """An action for a character to argue with another character."""
    def __init__(self, character: Character, target_name: str):
        super().__init__(character)
        self.target_name = target_name

    def execute(self, world: World) -> ActionStatus:
        target_char = world.get_character_by_name(self.target_name)
        if not target_char:
            self.character.add_memory(f"Wanted to argue with {self.target_name}, but they could not be found.")
            return ActionStatus.FAILED

        distance = abs(self.character.x - target_char.x) + abs(self.character.y - target_char.y)
        if distance > 2:
            self.character.add_memory(f"Trying to argue with {self.target_name}, moving closer.")
            self.character.move_towards(target_char.x, target_char.y, world)
            return ActionStatus.RUNNING

        self.character.add_memory(f"Having an argument with {self.target_name}.")

        initiator_hotheaded = "Hot-headed" in self.character.traits
        initiator_grumpy = "Grumpy" in self.character.traits
        target_hotheaded = "Hot-headed" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        rel_penalty = -10
        if initiator_hotheaded or target_hotheaded: rel_penalty -= 5
        if initiator_grumpy and target_grumpy: rel_penalty -=2

        self.character.modify_relationship(self.target_name, rel_penalty, world, reason=f"Had an argument with {self.target_name}.")
        target_char.modify_relationship(self.character.name, rel_penalty, world, reason=f"Had an argument with {self.character.name}.")

        arg_lines_initiator = [
            f"I completely disagree with your approach, {self.target_name}!",
            "That's just not right, and you know it!",
            "Are you even listening to yourself?"
        ]
        if initiator_hotheaded: arg_lines_initiator.append(f"This is outrageous, {self.target_name}!")
        elif initiator_grumpy: arg_lines_initiator.append(f"Whatever, {self.target_name}. You're wrong.")

        arg_lines_target = [
            f"Oh, here we go again, {self.character.name}...",
            "You're the one not making any sense!",
            "I don't have time for this nonsense."
        ]
        if target_hotheaded: arg_lines_target.append(f"How dare you say that to me, {self.character.name}?!")
        elif target_grumpy: arg_lines_target.append(f"Just leave me alone, {self.character.name}.")

        dialogue_line_self = random.choice(arg_lines_initiator)
        dialogue_line_target = random.choice(arg_lines_target)

        dialogue_entry = {
            "type": "argue", "initiator": self.character.name, "target": self.target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [ {"speaker": self.character.name, "line": dialogue_line_self}, {"speaker": target_char.name, "line": dialogue_line_target} ]
        }
        self.character.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        if self.target_name not in self.character.opinions: self.character.opinions[self.target_name] = {}
        self.character.opinions[self.target_name]["argumentative"] = self.character.opinions[self.target_name].get("argumentative", 0) - 2
        self.character.opinions[self.target_name]["disagreeable"] = self.character.opinions[self.target_name].get("disagreeable", 0) -1
        self.character.opinions[self.target_name]["argumentative"] = max(-5, min(5, self.character.opinions[self.target_name].get("argumentative",0)))
        self.character.opinions[self.target_name]["disagreeable"] = max(-5, min(5, self.character.opinions[self.target_name].get("disagreeable",0)))

        if self.character.name not in target_char.opinions: target_char.opinions[self.character.name] = {}
        target_char.opinions[self.character.name]["argumentative"] = target_char.opinions[self.character.name].get("argumentative", 0) - 2
        target_char.opinions[self.character.name]["disagreeable"] = target_char.opinions[self.character.name].get("disagreeable", 0) -1
        target_char.opinions[self.character.name]["argumentative"] = max(-5, min(5, target_char.opinions[self.character.name].get("argumentative",0)))
        target_char.opinions[self.character.name]["disagreeable"] = max(-5, min(5, target_char.opinions[self.character.name].get("disagreeable",0)))

        social_need_penalty = 15
        self.character.needs['Social'] = max(0, self.character.needs.get('Social', 0) - social_need_penalty)
        target_char.needs['Social'] = max(0, target_char.needs.get('Social', 0) - social_need_penalty)
        self.character.add_memory(f"Argument with {self.target_name} was draining. Social need -{social_need_penalty} to {self.character.needs['Social']}.")
        target_char.add_memory(f"Argument with {self.character.name} was draining. Social need -{social_need_penalty} to {target_char.needs['Social']}.")

        self.character.add_memory(f"Argued with {self.target_name}. I said: '{dialogue_line_self}'. They said: '{dialogue_line_target}'.")
        target_char.add_memory(f"Argued with {self.character.name}. They said: '{dialogue_line_self}'. I replied: '{dialogue_line_target}'.")
        world.add_event_log_message(f"{self.character.name} and {self.target_name} had an argument.")

        self.character._update_relationship_from_opinions(self.target_name, world)
        target_char._update_relationship_from_opinions(self.character.name, world)

        argue_mood_penalty = config.MOOD_CHANGE_NEGATIVE_SOCIAL - 5
        if initiator_hotheaded: argue_mood_penalty -=5
        if target_hotheaded:
             target_char.update_mood_score(argue_mood_penalty -5, f"Argued with hot-headed {self.character.name}")
        else:
             target_char.update_mood_score(argue_mood_penalty, f"Argued with {self.character.name}")
        self.character.update_mood_score(argue_mood_penalty, f"Argued with {self.target_name}")

        belonging_penalty = 10
        self.character.needs['Belonging'] = max(config.NEED_SCORE_MIN, self.character.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - belonging_penalty)
        target_char.needs['Belonging'] = max(config.NEED_SCORE_MIN, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - belonging_penalty)
        self.character.add_memory(f"Arguing with {self.target_name} damaged my sense of connection. Belonging: {self.character.needs['Belonging']}")
        target_char.add_memory(f"Arguing with {self.character.name} made me feel more isolated. Belonging: {target_char.needs['Belonging']}")

        self.character._process_nearby_listeners(world, target_char, "argue", self.character.traits, target_char.traits)

        return ActionStatus.COMPLETED
