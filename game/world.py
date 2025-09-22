# game/world.py
from typing import TYPE_CHECKING, List, Optional, Tuple, Dict, Any # Added Any
from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building
from .data import STRUCTURE_BLUEPRINTS, MARKET_PRICES # For get_tile fallback if needed, and add_building
# from .furniture import Furniture # Keep commented if main.py doesn't use it for this test
from .rumor import Rumor # Added for rumor system
from .edict import Edict
from . import config

if TYPE_CHECKING:
    from .character import Character
    # If Furniture class is used, it should be imported here for type checking too
    # from .furniture import Furniture
    # from .rumor import Rumor # Already imported above


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
        self.buildings: List[Building] = [] # Re-added
        # self.furniture: List[Furniture] = [] # Re-added, but keep commented if not used by this test
        self.ledger: Ledger = Ledger()
        self.game_time: Optional[Time] = game_time_ref
        self.work_orders: List[WorkOrder] = []
        self.event_log: List[str] = []
        self.active_world_effects: Dict[str, Any] = {}
        self.recent_notable_events: List[Dict[str, Any]] = [] # For rumor spreading
        self.rumors: List[Rumor] = [] # Added for rumor system
        self.market_prices: Dict[str, int] = MARKET_PRICES
        self.market_location: Tuple[int, int] = (5, 5) # Central market location
        self.last_tax_collection_day: int = -1
        self.edicts: List[Edict] = []

    def update_rumors_daily(self):
        """Decays strength of all rumors and removes very weak ones."""
        if not self.rumors:
            return

        # Iterate backwards for safe removal
        for i in range(len(self.rumors) - 1, -1, -1):
            rumor = self.rumors[i]
            rumor.decay(config.RUMOR_STRENGTH_DECAY_DAILY)
            if rumor.current_strength <= 0:
                self.add_event_log_message(f"Rumor faded: {rumor.subject_char_id} - {rumor.content_key} (ID: {rumor.rumor_id[:4]})")
                self.rumors.pop(i)
        # print(f"DEBUG: Daily rumor update complete. {len(self.rumors)} rumors remaining.")


    def __str__(self):
        # furniture_count = len(self.furniture) if hasattr(self, 'furniture') else 0
        # return f"World(Size: {self.grid_size}, Season: {self.season}, Chars: {len(self.characters)}, SPs: {len(self.stockpiles)}, Buildings: {len(self.buildings)}, Furniture: {furniture_count}, WOs: {len(self.work_orders)})"
        return f"World(Size: {self.grid_size}, Season: {self.season}, Chars: {len(self.characters)}, SPs: {len(self.stockpiles)}, Buildings: {len(self.buildings)}, WOs: {len(self.work_orders)})"


    def add_event_log_message(self, message: str): # Added from later step, useful for logging
        if not self.game_time:
            timestamp = "[NoTime]"
        else:
            timestamp = f"D{self.game_time.current_day} T{self.game_time.current_tick}"
        full_message = f"[{timestamp}] {message}"
        self.event_log.append(full_message)
        # print(full_message) # Console print handled by main loop if needed

    def set_game_time(self, game_time_obj: Time):
        if not self.game_time: self.game_time = game_time_obj

    def get_tile(self, x: int, y: int) -> str:
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            return "OutOfBounds"

        # Characters are drawn on top by the UI/print_map_to_console, not part of get_tile's role for terrain/structure

        building_at_loc = self.get_building_at(x, y)
        if building_at_loc:
            return building_at_loc.get_current_map_char()

        # furniture_at_loc = self.get_furniture_at(x,y) # If furniture is re-enabled
        # if furniture_at_loc:
        #     return furniture_at_loc.map_char

        return self.grid[x][y]

    def set_tile(self, x: int, y: int, tile_type: str):
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            is_building_tile = any((x,y) in b.get_tiles_occupied() for b in self.buildings)
            if not is_building_tile: # Only change base grid if no building is there
                 self.grid[x][y] = tile_type

    def add_building(self, building: Building):
        if building not in self.buildings:
            new_building_tiles = building.get_tiles_occupied()
            for tile_coord in new_building_tiles:
                if not (0 <= tile_coord[0] < self.grid_size[0] and 0 <= tile_coord[1] < self.grid_size[1]):
                    print(f"Error: Building '{building.display_name}' at {building.location} is out of bounds.")
                    return
                for existing_b in self.buildings:
                    if tile_coord in existing_b.get_tiles_occupied():
                        print(f"Error: Building '{building.display_name}' overlaps with '{existing_b.display_name}' at {tile_coord}.")
                        return
            self.buildings.append(building)
            print(f"Building: {building.display_name} added at {building.location} to world model.")


    def remove_building(self, building: Building):
        if building in self.buildings:
            self.buildings.remove(building)
            print(f"Removed building: {building.display_name} from {building.location}.")

    def get_building_at(self, x: int, y: int) -> Optional[Building]:
        for building in self.buildings:
            if (x,y) in building.get_tiles_occupied():
                return building
        return None

    def get_operational_buildings_of_type(self, structure_type_str: str) -> List[Building]:
        return [b for b in self.buildings if b.structure_type == structure_type_str and b.is_operational]

    # Furniture methods (can be kept commented if Furniture class is not re-added for this test)
    # def add_furniture(self, furniture_item: 'Furniture'):
    #     if not hasattr(self, 'furniture'): self.furniture = []
    #     if furniture_item not in self.furniture:
    #         self.furniture.append(furniture_item)
    # def get_furniture_at(self, x: int, y: int) -> Optional['Furniture']:
    #     if not hasattr(self, 'furniture'): return None
    #     for item in self.furniture:
    #         if item.is_inside(x,y):
    #             return item
    #     return None
    # def can_place_furniture(self, furniture_item_name: str, x: int, y: int, size: Tuple[int,int], furniture_blueprint: Dict[str, Any]) -> bool:
    #     # Basic check, can be expanded
    #     for r_offset in range(size[1]):
    #         for c_offset in range(size[0]):
    #             check_x, check_y = x + c_offset, y + r_offset
    #             if not (0 <= check_x < self.grid_size[0] and 0 <= check_y < self.grid_size[1]): return False
    #             if self.get_building_at(check_x, check_y) or self.get_furniture_at(check_x, check_y): return False
    #             if self.grid[check_x][check_y] in ["Water", "Mountain"]: return False
    #     return True


    def add_resource(self, resource_name: str, location: tuple[int, int], tile_becomes: str = None):
        x, y = location
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]): return
        if self.get_building_at(x,y): return
        if resource_name not in self.resources: self.resources[resource_name] = []
        self.resources[resource_name].append(location)
        current_tile = self.grid[x][y] # Check base grid before overlaying
        if tile_becomes:
            if current_tile != tile_becomes : self.set_tile(x, y, tile_becomes)
        elif current_tile == "Grass": self.set_tile(x,y, resource_name)


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

    def add_notable_event(self, event_type: str, details: Dict[str, Any], max_events: int = 10):
        """Adds a notable event to the world's recent memory, used for rumor spreading."""
        if not self.game_time:
            print("Warning: Cannot add notable event, game_time not set in world.")
            return

        event_id = f"{event_type}_{self.game_time.current_day}_{random.randint(1000,9999)}" # Simple unique enough ID
        event_data = {
            "id": event_id,
            "type": event_type,
            "day": self.game_time.current_day,
            "details": details # e.g., {"subject": "Harvest", "outcome": "bountiful"} or {"structure_name": "Town Hall"}
        }
        self.recent_notable_events.append(event_data)
        # Keep the list from growing too large
        if len(self.recent_notable_events) > max_events:
            self.recent_notable_events.pop(0) # Remove the oldest event

        self.add_event_log_message(f"Notable Event: {event_type} - {details.get('summary', str(details))}")


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
                        # Stockpiles are overlays, don't change base self.grid tile like resources do
                        # The get_tile method will need to account for stockpiles if they have a map char
                        pass


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

    def get_approved_craft_orders(self) -> List[WorkOrder]:
        approved = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "CraftItem" and wo.assigned_to is None
        ]
        approved.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved

    def get_approved_build_orders(self) -> List[WorkOrder]: # Re-added
        approved_build = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "BuildStructure" and wo.assigned_to is None
        ]
        approved_build.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved_build

    def get_work_order_by_id(self, order_id: str) -> Optional[WorkOrder]:
        for wo in self.work_orders:
            if wo.order_id == order_id:
                return wo
        return None

    def get_character_by_name(self, name: str) -> Optional['Character']: # Added utility
        for char in self.characters:
            if char.name == name:
                return char
        return None

    def add_edict(self, edict: Edict):
        """Adds a new edict to the world."""
        if not self.game_time:
            print("Warning: Cannot add edict, game_time not set in world.")
            return
        self.edicts.append(edict)
        self.add_event_log_message(f"New Edict enacted: {edict.edict_type}. Duration: {edict.duration} days.")

    def update_edicts(self):
        """Processes active edicts, applying their effects and removing expired ones."""
        if not self.game_time:
            return

        # Iterate backwards for safe removal
        for i in range(len(self.edicts) - 1, -1, -1):
            edict = self.edicts[i]
            if not edict.is_active:
                continue

            if edict.start_day is None:
                edict.start_day = self.game_time.current_day

            if self.game_time.current_day >= edict.start_day + edict.duration:
                edict.is_active = False
                self.add_event_log_message(f"Edict expired: {edict.edict_type}.")

        self.edicts = [e for e in self.edicts if e.is_active]

    def get_modified_tax_rate(self) -> float:
        """Calculates the tax rate after applying all active edict effects."""
        base_rate = config.TAX_RATE
        modifier = 0.0
        for edict in self.edicts:
            if edict.is_active:
                modifier += edict.effects.get("tax_rate_modifier", 0.0)
        return base_rate + modifier

    def calculate_total_wealth(self) -> int:
        """
        Calculates the total wealth of the settlement based on all resources
        in the ledger and their market prices.
        """
        total_wealth = 0
        if not self.ledger or not self.market_prices:
            return 0

        for resource_name, stockpiles in self.ledger.records.items():
            if resource_name in self.market_prices:
                total_quantity = sum(stockpiles.values())
                total_wealth += total_quantity * self.market_prices[resource_name]

        return total_wealth

    # Event related methods (can be kept minimal if EventManager is not fully used)
    def apply_event_effects(self, event_instance: Any): # Using Any if ActiveEvent is not defined
        pass # Placeholder
    def expire_event_effects(self, event_instance: Any):
        pass # Placeholder

    def handle_election(self):
        if not self.game_time or not hasattr(self.game_time, 'days_until_election'):
            # Should not happen if timer logic is correctly in Time class
            self.add_event_log_message("Election handling called but game_time or election timer is not properly set up.")
            return

        self.add_event_log_message(f"--- ELECTION DAY (Day {self.game_time.current_day}) ---")

        # Identify candidates: e.g., Nobles or high Leadership
        candidates: List['Character'] = []
        for char in self.characters:
            # Example criteria: Noble Lord rank OR Leadership skill > 3
            # Exclude current mayor from being a "new" candidate if we want to ensure change, or include for re-election.
            # For now, simple criteria:
            is_noble_lord = hasattr(char, 'rank') and char.rank == "Noble Lord"
            leadership_skill = 0
            if hasattr(char, 'skills') and char.skills and "Leadership" in char.skills and isinstance(char.skills["Leadership"], dict):
                leadership_skill = char.skills["Leadership"].get("level",0)

            if is_noble_lord or leadership_skill >= 3: # Min leadership 3 for candidacy
                if char.job != "Mayor": # Don't add current mayor to candidate list this way, handle re-election separately if needed
                    candidates.append(char)

        current_mayor: Optional['Character'] = None
        for char in self.characters:
            if char.job == "Mayor":
                current_mayor = char
                if current_mayor not in candidates: # Allow current mayor to be a candidate
                    # Add them if they meet criteria (e.g. still a Noble Lord, or if their leadership is high enough)
                    # For simplicity, if they are mayor, they can run again.
                    # More complex logic could check if they are eligible for re-election.
                    pass # current_mayor will be handled below

        if not candidates and not current_mayor:
            self.add_event_log_message("No eligible candidates found for Mayor. Election postponed.")
            self.game_time.days_until_election = config.ELECTION_CYCLE_DAYS // 2 # Postpone for a shorter period
            return

        # Add current mayor to candidate list if they exist, to allow for re-election possibility
        # or if they are the only option.
        eligible_candidates_for_vote = candidates[:] # copy
        if current_mayor and current_mayor not in eligible_candidates_for_vote:
             # Re-evaluate if current mayor should always be a candidate or based on criteria
             is_noble_lord = hasattr(current_mayor, 'rank') and current_mayor.rank == "Noble Lord"
             leadership_skill = 0
             if hasattr(current_mayor, 'skills') and current_mayor.skills and "Leadership" in current_mayor.skills and isinstance(current_mayor.skills["Leadership"], dict):
                leadership_skill = current_mayor.skills["Leadership"].get("level",0)
             if is_noble_lord or leadership_skill >=3:
                eligible_candidates_for_vote.append(current_mayor)


        if not eligible_candidates_for_vote: # Still no one after considering current mayor
            self.add_event_log_message("No eligible candidates (including current Mayor) for election. Term extended.")
            if current_mayor:
                 self.add_event_log_message(f"{current_mayor.name} continues as Mayor by default.")
            self.game_time.days_until_election = config.ELECTION_CYCLE_DAYS
            return

        # Winner selection: For now, highest Leadership. Tie-break randomly.
        eligible_candidates_for_vote.sort(key=lambda c: c.skills.get("Leadership", {}).get("level", 0), reverse=True)

        max_leadership = eligible_candidates_for_vote[0].skills.get("Leadership", {}).get("level", 0)
        top_candidates = [c for c in eligible_candidates_for_vote if c.skills.get("Leadership", {}).get("level", 0) == max_leadership]

        winner = random.choice(top_candidates)

        self.add_event_log_message(f"Candidates were: {[c.name for c in eligible_candidates_for_vote]}.")
        self.add_event_log_message(f"{winner.name} has been elected as the new Mayor with Leadership {winner.skills.get('Leadership', {}).get('level', 0)}!")

        if current_mayor and current_mayor.name != winner.name:
            self.add_event_log_message(f"Former Mayor {current_mayor.name} steps down.")
            current_mayor.job = "Noble" # Or "Commoner" or "Unemployed" depending on desired outcome
            current_mayor.current_goal = current_mayor.job_default_goal()
            # Clear subordinates if they were managing people directly as Mayor (not typical with current setup)
            # current_mayor.subordinates_names.clear()
            if current_mayor.name in winner.subordinates_names: # Should not happen
                 winner.remove_subordinate(current_mayor.name)


        winner.job = "Mayor"
        winner.rank = "Noble Lord" # Ensure rank is appropriate
        winner.current_goal = winner.job_default_goal() # Should be "Oversee Settlement"
        winner.appointed_by = None # Elected, not appointed by another individual in this context

        # Clear winner's previous supervisor/appointer if they had one from a lesser role
        if winner.supervisor_name:
            old_supervisor = self.get_character_by_name(winner.supervisor_name)
            if old_supervisor and winner.name in old_supervisor.subordinates_names:
                old_supervisor.remove_subordinate(winner.name)
            winner.supervisor_name = None
        if winner.appointed_by : winner.appointed_by = None


        # Reset election timer
        self.game_time.days_until_election = config.ELECTION_CYCLE_DAYS

    def add_rumor(self, rumor: Rumor):
        """Adds a new rumor to the world, ensuring it's not a duplicate subject/key too recently."""
        # Optional: Check for existing very similar rumors to avoid spam, or just let them stack/replace.
        # For now, just add. More complex logic could check if a rumor about subject_char_id with content_key
        # was added very recently.
        self.rumors.append(rumor)
        self.add_event_log_message(f"New Rumor Circulating: {rumor.subject_char_id} - {rumor.content_key} (Strength: {rumor.initial_strength})")
        # print(f"DEBUG: World added rumor: {rumor}")

    def get_rumor_by_id(self, rumor_id: str) -> Optional[Rumor]:
        """Finds a rumor in the world by its unique ID."""
        for rumor in self.rumors:
            if rumor.rumor_id == rumor_id:
                return rumor
        return None
