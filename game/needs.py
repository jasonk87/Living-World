from typing import TYPE_CHECKING, Optional, Dict, Any
from . import config

if TYPE_CHECKING:
    from .character import Character


class Needs:
    def __init__(self, character: 'Character', needs: Optional[Dict[str, int]] = None):
        self.character = character
        self.needs = needs if needs else {}
        if 'Social' not in self.needs: self.needs['Social'] = 70
        if 'Energy' not in self.needs: self.needs['Energy'] = 100
        if 'Safety' not in self.needs: self.needs['Safety'] = config.NEED_SAFETY_DEFAULT
        if 'Belonging' not in self.needs: self.needs['Belonging'] = config.NEED_BELONGING_DEFAULT
        if 'Esteem' not in self.needs: self.needs['Esteem'] = config.NEED_ESTEEM_DEFAULT
        if 'Familial' not in self.needs: self.needs['Familial'] = config.NEED_FAMILIAL_DEFAULT

    def to_dict(self) -> Dict[str, int]:
        return self.needs.copy()

    def get(self, key: str, default: Any = None) -> Any:
        return self.needs.get(key, default)

    def __getitem__(self, key: str) -> int:
        return self.needs[key]

    def __setitem__(self, key: str, value: int):
        self.needs[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.needs

    def update_mood_from_critical_needs(self):
        """Checks critical complex needs and updates mood accordingly."""
        if self.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_SAFETY_CRITICAL, "Critically low safety")

        if self.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_BELONGING_CRITICAL, "Critically low belonging")

        if self.get('Esteem', config.NEED_ESTEEM_DEFAULT) < config.NEED_ESTEEM_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_ESTEEM_CRITICAL, "Critically low esteem")

    def process_daily_decay(self):
        """Applies daily decay to basic needs like hunger, thirst, and energy."""
        self.needs['Hunger'] = max(0, self.needs.get('Hunger', 100) - config.DAILY_HUNGER_DECAY)
        self.needs['Thirst'] = max(0, self.needs.get('Thirst', 100) - config.DAILY_THIRST_DECAY)
        self.needs['Energy'] = max(0, self.needs.get('Energy', 100) - config.DAILY_ENERGY_DECAY)
