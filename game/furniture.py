# game/furniture.py
from typing import Tuple, Dict, Optional, List, Any

class Furniture:
    def __init__(self,
                 item_name: str,
                 display_name: str,
                 x: int,
                 y: int,
                 functionality: Dict[str, Any],
                 size: Tuple[int, int] = (1, 1),
                 map_char: str = 'f',
                 parent_building_id: Optional[str] = None):
        self.item_name = item_name
        self.display_name = display_name
        self.x = x  # Position of the top-left corner of the furniture
        self.y = y
        self.functionality = functionality if functionality else {}
        self.size = size
        self.map_char = map_char
        self.parent_building_id = parent_building_id # ID of the building this furniture is in, if any

    def __str__(self):
        return f"{self.display_name} ({self.item_name}) at ({self.x},{self.y})"

    def get_tiles_occupied(self) -> List[Tuple[int, int]]:
        """Returns a list of (x, y) tuples that this furniture piece occupies."""
        tiles = []
        for r_offset in range(self.size[1]):  # height
            for c_offset in range(self.size[0]):  # width
                tiles.append((self.x + c_offset, self.y + r_offset))
        return tiles

    def is_inside(self, check_x: int, check_y: int) -> bool:
        """Checks if the given world coordinates are part of this furniture."""
        return (self.x <= check_x < self.x + self.size[0] and
                self.y <= check_y < self.y + self.size[1])

    def is_usable(self) -> bool:
        """Basic usability check. Can be expanded later (e.g., if damaged)."""
        return True

    # Example of accessing functionality:
    # comfort_bonus = self.functionality.get("comfort_bonus", 0)
    # rest_quality = self.functionality.get("provides_rest_quality", 1.0)

# Example Usage (for testing, not part of the class itself):
# if __name__ == '__main__':
#     chair_func = {"comfort_bonus": 5, "allowed_activities": ["sitting", "eating"]}
#     chair = Furniture("wooden_chair", "Wooden Chair", 5, 5, functionality=chair_func, size=(1,1), map_char='c')
#     print(chair)
#     print(f"Tiles: {chair.get_tiles_occupied()}")

#     bed_func = {"provides_rest_quality": 1.5, "provides_comfort": 10}
#     bed = Furniture("wooden_bed", "Wooden Bed", 2, 3, functionality=bed_func, size=(1,2), map_char='b')
#     print(bed)
#     print(f"Tiles: {bed.get_tiles_occupied()}")
#     print(f"Is (2,3) part of bed? {bed.is_inside(2,3)}")
#     print(f"Is (2,4) part of bed? {bed.is_inside(2,4)}")
#     print(f"Is (3,3) part of bed? {bed.is_inside(3,3)}")
