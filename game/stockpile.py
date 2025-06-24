# game/stockpile.py
from typing import List, Optional, Dict, Tuple

class Stockpile:
    _init_default_allowed_resources_marker = object() # Unique marker for default argument

    def __init__(self, name: str, x: int, y: int, width: int, height: int,
                 allowed_resources: Optional[List[str]] = _init_default_allowed_resources_marker,
                 capacity_per_resource: Optional[int] = None, # Max items of a single resource type
                 total_capacity: Optional[int] = None): # Max total items in stockpile
        self.name = name
        self.rect = (x, y, width, height)  # (top_left_x, top_left_y, width, height)

        # If allowed_resources is explicitly passed (even if None), use that.
        # If the argument is omitted by the caller (i.e., it's our marker), then apply a game default.
        if allowed_resources == Stockpile._init_default_allowed_resources_marker:
            self.allowed_resources = ["Wood", "Stone"] # Game's default when arg is omitted
        else:
            self.allowed_resources = allowed_resources # Respects explicit None (for allow all) or a list

        self.inventory: Dict[str, int] = {}
        self.capacity_per_resource = capacity_per_resource # e.g., can hold 50 wood, 30 stone
        self.total_capacity = total_capacity # e.g., can hold 100 items total

        # For simplicity, interaction points are the perimeter of the stockpile OR its main tiles
        self.access_points = self._calculate_access_points() # For characters to stand on when interacting
        self.deposit_tiles = self._calculate_deposit_tiles() # Actual tiles of the stockpile

    def _calculate_deposit_tiles(self) -> List[Tuple[int,int]]:
        # Tiles the stockpile physically occupies
        points = []
        x,y,w,h = self.rect
        for r_offset in range(h):
            for c_offset in range(w):
                points.append((x + c_offset, y + r_offset))
        return list(set(p for p in points if p[0] >= 0 and p[1] >= 0))


    def _calculate_access_points(self) -> List[Tuple[int, int]]:
        # Points adjacent to the stockpile's physical area
        points = []
        x, y, w, h = self.rect
        # Top edge (above stockpile)
        for i in range(w): points.append((x + i, y - 1))
        # Bottom edge (below stockpile)
        for i in range(w): points.append((x + i, y + h))
        # Left edge (to the left of stockpile)
        for i in range(h): points.append((x - 1, y + i))
        # Right edge (to the right of stockpile)
        for i in range(h): points.append((x + w, y + i))

        # Basic filter for non-negative coords & uniqueness.
        # In a real game, also check against world grid_size and if points are walkable.
        return list(set(p for p in points if p[0] >= 0 and p[1] >= 0))

    def get_current_load(self) -> int:
        return sum(self.inventory.values())

    def has_space_for(self, resource_name: str, quantity: int = 1) -> bool:
        if not self.is_allowed(resource_name):
            # print(f"Debug: {resource_name} not allowed in {self.name}")
            return False

        current_resource_qty = self.inventory.get(resource_name, 0)
        if self.capacity_per_resource is not None and \
           current_resource_qty + quantity > self.capacity_per_resource:
            # print(f"Debug: {resource_name} over per-resource capacity in {self.name}")
            return False

        if self.total_capacity is not None and \
           self.get_current_load() + quantity > self.total_capacity:
            # print(f"Debug: {resource_name} over total capacity in {self.name}")
            return False

        return True

    def is_allowed(self, resource_name: str) -> bool:
        if self.allowed_resources is None:
            return True
        return resource_name in self.allowed_resources

    def add_item(self, resource_name: str, quantity: int = 1) -> Tuple[bool, int]:
        if not self.is_allowed(resource_name): # Double check, though has_space_for should catch it
            # print(f"Stockpile Error: {self.name} cannot accept {resource_name} (not allowed).")
            return False, 0

        # Calculate how much can actually be added based on available space
        actual_add_qty = 0
        for i in range(quantity, 0, -1): # Try adding full quantity, then one less, etc.
            if self.has_space_for(resource_name, i):
                actual_add_qty = i
                break

        if actual_add_qty > 0:
            self.inventory[resource_name] = self.inventory.get(resource_name, 0) + actual_add_qty
            # print(f"Added {actual_add_qty}/{quantity} {resource_name} to {self.name}. Inv: {self.inventory}")
            return True, actual_add_qty
        else:
            # print(f"Stockpile Full/Error: {self.name} could not add any {resource_name} (wanted {quantity}).")
            return False, 0


    def remove_item(self, resource_name: str, quantity: int = 1) -> Tuple[bool, int]:
        if resource_name not in self.inventory or self.inventory[resource_name] == 0:
            # print(f"Stockpile Empty/Error: {self.name} has no {resource_name} to remove.")
            return False, 0

        can_remove = min(quantity, self.inventory[resource_name])
        self.inventory[resource_name] -= can_remove
        if self.inventory[resource_name] == 0:
            del self.inventory[resource_name]
        # print(f"Removed {can_remove} {resource_name} from {self.name}. Inv: {self.inventory}")
        return True, can_remove

    def __str__(self):
        return f"Stockpile(Name='{self.name}', Rect={self.rect}, Inv={self.inventory}, Load={self.get_current_load()}/{self.total_capacity if self.total_capacity else 'Inf'}, Allowed={self.allowed_resources})"
