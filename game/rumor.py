from typing import Set
import uuid

class Rumor:
    def __init__(self, subject_char_id: str, content_key: str, initial_strength: int,
                 creation_day: int, is_positive: bool, original_source_char_id: str):
        self.rumor_id = str(uuid.uuid4())
        self.subject_char_id = subject_char_id
        self.content_key = content_key
        self.initial_strength = initial_strength
        self.current_strength = float(initial_strength)
        self.creation_day = creation_day
        self.is_positive = is_positive
        self.original_source_char_id = original_source_char_id
        self.known_by_char_ids: Set[str] = {original_source_char_id}
        self.last_spread_day = creation_day

    def __str__(self):
        sentiment = "Positive" if self.is_positive else "Negative"
        return (f"Rumor(ID: {self.rumor_id[:4]}, Subject: {self.subject_char_id}, "
                f"Content: {self.content_key}, Strength: {self.current_strength:.1f}, "
                f"Sentiment: {sentiment}, Known by: {len(self.known_by_char_ids)})")

    def add_knower(self, character_id: str):
        self.known_by_char_ids.add(character_id)

    def is_known_by(self, character_id: str) -> bool:
        return character_id in self.known_by_char_ids

    def decay(self, decay_amount: float):
        self.current_strength -= decay_amount
        if self.current_strength < 0:
            self.current_strength = 0

    def reinforce(self, reinforcement_amount: float, max_strength: int):
        self.current_strength += reinforcement_amount
        if self.current_strength > max_strength:
            self.current_strength = float(max_strength)