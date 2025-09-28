# game/world.py
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building
from .data import STRUCTURE_BLUEPRINTS, MARKET_PRICES, BLUEPRINTS
from .rumor import Rumor
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
        self.base_market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_location: Tuple[int, int] = (5, 5) # Central market location
        self.resource_yield_multipliers: Dict[str, float] = {
            "Wood": 1.0,
            "Stone": 1.0,
            "Herbs": 1.0,
            "Food": 1.0,
        }
        self.market_price_multipliers: Dict[str, float] = {
            item_name: 1.0 for item_name in self.base_market_prices.keys()
        }
        self.travel_speed_modifier: float = 1.0
        self.campaign_promises: Dict[str, List[Dict[str, Any]]] = {}
        self.active_campaign_cycle_start: Optional[int] = None
        self.last_campaign_day: Optional[int] = None
        self.resource_collection_directives: Dict[str, Dict[str, Any]] = {}
        self.treasury_coins: int = getattr(config, "STARTING_TREASURY_COINS", 0)
        self.pending_wages: List[Dict[str, Any]] = []
        self.todays_wages_paid: int = 0
        self.todays_wages_owed: int = 0
        self.last_daily_economic_report: Dict[str, Any] = {}
        self.crime_reports: List[Dict[str, Any]] = []

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
        if self.weather != new_weather:
            self.weather = new_weather
            self.add_event_log_message(f"Weather shifts to {new_weather}.")
            self._recalculate_environment_effects()

    def advance_season(self):
        self.season_index = (self.season_index + 1) % len(World.SEASONS)
        self.season = World.SEASONS[self.season_index]
        print(f"The season has changed to {self.season}.")
        if self.season == "Winter": self.update_weather("Snowy")
        elif self.season == "Spring": self.update_weather("Rainy")
        elif self.season == "Summer": self.update_weather("Sunny")
        else: self.update_weather("Cloudy")
        self._recalculate_environment_effects()

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
        # Campaign bookkeeping
        self.fulfill_campaign_promises(winner)
        self.active_campaign_cycle_start = None

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

    # --- Environment & Economy Utilities ---

    def _recalculate_environment_effects(self):
        """Rebuilds environmental modifiers from season, weather, and active policies."""
        # Reset modifiers
        for resource_name in list(self.resource_yield_multipliers.keys()):
            self.resource_yield_multipliers[resource_name] = 1.0
        self.travel_speed_modifier = 1.0
        for item_name in list(self.market_price_multipliers.keys()):
            self.market_price_multipliers[item_name] = 1.0

        # Seasonal baselines
        if self.season == "Winter":
            self.resource_yield_multipliers["Wood"] *= 0.8
            self.resource_yield_multipliers["Herbs"] *= 0.5
            self.travel_speed_modifier *= 0.85
            self.market_price_multipliers["Food"] *= 1.25
        elif self.season == "Summer":
            self.resource_yield_multipliers["Wood"] *= 1.1
            self.resource_yield_multipliers["Herbs"] *= 1.2
            self.market_price_multipliers["Food"] *= 0.9
        elif self.season == "Autumn":
            self.resource_yield_multipliers["Food"] *= 1.15

        # Weather adjustments
        if self.weather == "Rainy":
            self.resource_yield_multipliers["Herbs"] *= 1.2
            self.travel_speed_modifier *= 0.9
        elif self.weather == "Snowy":
            self.resource_yield_multipliers["Wood"] *= 0.9
            self.resource_yield_multipliers["Stone"] *= 0.85
            self.travel_speed_modifier *= 0.75
            self.market_price_multipliers["Wood"] *= 1.1
        elif self.weather == "Cloudy":
            self.travel_speed_modifier *= 0.95
        elif self.weather == "Sunny":
            self.resource_yield_multipliers["Stone"] *= 1.05

        # Apply active world effects (e.g., mayoral policies)
        if self.active_world_effects:
            for effect_key, effect_data in list(self.active_world_effects.items()):
                resource_bonus = effect_data.get("resource_yield_bonus")
                if resource_bonus:
                    res_name = resource_bonus.get("resource")
                    multiplier = resource_bonus.get("multiplier", 1.0)
                    if res_name in self.resource_yield_multipliers:
                        self.resource_yield_multipliers[res_name] *= multiplier
                travel_bonus = effect_data.get("travel_speed_multiplier")
                if travel_bonus:
                    self.travel_speed_modifier *= travel_bonus
                market_bonus = effect_data.get("market_price_adjustment")
                if market_bonus:
                    for item_name, multiplier in market_bonus.items():
                        if item_name in self.market_price_multipliers:
                            self.market_price_multipliers[item_name] *= multiplier

        # Supply and demand nudges based on resource totals
        pressures = self.identify_resource_pressures()
        for pressure in pressures:
            resource = pressure["resource"]
            status = pressure["status"]
            severity = pressure["severity"]
            multiplier_delta = 0.05 * min(3, max(1, severity // 10))
            if status == "shortage":
                if resource in self.market_price_multipliers:
                    self.market_price_multipliers[resource] *= (1.0 + multiplier_delta)
            elif status == "surplus":
                if resource in self.market_price_multipliers:
                    self.market_price_multipliers[resource] *= max(0.5, 1.0 - multiplier_delta)

        # Rebuild market price table from multipliers
        for item_name, base_price in self.base_market_prices.items():
            adjusted_price = int(round(base_price * self.market_price_multipliers.get(item_name, 1.0)))
            self.market_prices[item_name] = max(1, adjusted_price)

    def add_temporary_world_effect(self, effect_key: str, effect_data: Dict[str, Any]):
        """Adds or replaces a temporary world-level effect and reapplies environment modifiers."""
        self.active_world_effects[effect_key] = effect_data
        self._recalculate_environment_effects()

    def _cleanup_world_effects(self):
        if not self.game_time:
            return
        removed_keys: List[str] = []
        for effect_key, effect_data in list(self.active_world_effects.items()):
            expires_day = effect_data.get("expires_day")
            if expires_day is not None and expires_day < self.game_time.current_day:
                removed_keys.append(effect_key)
                del self.active_world_effects[effect_key]
        if removed_keys:
            self.add_event_log_message(f"World effects expired: {removed_keys}")
            self._recalculate_environment_effects()

    def get_resource_yield_multiplier(self, resource_name: str) -> float:
        return self.resource_yield_multipliers.get(resource_name, 1.0)

    def get_travel_speed_modifier(self) -> float:
        return max(0.0, self.travel_speed_modifier)

    def get_market_price(self, item_name: str) -> int:
        return self.market_prices.get(item_name, self.base_market_prices.get(item_name, 0))

    def get_total_resource_quantity(self, resource_name: str) -> int:
        total = 0
        for stockpile in self.stockpiles:
            total += stockpile.inventory.get(resource_name, 0)
        for character in self.characters:
            total += character.inventory.get(resource_name, 0)
        return total

    def _withdraw_from_stockpiles(self, resource_name: str, quantity: int) -> int:
        if quantity <= 0:
            return 0
        amount_taken = 0
        remaining = quantity
        sorted_stockpiles = sorted(
            self.stockpiles,
            key=lambda sp: sp.inventory.get(resource_name, 0),
            reverse=True,
        )
        for stockpile in sorted_stockpiles:
            available = stockpile.inventory.get(resource_name, 0)
            if available <= 0:
                continue
            take = min(available, remaining)
            success, removed = stockpile.remove_item(resource_name, take)
            if not success or removed <= 0:
                continue
            amount_taken += removed
            remaining -= removed
            if self.game_time:
                self.ledger.update_stockpile_record(stockpile.name, stockpile.inventory, self.game_time.current_day)
            if remaining <= 0:
                break
        return amount_taken

    def _consume_resource_for_character(self, character: 'Character', resource_name: str, quantity: int) -> int:
        if quantity <= 0:
            return 0
        consumed = 0
        available = character.inventory.get(resource_name, 0)
        if available > 0:
            take = min(quantity, available)
            character.inventory[resource_name] = available - take
            if character.inventory[resource_name] <= 0:
                del character.inventory[resource_name]
            consumed += take
        if consumed < quantity:
            pulled = self._withdraw_from_stockpiles(resource_name, quantity - consumed)
            if pulled > 0:
                consumed += pulled
        return consumed

    def identify_resource_pressures(self) -> List[Dict[str, Any]]:
        """Returns resource pressure descriptors sorted by severity."""
        pressures: List[Dict[str, Any]] = []
        resources_to_check = ["Wood", "Stone", "Herbs", "Food"]
        for resource in resources_to_check:
            quantity = self.get_total_resource_quantity(resource)
            low_threshold = getattr(config, "MAYOR_RESOURCE_LOW_THRESHOLD", 20)
            high_threshold = getattr(config, "MAYOR_RESOURCE_HIGH_THRESHOLD", 150)
            if quantity < low_threshold:
                severity = low_threshold - quantity
                pressures.append({
                    "resource": resource,
                    "status": "shortage",
                    "quantity": quantity,
                    "threshold": low_threshold,
                    "severity": severity,
                })
            elif quantity > high_threshold:
                severity = quantity - high_threshold
                pressures.append({
                    "resource": resource,
                    "status": "surplus",
                    "quantity": quantity,
                    "threshold": high_threshold,
                    "severity": severity,
                })
        pressures.sort(key=lambda entry: entry.get("severity", 0), reverse=True)
        return pressures

    def set_resource_collection_directive(
        self,
        resource_name: str,
        per_trip_quota: int,
        duration_days: int,
        reason: str,
        originator: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.game_time:
            raise ValueError("Cannot set resource directive without game time reference.")

        directive = {
            "resource": resource_name,
            "per_trip_quota": max(1, per_trip_quota),
            "set_day": self.game_time.current_day,
            "expires_day": self.game_time.current_day + max(1, duration_days),
            "reason": reason,
            "originator": originator,
            "last_reminded_day": None,
        }
        self.resource_collection_directives[resource_name] = directive
        summary = f"Resource directive for {resource_name}: gather at least {directive['per_trip_quota']} per trip"
        if originator:
            summary += f" (ordered by {originator})"
        self.add_event_log_message(summary)
        self.add_notable_event(
            "ResourceDirective",
            {
                "summary": summary,
                "resource": resource_name,
                "originator": originator,
            },
        )
        return directive

    def get_resource_directive(self, resource_name: str) -> Optional[Dict[str, Any]]:
        directive = self.resource_collection_directives.get(resource_name)
        if not directive or not self.game_time:
            return directive
        if directive["expires_day"] < self.game_time.current_day:
            # Expired directive
            del self.resource_collection_directives[resource_name]
            return None
        return directive

    def expire_resource_directives(self):
        if not self.game_time:
            return
        expired: List[str] = []
        for resource_name, directive in list(self.resource_collection_directives.items()):
            if directive["expires_day"] < self.game_time.current_day:
                expired.append(resource_name)
                del self.resource_collection_directives[resource_name]
        if expired:
            self.add_event_log_message(f"Resource directives concluded for: {expired}")

    def _apply_daily_food_consumption(self, report: Dict[str, Any]):
        per_capita = getattr(config, "DAILY_FOOD_CONSUMPTION_PER_CITIZEN", 0)
        hunger_recovery = BLUEPRINTS.get("Food", {}).get("hunger_satisfaction", 40)
        total_consumed = 0
        total_deficit = 0
        if per_capita <= 0:
            report["food_consumed"] = total_consumed
            report["food_deficit"] = total_deficit
            return

        for character in self.characters:
            required = per_capita
            consumed = self._consume_resource_for_character(character, "Food", required)
            if consumed > 0:
                total_consumed += consumed
                current_hunger = character.needs.get("Hunger", 50)
                hunger_gain = hunger_recovery * consumed
                character.needs["Hunger"] = min(config.NEED_SCORE_MAX, current_hunger + hunger_gain)
                ration_text = "ration" if consumed == 1 else "rations"
                character.add_memory(f"Shared the daily meal ({consumed} {ration_text}).")
                character.update_mood_score(config.MOOD_CHANGE_NEED_FULFILLED, "Ate communal meal")
            if consumed < required:
                shortage = required - consumed
                total_deficit += shortage
                current_hunger = character.needs.get("Hunger", 50)
                character.needs["Hunger"] = max(
                    config.NEED_SCORE_MIN,
                    current_hunger - getattr(config, "STARVATION_HUNGER_PENALTY", 10),
                )
                character.update_mood_score(getattr(config, "MOOD_CHANGE_STARVING", -12), "Missed daily ration")
                character.add_memory("Went hungry today—stores are running low.")
        report["food_consumed"] = total_consumed
        report["food_deficit"] = total_deficit

    def _get_security_modifier(self) -> float:
        modifier = 1.0
        if any(char.job == "Sheriff" for char in self.characters):
            modifier *= 0.6
        if any(char.job == "Deputy" for char in self.characters):
            modifier *= 0.75
        return modifier

    def _select_theft_target(self) -> Optional[Tuple[str, Stockpile]]:
        candidates: List[Tuple[str, Stockpile, float]] = []
        for stockpile in self.stockpiles:
            for resource_name, quantity in stockpile.inventory.items():
                if quantity <= 0:
                    continue
                desirability = float(quantity)
                if resource_name == "Food":
                    desirability *= 2.0
                candidates.append((resource_name, stockpile, desirability))
        if not candidates:
            return None
        total_weight = sum(weight for _, _, weight in candidates)
        if total_weight <= 0:
            return None
        pick = random.uniform(0, total_weight)
        cumulative = 0.0
        for resource_name, stockpile, weight in candidates:
            cumulative += weight
            if pick <= cumulative:
                return resource_name, stockpile
        return candidates[-1][0], candidates[-1][1]

    def _resolve_theft_attempts(self, report: Dict[str, Any]):
        base_chance = getattr(config, "THEFT_BASE_CHANCE", 0.0)
        theft_events: List[Dict[str, Any]] = []
        if base_chance <= 0 or not self.stockpiles:
            report["crime_events"] = theft_events
            return

        security_modifier = self._get_security_modifier()
        hunger_threshold = getattr(config, "THEFT_HUNGER_THRESHOLD", 35)
        desperation_scale = getattr(config, "THEFT_DESPERATION_SCALE", 0.3)
        low_funds_threshold = getattr(config, "THEFT_LOW_FUNDS_THRESHOLD", 5)
        max_quantity = getattr(config, "THEFT_MAX_QUANTITY", 2)
        detection_base = getattr(config, "THEFT_DETECTION_BASE", 0.25)

        for character in self.characters:
            hunger = character.needs.get("Hunger", 50)
            desperation = 0.0
            if hunger < hunger_threshold:
                desperation += (hunger_threshold - hunger) / max(1, hunger_threshold)
            if character.money < low_funds_threshold:
                desperation += 0.5
            if desperation <= 0:
                continue

            chance = (base_chance + desperation * desperation_scale) * security_modifier
            if random.random() >= chance:
                continue

            theft_target = self._select_theft_target()
            if not theft_target:
                continue
            resource_name, stockpile = theft_target
            available_qty = stockpile.inventory.get(resource_name, 0)
            if available_qty <= 0:
                continue
            steal_qty = min(max_quantity, available_qty)
            success, removed = stockpile.remove_item(resource_name, steal_qty)
            if not success or removed <= 0:
                continue

            character.inventory[resource_name] = character.inventory.get(resource_name, 0) + removed
            description = f"{character.name} stole {removed} {resource_name} from {stockpile.name}"

            detection_chance = detection_base / max(0.25, security_modifier)
            if random.random() < detection_chance:
                description += " but was caught"
                character.add_memory("Was caught stealing from the stockpile.")
                character.update_reputation(-3, "Caught stealing supplies", self)
                character.update_mood_score(getattr(config, "MOOD_CHANGE_CAUGHT_STEALING", -15), "Caught stealing supplies")
            else:
                character.add_memory(f"Stole {removed} {resource_name} from {stockpile.name} under cover of night.")
                character.update_mood_score(getattr(config, "MOOD_CHANGE_STOLE_SUCCESS", 2), "Stole supplies without notice")

            theft_events.append({
                "character": character.name,
                "resource": resource_name,
                "amount": removed,
                "description": description,
            })
            if self.game_time:
                self.ledger.update_stockpile_record(stockpile.name, stockpile.inventory, self.game_time.current_day)

        if theft_events:
            day_value = self.game_time.current_day if self.game_time else -1
            for event in theft_events:
                self.crime_reports.append({"day": day_value, **event})
            self.crime_reports = self.crime_reports[-12:]
        report["crime_events"] = theft_events

    def _settle_wage_backlog(self) -> int:
        if not self.pending_wages or self.treasury_coins <= 0:
            return 0
        paid_total = 0
        remaining_debts: List[Dict[str, Any]] = []
        for debt in self.pending_wages:
            amount_due = debt.get("amount_due", 0)
            if amount_due <= 0:
                continue
            character = self.get_character_by_name(debt.get("character", ""))
            if not character:
                continue
            payment = min(amount_due, self.treasury_coins)
            if payment <= 0:
                remaining_debts.append(debt)
                continue
            self.treasury_coins -= payment
            character.money += payment
            paid_total += payment
            amount_due -= payment
            character.add_memory(f"Received {payment} coin{'s' if payment != 1 else ''} in back pay for {debt.get('reason', 'work')}.")
            character.update_mood_score(config.MOOD_CHANGE_GOT_PAID, "Received back pay")
            if amount_due > 0:
                debt["amount_due"] = amount_due
                remaining_debts.append(debt)
            else:
                self.add_event_log_message(f"Cleared wage arrears for {character.name}'s {debt.get('reason', 'duties')}.")
        self.pending_wages = remaining_debts
        self.todays_wages_paid += paid_total
        return paid_total

    def process_payment(self, character: 'Character', amount: int, reason: str) -> Tuple[int, int]:
        if amount <= 0:
            return 0, 0
        paid = min(amount, self.treasury_coins)
        if paid > 0:
            self.treasury_coins -= paid
            character.money += paid
            self.todays_wages_paid += paid
        owed = amount - paid
        if owed > 0:
            self.todays_wages_owed += owed
            debt_record = {
                "character": character.name,
                "amount_due": owed,
                "reason": reason,
                "day_incurred": self.game_time.current_day if self.game_time else -1,
            }
            self.pending_wages.append(debt_record)
            self.add_event_log_message(
                f"Treasury short {owed} coins for {character.name}'s {reason}. Added to wage arrears."
            )
        return paid, owed

    def process_daily_economy(self):
        if not self.game_time:
            return

        previous_wages_paid = self.todays_wages_paid
        previous_wages_owed = self.todays_wages_owed
        self.todays_wages_paid = 0
        self.todays_wages_owed = 0

        report: Dict[str, Any] = {
            "day": self.game_time.current_day,
            "tax_collected": 0,
            "food_consumed": 0,
            "food_deficit": 0,
            "wages_paid": previous_wages_paid,
            "wages_owed": previous_wages_owed,
            "arrears": sum(debt.get("amount_due", 0) for debt in self.pending_wages),
            "arrears_paid": 0,
            "crime_events": [],
            "treasury": self.treasury_coins,
        }

        tax_income = getattr(config, "DAILY_BASE_TAX_INCOME", 0)
        if tax_income:
            self.treasury_coins += tax_income
            report["tax_collected"] = tax_income

        report["arrears_paid"] = self._settle_wage_backlog()
        report["treasury"] = self.treasury_coins
        report["arrears"] = sum(debt.get("amount_due", 0) for debt in self.pending_wages)

        self._apply_daily_food_consumption(report)
        self._resolve_theft_attempts(report)

        summary = (
            f"Economic summary — Treasury {self.treasury_coins}c "
            f"(tax +{report['tax_collected']}c, wages paid {report['wages_paid']}c, arrears settled {report['arrears_paid']}c). "
            f"Outstanding arrears {report['arrears']}c, food deficit {report['food_deficit']} rations."
        )
        self.add_event_log_message(summary)
        for crime_event in report.get("crime_events", []):
            self.add_event_log_message(f"Security report: {crime_event['description']}.")

        self.last_daily_economic_report = report

    # --- Governance & Campaign Management ---

    def _identify_mayoral_candidates(self) -> List['Character']:
        candidates: List['Character'] = []
        for char in self.characters:
            leadership_skill = char.skills.get("Leadership", {}).get("level", 0) if hasattr(char, "skills") else 0
            is_noble_lord = getattr(char, "rank", None) == "Noble Lord"
            if char.job == "Mayor":
                candidates.append(char)
            elif is_noble_lord or leadership_skill >= 3:
                candidates.append(char)
        return candidates

    def manage_campaigns(self):
        if not self.game_time:
            return
        days_left = getattr(self.game_time, "days_until_election", None)
        if days_left is None or days_left <= 0 or days_left > 5:
            self.active_campaign_cycle_start = None
            return

        if self.active_campaign_cycle_start is None:
            self.active_campaign_cycle_start = self.game_time.current_day
            self.add_event_log_message("Election season heats up. Candidates begin campaigning.")

        if self.last_campaign_day == self.game_time.current_day:
            return
        self.last_campaign_day = self.game_time.current_day

        pressures = self.identify_resource_pressures()
        candidates = self._identify_mayoral_candidates()
        if not candidates:
            return

        for candidate in candidates:
            promises_for_cycle = [
                promise for promise in self.campaign_promises.get(candidate.name, [])
                if promise.get("cycle_start_day") == self.active_campaign_cycle_start
            ]
            if promises_for_cycle:
                continue

            selected_issue: Optional[Dict[str, Any]] = pressures[0] if pressures else None
            if selected_issue:
                issue_resource = selected_issue["resource"]
                if selected_issue["status"] == "shortage":
                    promise_type = "resource_drive"
                    summary = f"promises to boost {issue_resource} supplies"
                else:
                    promise_type = "trade_policy"
                    summary = f"pledges to lower prices on {issue_resource}"
            else:
                issue_resource = None
                promise_type = "community_event"
                summary = "vows to host a community gathering to lift spirits"

            promise = {
                "candidate": candidate.name,
                "type": promise_type,
                "resource": issue_resource,
                "status": "pledged",
                "created_day": self.game_time.current_day,
                "cycle_start_day": self.active_campaign_cycle_start,
                "summary": summary,
            }
            self.campaign_promises.setdefault(candidate.name, []).append(promise)

            candidate.add_memory(f"Campaign promise: {summary}.")
            self.add_event_log_message(f"{candidate.name} {summary} ahead of the election.")
            self.add_notable_event(
                "CampaignPromise",
                {
                    "candidate": candidate.name,
                    "summary": summary,
                    "resource": issue_resource,
                },
            )

    def fulfill_campaign_promises(self, mayor: 'Character'):
        if not self.game_time:
            return
        promises = self.campaign_promises.get(mayor.name, [])
        if not promises:
            return

        for promise in promises:
            if promise.get("status") != "pledged":
                continue
            promise_type = promise.get("type")
            resource = promise.get("resource")
            if promise_type == "resource_drive" and resource:
                shortage_info = next((p for p in self.identify_resource_pressures() if p["resource"] == resource and p["status"] == "shortage"), None)
                severity = shortage_info["severity"] if shortage_info else 10
                per_trip_quota = max(5, min(20, severity + 5))
                duration_days = 7
                directive = self.set_resource_collection_directive(
                    resource,
                    per_trip_quota,
                    duration_days,
                    reason=f"Campaign pledge by Mayor {mayor.name}",
                    originator=mayor.name,
                )
                effect_key = f"mayor_policy_{resource}_{self.game_time.current_day}"
                self.add_temporary_world_effect(
                    effect_key,
                    {
                        "resource_yield_bonus": {
                            "resource": resource,
                            "multiplier": 1.15,
                        },
                        "expires_day": directive["expires_day"],
                    },
                )
                self.add_event_log_message(
                    f"Mayor {mayor.name} enacts a focused gathering effort for {resource}, boosting yields and directing workers."
                )
                promise["status"] = "enacted"
                promise["fulfilled_day"] = self.game_time.current_day
            elif promise_type == "trade_policy" and resource:
                effect_key = f"market_relief_{resource}_{self.game_time.current_day}"
                expires_day = self.game_time.current_day + 5
                self.add_temporary_world_effect(
                    effect_key,
                    {
                        "market_price_adjustment": {resource: 0.85},
                        "expires_day": expires_day,
                    },
                )
                self.add_event_log_message(
                    f"Mayor {mayor.name} temporarily subsidises {resource}, easing prices for citizens."
                )
                promise["status"] = "enacted"
                promise["fulfilled_day"] = self.game_time.current_day
            elif promise_type == "community_event":
                effect_key = f"community_morale_{self.game_time.current_day}"
                expires_day = self.game_time.current_day + 3
                self.add_temporary_world_effect(
                    effect_key,
                    {
                        "travel_speed_multiplier": 1.05,
                        "expires_day": expires_day,
                    },
                )
                self.add_event_log_message(
                    f"Mayor {mayor.name} hosts a festival to build community spirit."
                )
                promise["status"] = "enacted"
                promise["fulfilled_day"] = self.game_time.current_day

    def manage_economy(self):
        if not self.game_time:
            return
        pressures = self.identify_resource_pressures()
        for pressure in pressures:
            if pressure["status"] != "shortage":
                continue
            resource = pressure["resource"]
            if resource in self.resource_collection_directives:
                continue
            severity = pressure["severity"]
            per_trip_quota = max(4, min(15, severity + 3))
            duration_days = 5
            self.set_resource_collection_directive(
                resource,
                per_trip_quota,
                duration_days,
                reason="Automated economic response to shortage",
                originator="Economic Council",
            )

    def daily_environment_tick(self):
        if not self.game_time:
            return

        # Advance season at configured interval
        if (
            self.game_time.current_day > 1
            and (self.game_time.current_day - 1) % getattr(config, "DAYS_PER_SEASON", 10) == 0
        ):
            self.advance_season()

        # Chance for weather change biased by season
        weather_options = {
            "Spring": ["Rainy", "Cloudy", "Sunny"],
            "Summer": ["Sunny", "Sunny", "Cloudy"],
            "Autumn": ["Cloudy", "Rainy", "Sunny"],
            "Winter": ["Snowy", "Cloudy", "Snowy"],
        }
        current_choices = weather_options.get(self.season, [self.weather])
        if random.random() < 0.35:
            self.update_weather(random.choice(current_choices))

        self._cleanup_world_effects()
        self.expire_resource_directives()
        self._recalculate_environment_effects()
