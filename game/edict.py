from typing import Dict, Any
from enum import Enum

class EdictStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    EXPIRED = "expired"

class Edict:
    def __init__(self, edict_type: str, issued_by: str, start_day: int, duration: int, effects: Dict[str, Any], status: EdictStatus):
        self.edict_type = edict_type
        self.issued_by = issued_by
        self.start_day = start_day
        self.duration = duration
        self.effects = effects
        self.status = status

    def to_dict(self):
        return {
            "edict_type": self.edict_type,
            "issued_by": self.issued_by,
            "start_day": self.start_day,
            "duration": self.duration,
            "effects": self.effects,
            "status": self.status.name,
        }
