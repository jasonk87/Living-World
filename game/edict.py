from typing import Dict, Any

class Edict:
    def __init__(self, edict_type: str, issued_by: str, start_day: int, duration: int, effects: Dict[str, Any]):
        self.edict_type = edict_type
        self.issued_by = issued_by
        self.start_day = start_day
        self.duration = duration
        self.effects = effects
        self.is_active = True

    def to_dict(self):
        return {
            "edict_type": self.edict_type,
            "issued_by": self.issued_by,
            "start_day": self.start_day,
            "duration": self.duration,
            "effects": self.effects,
            "is_active": self.is_active,
        }
