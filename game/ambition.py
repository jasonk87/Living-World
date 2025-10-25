from enum import Enum
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from .character import Character
    from .goal import Goal

class AmbitionType(Enum):
    BECOME_TOWN_LEADER = "BECOME_TOWN_LEADER"
    BUILD_A_HOUSE = "BUILD_A_HOUSE"
    BECOME_MASTER_ARTISAN = "BECOME_MASTER_ARTISAN"
    ACCUMULATE_WEALTH = "ACCUMULATE_WEALTH"

class Ambition:
    def __init__(self, ambition_type: AmbitionType, data: Dict[str, Any]):
        self.type = ambition_type
        self.data = data

    @staticmethod
    def is_eligible(character: 'Character', ambition_data: Dict[str, Any]) -> bool:
        prerequisites = ambition_data.get("prerequisites", {})
        for key, value in prerequisites.items():
            if key == "trait":
                if value not in character.traits:
                    return False
            elif key == "min_money":
                if character.money < value:
                    return False
            elif key == "skill":
                for skill_name, level in value.items():
                    if character.skills.get(skill_name, {}).get("level", 0) < level:
                        return False
        return True

    def is_complete(self, character: 'Character') -> bool:
        completion_criteria = self.data.get("completion_criteria", {})
        if not completion_criteria:
            return False

        for key, value in completion_criteria.items():
            if key == "job":
                if not character.job or character.job.title != value:
                    return False
            elif key == "has_home":
                if not character.home_location:
                    return False
            elif key == "money":
                if character.money < value:
                    return False
            elif key == "skill":
                for skill_name, level in value.items():
                    if character.skills.get(skill_name, {}).get("level", 0) < level:
                        return False
            else:
                # If the criterion is unknown, we can't confirm completion.
                return False

        # If all criteria are met, the loop completes without returning False.
        return True

    def get_next_goal(self, character: 'Character') -> Optional['Goal']:
        from .goal import Goal, GoalType
        from .goal_runtime import GoalPriority
        from .goal_runtime import GoalPriority
        next_goal_data = self.data.get("next_goal", {})
        goal_type_str = next_goal_data.get("type")
        if goal_type_str:
            try:
                goal_type = GoalType[goal_type_str]
                return Goal(goal_type, character.name, character.name, priority=GoalPriority.LOW, parameters=next_goal_data.get("parameters", {}))
            except KeyError:
                return None
        return None
