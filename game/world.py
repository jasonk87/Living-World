# game/world.py
from __future__ import annotations

import random
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building
from .data import STRUCTURE_BLUEPRINTS, MARKET_PRICES, BLUEPRINTS
from .rumor import Rumor
from . import config
from .goal import Goal, GoalType

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
        self.stockpile_tiles: Dict[Tuple[int, int], str] = {}
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
            "Water": 1.0,
        }
        self.market_price_multipliers: Dict[str, float] = {
            item_name: 1.0 for item_name in self.base_market_prices.keys()
        }
        self.travel_speed_modifier: float = 1.0
        self.environment_effect_snapshot: Dict[str, Any] = {}
        self._last_environment_log_day: Optional[int] = None
        self._previous_environment_digest: Optional[str] = None
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
        self.pending_crimes: List[Dict[str, Any]] = []
        self.active_crimes: Dict[str, Dict[str, Any]] = {}
        self._crime_incident_counter: int = 0
        self.today_surplus_sales: List[Dict[str, Any]] = []
        self._residential_assignments: Dict[str, Tuple[int, int]] = {}

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

        if (x, y) in self.stockpile_tiles:
            return "Stockpile"

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

    def get_building_by_location(self, location: Tuple[int, int]) -> Optional[Building]:
        for building in self.buildings:
            if building.location == location:
                return building
        return None

    def _is_residential(self, building: Building) -> bool:
        tags = building.functionality.get("tags", []) if building.functionality else []
        provides = building.functionality.get("provides_shelter", 0) if building.functionality else 0
        return building.is_operational and "residential" in tags and provides

    def claim_residential_spot(self, character: 'Character') -> Optional[Building]:
        existing_location = self._residential_assignments.get(character.name)
        if existing_location:
            existing = self.get_building_by_location(existing_location)
            if existing and self._is_residential(existing):
                if character.name not in existing.occupants:
                    existing.add_occupant(character.name)
                return existing

        for building in self.buildings:
            if not self._is_residential(building):
                continue
            capacity = int(building.functionality.get("provides_shelter", 0))
            if character.name in building.occupants:
                self._residential_assignments[character.name] = building.location
                return building
            if len(building.occupants) < capacity:
                building.add_occupant(character.name)
                self._residential_assignments[character.name] = building.location
                return building
        return None

    def release_residential_spot(self, character: 'Character'):
        assigned = self._residential_assignments.get(character.name)
        target_building = None
        if assigned:
            target_building = self.get_building_by_location(assigned)
        if not target_building:
            # Attempt to locate any building currently listing the character as an occupant
            for building in self.buildings:
                if character.name in building.occupants:
                    target_building = building
                    break
        if target_building:
            target_building.remove_occupant(character.name)
        if character.name in self._residential_assignments:
            del self._residential_assignments[character.name]

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
                        self.stockpile_tiles[(tile_x, tile_y)] = stockpile.name

            self.add_event_log_message(
                f"Stockpile '{stockpile.name}' registered at tiles {stockpile.deposit_tiles}."
            )


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

    def _next_crime_id(self) -> str:
        self._crime_incident_counter += 1
        return f"crime_{self._crime_incident_counter}"

    def _record_crime_history(self, incident: Dict[str, Any]):
        """Store or update a snapshot of an incident for HUD/history purposes."""
        summary = {
            "id": incident.get("id"),
            "day": incident.get("resolved_day", incident.get("reported_day", -1)),
            "type": incident.get("type", "crime"),
            "suspect": incident.get("suspect"),
            "resource": incident.get("resource"),
            "amount": incident.get("amount"),
            "location": incident.get("location_label"),
            "status": incident.get("status"),
            "assigned_to": incident.get("assigned_to"),
            "result": incident.get("result"),
            "caught": incident.get("caught"),
            "description": incident.get("description"),
        }
        existing = next((entry for entry in self.crime_reports if entry.get("id") == summary["id"]), None)
        if existing:
            existing.update({k: v for k, v in summary.items() if v is not None})
        else:
            self.crime_reports.append(summary)
        self.crime_reports = self.crime_reports[-20:]

    def get_crime_by_id(self, crime_id: str) -> Optional[Dict[str, Any]]:
        if crime_id in self.active_crimes:
            return self.active_crimes[crime_id]
        for crime in self.pending_crimes:
            if crime.get("id") == crime_id:
                return crime
        return next((record for record in reversed(self.crime_reports) if record.get("id") == crime_id), None)

    def claim_next_crime(self, responder_name: str) -> Optional[Dict[str, Any]]:
        """Assign the oldest unclaimed crime incident to a responder."""
        for crime in self.pending_crimes:
            if crime.get("status") not in {"pending", "unassigned"}:
                continue
            next_review_day = crime.get("next_review_day")
            if (
                self.game_time
                and next_review_day is not None
                and next_review_day > self.game_time.current_day
            ):
                continue
            crime["status"] = "assigned"
            crime["assigned_to"] = responder_name
            crime["assignment_day"] = self.game_time.current_day if self.game_time else -1
            crime.pop("next_review_day", None)
            summary = crime.get("summary") or crime.get("description")
            if summary:
                self.add_event_log_message(f"{responder_name} responds to report: {summary}")
            self._record_crime_history(crime)
            self.active_crimes[crime["id"]] = crime
            return crime
        return None

    def resolve_crime_outcome(
        self,
        crime_id: str,
        result: str,
        responder_name: str,
        *,
        caught: bool,
        notes: Optional[str] = None,
        requeue: bool = False,
    ) -> Optional[Dict[str, Any]]:
        crime = self.get_crime_by_id(crime_id)
        if not crime:
            return None

        if requeue:
            crime["status"] = "pending"
            crime["assigned_to"] = None
            crime.pop("assignment_day", None)
            if self.game_time:
                crime["next_review_day"] = self.game_time.current_day + 1
            if notes:
                crime["description"] = f"{crime.get('description', 'Disturbance')} (lead cold: {notes})"
            self._record_crime_history(crime)
            return crime

        crime["status"] = "resolved"
        crime["resolved_day"] = self.game_time.current_day if self.game_time else -1
        crime["resolved_by"] = responder_name
        crime["result"] = result
        crime["caught"] = caught
        if notes:
            crime["resolution_notes"] = notes
            crime["description"] = f"{crime.get('description', 'Disturbance resolved')} ({notes})"
        resolution_blurb = crime.get("description") or result
        self.add_event_log_message(f"{responder_name} resolved {crime.get('type', 'incident')} — {resolution_blurb}.")

        self.pending_crimes = [c for c in self.pending_crimes if c.get("id") != crime_id]
        if crime_id in self.active_crimes:
            del self.active_crimes[crime_id]
        self._record_crime_history(crime)
        return crime

    # Event related methods (can be kept minimal if EventManager is not fully used)
    def _event_attr(self, event_instance: Any, key: str, default: Any = None) -> Any:
        """Safely fetches either a dict key or attribute from an event payload."""
        if isinstance(event_instance, dict):
            return event_instance.get(key, default)
        return getattr(event_instance, key, default)

    def _extract_event_effects(self, event_instance: Any) -> List[Tuple[str, Dict[str, Any]]]:
        """Normalises arbitrary event payloads into world-effect entries."""
        if not event_instance:
            return []

        effect_entries: List[Any] = []
        raw_effects = self._event_attr(event_instance, "effects")
        if isinstance(raw_effects, list):
            effect_entries = raw_effects
        elif isinstance(raw_effects, dict):
            effect_entries = [raw_effects]
        else:
            effect_entries = [event_instance]

        allowed_keys = {"resource_yield_bonus", "travel_speed_multiplier", "market_price_adjustment"}
        base_key = self._event_attr(event_instance, "effect_key") or self._event_attr(event_instance, "id")
        if not base_key:
            base_key = self._event_attr(event_instance, "name")

        extracted: List[Tuple[str, Dict[str, Any]]] = []
        for idx, entry in enumerate(effect_entries):
            entry_key = self._event_attr(entry, "effect_key") or base_key
            if not entry_key:
                if self.game_time:
                    entry_key = f"event_{self.game_time.current_day}_{idx}"
                else:
                    entry_key = f"event_{idx}"

            effect_data: Dict[str, Any] = {}
            for key in allowed_keys:
                value = self._event_attr(entry, key)
                if value is None:
                    value = self._event_attr(event_instance, key)
                if value is not None:
                    effect_data[key] = value

            expires_day = self._event_attr(entry, "expires_day")
            duration_days = self._event_attr(entry, "duration_days")
            if expires_day is None and duration_days is None:
                duration_days = self._event_attr(event_instance, "duration_days")

            if expires_day is None and duration_days is not None and self.game_time:
                expires_day = self.game_time.current_day + max(1, int(duration_days))

            if expires_day is not None:
                effect_data["expires_day"] = expires_day

            if effect_data:
                extracted.append((entry_key, effect_data))

        return extracted

    def apply_event_effects(self, event_instance: Any):  # Using Any if ActiveEvent is not defined
        effects = self._extract_event_effects(event_instance)
        if not effects:
            return

        applied_keys: List[str] = []
        for effect_key, effect_data in effects:
            self.add_temporary_world_effect(effect_key, effect_data)
            applied_keys.append(effect_key)

        summary = self._event_attr(event_instance, "summary") or self._event_attr(event_instance, "type")
        if applied_keys:
            self.add_event_log_message(
                f"Applied world effects {applied_keys} from event {summary or 'unknown'}"
            )

        if isinstance(event_instance, dict):
            stored = event_instance.setdefault("applied_effect_keys", [])
            stored.extend(applied_keys)
        else:
            already = getattr(event_instance, "applied_effect_keys", [])
            setattr(event_instance, "applied_effect_keys", list(already) + applied_keys)

    def expire_event_effects(self, event_instance: Any):
        if not event_instance:
            return

        if isinstance(event_instance, dict):
            effect_keys = list(event_instance.get("applied_effect_keys", []))
        else:
            effect_keys = list(getattr(event_instance, "applied_effect_keys", []))

        if not effect_keys:
            effect_keys = [key for key, _ in self._extract_event_effects(event_instance)]

        removed: List[str] = []
        for effect_key in effect_keys:
            if effect_key in self.active_world_effects:
                del self.active_world_effects[effect_key]
                removed.append(effect_key)

        if removed:
            self.add_event_log_message(f"Expired world effects {removed} tied to resolved event.")
            self._recalculate_environment_effects()

        if isinstance(event_instance, dict):
            event_instance.pop("applied_effect_keys", None)
        else:
            if hasattr(event_instance, "applied_effect_keys"):
                delattr(event_instance, "applied_effect_keys")

    def handle_election(self):
        if not self.game_time or not hasattr(self.game_time, 'days_until_election'):
            # Should not happen if timer logic is correctly in Time class
            self.add_event_log_message("Election handling called but game_time or election timer is not properly set up.")
            return

        self.add_event_log_message(f"--- ELECTION DAY (Day {self.game_time.current_day}) ---")

        # Identify candidates: e.g., Nobles or high Leadership
        candidates: List['Character'] = []
        current_mayor: Optional['Character'] = None
        for char in self.characters:
            if char.job == "Mayor":
                current_mayor = char

            is_noble_lord = hasattr(char, 'rank') and char.rank == "Noble Lord"
            leadership_skill = 0
            if (
                hasattr(char, 'skills')
                and char.skills
                and "Leadership" in char.skills
                and isinstance(char.skills["Leadership"], dict)
            ):
                leadership_skill = char.skills["Leadership"].get("level", 0)

            if (is_noble_lord or leadership_skill >= 3) and char.job != "Mayor":
                candidates.append(char)

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
        self.add_notable_event(
            "RumorStarted",
            {
                "summary": f"Rumor about {rumor.subject_char_id}: {rumor.content_key}",
                "subject": rumor.subject_char_id,
                "strength": rumor.initial_strength,
            },
        )
        # print(f"DEBUG: World added rumor: {rumor}")

    def get_rumor_by_id(self, rumor_id: str) -> Optional[Rumor]:
        """Finds a rumor in the world by its unique ID."""
        for rumor in self.rumors:
            if rumor.rumor_id == rumor_id:
                return rumor
        return None

    def get_rumor_digest(self, limit: int = 8) -> List[Dict[str, Any]]:
        if not self.rumors:
            return []
        sorted_rumors = sorted(self.rumors, key=lambda r: r.current_strength, reverse=True)
        digest: List[Dict[str, Any]] = []
        for rumor in sorted_rumors[:limit]:
            digest.append({
                "id": rumor.rumor_id,
                "subject": rumor.subject_char_id,
                "content": rumor.content_key,
                "strength": rumor.current_strength,
                "known_count": len(rumor.known_by_char_ids),
                "is_positive": rumor.is_positive,
            })
        return digest

    # --- Environment & Economy Utilities ---

    def _recalculate_environment_effects(self):
        """Rebuild environmental modifiers from season, weather, player policies, and economic pressures."""
        previous_snapshot = deepcopy(self.environment_effect_snapshot)

        resource_modifiers: Dict[str, float] = {
            resource: 1.0 for resource in self.resource_yield_multipliers.keys()
        }
        travel_modifier = 1.0
        market_modifiers: Dict[str, float] = {
            item_name: 1.0 for item_name in self.market_price_multipliers.keys()
        }

        contribution_map = {
            "resource_multipliers": {},
            "market_multipliers": {},
            "travel_sources": [],
        }

        def apply_resource(resource: str, multiplier: float, source: str):
            if multiplier == 1.0:
                return
            resource_modifiers[resource] = resource_modifiers.get(resource, 1.0) * multiplier
            contribution_map.setdefault("resource_multipliers", {}).setdefault(resource, []).append({
                "source": source,
                "multiplier": multiplier,
            })

        def apply_market(item: str, multiplier: float, source: str):
            if multiplier == 1.0:
                return
            market_modifiers[item] = market_modifiers.get(item, 1.0) * multiplier
            contribution_map.setdefault("market_multipliers", {}).setdefault(item, []).append({
                "source": source,
                "multiplier": multiplier,
            })

        def apply_travel(multiplier: float, source: str):
            nonlocal travel_modifier
            if multiplier == 1.0:
                return
            travel_modifier *= multiplier
            contribution_map.setdefault("travel_sources", []).append({
                "source": source,
                "multiplier": multiplier,
            })

        # Seasonal presets
        season_modifiers = config.SEASON_ENVIRONMENT_MODIFIERS.get(self.season, {})
        for resource, multiplier in season_modifiers.get("resource_yield", {}).items():
            apply_resource(resource, multiplier, f"{self.season} climate")
        for item, multiplier in season_modifiers.get("market_prices", {}).items():
            apply_market(item, multiplier, f"{self.season} demand")
        apply_travel(season_modifiers.get("travel_speed", 1.0), f"{self.season} roads")

        # Weather overlays
        weather_modifiers = config.WEATHER_ENVIRONMENT_MODIFIERS.get(self.weather, {})
        for resource, multiplier in weather_modifiers.get("resource_yield", {}).items():
            apply_resource(resource, multiplier, f"{self.weather} weather")
        for item, multiplier in weather_modifiers.get("market_prices", {}).items():
            apply_market(item, multiplier, f"{self.weather} conditions")
        apply_travel(weather_modifiers.get("travel_speed", 1.0), f"{self.weather} weather")

        # Active world policies or effects
        for effect_key, effect_data in list(self.active_world_effects.items()):
            resource_bonus = effect_data.get("resource_yield_bonus")
            if resource_bonus:
                res_name = resource_bonus.get("resource")
                multiplier = resource_bonus.get("multiplier", 1.0)
                apply_resource(res_name, multiplier, f"Policy: {effect_key}")
            travel_bonus = effect_data.get("travel_speed_multiplier")
            if travel_bonus:
                apply_travel(travel_bonus, f"Policy: {effect_key}")
            market_bonus = effect_data.get("market_price_adjustment")
            if market_bonus:
                for item_name, multiplier in market_bonus.items():
                    apply_market(item_name, multiplier, f"Policy: {effect_key}")

        # Economic pressures adjust prices slightly
        pressures = self.identify_resource_pressures()
        for pressure in pressures:
            resource = pressure["resource"]
            severity = pressure.get("severity", 0)
            status = pressure.get("status")
            elasticity = 1.0 + config.ENVIRONMENT_PRICE_ELASTICITY * min(4, max(1, severity // 10 or 1))
            if status == "shortage":
                apply_market(resource, elasticity, "Shortage pressure")
            elif status == "surplus":
                apply_market(resource, max(0.5, 1 / elasticity), "Surplus pressure")

        # Persist recalculated values
        self.resource_yield_multipliers.update(resource_modifiers)
        self.travel_speed_modifier = travel_modifier
        self.market_price_multipliers.update(market_modifiers)

        for item_name, base_price in self.base_market_prices.items():
            adjusted_price = int(round(base_price * self.market_price_multipliers.get(item_name, 1.0)))
            self.market_prices[item_name] = max(1, adjusted_price)

        season_day = None
        if self.game_time:
            days_per_season = getattr(config, "DAYS_PER_SEASON", 10)
            season_day = ((self.game_time.current_day - 1) % days_per_season) + 1

        snapshot = {
            "season": self.season,
            "weather": self.weather,
            "season_day": season_day,
            "travel_speed": round(self.travel_speed_modifier, 3),
            "resource_multipliers": contribution_map.get("resource_multipliers", {}),
            "market_multipliers": contribution_map.get("market_multipliers", {}),
            "travel_sources": contribution_map.get("travel_sources", []),
            "active_effects": list(self.active_world_effects.keys()),
        }
        self.environment_effect_snapshot = snapshot

        if previous_snapshot != snapshot:
            self._log_environment_summary()

    def get_environment_snapshot(self) -> Dict[str, Any]:
        return deepcopy(self.environment_effect_snapshot)

    def _log_environment_summary(self):
        if not self.environment_effect_snapshot:
            return

        snapshot = self.environment_effect_snapshot
        digest_components = [
            snapshot.get("season", ""),
            snapshot.get("weather", ""),
            str(snapshot.get("season_day", "")),
            f"{snapshot.get('travel_speed', 1.0):.2f}",
        ]

        resource_bits = []
        for resource, entries in snapshot.get("resource_multipliers", {}).items():
            total = 1.0
            for entry in entries:
                total *= entry.get("multiplier", 1.0)
            if abs(total - 1.0) > 0.01:
                resource_bits.append(f"{resource} x{total:.2f}")

        market_bits = []
        for item, entries in snapshot.get("market_multipliers", {}).items():
            total = 1.0
            for entry in entries:
                total *= entry.get("multiplier", 1.0)
            if abs(total - 1.0) > 0.01:
                market_bits.append(f"{item} x{total:.2f}")

        digest_components.extend(sorted(resource_bits)[:3])
        digest_components.extend(sorted(market_bits)[:3])
        digest_key = "|".join(digest_components)

        current_day = self.game_time.current_day if self.game_time else None
        if (
            current_day is not None
            and self._last_environment_log_day == current_day
            and self._previous_environment_digest == digest_key
        ):
            return

        season_day = snapshot.get("season_day")
        header = f"Environment update — {snapshot.get('season', 'Unknown')}"
        if isinstance(season_day, int):
            header += f" (Day {season_day})"
        header += f", Weather: {snapshot.get('weather', 'Calm')}"

        travel_text = f"Travel modifier {snapshot.get('travel_speed', 1.0):.2f}×"
        resource_text = ", ".join(resource_bits[:3]) if resource_bits else "Stable yields"
        market_text = ", ".join(market_bits[:3]) if market_bits else "Stable prices"

        message = f"{header}. {travel_text}. Yields: {resource_text}. Markets: {market_text}."
        self.add_event_log_message(message)
        self.add_notable_event(
            "EnvironmentShift",
            {
                "summary": message,
                "season": snapshot.get("season"),
                "weather": snapshot.get("weather"),
            },
        )

        self._last_environment_log_day = current_day
        self._previous_environment_digest = digest_key

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

    def withdraw_resource(self, resource_name: str, quantity: int) -> int:
        return self._withdraw_from_stockpiles(resource_name, quantity)

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
        resources_to_check = ["Wood", "Stone", "Herbs", "Food", "Water"]
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

    def _handle_surplus_trade(self, resource_name: str, severity: int) -> Optional[Dict[str, Any]]:
        sale_cap = getattr(config, "MAX_SURPLUS_SALE_PER_DAY", 0)
        if sale_cap <= 0 or severity <= 0:
            return None
        if any(trade.get("resource") == resource_name for trade in self.today_surplus_sales):
            return None

        quantity_to_sell = min(severity, sale_cap)
        withdrawn = self._withdraw_from_stockpiles(resource_name, quantity_to_sell)
        if withdrawn <= 0:
            return None

        unit_price = self.get_market_price(resource_name)
        revenue = unit_price * withdrawn
        self.treasury_coins += revenue
        trade_details = {
            "resource": resource_name,
            "quantity": withdrawn,
            "unit_price": unit_price,
            "revenue": revenue,
            "day": self.game_time.current_day if self.game_time else -1,
        }
        self.today_surplus_sales.append(trade_details)
        self.add_event_log_message(
            f"Converted surplus {withdrawn} {resource_name} into {revenue} coins at the market."
        )
        self.add_notable_event(
            "SurplusTrade",
            {
                "summary": f"Sold {withdrawn} {resource_name} for {revenue} coins.",
                "resource": resource_name,
                "revenue": revenue,
            },
        )
        return trade_details

    def _spawn_conversion_work_order(self, resource_name: str, severity: int) -> Optional[WorkOrder]:
        if not self.game_time or severity <= 0:
            return None

        conversion_map = {
            "Wood": {"item_name": "Arrow Bundle", "quantity_factor": 1},
            "Herbs": {"item_name": "Bandages", "quantity_factor": 1},
        }
        recipe = conversion_map.get(resource_name)
        if not recipe:
            return None

        target_item = recipe["item_name"]
        existing = [
            wo for wo in self.work_orders
            if wo.details.get("item_name") == target_item and wo.status in {"Pending", "Approved", "InProgress"}
        ]
        if existing:
            return None

        blueprint = BLUEPRINTS.get(target_item)
        if not blueprint or "required_resources" not in blueprint:
            return None

        quantity = max(1, severity // 5 * recipe.get("quantity_factor", 1))
        required_resources = {
            res: qty * quantity for res, qty in blueprint["required_resources"].items()
        }
        details = {
            "item_name": target_item,
            "quantity": quantity,
            "required_resources": required_resources,
        }
        work_order = WorkOrder(
            order_type="CraftItem",
            details=details,
            priority=3,
            creation_day=self.game_time.current_day,
        )
        self.add_work_order(work_order)
        self.add_event_log_message(
            f"Economic council schedules crafting of {quantity} {target_item} to soak {resource_name} surplus."
        )
        return work_order

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

    def _apply_daily_water_consumption(self, report: Dict[str, Any]):
        per_capita = getattr(config, "DAILY_WATER_CONSUMPTION_PER_CITIZEN", 0)
        thirst_recovery = BLUEPRINTS.get("Water", {}).get("thirst_satisfaction", 40)
        total_consumed = 0
        total_deficit = 0
        if per_capita <= 0:
            report["water_consumed"] = total_consumed
            report["water_deficit"] = total_deficit
            return

        for character in self.characters:
            required = per_capita
            consumed = self._consume_resource_for_character(character, "Water", required)
            if consumed > 0:
                total_consumed += consumed
                thirst = character.needs.get("Thirst", 80)
                thirst_gain = thirst_recovery * consumed
                character.needs["Thirst"] = min(config.NEED_SCORE_MAX, thirst + thirst_gain)
                ration_text = "drink" if consumed == 1 else "drinks"
                character.add_memory(f"Drank {consumed} water {ration_text} with the community.")
                character.update_mood_score(getattr(config, "MOOD_CHANGE_REPLENISHED_WATER", 3), "Enjoyed fresh water")
            if consumed < required:
                shortage = required - consumed
                if shortage <= 0:
                    continue
                total_deficit += shortage
                thirst = character.needs.get("Thirst", 60)
                character.needs["Thirst"] = max(
                    config.NEED_SCORE_MIN,
                    thirst - getattr(config, "DEHYDRATION_THIRST_PENALTY", 15),
                )
                character.update_mood_score(getattr(config, "MOOD_CHANGE_DEHYDRATED", -12), "Went without water")
                character.add_memory("Felt parched—stores couldn't provide water today.")

        report["water_consumed"] = total_consumed
        report["water_deficit"] = total_deficit

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

            day_value = self.game_time.current_day if self.game_time else -1
            character.inventory[resource_name] = character.inventory.get(resource_name, 0) + removed
            location_coords = (stockpile.rect[0], stockpile.rect[1])
            location_label = f"{stockpile.name} ({location_coords[0]}, {location_coords[1]})"
            summary = f"{removed} {resource_name} missing from {stockpile.name}"
            description = f"{character.name} stole {removed} {resource_name} from {stockpile.name}"

            detection_chance = detection_base / max(0.25, security_modifier)
            caught = random.random() < detection_chance
            recovered_amount = 0
            if caught:
                description += " but was caught"
                recovered_amount = min(removed, character.inventory.get(resource_name, 0))
                if recovered_amount > 0:
                    success_add, returned = stockpile.add_item(resource_name, recovered_amount)
                    if success_add:
                        recovered_amount = returned
                        character.inventory[resource_name] = character.inventory.get(resource_name, 0) - returned
                        if character.inventory.get(resource_name, 0) <= 0:
                            character.inventory.pop(resource_name, None)
                        summary = f"Recovered {returned} {resource_name} from {character.name}"
                        if self.game_time:
                            self.ledger.update_stockpile_record(
                                stockpile.name, stockpile.inventory, self.game_time.current_day
                            )
                character.add_memory("Was caught stealing from the stockpile.")
                character.update_reputation(-3, "Caught stealing supplies", self)
                character.update_mood_score(
                    getattr(config, "MOOD_CHANGE_CAUGHT_STEALING", -15), "Caught stealing supplies"
                )
            else:
                character.add_memory(
                    f"Stole {removed} {resource_name} from {stockpile.name} under cover of night."
                )
                character.update_mood_score(
                    getattr(config, "MOOD_CHANGE_STOLE_SUCCESS", 2), "Stole supplies without notice"
                )

            incident_id = self._next_crime_id()
            incident = {
                "id": incident_id,
                "type": "theft",
                "reported_day": day_value,
                "suspect": character.name,
                "resource": resource_name,
                "amount": removed,
                "recovered": recovered_amount,
                "location": {"stockpile": stockpile.name, "coords": location_coords},
                "location_label": location_label,
                "description": description,
                "summary": summary,
                "status": "resolved" if caught else "pending",
                "caught": caught,
            }

            self.add_event_log_message(f"Security incident: {description}.")
            if not caught:
                self.pending_crimes.append(incident)
                self.active_crimes[incident_id] = incident
                self.add_event_log_message(
                    f"Case opened: {incident['summary']} (suspect {character.name})."
                )
            else:
                incident["result"] = "apprehended_on_scene"

            self._record_crime_history(incident)
            theft_events.append({
                "id": incident_id,
                "character": character.name,
                "resource": resource_name,
                "amount": removed,
                "status": incident["status"],
                "description": description,
                "caught": caught,
            })
            if self.game_time:
                self.ledger.update_stockpile_record(stockpile.name, stockpile.inventory, self.game_time.current_day)

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
            "water_consumed": 0,
            "water_deficit": 0,
            "wages_paid": previous_wages_paid,
            "wages_owed": previous_wages_owed,
            "arrears": sum(debt.get("amount_due", 0) for debt in self.pending_wages),
            "arrears_paid": 0,
            "crime_events": [],
            "treasury": self.treasury_coins,
            "surplus_trades": list(self.today_surplus_sales),
            "pending_crimes": len(self.pending_crimes),
            "environment": self.environment_effect_snapshot,
        }

        tax_income = getattr(config, "DAILY_BASE_TAX_INCOME", 0)
        if tax_income:
            self.treasury_coins += tax_income
            report["tax_collected"] = tax_income

        report["arrears_paid"] = self._settle_wage_backlog()
        report["treasury"] = self.treasury_coins
        report["arrears"] = sum(debt.get("amount_due", 0) for debt in self.pending_wages)

        self._apply_daily_food_consumption(report)
        self._apply_daily_water_consumption(report)
        self._resolve_theft_attempts(report)
        report["pending_crimes"] = len(self.pending_crimes)
        report["surplus_trades"] = list(self.today_surplus_sales)

        summary = (
            f"Economic summary — Treasury {self.treasury_coins}c "
            f"(tax +{report['tax_collected']}c, wages paid {report['wages_paid']}c, arrears settled {report['arrears_paid']}c)."
            f" Outstanding arrears {report['arrears']}c, food deficit {report['food_deficit']} rations,"
            f" water deficit {report['water_deficit']} casks."
        )
        self.add_event_log_message(summary)
        for crime_event in report.get("crime_events", []):
            self.add_event_log_message(f"Security report: {crime_event['description']}.")

        if report["surplus_trades"]:
            trade_summaries = ", ".join(
                f"{trade['quantity']} {trade['resource']} (+{trade['revenue']}c)"
                for trade in report["surplus_trades"]
            )
            self.add_event_log_message(f"Trade ledger: {trade_summaries} exported to market.")

        self.last_daily_economic_report = report
        self.today_surplus_sales = []

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
                "deadline_day": self.game_time.current_day
                + max(
                    1,
                    getattr(config, "CAMPAIGN_PROMISE_DEADLINES", {}).get(
                        promise_type, getattr(config, "CAMPAIGN_PROMISE_DEFAULT_WINDOW", 4)
                    ),
                ),
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

            if self.game_time:
                cooldown = getattr(config, "CAMPAIGN_SPEECH_COOLDOWN_DAYS", 2)
                last_speech_day = getattr(candidate, "last_campaign_speech_day", None)
                can_schedule = (
                    last_speech_day is None
                    or self.game_time.current_day - last_speech_day >= cooldown
                )
                current_goal = getattr(candidate, "current_goal", None)
                is_available = False
                if current_goal is None:
                    is_available = True
                else:
                    is_available = (
                        current_goal.type in [GoalType.IDLE, GoalType.WANDER]
                        or getattr(current_goal, "priority", 10) >= 6
                    )
                focus = summary
                pledged = [
                    p.get("summary")
                    for p in self.campaign_promises.get(candidate.name, [])
                    if p.get("status") == "pledged"
                ]
                if pledged:
                    focus = pledged[0]
                if can_schedule and is_available:
                    candidate.current_goal = Goal(
                        GoalType.CAMPAIGN_SPEECH,
                        assignee_id=candidate.name,
                        originator_id="Campaign",
                        parameters={"focus_summary": focus},
                        priority=4,
                    )
                    candidate.add_memory(f"Scheduled to deliver a campaign speech about {focus}.")

    def fulfill_campaign_promises(self, mayor: 'Character'):
        if not self.game_time:
            return
        promises = self.campaign_promises.get(mayor.name, [])
        if not promises:
            return

        today = self.game_time.current_day
        failure_rep_delta = getattr(config, "CAMPAIGN_PROMISE_FAILURE_REPUTATION", -5)
        failure_mood_delta = getattr(config, "MOOD_CHANGE_CAMPAIGN_PROMISE_FAILED", -10)
        for promise in promises:
            if promise.get("status") != "pledged":
                continue
            deadline_day = promise.get("deadline_day")
            if deadline_day is not None and today > deadline_day:
                promise["status"] = "failed"
                promise["failed_day"] = today
                summary = promise.get("summary", "campaign promise")
                mayor.add_memory(f"Failed to deliver on promise: {summary}.")
                mayor.update_reputation(failure_rep_delta, f"Failed promise: {summary}", self)
                mayor.update_mood_score(failure_mood_delta, "Failed to deliver campaign promise")
                self.add_event_log_message(
                    f"Promise broken — Mayor {mayor.name} did not fulfill '{summary}' before Day {deadline_day}."
                )
                self.add_notable_event(
                    "CampaignPromiseFailed",
                    {
                        "candidate": mayor.name,
                        "summary": summary,
                        "deadline_day": deadline_day,
                    },
                )

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
            resource = pressure["resource"]
            if pressure["status"] == "shortage":
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
            elif pressure["status"] == "surplus":
                severity = pressure.get("severity", 0)
                self._handle_surplus_trade(resource, severity)
                self._spawn_conversion_work_order(resource, severity)

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
