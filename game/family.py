# game/family.py
import random
from typing import Optional, Set, List, TYPE_CHECKING
from . import config

if TYPE_CHECKING:
    from .character import Character
    from .world import World

class Family:
    def __init__(self, family_id: str, member_names: Set[str]):
        self.family_id = family_id
        self.member_names = member_names
        self.children_names: Set[str] = set()
        self.spouse_pair: Optional[Set[str]] = None

    def add_child(self, child_name: str):
        self.children_names.add(child_name)
        self.member_names.add(child_name)

    def form_union(self, spouse1_name: str, spouse2_name: str):
        self.spouse_pair = {spouse1_name, spouse2_name}
        self.member_names.add(spouse1_name)
        self.member_names.add(spouse2_name)

    def dissolve_union(self):
        self.spouse_pair = None

    def to_dict(self):
        return {
            "family_id": self.family_id,
            "members": list(self.member_names),
            "children": list(self.children_names),
            "spouses": list(self.spouse_pair) if self.spouse_pair else []
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Creates a Family instance from a dictionary."""
        family = cls(data['family_id'], set(data.get('members', [])))
        family.children_names = set(data.get('children', []))
        spouses = data.get('spouses')
        if spouses:
            family.spouse_pair = set(spouses)
        return family

    def _child_desire_score(self, parent1: 'Character', parent2: 'Character') -> float:
        base = getattr(config, "FAMILY_CHILD_DESIRE_BASE", 0.12)
        personality_bonus = getattr(config, "FAMILY_CHILD_PERSONALITY_BONUS", {})
        trait_bonus = getattr(config, "FAMILY_CHILD_TRAIT_BONUS", {})
        base += personality_bonus.get(parent1.personality, 0.0)
        base += personality_bonus.get(parent2.personality, 0.0)
        for trait in parent1.traits:
            base += trait_bonus.get(trait, 0.0)
        for trait in parent2.traits:
            base += trait_bonus.get(trait, 0.0)
        belonging = min(parent1.needs.get("Belonging", 0), parent2.needs.get("Belonging", 0))
        threshold = getattr(config, "FAMILY_CHILD_MIN_BELONGING", 55)
        if belonging < threshold:
            base -= 0.3
        wealth_total = getattr(parent1, "net_worth", 0) + getattr(parent2, "net_worth", 0)
        if wealth_total > 500:
            base += 0.05
        elif wealth_total < 60:
            base -= 0.05
        if getattr(parent1, "retired", False) or getattr(parent2, "retired", False):
            base -= 0.05
        return max(0.0, min(0.9, base))

    def _can_plan_child(self, parent1: 'Character', parent2: 'Character', world: 'World', day: int) -> bool:
        min_age = getattr(config, "FAMILY_CHILD_MIN_AGE", 18)
        max_age = getattr(config, "FAMILY_CHILD_MAX_AGE", 45)
        if not (min_age <= parent1.age_years <= max_age and min_age <= parent2.age_years <= max_age):
            return False
        cooldown = getattr(config, "FAMILY_CHILD_COOLDOWN_DAYS", 18)
        if (parent1._last_child_day is not None and day - parent1._last_child_day < cooldown) or \
           (parent2._last_child_day is not None and day - parent2._last_child_day < cooldown):
            return False
        if parent1.health.is_sick or parent1.health.is_injured or parent2.health.is_sick or parent2.health.is_injured:
            return False
        housing_requirement = getattr(config, "FAMILY_CHILD_HOUSING_REQUIREMENT", 0)
        if housing_requirement and not (parent1.home_location or parent2.home_location):
            return False
        if parent1.get_relationship_score(parent2.name) < getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT", 55) // 2 or \
           parent2.get_relationship_score(parent1.name) < getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT", 55) // 2:
            return False
        return True

    def should_plan_child(self, world: 'World') -> Optional[List[str]]:
        if not self.spouse_pair or len(self.spouse_pair) != 2:
            return None

        spouses = list(self.spouse_pair)
        parent1 = world.get_character_by_name(spouses[0])
        parent2 = world.get_character_by_name(spouses[1])

        if not parent1 or not parent2 or not world.game_time:
            return None

        day = world.game_time.current_day
        if self._can_plan_child(parent1, parent2, world, day):
            desire = self._child_desire_score(parent1, parent2)
            if random.random() < desire:
                return [parent1.name, parent2.name]
        return None
