from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict
from game.components.component import Component
from game import config

if TYPE_CHECKING:
    from game.character import Character

class NeedsComponent(Component):
    """
    Manages the needs of a character.
    """
    def __init__(self, character: Character, needs: Optional[Dict[str, int]] = None):
        super().__init__(character)
        self.needs = needs if needs is not None else {}

        if 'Social' not in self.needs: self.needs['Social'] = 70
        if 'Energy' not in self.needs: self.needs['Energy'] = 100
        if 'Safety' not in self.needs: self.needs['Safety'] = config.NEED_SAFETY_DEFAULT
        if 'Belonging' not in self.needs: self.needs['Belonging'] = config.NEED_BELONGING_DEFAULT
        if 'Esteem' not in self.needs: self.needs['Esteem'] = config.NEED_ESTEEM_DEFAULT

    def update_mood_from_critical_needs(self):
        """Checks critical complex needs and updates mood accordingly."""
        # Safety Need
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_SAFETY_CRITICAL, "Critically low safety")

        # Belonging Need
        if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_BELONGING_CRITICAL, "Critically low belonging")

        # Esteem Need
        if self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) < config.NEED_ESTEEM_CRITICAL_THRESHOLD:
            self.character.update_mood_score(config.MOOD_CHANGE_ESTEEM_CRITICAL, "Critically low esteem")
