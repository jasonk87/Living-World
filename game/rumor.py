# game/rumor.py
import uuid
from typing import Optional, Set

class Rumor:
    def __init__(self, subject_char_id: str, content_key: str, initial_strength: float, creation_day: int, is_positive: bool, original_source_char_id: Optional[str] = None):
        self.rumor_id: str = str(uuid.uuid4())
        self.subject_char_id: str = subject_char_id
        self.content_key: str = content_key
        self.initial_strength: float = initial_strength
        self.current_strength: float = initial_strength
        self.creation_day: int = creation_day
        self.last_spread_day: int = creation_day
        self.is_positive: bool = is_positive
        self.known_by_char_ids: Set[str] = set()
        if original_source_char_id:
            self.known_by_char_ids.add(original_source_char_id)
        self.original_source_char_id: Optional[str] = original_source_char_id

    def decay(self, current_day: int, decay_rate: float):
        days_since_spread = current_day - self.last_spread_day
        if days_since_spread > 0:
            self.current_strength -= decay_rate * days_since_spread
            self.current_strength = max(0, self.current_strength)

    def reinforce(self, increase_amount: float, max_strength: float):
        """Increases the rumor's strength, capping at a maximum."""
        self.current_strength += increase_amount
        self.current_strength = min(self.current_strength, max_strength)

    def is_known_by(self, char_id: str) -> bool:
        return char_id in self.known_by_char_ids

    def add_knower(self, char_id: str):
        self.known_by_char_ids.add(char_id)

    def to_dict(self):
        return {
            "rumor_id": self.rumor_id,
            "subject_char_id": self.subject_char_id,
            "content_key": self.content_key,
            "current_strength": self.current_strength,
            "is_positive": self.is_positive,
        }
