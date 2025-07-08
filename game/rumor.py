# game/rumor.py
import uuid
from typing import List, Set

class Rumor:
    def __init__(self, subject_char_id: str, content_key: str,
                 initial_strength: int, creation_day: int, is_positive: bool,
                 original_source_char_id: str = None, world_event_id: str = None):
        self.rumor_id: str = str(uuid.uuid4())
        self.subject_char_id: str = subject_char_id  # Character ID of who the rumor is about
        self.content_key: str = content_key  # e.g., "helped_other_positive", "fired_negative", "skill_max_combat"
                                            # Suffix like _positive/_negative might be redundant if is_positive is used
        self.initial_strength: int = initial_strength # How strong it was when created
        self.current_strength: int = initial_strength # Current strength, decays over time
        self.creation_day: int = creation_day
        self.is_positive: bool = is_positive # True if positive, False if negative/neutral gossip

        # Optional: Who was directly involved or perceived as the source. Can be None.
        self.original_source_char_id: str = original_source_char_id

        # Optional: Link to a more detailed world event if applicable
        self.world_event_id: str = world_event_id

        self.known_by_char_ids: Set[str] = set()
        if subject_char_id:
            self.known_by_char_ids.add(subject_char_id)
        if original_source_char_id:
            self.known_by_char_ids.add(original_source_char_id)

        # To be set by config
        # self.decay_rate_per_day: int = 1 # Example: loses 1 strength per day

    def __str__(self):
        return (f"Rumor(ID: {self.rumor_id[:4]}..., Subject: {self.subject_char_id}, "
                f"Key: '{self.content_key}', Strength: {self.current_strength}/{self.initial_strength}, "
                f"Positive: {self.is_positive}, Day: {self.creation_day}, "
                f"Known by: {len(self.known_by_char_ids)})")

    def add_knower(self, char_id: str):
        self.known_by_char_ids.add(char_id)

    def decay(self, decay_amount: int = 1):
        self.current_strength -= decay_amount
        if self.current_strength < 0:
            self.current_strength = 0

    def is_known_by(self, char_id: str) -> bool:
        return char_id in self.known_by_char_ids

# Example Usage (not part of the class itself, for testing/dev):
# if __name__ == '__main__':
#     rumor1 = Rumor(subject_char_id="Alice", content_key="found_treasure_positive",
#                    initial_strength=70, creation_day=1, is_positive=True, original_source_char_id="Alice")
#     rumor1.add_knower("Bob")
#     print(rumor1)
#     rumor1.decay(5)
#     print(rumor1)
#     print(f"Bob knows: {rumor1.is_known_by('Bob')}")
#     print(f"Charlie knows: {rumor1.is_known_by('Charlie')}")
