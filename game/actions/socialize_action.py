from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class SocializeAction(Action):
    """
    An action for a character to seek out and initiate a social interaction.
    The type of interaction is determined by personality and relationships.
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        """
        Finds a target and initiates a social interaction based on personality.
        """
        # Find a nearby character to interact with
        nearby_chars = world.get_nearby_characters(self.character, radius=5)
        if not nearby_chars:
            self.character.add_memory("No one nearby to talk to, I'll wander a bit.")
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0:
                self.character.move(dx, dy, world)
            return ActionStatus.COMPLETED

        target = random.choice(nearby_chars)
        self.character.add_memory(f"I see {target.name}. I should interact with them.")

        # Determine the type of interaction based on traits and relationship
        interaction_goal = self._get_interaction_goal(target)

        if interaction_goal:
            self.character.current_goal = interaction_goal
        else:
            # If no specific interaction is chosen, just move closer or do nothing.
            self.character.move_towards(target.x, target.y, world)

        return ActionStatus.COMPLETED

    def _get_interaction_goal(self, target: Character) -> Goal | None:
        """
        Determines the social goal based on personality and relationship.
        """
        char = self.character
        relationship_score = char.get_relationship_score(target.name)

        if relationship_score < 20 and random.random() < 0.7:
             return Goal(GoalType.GREET_CHARACTER, assignee_id=char.name, originator_id="SelfSocial", parameters={"target_char_name": target.name})

        if "Friendly" in char.traits and random.random() < 0.5:
            return Goal(GoalType.SHARE_POSITIVE_NEWS, assignee_id=char.name, originator_id="SelfSocial", parameters={"target_char_name": target.name})

        if "Grumpy" in char.traits and relationship_score < 0 and random.random() < 0.3:
            return Goal(GoalType.ARGUE, assignee_id=char.name, originator_id="SelfSocial", parameters={"target_char_name": target.name})

        if random.random() < 0.6:
            return Goal(GoalType.SMALL_TALK, assignee_id=char.name, originator_id="SelfSocial", parameters={"target_char_name": target.name})

        return None
