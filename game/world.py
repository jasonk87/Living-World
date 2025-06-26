# game/world.py
from typing import TYPE_CHECKING, List, Optional, Tuple, Dict
from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building
from .data import STRUCTURE_BLUEPRINTS
from .furniture import Furniture # Import Furniture class

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
        self.buildings: List[Building] = []
        self.furniture: List[Furniture] = [] # New list for furniture
        self.ledger: Ledger = Ledger()
        self.game_time: Optional[Time] = game_time_ref
        self.work_orders: List[WorkOrder] = []
        self.event_log: List[str] = []
        self.active_world_effects: Dict[str, Any] = {}

    def __str__(self):
        return f"World(Size: {self.grid_size}, Season: {self.season}, Chars: {len(self.characters)}, SPs: {len(self.stockpiles)}, Buildings: {len(self.buildings)}, Furniture: {len(self.furniture)}, WOs: {len(self.work_orders)})"

    def add_event_log_message(self, message: str):
        if not self.game_time:
            timestamp = "[NoTime]"
        else:
            timestamp = f"D{self.game_time.current_day} T{self.game_time.current_tick}"

        full_message = f"[{timestamp}] {message}" # Removed "EVENT: " prefix, message should be self-contained
        self.event_log.append(full_message)
        # Console print removed, UI will handle display
        # print(full_message)

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
                return "B?" # Fallback if blueprint not found

        # Check for furniture next
        furniture_at_loc = self.get_furniture_at(x,y)
        if furniture_at_loc:
            return furniture_at_loc.map_char

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

    def add_furniture(self, furniture_item: Furniture):
        """Adds a furniture item to the world."""
        # Basic check for overlap with other furniture or critical structures.
        # More advanced placement rules (e.g., inside buildings, not blocking paths) can be added.
        new_furniture_tiles = furniture_item.get_tiles_occupied()
        for tile_coord in new_furniture_tiles:
            if not (0 <= tile_coord[0] < self.grid_size[0] and 0 <= tile_coord[1] < self.grid_size[1]):
                print(f"Error: Furniture '{furniture_item.display_name}' at ({furniture_item.x},{furniture_item.y}) is out of bounds.")
                return
            if self.get_building_at(tile_coord[0], tile_coord[1]): # Check against buildings
                 print(f"Error: Furniture '{furniture_item.display_name}' overlaps with a building at {tile_coord}.")
                 return
            existing_furniture = self.get_furniture_at(tile_coord[0], tile_coord[1])
            if existing_furniture and existing_furniture != furniture_item : # Check against other furniture
                 print(f"Error: Furniture '{furniture_item.display_name}' overlaps with '{existing_furniture.display_name}' at {tile_coord}.")
                 return

        if furniture_item not in self.furniture:
            self.furniture.append(furniture_item)
            # print(f"Added furniture: {furniture_item.display_name} at ({furniture_item.x},{furniture_item.y})")

    def can_place_furniture(self, furniture_item_name: str, x: int, y: int, size: Tuple[int,int], furniture_blueprint: Dict[str, Any]) -> bool:
        """Checks if a piece of furniture can be placed at the given location."""
        # furniture_blueprint is passed in directly to avoid repeated lookups

        required_tags = furniture_blueprint.get("requires_building_tags", [])
        first_tile_building: Optional[Building] = None
        all_tiles_in_same_building = True

        # Check bounds, obstructions, and building requirements for all tiles the furniture would occupy
        for r_offset in range(size[1]):  # height
            for c_offset in range(size[0]):  # width
                check_x, check_y = x + c_offset, y + r_offset

                if not (0 <= check_x < self.grid_size[0] and 0 <= check_y < self.grid_size[1]):
                    # print(f"Placement check: Out of bounds for {furniture_item_name} at ({check_x},{check_y})")
                    return False # Out of bounds

                # Check for existing buildings
                if self.get_building_at(check_x, check_y):
                    # print(f"Placement check: Obstructed by building for {furniture_item_name} at ({check_x},{check_y})")
                    return False

                # Check for other furniture
                if self.get_furniture_at(check_x, check_y):
                    # print(f"Placement check: Obstructed by other furniture for {furniture_item_name} at ({check_x},{check_y})")
                    return False

                # Check if base tile is suitable (e.g., not Water or Mountain)
                # Note: self.grid[x][y] is base terrain, self.get_tile() also considers overlays.
                # We should check the base terrain from self.grid.
                base_tile = self.grid[check_x][check_y] # Direct grid access for base terrain
                if base_tile in ["Water", "Mountain"]: # Add other non-placeable terrains if any
                    # print(f"Placement check: Unsuitable terrain '{base_tile}' for {furniture_item_name} at ({check_x},{check_y})")
                    return False

                # Building checks for furniture requiring specific building tags
                if required_tags:
                    current_tile_building = self.get_building_at(check_x, check_y)
                    if r_offset == 0 and c_offset == 0: # First tile
                        first_tile_building = current_tile_building
                        if not first_tile_building: # Must be in a building if tags are required
                            # print(f"Placement check: {furniture_item_name} requires building, but not placed in one at ({check_x},{check_y}).")
                            return False
                    elif current_tile_building != first_tile_building: # All parts must be in the SAME building
                        all_tiles_in_same_building = False
                        # print(f"Placement check: {furniture_item_name} spans multiple buildings or is partially outside.")
                        break
            if not all_tiles_in_same_building:
                return False

        # After checking all tiles, if tags are required, verify building has them
        if required_tags and first_tile_building: # We know it's in a building and all parts in same building
            building_tags = first_tile_building.functionality.get("tags", [])
            for req_tag in required_tags:
                if req_tag not in building_tags:
                    # print(f"Placement check: Building '{first_tile_building.display_name}' lacks required tag '{req_tag}' for {furniture_item_name}.")
                    return False
        elif required_tags and not first_tile_building: # Should have been caught earlier, but double check
            # print(f"Placement check: {furniture_item_name} requires building tags but not placed in any building.")
            return False

        # TODO: Add more rules:
        # - Cannot block doorways or critical paths (more complex pathfinding check)

        return True

    def get_furniture_at(self, x: int, y: int) -> Optional[Furniture]:
        """Returns the furniture object at a given coordinate, if any."""
        for item in self.furniture:
            if item.is_inside(x,y):
                return item
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

    def apply_event_effects(self, event_instance: 'ActiveEvent'):
        """Applies the effects of a triggered event."""
        from .event_manager import ActiveEvent # Local import for type hint

        print(f"DEBUG: Applying effects for event: {event_instance.event_id} - {event_instance.description}")
        for effect_data in event_instance.effects:
            effect_type = effect_data.get("type")

            if effect_type == "add_character_status":
                target_char_name = event_instance.instance_data.get("target_character_name")
                if target_char_name:
                    target_char = next((c for c in self.characters if c.name == target_char_name), None)
                    if target_char:
                        target_char.apply_status_effect(effect_data, self)
                        # Add to affected list if not already present
                        if target_char.name not in event_instance.affected_character_names:
                            event_instance.affected_character_names.append(target_char.name)

                        # Apply shared experience relationship modifier
                        # This character (target_char) just got affected.
                        # Check against all *other* already affected characters for this event instance.
                        for other_affected_char_name in event_instance.affected_character_names:
                            if other_affected_char_name != target_char.name:
                                other_char_obj = self.get_character_by_name(other_affected_char_name)
                                if other_char_obj:
                                    # Simple +1 for shared experience, could be configured per event later
                                    relationship_change = 1
                                    reason = f"experienced '{event_instance.description}' alongside {other_char_obj.name}"
                                    target_char.modify_relationship(other_char_obj.name, relationship_change, self, reason=reason)

                                    reason_other = f"experienced '{event_instance.description}' alongside {target_char.name}"
                                    other_char_obj.modify_relationship(target_char.name, relationship_change, self, reason=reason_other)
                                    # Avoid spamming logs for this, or make it a rarer memory.
                                    # target_char.add_memory(f"Shared event '{event_instance.description}' with {other_char_obj.name}, rel +{relationship_change}.")
                                    # other_char_obj.add_memory(f"Shared event '{event_instance.description}' with {target_char.name}, rel +{relationship_change}.")
                    else:
                        print(f"Warning: Could not find target character {target_char_name} for status effect from event {event_instance.event_id}")
                else: # Should be a global character effect, or target all. For now, assume targeted events specify target via instance_data
                    print(f"Warning: Effect 'add_character_status' for event {event_instance.event_id} needs a target character.")

            elif effect_type == "modify_resource_yield":
                resource_type = effect_data.get("resource_type")
                multiplier = effect_data.get("multiplier", 1.0)
                duration_days = effect_data.get("duration_days", 0)
                if resource_type and duration_days > 0:
                    # Store this modifier in the world, to be checked by resource gathering tasks
                    # Key could be f"yield_modifier_{resource_type}"
                    modifier_key = f"yield_multiplier_{resource_type}"
                    self.active_world_effects[modifier_key] = {
                        "multiplier": multiplier,
                        "expires_tick": self.game_time.current_total_ticks + (duration_days * self.game_time.ticks_per_day),
                        "event_id": event_instance.event_id # To know which event caused it for removal
                    }
                    self.add_event_log_message(f"Yield for {resource_type} is now x{multiplier} for {duration_days} days (due to {event_instance.description}).")

            elif effect_type == "modify_crafting_output":
                item_type = effect_data.get("item_type") # e.g., "Tool"
                bonus = effect_data.get("bonus", {}) # e.g., {"durability_multiplier": 1.2}
                duration_days = effect_data.get("duration_days", 0)
                if item_type and bonus and duration_days > 0:
                    modifier_key = f"craft_bonus_{item_type}"
                    self.active_world_effects[modifier_key] = {
                        "bonus_details": bonus,
                        "expires_tick": self.game_time.current_total_ticks + (duration_days * self.game_time.ticks_per_day),
                        "event_id": event_instance.event_id
                    }
                    self.add_event_log_message(f"Crafting for {item_type}s might have bonuses for {duration_days} days (due to {event_instance.description}).")

            # Add more effect handlers here
            else:
                print(f"Warning: Unknown or unhandled effect type '{effect_type}' for event {event_instance.event_id}")

    def expire_event_effects(self, event_instance: 'ActiveEvent'):
        """Removes effects of an expired event from the world state."""
        from .event_manager import ActiveEvent # Local import for type hint

        print(f"DEBUG: Expiring effects for event: {event_instance.event_id} - {event_instance.description}")
        # Remove global world effects tied to this event_instance.event_id
        effects_to_remove_keys = []
        for key, effect_details in self.active_world_effects.items():
            if effect_details.get("event_id") == event_instance.event_id:
                effects_to_remove_keys.append(key)

        for key in effects_to_remove_keys:
            removed_effect = self.active_world_effects.pop(key)
            self.add_event_log_message(f"World effect '{key}' (bonus: {removed_effect.get('multiplier') or removed_effect.get('bonus_details')}) from event '{event_instance.description}' has expired.")
            print(f"World effect '{key}' from event '{event_instance.description}' expired.")

        # Character status effects are managed by Character.process_status_effects based on their own duration.
        # If an event ending needs to explicitly remove a status it applied regardless of status duration,
        # that would need specific logic here or a different effect type.
        # For now, status effects time out on their own.
