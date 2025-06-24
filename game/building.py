# game/building.py
from typing import Tuple, Dict, Optional

class Building:
    def __init__(self, structure_type: str, location: Tuple[int, int], size: Tuple[int, int],
                 display_name: str, required_resources: Dict[str, int], build_time: int,
                 functionality: Optional[Dict] = None, required_skill: Optional[Dict] = None):
        self.structure_type = structure_type  # e.g., "small_workshop"
        self.display_name = display_name    # e.g., "Small Workshop"
        self.location = location            # (x, y) top-left corner
        self.size = size                    # (width, height)
        self.required_resources = required_resources
        self.build_time = build_time        # Total work units needed
        self.functionality = functionality if functionality else {}
        self.required_skill = required_skill if required_skill else {}

        self.current_progress = 0
        self.is_operational = False
        self.occupants: list[str] = [] # Names of characters currently inside

    def __str__(self):
        return f"{self.display_name} at {self.location} ({self.current_progress}/{self.build_time} built, Operational: {self.is_operational})"

    def work_on(self, amount: int) -> bool:
        """
        Adds work to the building's construction.
        Returns True if construction is now complete, False otherwise.
        """
        if not self.is_operational:
            self.current_progress += amount
            if self.current_progress >= self.build_time:
                self.current_progress = self.build_time
                self.is_operational = True
                print(f"{self.display_name} at {self.location} is now complete and operational!")
                return True
        if actual_progress_made > 0 and not self.is_operational and self.current_progress >= self.build_time:
             self.current_progress = self.build_time
             self.is_operational = True
             print(f"{self.display_name} at {self.location} is now complete and operational!")

        return actual_progress_made # Return the actual progress made

    def get_tiles_occupied(self) -> list[Tuple[int, int]]:
        """Returns a list of (x,y) tuples for all tiles occupied by the building."""
        tiles = []
        x, y = self.location
        w, h = self.size
        for r_offset in range(h):
            for c_offset in range(w):
                tiles.append((x + c_offset, y + r_offset))
        return tiles

    def is_inside(self, char_x: int, char_y: int) -> bool:
        """Checks if a given coordinate is within the building's footprint."""
        building_tiles = self.get_tiles_occupied()
        return (char_x, char_y) in building_tiles

    def add_occupant(self, char_name: str):
        if char_name not in self.occupants:
            self.occupants.append(char_name)

    def remove_occupant(self, char_name: str):
        if char_name in self.occupants:
            self.occupants.remove(char_name)
