# game/world.py
from typing import TYPE_CHECKING, List, Optional, Tuple, Dict
from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building # Added import
from .data import STRUCTURE_BLUEPRINTS # Added import

if TYPE_CHECKING:
    from .character import Character

class World:
    SEASONS = ["Spring", "Summer", "Autumn", "Winter"]

    def __init__(self, grid_size: tuple[int, int] = (10, 10), game_time_ref: Optional[Time] = None):
        self.grid_size = grid_size
        self.grid = [["Grass" for _ in range(grid_size[1])] for _ in range(grid_size[0])]
        self.resources: Dict[str, List[Tuple[int,int]]] = {}
        self.season_index = 0
        self.season = World.SEASONS[self.season_index]
        self.weather = "Sunny"
        self.characters: List['Character'] = []
        self.stockpiles: List[Stockpile] = []
        self.buildings: List[Building] = [] # Added list for buildings
        self.ledger: Ledger = Ledger()
        self.game_time: Optional[Time] = game_time_ref
        self.work_orders: List[WorkOrder] = []

    def __str__(self):
        return f"World(Size: {self.grid_size}, Season: {self.season}, Chars: {len(self.characters)}, SPs: {len(self.stockpiles)}, Buildings: {len(self.buildings)}, WOs: {len(self.work_orders)})"

    def set_game_time(self, game_time_obj: Time):
        if not self.game_time: self.game_time = game_time_obj

    def get_tile(self, x: int, y: int) -> str:
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            return "OutOfBounds"
        # Check for buildings first, as they overlay the base grid
        for building in self.buildings:
            if (x,y) in building.get_tiles_occupied():
                blueprint = STRUCTURE_BLUEPRINTS.get(building.structure_type)
                if blueprint:
                    return blueprint["map_char_complete"] if building.is_operational else blueprint["map_char_initial"]
                return "Bldg?" # Fallback if blueprint not found
        return self.grid[x][y]


    def set_tile(self, x: int, y: int, tile_type: str):
        # This function primarily sets the base terrain. Buildings will overlay this.
        # If a building is ever removed, the underlying terrain set here would be revealed.
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            # Check if a building occupies this tile. If so, don't change base grid easily
            # unless explicitly deconstructing. For now, allow overwrite if not a building tile.
            is_building_tile = any((x,y) in b.get_tiles_occupied() for b in self.buildings)
            if not is_building_tile:
                 self.grid[x][y] = tile_type
            # If it IS a building tile, the visual is handled by get_tile() looking at self.buildings

    def add_building(self, building: Building):
        """Adds a building to the world and updates map tiles."""
        if building not in self.buildings:
            # Check for overlap with existing buildings or critical map features before adding
            new_building_tiles = building.get_tiles_occupied()
            for tile_coord in new_building_tiles:
                if not (0 <= tile_coord[0] < self.grid_size[0] and 0 <= tile_coord[1] < self.grid_size[1]):
                    print(f"Error: Building '{building.display_name}' at {building.location} is out of bounds.")
                    return
                # Check overlap with other buildings
                for existing_b in self.buildings:
                    if tile_coord in existing_b.get_tiles_occupied():
                        print(f"Error: Building '{building.display_name}' overlaps with '{existing_b.display_name}' at {tile_coord}.")
                        return
                # Optionally, check for unbuildable terrain (e.g. Water, Mountain if not handled by character)
                # base_tile = self.grid[tile_coord[0]][tile_coord[1]]
                # if base_tile in ["Water", "Mountain"]:
                #     print(f"Error: Cannot build '{building.display_name}' on {base_tile} at {tile_coord}.")
                #     return

            self.buildings.append(building)
            # The visual representation is handled by get_tile()
            print(f"Added building: {building.display_name} at {building.location} to the world. Tiles will be updated by get_tile.")

    def remove_building(self, building: Building):
        """Removes a building from the world."""
        if building in self.buildings:
            self.buildings.remove(building)
            # Tiles will revert to base grid characters automatically via get_tile()
            print(f"Removed building: {building.display_name} from {building.location}.")
        else:
            print(f"Warning: Tried to remove building {building.display_name} but it was not found.")

    def get_building_at(self, x: int, y: int) -> Optional[Building]:
        """Returns the building object at a given coordinate, if any."""
        for building in self.buildings:
            if (x,y) in building.get_tiles_occupied():
                return building
        return None

    def get_operational_buildings_of_type(self, structure_type_str: str) -> List[Building]:
        """Returns a list of operational buildings of a specific type."""
        return [b for b in self.buildings if b.structure_type == structure_type_str and b.is_operational]

    def add_resource(self, resource_name: str, location: tuple[int, int], tile_becomes: str = None):
        x, y = location
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]): return
        if self.get_building_at(x,y): return # Don't add resource if a building is there

        if resource_name not in self.resources: self.resources[resource_name] = []
        self.resources[resource_name].append(location)
        current_tile = self.get_tile(x,y) # Use get_tile to respect overlays
        if tile_becomes:
            if current_tile != tile_becomes : self.set_tile(x, y, tile_becomes) # set_tile handles base grid
        elif current_tile == "Grass": self.set_tile(x,y, resource_name) # set_tile handles base grid

    def get_resources(self, resource_name: str) -> List[tuple[int, int]]:
        return list(self.resources.get(resource_name, []))

    def update_weather(self, new_weather: str):
        if self.weather != new_weather: self.weather = new_weather

    def advance_season(self):
        self.season_index = (self.season_index + 1) % len(World.SEASONS)
        self.season = World.SEASONS[self.season_index]
        print(f"The season has changed to {self.season}.")
        if self.season == "Winter": self.update_weather("Snowy")
        elif self.season == "Spring": self.update_weather("Rainy")
        elif self.season == "Summer": self.update_weather("Sunny")
        else: self.update_weather("Cloudy")

    def add_character(self, character: 'Character'):
        if character not in self.characters: self.characters.append(character)

    def remove_character(self, character: 'Character'):
        if character in self.characters: self.characters.remove(character)

    def get_characters_at_location(self, x: int, y: int) -> List['Character']:
        return [char for char in self.characters if char.x == x and char.y == y]

    def get_nearby_characters(self, character: 'Character', radius: int = 1) -> List['Character']:
        nearby = []
        for other_char in self.characters:
            if other_char.name == character.name: continue
            if abs(other_char.x - character.x) + abs(other_char.y - character.y) <= radius:
                nearby.append(other_char)
        return nearby

    def add_stockpile(self, stockpile: Stockpile):
        if stockpile not in self.stockpiles:
            self.stockpiles.append(stockpile)
            if self.game_time:
                 self.ledger.update_stockpile_record(stockpile.name, stockpile.inventory, self.game_time.current_day)
            x, y, w, h = stockpile.rect
            for r_offset in range(h):
                for c_offset in range(w):
                    tile_x, tile_y = x + c_offset, y + r_offset
                    if 0 <= tile_x < self.grid_size[0] and 0 <= tile_y < self.grid_size[1]:
                        self.set_tile(tile_x, tile_y, f"SP_{stockpile.name[:3]}")

    def get_stockpiles_for_resource(self, resource_name: str) -> List[Stockpile]:
        return [sp for sp in self.stockpiles if sp.is_allowed(resource_name)]

    def get_stockpile_by_name(self, name: str) -> Optional[Stockpile]:
        for sp in self.stockpiles:
            if sp.name == name: return sp
        return None

    def add_work_order(self, work_order: WorkOrder):
        if work_order not in self.work_orders:
            self.work_orders.append(work_order)

    def get_pending_work_orders(self) -> List[WorkOrder]:
        pending = [wo for wo in self.work_orders if wo.status == "Pending"]
        pending.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return pending

    def get_approved_craft_orders(self) -> List[WorkOrder]: # New method
        approved = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "CraftItem" and wo.assigned_to is None
        ]
        approved.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved

    def get_approved_build_orders(self) -> List[WorkOrder]:
        approved_build = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "BuildStructure" and wo.assigned_to is None
        ]
        approved_build.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved_build

    def get_work_order_by_id(self, order_id: str) -> Optional[WorkOrder]: # New method
        for wo in self.work_orders:
            if wo.order_id == order_id:
                return wo
        return None
