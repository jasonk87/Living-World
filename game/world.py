# game/world.py
from __future__ import annotations

import random
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple

from .stockpile import Stockpile
from .ledger import Ledger
from .time import Time
from .work_order import WorkOrder
from .building import Building
from .data import (
    STRUCTURE_BLUEPRINTS,
    MARKET_PRICES,
    BLUEPRINTS,
    JOB_TASK_DEFINITIONS,
    CITIZEN_NAME_POOL,
    CITIZEN_PERSONALITY_POOL,
    CITIZEN_TRAIT_POOL,
    MIGRANT_ARCHETYPES,
)
from .rumor import Rumor
from . import config
from .goal import Goal, GoalType
from .pathfinding import Pathfinder

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
        self.resources: Dict[str, List[Dict[str, Any]]] = {}
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
        self.legal_cases: Dict[str, Dict[str, Any]] = {}
        self.trial_queue: List[str] = []
        self.trial_history: List[Dict[str, Any]] = []
        self.medical_cases: Dict[str, Dict[str, Any]] = {}
        self.medical_triage_queue: List[str] = []
        self.medical_history: List[Dict[str, Any]] = []
        self.clinic_supply_requests: List[Dict[str, Any]] = []
        self.latest_healthcare_report: Dict[str, Any] = {}
        self._medical_case_counter: int = 0
        courthouse_y = max(0, self.market_location[1] - 1)
        self.courthouse_location: Tuple[int, int] = (self.market_location[0], courthouse_y)
        self.today_surplus_sales: List[Dict[str, Any]] = []
        self._residential_assignments: Dict[str, Tuple[int, int]] = {}
        self.last_housing_evaluation_day: Optional[int] = None
        self.latest_housing_snapshot: Dict[str, Any] = self.get_housing_snapshot()
        self.current_phase: Dict[str, Any] = {}
        self.phase_history: List[Dict[str, Any]] = []
        self._last_phase_day: Optional[int] = None
        self.active_weather_event: Optional[Dict[str, Any]] = None
        self.weather_event_history: List[Dict[str, Any]] = []
        self.population_stats: Dict[str, Any] = {
            "population": 0,
            "births_today": 0,
            "migrants_today": 0,
            "departures_today": 0,
            "last_updated_day": 0,
        }
        self.demographic_history: List[Dict[str, Any]] = []
        self._last_population_event_day: Optional[int] = None
        self._resident_registry: Dict[str, Dict[str, Any]] = {}
        self.map_revision: int = 0
        self._tile_reservations: Dict[Tuple[int, int], str] = {}
        self._reservation_by_character: Dict[str, Tuple[int, int]] = {}
        self._pathfinder = Pathfinder()
        self.cultural_calendar: List[Dict[str, Any]] = []
        self._generated_cultural_years: Set[int] = set()
        self._active_cultural_event_data: Optional[Dict[str, Any]] = None
        self.active_cultural_event: Optional[Dict[str, Any]] = None
        self._active_cultural_event_end_day: Optional[int] = None
        self.community_spirit: float = getattr(config, "CULTURAL_SPIRIT_BASELINE", 0.4)
        self.cultural_history: List[Dict[str, Any]] = []
        self._last_cultural_update_day: Optional[int] = None
        self.training_program_definitions: Dict[str, Dict[str, Any]] = deepcopy(
            getattr(config, "TRAINING_PROGRAM_DEFINITIONS", {})
        )
        self.training_waitlists: Dict[str, List[str]] = {
            key: [] for key in self.training_program_definitions
        }
        self.active_training_sessions: List[Dict[str, Any]] = []
        self.training_history: List[Dict[str, Any]] = []
        self.latest_training_report: Dict[str, Any] = {}
        self._last_training_update_day: Optional[int] = None
        self.work_shift_definitions: Dict[str, Dict[str, Any]] = deepcopy(
            getattr(config, "WORK_SHIFT_DEFINITIONS", {})
        )
        self.work_shift_backlog: Dict[str, float] = {
            key: 0.0 for key in self.work_shift_definitions
        }
        self.latest_workforce_report: Dict[str, Any] = {}
        self._last_workforce_update_day: Optional[int] = None
        self.work_logistics_history: List[Dict[str, Any]] = []

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

        if self.rumors:
            self._propagate_rumors_daily()
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

    def is_walkable(
        self,
        x: int,
        y: int,
        *,
        ignore_characters: Optional[Iterable[str]] = None,
        goal: Optional[Tuple[int, int]] = None,
    ) -> bool:
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            return False

        ignore_set: Set[str] = set(ignore_characters or [])
        goal_override = goal == (x, y)

        tile_type = self.grid[x][y]
        if tile_type in config.IMPASSABLE_TERRAINS and not goal_override:
            return False

        reservation_holder = self._tile_reservations.get((x, y))
        if reservation_holder and reservation_holder not in ignore_set and not goal_override:
            return False

        for char in self.characters:
            if char.name in ignore_set:
                continue
            if (char.x, char.y) == (x, y):
                if goal_override:
                    continue
                return False

        return True

    def reserve_tile(self, character_name: str, coords: Tuple[int, int]) -> bool:
        current_holder = self._tile_reservations.get(coords)
        if current_holder and current_holder != character_name:
            return False

        previous = self._reservation_by_character.get(character_name)
        if previous == coords:
            return True

        if previous is not None and self._tile_reservations.get(previous) == character_name:
            del self._tile_reservations[previous]

        self._tile_reservations[coords] = character_name
        self._reservation_by_character[character_name] = coords
        return True

    def release_tile(self, character_name: str, coords: Optional[Tuple[int, int]] = None) -> None:
        if coords is None:
            coords = self._reservation_by_character.pop(character_name, None)
        else:
            stored = self._reservation_by_character.get(character_name)
            if stored == coords:
                self._reservation_by_character.pop(character_name, None)

        if coords and self._tile_reservations.get(coords) == character_name:
            del self._tile_reservations[coords]

    def clear_reservations_for_character(self, character_name: str) -> None:
        self.release_tile(character_name)

    def find_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        *,
        ignore_characters: Optional[Iterable[str]] = None,
    ) -> List[Tuple[int, int]]:
        return self._pathfinder.find_path(self, start, goal, ignore_characters=ignore_characters)

    def set_tile(self, x: int, y: int, tile_type: str):
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            is_building_tile = any((x,y) in b.get_tiles_occupied() for b in self.buildings)
            if not is_building_tile: # Only change base grid if no building is there
                if self.grid[x][y] != tile_type:
                    self.grid[x][y] = tile_type
                    self.map_revision += 1

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
            self.map_revision += 1


    def remove_building(self, building: Building):
        if building in self.buildings:
            self.buildings.remove(building)
            print(f"Removed building: {building.display_name} from {building.location}.")
            self.map_revision += 1

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
        assigned_building: Optional[Building] = None
        if existing_location:
            existing = self.get_building_by_location(existing_location)
            if existing and self._is_residential(existing):
                if character.name not in existing.occupants:
                    existing.add_occupant(character.name)
                assigned_building = existing
        if assigned_building:
            self.latest_housing_snapshot = self.get_housing_snapshot()
            return assigned_building

        for building in self.buildings:
            if not self._is_residential(building):
                continue
            capacity = int(building.functionality.get("provides_shelter", 0))
            if character.name in building.occupants:
                self._residential_assignments[character.name] = building.location
                assigned_building = building
                break
            if len(building.occupants) < capacity:
                building.add_occupant(character.name)
                self._residential_assignments[character.name] = building.location
                assigned_building = building
                break

        if assigned_building:
            self.latest_housing_snapshot = self.get_housing_snapshot()
        return assigned_building

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
        self.latest_housing_snapshot = self.get_housing_snapshot()

    def get_housing_snapshot(self) -> Dict[str, Any]:
        total_beds = 0
        claimed_beds = 0
        structures: List[Dict[str, Any]] = []
        occupant_lookup: Dict[str, str] = {}

        for building in self.buildings:
            if not self._is_residential(building):
                continue

            capacity = max(0, int(building.functionality.get("provides_shelter", 0)))
            total_beds += capacity
            occupants = list(building.occupants)
            claimed_beds += min(len(occupants), capacity)
            available = max(0, capacity - min(len(occupants), capacity))

            structures.append(
                {
                    "name": building.display_name,
                    "location": building.location,
                    "capacity": capacity,
                    "occupants": occupants,
                    "available": available,
                }
            )

            for occupant_name in occupants:
                occupant_lookup[occupant_name] = building.display_name

        assignments: Dict[str, str] = {}
        for char_name, location in self._residential_assignments.items():
            building = self.get_building_by_location(location)
            if building and self._is_residential(building):
                assignments[char_name] = building.display_name

        homeless: List[str] = []
        for character in self.characters:
            home_name = assignments.get(character.name) or occupant_lookup.get(character.name)
            if home_name:
                assignments[character.name] = home_name
            else:
                homeless.append(character.name)

        resting_characters = [
            character.name
            for character in self.characters
            if getattr(character, "resting_at_home", False)
        ]

        snapshot = {
            "total_beds": total_beds,
            "claimed_beds": claimed_beds,
            "available_beds": max(0, total_beds - claimed_beds),
            "structures": structures,
            "assignments": assignments,
            "homeless_characters": homeless,
            "resting_characters": resting_characters,
        }
        return snapshot

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


    def add_resource(
        self,
        resource_name: str,
        location: tuple[int, int],
        tile_becomes: Optional[str] = None,
        durability: Optional[int] = None,
    ):
        x, y = location
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            return
        if self.get_building_at(x, y):
            return

        node_list = self.resources.setdefault(resource_name, [])
        current_tile = self.grid[x][y]
        max_durability = durability if durability is not None else config.RESOURCE_NODE_DURABILITY.get(resource_name, 5)
        node = {
            "resource": resource_name,
            "location": (x, y),
            "durability": max_durability,
            "max_durability": max_durability,
            "regrowth_progress": 0.0,
            "depleted": False,
            "active_tile": tile_becomes or current_tile,
            "original_tile": current_tile,
            "depleted_tile": config.RESOURCE_NODE_DEPLETED_TILES.get(resource_name, current_tile),
        }
        node_list.append(node)

        if tile_becomes and current_tile != tile_becomes:
            self.set_tile(x, y, tile_becomes)
        elif not tile_becomes and current_tile == "Grass":
            self.set_tile(x, y, resource_name)


    def get_resources(self, resource_name: str) -> List[Any]:
        nodes = self.resources.get(resource_name, [])
        return [node for node in nodes if not node.get("depleted", False)]

    def is_resource_node(self, resource_name: str, location: Tuple[int, int]) -> bool:
        for node in self.resources.get(resource_name, []):
            if tuple(node.get("location", ())) == tuple(location):
                return not node.get("depleted", False)
        return False

    def record_resource_harvest(self, resource_name: str, location: Tuple[int, int], amount: int = 1) -> None:
        nodes = self.resources.get(resource_name, [])
        for node in nodes:
            if tuple(node.get("location", ())) != tuple(location):
                continue
            if node.get("depleted") or node.get("max_durability", 0) >= 999:
                return
            node["durability"] = max(0, node.get("durability", 0) - amount)
            node.setdefault("harvested_today", 0)
            node["harvested_today"] += amount
            if node["durability"] <= 0:
                node["depleted"] = True
                node["regrowth_progress"] = 0.0
                depleted_tile = node.get("depleted_tile")
                if depleted_tile:
                    self.set_tile(location[0], location[1], depleted_tile)
                self.add_event_log_message(
                    f"{resource_name} exhausted at {location}. The area now shows {depleted_tile or 'scars of overuse'}."
                )
                self.add_notable_event(
                    "ResourceDepleted",
                    {
                        "summary": f"{resource_name} depleted at {location}",
                        "resource": resource_name,
                        "location": location,
                    },
                )
            return

    def _advance_resource_regrowth(self) -> None:
        for resource_name, nodes in self.resources.items():
            regrowth_days = config.RESOURCE_NODE_REGROWTH_DAYS.get(resource_name)
            if not regrowth_days:
                for node in nodes:
                    node.pop("harvested_today", None)
                continue
            regrowth_increment = 1.0 / max(1, regrowth_days)
            env_modifier = self.resource_yield_multipliers.get(resource_name, 1.0)
            env_modifier = max(0.25, env_modifier)
            for node in nodes:
                node.pop("harvested_today", None)
                if not node.get("depleted"):
                    continue
                node["regrowth_progress"] += regrowth_increment * env_modifier
                if node["regrowth_progress"] >= 1.0:
                    node["regrowth_progress"] = 0.0
                    node["depleted"] = False
                    node["durability"] = node.get("max_durability", 1)
                    active_tile = node.get("active_tile") or node.get("original_tile")
                    if active_tile:
                        self.set_tile(node["location"][0], node["location"][1], active_tile)
                    self.add_event_log_message(
                        f"{resource_name} has regrown at {node['location']} after a period of rest."
                    )
                    self.add_notable_event(
                        "ResourceRegrowth",
                        {
                            "summary": f"{resource_name} regrew at {node['location']}",
                            "resource": resource_name,
                            "location": tuple(node["location"]),
                        },
                    )

    def get_resource_nodes_snapshot(self) -> List[Dict[str, Any]]:
        snapshot: List[Dict[str, Any]] = []
        for resource_name, nodes in self.resources.items():
            for node in nodes:
                snapshot.append(
                    {
                        "resource": resource_name,
                        "location": tuple(node.get("location", (0, 0))),
                        "durability": node.get("durability"),
                        "max_durability": node.get("max_durability"),
                        "depleted": node.get("depleted", False),
                        "regrowth_progress": round(node.get("regrowth_progress", 0.0), 3),
                    }
                )
        return snapshot

    def update_weather(self, new_weather: str):
        if self.weather != new_weather:
            self.weather = new_weather
            self.add_event_log_message(f"Weather shifts to {new_weather}.")
            self._recalculate_environment_effects()

    def update_day_phase(self) -> None:
        if not self.game_time:
            return
        phase_info = self.game_time.get_phase()
        if not isinstance(phase_info, dict):
            phase_info = {"name": str(phase_info), "key": str(phase_info).lower()}
        previous_key = self.current_phase.get("key") if self.current_phase else None
        new_key = phase_info.get("key")
        if previous_key == new_key and self.current_phase.get("day") == self.game_time.current_day:
            return

        phase_record = {
            "name": phase_info.get("name", new_key or "Phase"),
            "key": new_key,
            "description": phase_info.get("description"),
            "day": self.game_time.current_day,
            "tick": self.game_time.current_tick,
        }
        self.current_phase = phase_record
        self.phase_history.append(phase_record)
        if len(self.phase_history) > 24:
            self.phase_history.pop(0)

        description_suffix = f" — {phase_info.get('description')}" if phase_info.get("description") else ""
        self.add_event_log_message(
            f"Day phase shifts to {phase_record['name']}{description_suffix}."
        )
        self.add_notable_event(
            "PhaseShift",
            {
                "summary": f"Phase changed to {phase_record['name']}",
                "phase": phase_record,
            },
        )

    def get_current_phase(self) -> Dict[str, Any]:
        return dict(self.current_phase) if self.current_phase else {}

    def _update_weather_event_state(self) -> None:
        if not self.active_weather_event or not self.game_time:
            return
        if self.game_time.current_day <= self.active_weather_event.get("end_day", -1):
            return

        event = self.active_weather_event
        effect_key = event.get("effect_key")
        if effect_key and effect_key in self.active_world_effects:
            del self.active_world_effects[effect_key]
            self._recalculate_environment_effects()
        self.add_event_log_message(f"{event.get('name', 'Severe weather')} has passed.")
        self.add_notable_event(
            "WeatherEventEnd",
            {
                "summary": f"{event.get('name', 'Weather event')} concluded",
                "event": event,
            },
        )
        self.weather_event_history.append(event)
        self.active_weather_event = None

    def _start_weather_event(self, name: str, definition: Dict[str, Any]) -> None:
        if not self.game_time:
            return
        severity_range = definition.get("severity_range", (1, 1))
        duration_range = definition.get("duration_days", (1, 1))
        severity = random.randint(severity_range[0], severity_range[1])
        duration = random.randint(duration_range[0], duration_range[1])
        end_day = self.game_time.current_day + max(0, duration - 1)
        effect_key = f"WeatherEvent:{name}"

        resource_bonuses = []
        for resource, multiplier in definition.get("resource_yield", {}).items():
            resource_bonuses.append({"resource": resource, "multiplier": multiplier})

        effect_data = {
            "resource_yield_bonus": resource_bonuses or None,
            "travel_speed_multiplier": definition.get("travel_speed_multiplier"),
            "market_price_adjustment": definition.get("market_multipliers", {}),
            "expires_day": end_day,
        }
        # Clean None entries for consistent processing
        effect_data = {k: v for k, v in effect_data.items() if v}

        if effect_data:
            self.add_temporary_world_effect(effect_key, effect_data)

        event_instance = {
            "name": name,
            "severity": severity,
            "start_day": self.game_time.current_day,
            "end_day": end_day,
            "effect_key": effect_key if effect_data else None,
            "requires_shelter": definition.get("requires_shelter", False),
            "hazards": definition.get("hazards", {}),
        }
        self.active_weather_event = event_instance
        self.add_event_log_message(
            f"{name} sweeps the settlement (severity {severity}) and is expected to last {duration} day{'s' if duration != 1 else ''}."
        )
        self.add_notable_event(
            "WeatherEvent",
            {
                "summary": f"{name} in effect (severity {severity})",
                "event": event_instance,
            },
        )

    def _maybe_trigger_weather_event(self) -> None:
        if self.active_weather_event or not self.game_time:
            return
        definitions = getattr(config, "WEATHER_EVENT_DEFINITIONS", {})
        if not definitions:
            return
        candidates = []
        for name, definition in definitions.items():
            seasons = definition.get("seasons")
            if seasons and self.season not in seasons:
                continue
            weather_states = definition.get("weather")
            if weather_states and self.weather not in weather_states:
                continue
            chance = definition.get("base_chance", 0.0)
            if chance <= 0:
                continue
            candidates.append((name, definition, chance))
        random.shuffle(candidates)
        for name, definition, chance in candidates:
            if random.random() < chance:
                self._start_weather_event(name, definition)
                break

    def get_active_weather_event(self) -> Optional[Dict[str, Any]]:
        if not self.active_weather_event:
            return None
        return deepcopy(self.active_weather_event)

    def _generate_citizen_profile(
        self,
        *,
        job: str = "Unemployed",
        age: Optional[int] = None,
        needs: Optional[Dict[str, int]] = None,
        traits: Optional[List[str]] = None,
        personality: Optional[str] = None,
        origin: Optional[str] = None,
        citizenship: str = "Resident",
        skills: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        given = random.choice(CITIZEN_NAME_POOL.get("given", ["Citizen"]))
        surname = random.choice(CITIZEN_NAME_POOL.get("surnames", ["of Nowhere"]))
        base_name = f"{given} {surname}"
        existing_names = {char.name for char in self.characters}
        name = base_name
        suffix = 2
        while name in existing_names:
            name = f"{base_name} {suffix}"
            suffix += 1

        if traits is None:
            traits = random.sample(CITIZEN_TRAIT_POOL, k=min(2, len(CITIZEN_TRAIT_POOL)))
        if personality is None:
            personality = random.choice(CITIZEN_PERSONALITY_POOL)

        profile = {
            "name": name,
            "job": job,
            "age": age if age is not None else random.randint(18, 45),
            "needs": needs,
            "traits": traits,
            "personality": personality,
            "origin": origin or "Local",
            "citizenship": citizenship,
            "skills": skills or {},
        }
        return profile

    def _spawn_new_citizen(self, profile: Dict[str, Any], *, arrival_reason: str) -> Optional['Character']:
        from .character import Character

        needs = profile.get("needs")
        if needs is None:
            needs = {
                "Hunger": 85,
                "Thirst": 85,
                "Energy": 100,
                "Social": 75,
                "Safety": config.NEED_SAFETY_DEFAULT,
                "Belonging": config.NEED_BELONGING_DEFAULT,
                "Esteem": config.NEED_ESTEEM_DEFAULT,
            }
        character = Character(
            name=profile["name"],
            personality=profile.get("personality", "Even-tempered"),
            traits=list(profile.get("traits", [])),
            skills=profile.get("skills", {}),
            x=profile.get("x", self.market_location[0]),
            y=profile.get("y", self.market_location[1]),
            needs=needs,
            job=profile.get("job", "Unemployed"),
            rank=profile.get("rank", "Worker"),
            age=profile.get("age"),
            origin=profile.get("origin"),
            citizenship=profile.get("citizenship", "Resident"),
            arrival_day=self.game_time.current_day if self.game_time else None,
        )
        self.add_character(character)
        self.add_event_log_message(arrival_reason)
        return character

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
        if character in self.characters:
            return
        self.characters.append(character)
        self.clear_reservations_for_character(character.name)
        if hasattr(character, "arrival_day") and character.arrival_day is None and self.game_time:
            character.arrival_day = self.game_time.current_day
        self._register_character_demographics(character)
        self._update_population_stats(delta=1)

    def remove_character(self, character: 'Character'):
        if character not in self.characters:
            return
        self.characters.remove(character)
        self.clear_reservations_for_character(character.name)
        if character.name in self._resident_registry:
            del self._resident_registry[character.name]
        self._update_population_stats(delta=-1)

    def _register_character_demographics(self, character: 'Character') -> None:
        record = {
            "age": getattr(character, "age_years", None),
            "origin": getattr(character, "origin", "Unknown"),
            "citizenship": getattr(character, "citizenship_status", "Resident"),
            "arrival_day": getattr(character, "arrival_day", self.game_time.current_day if self.game_time else None),
        }
        self._resident_registry[character.name] = record

    def _update_population_stats(self, delta: int = 0) -> None:
        self.population_stats["population"] = max(0, len(self.characters))
        if self.game_time:
            self.population_stats["last_updated_day"] = self.game_time.current_day

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
            self.map_revision += 1


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
        evidence_strength: Optional[float] = None,
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
            if evidence_strength is not None:
                crime["evidence_strength"] = evidence_strength
            self._record_crime_history(crime)
            return crime

        crime["status"] = "resolved"
        crime["resolved_day"] = self.game_time.current_day if self.game_time else -1
        crime["resolved_by"] = responder_name
        crime["result"] = result
        crime["caught"] = caught
        if evidence_strength is not None:
            crime["evidence_strength"] = evidence_strength
        if notes:
            crime["resolution_notes"] = notes
            crime["description"] = f"{crime.get('description', 'Disturbance resolved')} ({notes})"
        resolution_blurb = crime.get("description") or result
        self.add_event_log_message(f"{responder_name} resolved {crime.get('type', 'incident')} — {resolution_blurb}.")

        self.pending_crimes = [c for c in self.pending_crimes if c.get("id") != crime_id]
        if crime_id in self.active_crimes:
            del self.active_crimes[crime_id]
        self._record_crime_history(crime)

        if caught and crime.get("suspect"):
            baseline_strength = evidence_strength if evidence_strength is not None else 0.5
            self.schedule_trial_for_crime(crime, responder_name, baseline_strength)
        return crime

    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.legal_cases.get(case_id)

    def schedule_trial_for_crime(
        self,
        crime: Dict[str, Any],
        prosecutor_name: str,
        evidence_strength: float,
    ) -> Optional[Dict[str, Any]]:
        suspect = crime.get("suspect")
        if not suspect:
            return None

        case_id = crime.get("trial_case_id")
        if case_id:
            existing_case = self.legal_cases.get(case_id)
            if existing_case and existing_case.get("status") not in {"concluded", "cancelled"}:
                existing_case["evidence_strength"] = max(
                    existing_case.get("evidence_strength", 0.0), evidence_strength
                )
                crime["evidence_strength"] = existing_case["evidence_strength"]
                return existing_case

        case_id = f"{crime.get('id', self._next_crime_id())}_trial"
        if case_id in self.legal_cases and self.legal_cases[case_id].get("status") not in {"concluded", "cancelled"}:
            return self.legal_cases[case_id]

        current_day = self.game_time.current_day if self.game_time else 0
        base_delay = getattr(config, "TRIAL_SCHEDULING_DELAY", 2)
        variance = getattr(config, "TRIAL_SCHEDULING_VARIANCE", 1)
        scheduled_day = current_day + base_delay + random.randint(0, max(0, variance))
        if scheduled_day <= current_day:
            scheduled_day = current_day + 1

        presiding = self._select_presiding_officer()
        severity = crime.get("amount") or 1
        try:
            severity_value = int(severity)
        except (TypeError, ValueError):
            severity_value = 1
        severity_value = max(1, min(5, severity_value))

        case = {
            "case_id": case_id,
            "crime_id": crime.get("id"),
            "defendant": suspect,
            "charge": crime.get("type", "crime"),
            "prosecutor": prosecutor_name,
            "presiding_officer": presiding,
            "status": "scheduled",
            "scheduled_day": scheduled_day,
            "evidence_strength": max(0.0, min(1.0, evidence_strength)),
            "preparedness": 0.0,
            "crime_summary": crime.get("description") or crime.get("summary"),
            "severity": severity_value,
            "preparation_notes": [],
        }

        self.legal_cases[case_id] = case
        crime["trial_case_id"] = case_id
        self.trial_queue.append(case_id)
        self.trial_queue = sorted(
            {cid for cid in self.trial_queue if cid in self.legal_cases},
            key=lambda cid: self.legal_cases[cid].get("scheduled_day", float("inf")),
        )
        self.add_event_log_message(
            f"Trial scheduled: {suspect} will face charges of {case['charge']} on Day {scheduled_day}."
        )

        prosecutor = self.get_character_by_name(prosecutor_name)
        if prosecutor:
            prosecutor.add_memory(
                f"Scheduled trial {case_id} for {suspect} on Day {scheduled_day}."
            )
        defendant = self.get_character_by_name(suspect)
        if defendant:
            defendant.add_memory(
                f"Summoned to stand trial ({case['charge']}) on Day {scheduled_day}."
            )
            defendant.update_mood_score(-6, "Awaiting trial")
        if presiding:
            presiding_char = self.get_character_by_name(presiding)
            if presiding_char:
                presiding_char.add_memory(
                    f"Assigned to preside over trial {case_id} on Day {scheduled_day}."
                )
        return case

    def progress_case_preparation(
        self,
        case_id: str,
        effort: float,
        *,
        contributor: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        case = self.legal_cases.get(case_id)
        if not case:
            return None
        if case.get("status") in {"concluded", "cancelled"}:
            return case

        case.setdefault("preparedness", 0.0)
        case["preparedness"] = min(1.0, case.get("preparedness", 0.0) + max(0.0, effort))
        case.setdefault("evidence_strength", 0.5)
        case["evidence_strength"] = min(1.0, case["evidence_strength"] + max(0.0, effort) * 0.1)

        if contributor:
            day = self.game_time.current_day if self.game_time else None
            last_day = case.get("last_prepared_day")
            if day is None or day != last_day:
                note = f"{contributor} reviewed evidence on Day {day if day is not None else '?'}"
                case["preparation_notes"].append(note)
                case["preparation_notes"] = case["preparation_notes"][-10:]
                case["last_prepared_day"] = day

        if case.get("preparedness", 0.0) >= 0.95:
            if case.get("status") != "ready":
                case["status"] = "ready"
                self.add_event_log_message(
                    f"Case {case_id} is fully prepared for trial."
                )
        else:
            if case.get("status") in {"scheduled", "ready"}:
                case["status"] = "preparing"

        return case

    def get_case_to_prepare(self, prosecutor_name: str) -> Optional[Dict[str, Any]]:
        if not prosecutor_name:
            return None
        today = self.game_time.current_day if self.game_time else 0
        prep_window = getattr(config, "TRIAL_PREPARATION_WINDOW", 2)
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        for case in self.legal_cases.values():
            if case.get("prosecutor") != prosecutor_name:
                continue
            if case.get("status") in {"concluded", "cancelled", "in_session"}:
                continue
            scheduled_day = case.get("scheduled_day")
            if scheduled_day is None:
                continue
            days_until = scheduled_day - today
            if case.get("preparedness", 0.0) >= 0.95 and days_until > 0:
                continue
            if days_until <= prep_window:
                candidates.append((max(days_until, 0), case))
        if not candidates:
            return None
        candidates.sort(key=lambda entry: (entry[0], entry[1].get("preparedness", 0.0)))
        return candidates[0][1]

    def get_case_in_session_for(self, participant_name: str) -> Optional[Dict[str, Any]]:
        if not participant_name:
            return None
        for case in self.legal_cases.values():
            if case.get("status") != "in_session":
                continue
            if participant_name in {
                case.get("prosecutor"),
                case.get("defendant"),
                case.get("presiding_officer"),
            }:
                return case
        return None

    def process_legal_system_daily(self) -> None:
        if not self.legal_cases:
            return
        today = self.game_time.current_day if self.game_time else 0
        prep_window = getattr(config, "TRIAL_PREPARATION_WINDOW", 2)
        for case_id in list(self.trial_queue):
            case = self.legal_cases.get(case_id)
            if not case:
                self.trial_queue.remove(case_id)
                continue
            status = case.get("status")
            if status in {"concluded", "cancelled"}:
                self.trial_queue.remove(case_id)
                continue
            scheduled_day = case.get("scheduled_day")
            if scheduled_day is None:
                continue
            if status == "scheduled" and scheduled_day - today <= prep_window:
                case["status"] = "preparing"
                self.add_event_log_message(
                    f"Case {case_id} enters preparation ahead of its trial."
                )
            if today >= scheduled_day:
                case["status"] = "in_session"
                self.add_event_log_message(
                    f"Trial begins for case {case_id}: {case.get('defendant')} faces {case.get('charge', 'charges')}.")
                self._summon_trial_attendees(case)
                outcome = self._conduct_trial(case)
                self.trial_history.append(outcome)
                if case_id in self.trial_queue:
                    self.trial_queue.remove(case_id)

    def _conduct_trial(self, case: Dict[str, Any]) -> Dict[str, Any]:
        evidence = case.get("evidence_strength", 0.5)
        preparedness = case.get("preparedness", 0.0)
        base_probability = 0.35 + 0.4 * evidence + 0.1 * preparedness
        defendant = self.get_character_by_name(case.get("defendant", ""))
        if defendant:
            rep_modifier = max(-0.1, min(0.1, -defendant.reputation_score / 200.0))
            base_probability += rep_modifier
        base_probability = max(0.05, min(0.95, base_probability))
        verdict = "guilty" if random.random() < base_probability else "not_guilty"

        case["verdict"] = verdict
        case["verdict_day"] = self.game_time.current_day if self.game_time else None
        case["status"] = "concluded"

        prosecutor = self.get_character_by_name(case.get("prosecutor", ""))
        presiding = self.get_character_by_name(case.get("presiding_officer", ""))
        severity = case.get("severity", 1)

        crime_record = self.get_crime_by_id(case.get("crime_id", ""))
        if crime_record:
            crime_record["verdict"] = verdict

        if verdict == "guilty":
            fine_amount = max(3, int(round(4 * severity + evidence * 6)))
            fine_paid = 0
            if defendant:
                fine_paid = min(defendant.money, fine_amount)
                if fine_paid:
                    defendant.money -= fine_paid
                    self.treasury_coins += fine_paid
                defendant.update_mood_score(-15, f"Found guilty of {case.get('charge', 'a crime')}")
                defendant.update_reputation(-8, f"Convicted of {case.get('charge', 'a crime')}", self)
                defendant.add_memory(
                    f"Found guilty in trial {case.get('case_id')} and fined {fine_amount} coins."
                )
                esteem = defendant.needs.get("Esteem", config.NEED_ESTEEM_DEFAULT)
                defendant.needs["Esteem"] = max(config.NEED_SCORE_MIN, esteem - 10)
            if prosecutor:
                prosecutor.update_mood_score(6, "Secured conviction at trial")
                prosecutor.add_memory(
                    f"Verdict: {case.get('defendant')} found guilty in case {case.get('case_id')}."
                )
            if presiding:
                presiding.add_memory(
                    f"Presided over guilty verdict for case {case.get('case_id')}."
                )
            case["sentence"] = {"type": "fine", "amount": fine_amount, "paid": fine_paid}
            self.add_event_log_message(
                f"Verdict reached: {case.get('defendant')} found guilty of {case.get('charge', 'charges')} (fine {fine_amount} coins)."
            )
        else:
            if defendant:
                defendant.update_mood_score(8, "Acquitted at trial")
                defendant.update_reputation(3, f"Cleared of {case.get('charge', 'charges')}", self)
                defendant.add_memory(
                    f"Acquitted in trial {case.get('case_id')} and cleared of charges."
                )
                belonging = defendant.needs.get("Belonging", config.NEED_BELONGING_DEFAULT)
                defendant.needs["Belonging"] = min(config.NEED_SCORE_MAX, belonging + 5)
            if prosecutor:
                prosecutor.update_mood_score(-4, "Case dismissed at trial")
                prosecutor.add_memory(
                    f"Verdict: {case.get('defendant')} acquitted in case {case.get('case_id')}."
                )
            if presiding:
                presiding.add_memory(
                    f"Presided over acquittal for case {case.get('case_id')}."
                )
            case["sentence"] = {"type": "acquittal"}
            self.add_event_log_message(
                f"Verdict reached: {case.get('defendant')} acquitted of {case.get('charge', 'charges')}."
            )

        return case

    def _summon_trial_attendees(self, case: Dict[str, Any]) -> None:
        for role_key in ("prosecutor", "defendant", "presiding_officer"):
            name = case.get(role_key)
            if not name:
                continue
            character = self.get_character_by_name(name)
            if not character:
                continue
            character.current_goal = Goal(
                GoalType.ATTEND_TRIAL,
                assignee_id=character.name,
                originator_id="CourtSummons",
                parameters={
                    "case_id": case.get("case_id"),
                    "location": self.courthouse_location,
                },
            )
            character.add_memory(
                f"Summoned to attend trial {case.get('case_id')} at the courthouse."
            )

    def _select_presiding_officer(self) -> Optional[str]:
        mayor = next((char for char in self.characters if char.job == "Mayor"), None)
        if mayor:
            return mayor.name
        best_candidate: Optional['Character'] = None
        best_score = -1
        for char in self.characters:
            leadership = char.skills.get("Leadership", {}).get("level", 0)
            if leadership > best_score:
                best_score = leadership
                best_candidate = char
        return best_candidate.name if best_candidate else None

    def get_public_trial_snapshot(self) -> List[Dict[str, Any]]:
        if not self.legal_cases:
            return []
        ordered_cases = sorted(
            self.legal_cases.values(),
            key=lambda case: (
                case.get("status") not in {"scheduled", "preparing", "ready"},
                case.get("scheduled_day", float("inf")),
            ),
        )
        snapshot: List[Dict[str, Any]] = []
        for case in ordered_cases[:10]:
            snapshot.append(
                {
                    "case_id": case.get("case_id"),
                    "defendant": case.get("defendant"),
                    "charge": case.get("charge"),
                    "status": case.get("status"),
                    "scheduled_day": case.get("scheduled_day"),
                    "verdict": case.get("verdict"),
                }
            )
        return snapshot

    # --- Healthcare & Medical Coordination -------------------------------------------------

    def _next_medical_case_id(self) -> str:
        self._medical_case_counter += 1
        return f"med_{self._medical_case_counter}"

    def _prioritize_medical_queue(self) -> None:
        if not self.medical_cases:
            self.medical_triage_queue = []
            return
        unique_ids = []
        seen: Set[str] = set()
        for cid in self.medical_triage_queue:
            if cid in seen:
                continue
            if cid not in self.medical_cases:
                continue
            if self.medical_cases[cid].get("status") == "resolved":
                continue
            seen.add(cid)
            unique_ids.append(cid)
        unique_ids.sort(
            key=lambda case_id: (
                -self.medical_cases[case_id].get("severity", 0),
                self.medical_cases[case_id].get("reported_day", float("inf")),
                self.medical_cases[case_id].get("last_report_day", float("inf")),
            )
        )
        self.medical_triage_queue = unique_ids

    def register_medical_case(
        self,
        patient_name: str,
        condition: str,
        severity: float,
        *,
        reporter: Optional[str] = None,
        cause: Optional[str] = None,
        location: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        patient = self.get_character_by_name(patient_name)
        if not patient:
            return None, False

        severity = max(0.0, float(severity))
        existing_id: Optional[str] = None
        for cid, case in self.medical_cases.items():
            if (
                case.get("patient") == patient_name
                and case.get("condition") == condition
                and case.get("status") != "resolved"
            ):
                existing_id = cid
                break

        day = self.game_time.current_day if self.game_time else 0
        note = {
            "day": day,
            "reporter": reporter or patient_name,
            "summary": cause or "Condition update",
        }

        if existing_id:
            case = self.medical_cases[existing_id]
            previous_severity = case.get("severity", 0.0)
            if severity > previous_severity:
                case["severity"] = severity
                case.setdefault("alerts", []).append(
                    {
                        "day": day,
                        "message": f"Severity increased to {severity:.1f}",
                    }
                )
                self.add_event_log_message(
                    f"Medical update: {patient_name}'s {condition} escalated to severity {severity:.1f}."
                )
            case.setdefault("reports", []).append(note)
            case["last_report_day"] = day
            if case.get("status") == "waiting" and existing_id not in self.medical_triage_queue:
                self.medical_triage_queue.append(existing_id)
            self._prioritize_medical_queue()
            return case, False

        case_id = self._next_medical_case_id()
        case = {
            "case_id": case_id,
            "patient": patient_name,
            "condition": condition,
            "severity": severity,
            "reported_day": day,
            "last_report_day": day,
            "status": "waiting",
            "assigned_to": None,
            "location": location or (patient.x, patient.y),
            "reports": [note],
            "alerts": [],
        }
        self.medical_cases[case_id] = case
        self.medical_triage_queue.append(case_id)
        self._prioritize_medical_queue()

        patient.add_memory(
            f"Medical case opened for {condition} (severity {severity:.1f})."
        )
        self.add_event_log_message(
            f"Medical case {case_id} opened for {patient_name} ({condition}, severity {severity:.1f})."
        )
        return case, True

    def get_medical_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.medical_cases.get(case_id)

    def claim_medical_case(self, medic_name: str) -> Optional[Dict[str, Any]]:
        if not self.medical_cases:
            return None
        for case_id in list(self.medical_triage_queue):
            case = self.medical_cases.get(case_id)
            if not case:
                self.medical_triage_queue.remove(case_id)
                continue
            if case.get("status") == "resolved":
                self.medical_triage_queue.remove(case_id)
                continue
            if case.get("assigned_to") and case.get("assigned_to") != medic_name:
                continue
            patient = self.get_character_by_name(case.get("patient", ""))
            if not patient:
                self.resolve_medical_case(
                    case_id,
                    "cancelled",
                    notes=f"Patient {case.get('patient')} no longer in settlement.",
                )
                self.medical_triage_queue.remove(case_id)
                continue
            case["status"] = "assigned"
            case["assigned_to"] = medic_name
            case["last_assignment_day"] = self.game_time.current_day if self.game_time else 0
            case.setdefault("reports", []).append(
                {
                    "day": self.game_time.current_day if self.game_time else 0,
                    "reporter": medic_name,
                    "summary": "Case claimed for treatment",
                }
            )
            self.medical_triage_queue.remove(case_id)
            return case
        return None

    def record_medical_treatment(
        self,
        case_id: str,
        caregiver: str,
        severity_after: float,
        *,
        item_used: Optional[str] = None,
        notes: Optional[str] = None,
        success: bool = False,
    ) -> bool:
        case = self.medical_cases.get(case_id)
        if not case:
            return False

        day = self.game_time.current_day if self.game_time else 0
        case["severity"] = max(0.0, severity_after)
        case["last_treated_day"] = day
        case["assigned_to"] = None
        summary = notes or ("Treatment succeeded" if success else "Treatment attempted")
        if item_used:
            summary = f"{summary} using {item_used}"
        case.setdefault("reports", []).append(
            {
                "day": day,
                "reporter": caregiver,
                "summary": summary,
            }
        )
        if success:
            case.setdefault("alerts", []).append(
                {
                    "day": day,
                    "message": f"Improvement noted by {caregiver}",
                }
            )

        if case["severity"] <= 0:
            self.resolve_medical_case(
                case_id,
                "recovered",
                notes=f"{caregiver} resolved the case.",
            )
            return True

        case["status"] = "waiting"
        if case_id not in self.medical_triage_queue:
            self.medical_triage_queue.append(case_id)
        self._prioritize_medical_queue()
        return False

    def resolve_medical_case(
        self,
        case_id: str,
        outcome: str,
        *,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        case = self.medical_cases.get(case_id)
        if not case:
            return None
        day = self.game_time.current_day if self.game_time else 0
        case["status"] = "resolved"
        case["resolved_day"] = day
        case["outcome"] = outcome
        if notes:
            case.setdefault("reports", []).append(
                {
                    "day": day,
                    "reporter": "System",
                    "summary": notes,
                }
            )
        history_entry = deepcopy(case)
        self.medical_history.append(history_entry)
        self.medical_cases.pop(case_id, None)
        if case_id in self.medical_triage_queue:
            self.medical_triage_queue.remove(case_id)
        self.add_event_log_message(
            f"Medical case {case_id} closed ({outcome})."
        )
        return history_entry

    def _get_open_supply_request(self, resource: str) -> Optional[Dict[str, Any]]:
        for request in self.clinic_supply_requests:
            if request.get("resource") == resource and request.get("status") == "open":
                return request
        return None

    def get_clinic_supply_requests(self) -> List[Dict[str, Any]]:
        return [deepcopy(req) for req in self.clinic_supply_requests]

    def get_medical_queue_snapshot(self) -> List[Dict[str, Any]]:
        if not self.medical_cases:
            return []
        active_cases = [
            case
            for case in self.medical_cases.values()
            if case.get("status") != "resolved"
        ]
        active_cases.sort(
            key=lambda case: (
                -case.get("severity", 0),
                case.get("reported_day", float("inf")),
                case.get("patient", ""),
            )
        )
        snapshot: List[Dict[str, Any]] = []
        for case in active_cases[:15]:
            snapshot.append(
                {
                    "case_id": case.get("case_id"),
                    "patient": case.get("patient"),
                    "condition": case.get("condition"),
                    "severity": case.get("severity"),
                    "status": case.get("status"),
                    "assigned_to": case.get("assigned_to"),
                    "reported_day": case.get("reported_day"),
                }
            )
        return snapshot

    def process_healthcare_daily(self) -> None:
        if not self.game_time:
            return

        day = self.game_time.current_day
        new_cases: List[str] = []
        worsened_cases: List[str] = []

        for char in self.characters:
            if char.is_sick and char.sickness_severity > 0:
                case, created = self.register_medical_case(
                    char.name,
                    "sickness",
                    char.sickness_severity,
                    reporter=char.name,
                    cause="Daily health check-in",
                    location=(char.x, char.y),
                )
                if created and case:
                    new_cases.append(case.get("case_id"))
            if char.is_injured and char.injury_severity > 0:
                case, created = self.register_medical_case(
                    char.name,
                    "injury",
                    char.injury_severity,
                    reporter=char.name,
                    cause="Daily injury assessment",
                    location=(char.x, char.y),
                )
                if created and case:
                    new_cases.append(case.get("case_id"))

        for case_id, case in list(self.medical_cases.items()):
            if case.get("status") == "resolved":
                continue
            last_treatment_day = case.get("last_treated_day", case.get("reported_day", day))
            waiting_days = max(0, day - last_treatment_day)
            if waiting_days > 0:
                severity_before = case.get("severity", 0.0)
                escalation_chance = 0.2 + 0.05 * waiting_days + 0.03 * severity_before
                if random.random() < min(0.9, escalation_chance):
                    case["severity"] = min(10.0, severity_before + random.choice([0.5, 1.0]))
                    patient = self.get_character_by_name(case.get("patient", ""))
                    if patient:
                        if case.get("condition") == "injury":
                            patient.is_injured = True
                            patient.injury_severity = max(patient.injury_severity, case["severity"])
                        else:
                            patient.is_sick = True
                            patient.sickness_severity = max(patient.sickness_severity, case["severity"])
                        patient.update_mood_score(
                            -3,
                            "Health worsened while awaiting treatment",
                        )
                        patient.add_memory(
                            f"Condition worsened to severity {case['severity']:.1f} while waiting for care."
                        )
                    case.setdefault("alerts", []).append(
                        {
                            "day": day,
                            "message": "Condition worsened while unattended.",
                        }
                    )
                    case.setdefault("reports", []).append(
                        {
                            "day": day,
                            "reporter": "System",
                            "summary": "Severity escalated due to treatment delay",
                        }
                    )
                    self.add_event_log_message(
                        f"Medical case {case_id} for {case.get('patient')} worsened to severity {case['severity']:.1f}."
                    )
                    worsened_cases.append(case_id)
            if case.get("status") == "waiting" and case_id not in self.medical_triage_queue:
                self.medical_triage_queue.append(case_id)

        self._prioritize_medical_queue()

        supply_alerts: List[Dict[str, Any]] = []
        if self.ledger:
            thresholds = getattr(
                config,
                "CLINIC_SUPPLY_THRESHOLDS",
                {"Bandages": 5, "Herbs": 8},
            )
            for resource, threshold in thresholds.items():
                quantity = self.ledger.get_total_resource_count(resource)
                open_request = self._get_open_supply_request(resource)
                if quantity < threshold:
                    if not open_request:
                        request = {
                            "resource": resource,
                            "threshold": threshold,
                            "current": quantity,
                            "status": "open",
                            "requested_day": day,
                        }
                        self.clinic_supply_requests.append(request)
                        self.add_event_log_message(
                            f"Clinic flagged low {resource} levels ({quantity}/{threshold})."
                        )
                    else:
                        open_request["current"] = quantity
                    supply_alerts.append(
                        {
                            "resource": resource,
                            "current": quantity,
                            "threshold": threshold,
                        }
                    )
                elif open_request:
                    open_request["status"] = "fulfilled"
                    open_request["fulfilled_day"] = day
                    open_request["current"] = quantity
                    self.add_event_log_message(
                        f"Clinic restocked {resource} (now {quantity})."
                    )

        self.latest_healthcare_report = {
            "day": day,
            "new_cases": new_cases,
            "worsened_cases": worsened_cases,
            "active_cases": len(self.medical_cases),
            "supply_alerts": supply_alerts,
        }

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

    def _propagate_rumors_daily(self) -> None:
        """Passively spreads strong rumors to nearby citizens to keep the social web alive."""
        if not self.game_time or not self.characters:
            return

        attempts = getattr(config, "DAILY_RUMOR_SPREAD_ATTEMPTS", 0)
        if attempts <= 0:
            return

        min_strength = getattr(config, "MIN_RUMOR_STRENGTH_TO_SPREAD", 0)
        viable_rumors = [
            rumor for rumor in sorted(self.rumors, key=lambda r: r.current_strength, reverse=True)
            if rumor.current_strength >= min_strength
        ]
        if not viable_rumors:
            return

        attempts = min(attempts, len(viable_rumors))
        for rumor in viable_rumors[:attempts]:
            subject_char = self.get_character_by_name(rumor.subject_char_id)
            carriers = [
                char for char in self.characters
                if rumor.rumor_id in getattr(char, "known_rumor_ids", set())
            ]
            if not carriers:
                if subject_char:
                    carriers.append(subject_char)
            if not carriers:
                continue

            carrier = random.choice(carriers)
            rumor.add_knower(carrier.name)

            potential_listeners = [
                char
                for char in self.characters
                if char.name != carrier.name and rumor.rumor_id not in char.known_rumor_ids
            ]
            if not potential_listeners:
                continue

            acquainted_listeners = [
                char
                for char in potential_listeners
                if carrier.name in char.known_characters or char.name in carrier.known_characters
            ]
            if acquainted_listeners:
                potential_listeners = acquainted_listeners

            listener = random.choice(potential_listeners)
            listener.known_rumor_ids.add(rumor.rumor_id)
            rumor.add_knower(listener.name)
            if carrier.name not in listener.known_characters:
                listener.known_characters.append(carrier.name)

            if subject_char and subject_char.name not in listener.known_characters:
                listener.known_characters.append(subject_char.name)

            listener.add_memory(
                f"Heard a rumor about {rumor.subject_char_id} from {carrier.name}."
            )
            carrier.add_memory(
                f"Rumor about {rumor.subject_char_id} reached {listener.name}."
            )

            rumor.reinforce(
                getattr(config, "RUMOR_SPREAD_STRENGTH_INCREASE", 0),
                getattr(config, "RUMOR_MAX_STRENGTH", 100),
            )
            rumor.last_spread_day = self.game_time.current_day

            # Let the listener react to the rumor's content.
            listener._process_learned_rumor(rumor, self)

            relation_delta = (
                getattr(config, "RUMOR_PASSIVE_RELATIONSHIP_POSITIVE", 0)
                if rumor.is_positive
                else getattr(config, "RUMOR_PASSIVE_RELATIONSHIP_NEGATIVE", 0)
            )
            if relation_delta and subject_char:
                listener.modify_relationship(
                    subject_char.name,
                    relation_delta,
                    self,
                    reason="Rumor shaped my view of them.",
                )

                subject_reaction = (
                    getattr(config, "RUMOR_PASSIVE_SUBJECT_REACTION_BONUS", 0)
                    if rumor.is_positive
                    else getattr(config, "RUMOR_PASSIVE_SUBJECT_REACTION_PENALTY", 0)
                )
                if subject_reaction and listener.name in subject_char.known_characters:
                    subject_char.modify_relationship(
                        listener.name,
                        subject_reaction,
                        self,
                        reason="They believed a story about me.",
                    )

            sentiment = "praises" if rumor.is_positive else "slanders"
            self.add_event_log_message(
                f"Rumor travels: {carrier.name} {sentiment} {rumor.subject_char_id} to {listener.name}."
            )
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
                bonuses = resource_bonus if isinstance(resource_bonus, list) else [resource_bonus]
                for bonus in bonuses:
                    res_name = bonus.get("resource")
                    multiplier = bonus.get("multiplier", 1.0)
                    if res_name:
                        apply_resource(res_name, multiplier, f"Effect: {effect_key}")
            travel_bonus = effect_data.get("travel_speed_multiplier")
            if travel_bonus:
                apply_travel(travel_bonus, f"Effect: {effect_key}")
            market_bonus = effect_data.get("market_price_adjustment")
            if market_bonus:
                for item_name, multiplier in market_bonus.items():
                    apply_market(item_name, multiplier, f"Effect: {effect_key}")

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
        snapshot["phase"] = self.get_current_phase()
        snapshot["weather_event"] = self.get_active_weather_event()
        snapshot["community_spirit"] = round(self.community_spirit, 3)
        snapshot["cultural_event"] = deepcopy(self.active_cultural_event) if self.active_cultural_event else None
        snapshot["upcoming_cultural_events"] = self._get_upcoming_cultural_events(limit=3)
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

    def _deposit_work_output(
        self,
        resource_name: str,
        quantity: int,
        preferred_stockpiles: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "delivered": 0,
            "overflow": max(0, quantity),
            "routes": [],
        }
        if quantity <= 0:
            return result

        stockpiles = list(self.get_stockpiles_for_resource(resource_name))
        if not stockpiles:
            return result

        ordered: List[Stockpile] = []
        preferred_lookup: Set[str] = set(preferred_stockpiles or [])
        if preferred_lookup:
            for name in preferred_stockpiles or []:
                stockpile = self.get_stockpile_by_name(name)
                if stockpile and stockpile in stockpiles and stockpile not in ordered:
                    ordered.append(stockpile)
        for stockpile in stockpiles:
            if stockpile not in ordered:
                ordered.append(stockpile)

        remaining = quantity
        routes: List[Dict[str, Any]] = []
        for stockpile in ordered:
            if remaining <= 0:
                break
            success, added = stockpile.add_item(resource_name, remaining)
            if not success or added <= 0:
                continue
            routes.append({"stockpile": stockpile.name, "quantity": added})
            remaining -= added
            if self.game_time:
                self.ledger.update_stockpile_record(
                    stockpile.name,
                    stockpile.inventory,
                    self.game_time.current_day,
                )

        delivered = quantity - remaining
        result["delivered"] = delivered
        result["overflow"] = max(0, remaining)
        result["routes"] = routes

        if delivered > 0:
            for route in routes:
                history_entry = {
                    "day": self.game_time.current_day if self.game_time else -1,
                    "resource": resource_name,
                    "stockpile": route["stockpile"],
                    "quantity": route["quantity"],
                }
                self.work_logistics_history.append(history_entry)
            self.work_logistics_history = self.work_logistics_history[-25:]

        return result

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

        food_yield = self.get_resource_yield_multiplier("Food")
        scarcity_factor = max(0.0, 1.0 - min(food_yield, 1.0))
        abundance_factor = max(0.0, food_yield - 1.0)
        consumption_min = getattr(config, "ENVIRONMENT_CONSUMPTION_MINIMUM", 1)
        scarcity_scale = getattr(config, "ENVIRONMENT_SCARCITY_CONSUMPTION_SCALE", 0.0)
        abundance_scale = getattr(config, "ENVIRONMENT_ABUNDANCE_CONSUMPTION_SCALE", 0.0)

        effective_per_capita = per_capita
        if scarcity_factor > 0:
            effective_per_capita = max(
                consumption_min,
                int(round(per_capita * (1 + scarcity_factor * scarcity_scale))),
            )
        elif abundance_factor > 0:
            effective_per_capita = max(
                consumption_min,
                int(round(per_capita * (1 - abundance_factor * abundance_scale))),
            )

        scarcity_mood = int(round(getattr(config, "ENVIRONMENT_SCARCITY_MOOD_PENALTY", 0) * scarcity_factor))
        abundance_mood = int(round(getattr(config, "ENVIRONMENT_ABUNDANCE_MOOD_BONUS", 0) * abundance_factor))

        population = len(self.characters)
        report["food_per_capita"] = effective_per_capita
        report["food_required"] = effective_per_capita * population
        report["food_consumption_modifier"] = food_yield

        for character in self.characters:
            required = effective_per_capita
            consumed = self._consume_resource_for_character(character, "Food", required)
            if consumed > 0:
                total_consumed += consumed
                current_hunger = character.needs.get("Hunger", 50)
                hunger_gain = hunger_recovery * consumed
                character.needs["Hunger"] = min(config.NEED_SCORE_MAX, current_hunger + hunger_gain)
                ration_text = "ration" if consumed == 1 else "rations"
                character.add_memory(f"Shared the daily meal ({consumed} {ration_text}).")
                character.update_mood_score(config.MOOD_CHANGE_NEED_FULFILLED, "Ate communal meal")
                if scarcity_factor > 0 and scarcity_mood < 0:
                    character.update_mood_score(
                        scarcity_mood,
                        "Rations felt meagre under harsh conditions",
                    )
                elif abundance_factor > 0 and abundance_mood > 0:
                    character.update_mood_score(
                        abundance_mood,
                        "Feasted thanks to generous harvests",
                    )
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

        water_yield = self.get_resource_yield_multiplier("Water")
        scarcity_factor = max(0.0, 1.0 - min(water_yield, 1.0))
        abundance_factor = max(0.0, water_yield - 1.0)
        consumption_min = getattr(config, "ENVIRONMENT_CONSUMPTION_MINIMUM", 1)
        scarcity_scale = getattr(config, "ENVIRONMENT_SCARCITY_CONSUMPTION_SCALE", 0.0)
        abundance_scale = getattr(config, "ENVIRONMENT_ABUNDANCE_CONSUMPTION_SCALE", 0.0)

        effective_per_capita = per_capita
        if scarcity_factor > 0:
            effective_per_capita = max(
                consumption_min,
                int(round(per_capita * (1 + scarcity_factor * scarcity_scale))),
            )
        elif abundance_factor > 0:
            effective_per_capita = max(
                consumption_min,
                int(round(per_capita * (1 - abundance_factor * abundance_scale))),
            )

        scarcity_mood = int(round(getattr(config, "ENVIRONMENT_SCARCITY_MOOD_PENALTY", 0) * scarcity_factor))
        abundance_mood = int(round(getattr(config, "ENVIRONMENT_ABUNDANCE_MOOD_BONUS", 0) * abundance_factor))

        population = len(self.characters)
        report["water_per_capita"] = effective_per_capita
        report["water_required"] = effective_per_capita * population
        report["water_consumption_modifier"] = water_yield

        for character in self.characters:
            required = effective_per_capita
            consumed = self._consume_resource_for_character(character, "Water", required)
            if consumed > 0:
                total_consumed += consumed
                thirst = character.needs.get("Thirst", 80)
                thirst_gain = thirst_recovery * consumed
                character.needs["Thirst"] = min(config.NEED_SCORE_MAX, thirst + thirst_gain)
                ration_text = "drink" if consumed == 1 else "drinks"
                character.add_memory(f"Drank {consumed} water {ration_text} with the community.")
                character.update_mood_score(getattr(config, "MOOD_CHANGE_REPLENISHED_WATER", 3), "Enjoyed fresh water")
                if scarcity_factor > 0 and scarcity_mood < 0:
                    character.update_mood_score(
                        scarcity_mood,
                        "Cisterns are low; every sip is rationed",
                    )
                elif abundance_factor > 0 and abundance_mood > 0:
                    character.update_mood_score(
                        abundance_mood,
                        "Plentiful water kept spirits high",
                    )
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

    def _evaluate_housing_daily(self, report: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self.get_housing_snapshot()
        report["housing"] = snapshot
        self.latest_housing_snapshot = snapshot

        if not self.game_time:
            return snapshot

        today = self.game_time.current_day
        if self.last_housing_evaluation_day == today:
            return snapshot

        homeless_names = snapshot.get("homeless_characters", [])
        mood_penalty = getattr(config, "MOOD_CHANGE_HOMELESS_SLEEP", -6)
        energy_penalty = getattr(config, "ENERGY_PENALTY_HOMELESS_SLEEP", 8)
        belonging_penalty = getattr(config, "BELONGING_PENALTY_HOMELESS_SLEEP", 4)
        for name in homeless_names:
            character = self.get_character_by_name(name)
            if not character:
                continue
            character.add_memory("Slept outdoors without the safety of a roof.")
            if mood_penalty:
                character.update_mood_score(mood_penalty, "Slept without shelter")
            if energy_penalty:
                current_energy = character.needs.get("Energy", 70)
                character.needs["Energy"] = max(
                    config.NEED_SCORE_MIN,
                    current_energy - energy_penalty,
                )
            if belonging_penalty:
                current_belonging = character.needs.get(
                    "Belonging", config.NEED_BELONGING_DEFAULT
                )
                character.needs["Belonging"] = max(
                    config.NEED_SCORE_MIN,
                    current_belonging - belonging_penalty,
                )

        rest_bonus = getattr(config, "MOOD_CHANGE_RESTED_IN_HOME", 0)
        if rest_bonus:
            for name in snapshot.get("resting_characters", []):
                character = self.get_character_by_name(name)
                if not character:
                    continue
                character.update_mood_score(rest_bonus, "Recovered in warm shelter")

        self.last_housing_evaluation_day = today
        return snapshot

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

    def evaluate_population_dynamics(
        self,
        economy_report: Dict[str, Any],
        housing_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.game_time:
            return

        day = self.game_time.current_day
        self.population_stats.update(
            {
                "population": len(self.characters),
                "births_today": 0,
                "migrants_today": 0,
                "departures_today": 0,
                "last_updated_day": day,
            }
        )

        for character in list(self.characters):
            if hasattr(character, "advance_age"):
                character.advance_age(self)
                if character.name in self._resident_registry:
                    self._resident_registry[character.name]["age"] = getattr(character, "age_years", None)

        available_beds = None
        homeless_names: Set[str] = set()
        if housing_snapshot:
            available_beds = housing_snapshot.get("available_beds")
            homeless_names = set(housing_snapshot.get("homeless_characters", []))

        food_deficit = economy_report.get("food_deficit", 0)
        water_deficit = economy_report.get("water_deficit", 0)
        pressures = self.identify_resource_pressures()

        population_events: List[Dict[str, Any]] = []

        birth_threshold = getattr(config, "POPULATION_BELONGING_THRESHOLD_FOR_BIRTH", 60)
        birth_chance = getattr(config, "POPULATION_BIRTH_BASE_CHANCE", 0.0)
        if (
            available_beds
            and available_beds > 0
            and food_deficit <= 0
            and water_deficit <= 0
            and random.random() < birth_chance
        ):
            eligible_parents = [
                char
                for char in self.characters
                if getattr(char, "age_years", 18) >= 18
                and getattr(char, "age_years", 18) <= 45
                and char.needs.get("Belonging", 0) >= birth_threshold
                and not getattr(char, "is_sick", False)
            ]
            if eligible_parents:
                parent = random.choice(eligible_parents)
                child_profile = self._generate_citizen_profile(
                    job="Unemployed",
                    age=0,
                    needs=dict(config.DEFAULT_CHILD_NEEDS),
                    traits=["Innocent"],
                    personality="Curious",
                    origin=f"Born to {parent.name}",
                )
                child_profile["x"], child_profile["y"] = parent.x, parent.y
                child = self._spawn_new_citizen(
                    child_profile,
                    arrival_reason=f"A new child, {child_profile['name']}, is born into {parent.name}'s household.",
                )
                if child:
                    self.population_stats["births_today"] += 1
                    child.resting_at_home = True
                    if parent.home_location:
                        building = self.get_building_by_location(parent.home_location)
                        if building:
                            building.add_occupant(child.name)
                            self._residential_assignments[child.name] = building.location
                            child.home_location = building.location
                    population_events.append({"type": "birth", "name": child.name, "parent": parent.name})

        migration_chance = getattr(config, "POPULATION_MIGRATION_BASE_CHANCE", 0.0)
        surplus_resources = [p for p in pressures if p.get("status") == "surplus"]
        if (
            available_beds
            and available_beds > 0
            and food_deficit <= 0
            and water_deficit <= 0
            and surplus_resources
            and random.random() < migration_chance
        ):
            archetype = random.choice(MIGRANT_ARCHETYPES)
            migrant_profile = self._generate_citizen_profile(
                job=archetype.get("job", "Laborer"),
                traits=archetype.get("traits"),
                personality=archetype.get("personality"),
                skills=archetype.get("skills"),
                origin="Nearby hamlet",
                citizenship="Immigrant",
            )
            migrant = self._spawn_new_citizen(
                migrant_profile,
                arrival_reason=f"Migrant {migrant_profile['name']} arrives seeking {migrant_profile['job']} work.",
            )
            if migrant:
                self.population_stats["migrants_today"] += 1
                self.claim_residential_spot(migrant)
                population_events.append({"type": "arrival", "name": migrant.name, "job": migrant.job})

        departure_chance = getattr(config, "POPULATION_DEPARTURE_BASE_CHANCE", 0.0)
        hardship = 0.0
        if food_deficit > 0:
            hardship += 0.15
        if water_deficit > 0:
            hardship += 0.15
        if homeless_names:
            hardship += getattr(config, "POPULATION_DEPARTURE_HOMELESS_WEIGHT", 0.2)

        departure_candidates = [
            char
            for char in self.characters
            if getattr(char, "mood_score", 0) <= getattr(config, "POPULATION_DEPARTURE_MOOD_THRESHOLD", -35)
            or char.name in homeless_names
        ]
        departure_candidates = [
            char for char in departure_candidates if char.rank not in ["Mayor", "Duke", "Baroness", "Noble Lord"]
        ]
        if (
            departure_candidates
            and len(self.characters) > 3
            and random.random() < (departure_chance + hardship)
        ):
            leaving = random.choice(departure_candidates)
            reason = "homelessness" if leaving.name in homeless_names else "hardship"
            self.add_event_log_message(f"{leaving.name} departs the settlement due to {reason}.")
            self.add_notable_event(
                "Departure",
                {"summary": f"{leaving.name} left because of {reason}.", "name": leaving.name, "reason": reason},
            )
            self.remove_character(leaving)
            self.population_stats["departures_today"] += 1
            population_events.append({"type": "departure", "name": leaving.name, "reason": reason})

        self.population_stats["population"] = len(self.characters)
        self.demographic_history.append(
            {
                "day": day,
                "population": self.population_stats["population"],
                "births": self.population_stats["births_today"],
                "migrants": self.population_stats["migrants_today"],
                "departures": self.population_stats["departures_today"],
            }
        )
        if len(self.demographic_history) > 30:
            self.demographic_history.pop(0)

        if population_events:
            economy_report.setdefault("population_events", []).extend(population_events)
        economy_report["population_snapshot"] = dict(self.population_stats)

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

    # --- Training & Apprenticeships ---

    def _assess_training_needs(self) -> Dict[str, Dict[str, Any]]:
        metrics: Dict[str, Dict[str, Any]] = {}
        if not self.training_program_definitions:
            return metrics

        for program_key, definition in self.training_program_definitions.items():
            skill_name = definition.get("skill")
            if not skill_name:
                continue
            focus_jobs = definition.get("focus_jobs", [])
            relevant_chars = [
                char
                for char in self.characters
                if not focus_jobs or char.job in focus_jobs
            ]
            levels: List[int] = []
            under_target: List[str] = []
            target_level = definition.get("target_level", 1)
            for char in relevant_chars:
                skill_data = char.skills.get(skill_name)
                level = skill_data.get("level", 0) if skill_data else 0
                levels.append(level)
                if level < target_level:
                    under_target.append(char.name)
            avg_level = sum(levels) / len(levels) if levels else 0.0
            metrics[program_key] = {
                "definition": definition,
                "skill": skill_name,
                "focus_jobs": focus_jobs,
                "avg_level": avg_level,
                "under_target": under_target,
                "total_characters": len(relevant_chars),
            }
        return metrics

    def _refresh_training_waitlists(
        self, metrics: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        snapshot: List[Dict[str, Any]] = []
        active_names = {
            name
            for session in self.active_training_sessions
            for name in session.get("trainees", [])
        }
        valid_programs = set(metrics.keys())
        for stale_key in set(self.training_waitlists.keys()) - valid_programs:
            self.training_waitlists.pop(stale_key, None)

        for program_key, data in metrics.items():
            definition = data["definition"]
            skill_name = data["skill"]
            target_level = definition.get("target_level", 1)
            min_level = definition.get("min_level", 0)
            focus_jobs = data.get("focus_jobs", [])
            waitlist = self.training_waitlists.setdefault(program_key, [])
            filtered_queue: List[str] = []
            for name in waitlist:
                char = self.get_character_by_name(name)
                if not char:
                    continue
                if focus_jobs and char.job not in focus_jobs:
                    continue
                skill_level = char.skills.get(skill_name, {}).get("level", 0)
                if skill_level >= target_level:
                    continue
                filtered_queue.append(name)

            new_entries: List[str] = []
            for name in data.get("under_target", []):
                if name in filtered_queue or name in active_names:
                    continue
                char = self.get_character_by_name(name)
                if not char:
                    continue
                skill_level = char.skills.get(skill_name, {}).get("level", 0)
                if skill_level < target_level and skill_level >= min_level:
                    filtered_queue.append(name)
                    new_entries.append(name)

            self.training_waitlists[program_key] = filtered_queue
            if new_entries:
                cohort = ", ".join(new_entries)
                title = definition.get("title", program_key)
                self.add_event_log_message(
                    f"Training queue: {title} adds {cohort}."
                )

            snapshot.append(
                {
                    "program": definition.get("title", program_key),
                    "program_key": program_key,
                    "skill": skill_name,
                    "queued": list(filtered_queue),
                    "count": len(filtered_queue),
                }
            )

        return snapshot

    def _select_training_instructor(
        self, definition: Dict[str, Any], busy_instructors: Set[str]
    ) -> Optional['Character']:
        instructor_roles = definition.get("instructor_roles", [])
        if not instructor_roles:
            return None
        skill_name = definition.get("skill")
        best_candidate: Optional['Character'] = None
        best_score = -1
        for char in self.characters:
            if char.name in busy_instructors:
                continue
            if char.job not in instructor_roles:
                continue
            skill_level = char.skills.get(skill_name, {}).get("level", 0)
            if skill_level > best_score:
                best_candidate = char
                best_score = skill_level
        return best_candidate

    def _start_training_sessions(
        self,
        metrics: Dict[str, Dict[str, Any]],
        current_day: int,
    ) -> List[Dict[str, Any]]:
        started: List[Dict[str, Any]] = []
        busy_instructors: Set[str] = {
            session.get("instructor", "")
            for session in self.active_training_sessions
        }

        for program_key, data in metrics.items():
            waitlist = self.training_waitlists.get(program_key, [])
            if not waitlist:
                continue
            allow_parallel = data["definition"].get("parallel_sessions", False)
            if not allow_parallel and any(
                session.get("program_key") == program_key
                for session in self.active_training_sessions
            ):
                continue

            instructor = self._select_training_instructor(
                data["definition"], busy_instructors
            )
            if not instructor:
                continue

            capacity = max(1, int(data["definition"].get("capacity", 1)))
            trainees = waitlist[:capacity]
            if not trainees:
                continue
            self.training_waitlists[program_key] = waitlist[capacity:]

            session = {
                "program_key": program_key,
                "program_title": data["definition"].get("title", program_key),
                "skill": data["skill"],
                "instructor": instructor.name,
                "trainees": list(trainees),
                "original_trainees": list(trainees),
                "start_day": current_day,
                "duration": max(1, int(data["definition"].get("duration_days", 1))),
                "daily_exp": float(data["definition"].get("daily_exp_gain", 1.0)),
                "progress": 0,
                "trainee_baselines": {},
                "latest_results": {},
            }

            for trainee_name in trainees:
                character = self.get_character_by_name(trainee_name)
                if not character:
                    continue
                skill_data = character.skills.get(data["skill"], {})
                session["trainee_baselines"][trainee_name] = {
                    "level": skill_data.get("level", 0),
                    "experience": skill_data.get("experience", 0.0),
                }

            self.active_training_sessions.append(session)
            busy_instructors.add(instructor.name)
            trainee_label = ", ".join(trainees)
            self.add_event_log_message(
                f"{instructor.name} opens {session['program_title']} for {trainee_label}."
            )
            started.append(
                {
                    "program": session["program_title"],
                    "instructor": instructor.name,
                    "trainees": list(trainees),
                }
            )

        return started

    def _advance_training_sessions(
        self, current_day: int
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not self.active_training_sessions:
            return [], []

        daily_updates: List[Dict[str, Any]] = []
        concluded_summaries: List[Dict[str, Any]] = []
        sessions_to_remove: List[Dict[str, Any]] = []

        for session in list(self.active_training_sessions):
            day_results: List[Dict[str, Any]] = []
            level_ups: List[Dict[str, Any]] = []
            remaining_trainees: List[str] = []

            for trainee_name in list(session.get("trainees", [])):
                character = self.get_character_by_name(trainee_name)
                if not character:
                    day_results.append({"name": trainee_name, "status": "absent"})
                    continue
                result = character.participate_in_training(
                    session["program_title"],
                    session["skill"],
                    session["daily_exp"],
                    self,
                )
                session["latest_results"][trainee_name] = {
                    "level": result["level_after"],
                    "experience": result["experience_after"],
                }
                day_results.append(
                    {
                        "name": trainee_name,
                        "level_before": result["level_before"],
                        "level_after": result["level_after"],
                        "experience_gain": session["daily_exp"],
                    }
                )
                if result["level_after"] > result["level_before"]:
                    level_ups.append(
                        {
                            "name": trainee_name,
                            "new_level": result["level_after"],
                        }
                    )
                    self.add_event_log_message(
                        f"{trainee_name} advanced to {session['skill']} "
                        f"{result['level_after']} via {session['program_title']}."
                    )
                remaining_trainees.append(trainee_name)

            session["trainees"] = remaining_trainees
            session["progress"] += 1
            daily_updates.append(
                {
                    "program": session["program_title"],
                    "day": current_day,
                    "results": day_results,
                    "level_ups": level_ups,
                    "progress": session["progress"],
                    "duration": session["duration"],
                }
            )

            if not session["trainees"]:
                self.add_event_log_message(
                    f"{session['program_title']} paused—no trainees remaining."
                )
                summary = self._summarize_training_session(
                    session, current_day, reason="empty"
                )
                concluded_summaries.append(summary)
                sessions_to_remove.append(session)
                continue

            if session["progress"] >= session["duration"]:
                summary = self._summarize_training_session(
                    session, current_day, reason="completed"
                )
                concluded_summaries.append(summary)
                sessions_to_remove.append(session)

        for session in sessions_to_remove:
            if session in self.active_training_sessions:
                self.active_training_sessions.remove(session)

        return daily_updates, concluded_summaries

    def _summarize_training_session(
        self, session: Dict[str, Any], end_day: int, reason: str
    ) -> Dict[str, Any]:
        summary = {
            "program": session.get("program_title"),
            "program_key": session.get("program_key"),
            "skill": session.get("skill"),
            "instructor": session.get("instructor"),
            "trainees": list(session.get("original_trainees", [])),
            "start_day": session.get("start_day"),
            "end_day": end_day,
            "reason": reason,
            "outcomes": [],
        }
        for name in summary["trainees"]:
            baseline = session.get("trainee_baselines", {}).get(name, {})
            latest = session.get("latest_results", {}).get(name, baseline)
            summary["outcomes"].append(
                {
                    "name": name,
                    "level_before": baseline.get("level"),
                    "level_after": latest.get("level"),
                }
            )

        if reason == "completed":
            self.add_event_log_message(
                f"{summary['program']} concludes under {summary['instructor']}."
            )
        else:
            self.add_event_log_message(
                f"{summary['program']} closed without a full cohort."
            )

        self.training_history.append(summary)
        self.training_history = self.training_history[-25:]
        return summary

    def process_training_daily(
        self, economy_report: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.game_time:
            return {}

        current_day = self.game_time.current_day
        if not self.training_program_definitions:
            self.latest_training_report = {}
            self._last_training_update_day = current_day
            if economy_report is not None:
                economy_report["training"] = {}
            return {}

        if (
            self._last_training_update_day == current_day
            and self.latest_training_report
        ):
            if economy_report is not None:
                economy_report["training"] = self.latest_training_report
            return self.latest_training_report

        metrics = self._assess_training_needs()
        waitlists = self._refresh_training_waitlists(metrics)
        started_sessions = self._start_training_sessions(metrics, current_day)
        session_updates, concluded_sessions = self._advance_training_sessions(
            current_day
        )

        active_sessions = [
            {
                "program": session["program_title"],
                "program_key": session["program_key"],
                "skill": session["skill"],
                "instructor": session["instructor"],
                "trainees": list(session["trainees"]),
                "progress": session["progress"],
                "duration": session["duration"],
                "start_day": session["start_day"],
            }
            for session in self.active_training_sessions
        ]

        assessed_needs = [
            {
                "program": data["definition"].get("title", key),
                "program_key": key,
                "avg_level": round(data.get("avg_level", 0.0), 2),
                "under_target": len(data.get("under_target", [])),
                "total_characters": data.get("total_characters", 0),
            }
            for key, data in metrics.items()
        ]

        report = {
            "day": current_day,
            "assessed_needs": assessed_needs,
            "waitlists": [
                {
                    "program": entry.get("program"),
                    "skill": entry.get("skill"),
                    "queued": entry.get("queued", []),
                    "count": entry.get("count", 0),
                }
                for entry in waitlists
            ],
            "started_sessions": started_sessions,
            "active_sessions": active_sessions,
            "session_updates": session_updates,
            "concluded_sessions": concluded_sessions,
            "recent_history": deepcopy(self.training_history[-6:]),
        }

        self.latest_training_report = report
        self._last_training_update_day = current_day
        if economy_report is not None:
            economy_report["training"] = report
        return report

    def get_training_snapshot(self) -> Dict[str, Any]:
        return deepcopy(self.latest_training_report)

    def process_workforce_daily(
        self, economy_report: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.game_time:
            return {}

        current_day = self.game_time.current_day
        if not self.work_shift_definitions:
            self.latest_workforce_report = {}
            self._last_workforce_update_day = current_day
            if economy_report is not None:
                economy_report["workforce"] = {}
            return {}

        if (
            self._last_workforce_update_day == current_day
            and self.latest_workforce_report
        ):
            if economy_report is not None:
                economy_report["workforce"] = self.latest_workforce_report
            return self.latest_workforce_report

        crews_report: List[Dict[str, Any]] = []
        shipments: List[Dict[str, Any]] = []
        alerts: List[str] = []
        total_gathered = 0
        total_delivered = 0
        total_backlog = 0.0

        for key, definition in self.work_shift_definitions.items():
            workers = [
                char
                for char in self.characters
                if char.job in definition.get("jobs", [])
            ]
            haulers = [
                char
                for char in self.characters
                if char.job in definition.get("hauler_jobs", [])
            ]

            backlog_existing = self.work_shift_backlog.setdefault(key, 0.0)
            resource = definition.get("resource")
            task_name = definition.get("task")
            skill_name = definition.get("skill") or (
                JOB_TASK_DEFINITIONS.get(task_name, {}).get("skill_used")
                if task_name
                else None
            )
            shift_ticks = definition.get(
                "shift_ticks", getattr(config, "DEFAULT_WORK_SHIFT_TICKS", 6)
            )
            base_output = definition.get("base_output_per_worker")
            task_def = JOB_TASK_DEFINITIONS.get(task_name, {}) if task_name else {}
            if base_output is None and task_def:
                cycles = shift_ticks / max(1, task_def.get("base_time_per_yield", 1))
                base_output = cycles * task_def.get("base_yield", 1)
            if base_output is None:
                base_output = max(1.0, float(shift_ticks))

            worker_details: List[Dict[str, Any]] = []
            sector_output = 0.0
            directive_bonus = 1.0
            if resource and resource in self.resource_collection_directives:
                directive_bonus += 0.1
            resource_multiplier = (
                self.get_resource_yield_multiplier(resource)
                if resource
                else 1.0
            )

            for worker in workers:
                skill_level = (
                    worker.skills.get(skill_name, {}).get("level", 0)
                    if skill_name
                    else 0
                )
                efficiency_bonus = 1.0 + skill_level * definition.get(
                    "skill_yield_bonus", 0.1
                )
                morale_bonus = 1.0
                if worker.mood_score > config.MOOD_SCORE_NEUTRAL_START + 10:
                    morale_bonus += 0.05
                elif worker.mood_score < config.MOOD_SCORE_NEUTRAL_START - 10:
                    morale_bonus -= 0.05

                worker_output = (
                    base_output * efficiency_bonus * directive_bonus * morale_bonus
                )
                worker_output *= resource_multiplier
                sector_output += worker_output
                worker_details.append(
                    {
                        "name": worker.name,
                        "skill_level": skill_level,
                        "estimated_output": round(worker_output, 1),
                    }
                )

            gathered_units = int(sector_output)
            total_gathered += gathered_units
            pending_output = backlog_existing + sector_output

            carry_capacity = len(workers) * definition.get(
                "carry_capacity_per_worker", 6
            )
            haul_capacity = len(haulers) * definition.get("hauler_capacity", 12)
            total_capacity = carry_capacity + haul_capacity

            deliverable = min(pending_output, total_capacity) if total_capacity else 0.0
            deliver_units = int(deliverable)
            deposit_result: Optional[Dict[str, Any]] = None
            delivered_actual = 0

            if deliver_units > 0 and resource:
                deposit_result = self._deposit_work_output(
                    resource,
                    deliver_units,
                    preferred_stockpiles=definition.get("preferred_stockpiles"),
                )
                delivered_actual = deposit_result.get("delivered", 0)
                if delivered_actual < deliver_units:
                    alerts.append(
                        f"{definition.get('title', key.title())} lacked storage for {deliver_units - delivered_actual} {resource}."
                    )
            backlog_after_delivery = max(0.0, pending_output - delivered_actual)
            self.work_shift_backlog[key] = backlog_after_delivery

            crew_entry = {
                "key": key,
                "title": definition.get("title", key.title()),
                "resource": resource,
                "workers": [detail["name"] for detail in worker_details],
                "haulers": [hauler.name for hauler in haulers],
                "gathered": gathered_units,
                "delivered": delivered_actual,
                "backlog": round(backlog_after_delivery, 1),
                "capacity": total_capacity,
                "pending": round(pending_output, 1),
                "workers_detail": worker_details,
            }

            if not workers and backlog_existing <= 0:
                crew_entry.setdefault("notes", []).append("No crew reported for duty.")
            elif not workers and backlog_existing > 0:
                crew_entry.setdefault("notes", []).append(
                    "Haulers awaiting gathered stock from previous days."
                )

            if deposit_result and deposit_result.get("routes"):
                crew_entry.setdefault("notes", []).append(
                    ", ".join(
                        f"{route['quantity']} to {route['stockpile']}"
                        for route in deposit_result["routes"]
                    )
                )
                shipments.append(
                    {
                        "sector": key,
                        "resource": resource,
                        "delivered": deposit_result["delivered"],
                        "routes": deposit_result["routes"],
                    }
                )

            if backlog_after_delivery and resource:
                crew_entry.setdefault("notes", []).append(
                    f"{backlog_after_delivery:.1f} {resource} waiting on carts."
                )

            if not workers and not haulers and backlog_after_delivery <= 0:
                crew_entry.setdefault("status", "idle")

            crews_report.append(crew_entry)
            total_backlog += backlog_after_delivery
            total_delivered += delivered_actual

        report = {
            "day": current_day,
            "crews": crews_report,
            "shipments": shipments,
            "alerts": alerts,
            "gathered_total": total_gathered,
            "delivered_total": total_delivered,
            "backlog_total": round(total_backlog, 1),
            "recent_shipments": deepcopy(self.work_logistics_history[-8:]),
        }

        self.latest_workforce_report = report
        self._last_workforce_update_day = current_day
        if economy_report is not None:
            economy_report["workforce"] = report

        if crews_report:
            summary = (
                f"Work crews gathered {total_gathered} units and delivered {total_delivered}."
            )
            if total_backlog:
                summary += f" Backlog stands at {total_backlog:.1f} units."
            self.add_event_log_message(summary)
        if alerts:
            for alert in alerts[:3]:
                self.add_event_log_message(f"Work alert: {alert}")

        return report

    def get_workforce_snapshot(self) -> Dict[str, Any]:
        return deepcopy(self.latest_workforce_report)

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
        housing_snapshot = self._evaluate_housing_daily(report)
        self._resolve_theft_attempts(report)
        self.process_workforce_daily(report)
        report["pending_crimes"] = len(self.pending_crimes)
        report["surplus_trades"] = list(self.today_surplus_sales)
        self.evaluate_population_dynamics(report, housing_snapshot)
        training_report = self.process_training_daily(report)

        summary = (
            f"Economic summary — Treasury {self.treasury_coins}c "
            f"(tax +{report['tax_collected']}c, wages paid {report['wages_paid']}c, arrears settled {report['arrears_paid']}c)."
            f" Outstanding arrears {report['arrears']}c, food deficit {report['food_deficit']} rations,"
            f" water deficit {report['water_deficit']} casks."
        )
        self.add_event_log_message(summary)
        if housing_snapshot:
            homeless_count = len(housing_snapshot.get("homeless_characters", []))
            available_beds = housing_snapshot.get("available_beds")
            if homeless_count:
                self.add_event_log_message(
                    f"Housing report: {homeless_count} citizen{'s' if homeless_count != 1 else ''} slept outdoors."
                )
            elif isinstance(available_beds, int):
                self.add_event_log_message(
                    f"Housing report: {available_beds} bed{'s' if available_beds != 1 else ''} currently open."
                )
        if training_report:
            active_count = len(training_report.get("active_sessions", []))
            queued_total = sum(
                len(entry.get("queued", []))
                for entry in training_report.get("waitlists", [])
            )
            if active_count or queued_total:
                self.add_event_log_message(
                    f"Training grounds: {active_count} session{'s' if active_count != 1 else ''} active, "
                    f"{queued_total} queued for instruction."
                )
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

    # --- Cultural Life & Festivals ---

    def _ensure_cultural_calendar(self) -> None:
        if not self.game_time:
            return

        days_per_season = getattr(config, "DAYS_PER_SEASON", 10)
        year_length = days_per_season * len(self.SEASONS)
        current_year = (self.game_time.current_day - 1) // year_length

        for year in range(current_year, current_year + 2):
            if year in self._generated_cultural_years:
                continue
            events = self._generate_cultural_calendar_for_year(year)
            if events:
                self.cultural_calendar.extend(events)
                self._generated_cultural_years.add(year)

        if self.cultural_calendar:
            self.cultural_calendar.sort(key=lambda entry: entry["day"])

    def _generate_cultural_calendar_for_year(self, year_index: int) -> List[Dict[str, Any]]:
        days_per_season = getattr(config, "DAYS_PER_SEASON", 10)
        year_length = days_per_season * len(self.SEASONS)
        start_day = year_index * year_length

        events: List[Dict[str, Any]] = []
        library = getattr(config, "CULTURAL_EVENT_LIBRARY", {})
        for season_idx, season in enumerate(self.SEASONS):
            definitions = library.get(season, [])
            if not definitions:
                continue
            base_day = start_day + season_idx * days_per_season
            for definition in definitions:
                anchor = int(definition.get("anchor_day", 1))
                anchor = max(1, min(days_per_season, anchor))
                scheduled_day = base_day + anchor
                event = {
                    "year": year_index,
                    "season": season,
                    "day": scheduled_day,
                    "key": definition.get("key", f"{season.lower()}_{anchor}"),
                    "name": definition.get("name", f"{season} Gathering"),
                    "description": definition.get("description"),
                    "duration": max(1, int(definition.get("duration", 1))),
                    "belonging_bonus": int(definition.get("belonging_bonus", 0)),
                    "esteem_bonus": int(definition.get("esteem_bonus", 0)),
                    "social_bonus": int(definition.get("social_bonus", 0)),
                    "mood_bonus": int(definition.get("mood_bonus", 0)),
                    "community_spirit_delta": float(definition.get("community_spirit_delta", 0.0)),
                    "travel_speed_multiplier": definition.get("travel_speed_multiplier"),
                    "market_price_adjustment": deepcopy(definition.get("market_price_adjustment"))
                    if definition.get("market_price_adjustment")
                    else None,
                    "resource_yield_bonus": deepcopy(definition.get("resource_yield_bonus"))
                    if definition.get("resource_yield_bonus")
                    else None,
                    "flavor": list(definition.get("flavor", [])),
                    "has_triggered": False,
                }
                events.append(event)

        events.sort(key=lambda entry: entry["day"])
        return events

    def _daily_cultural_tick(self) -> None:
        if not self.game_time:
            return

        current_day = self.game_time.current_day
        if self._last_cultural_update_day == current_day:
            return

        self._ensure_cultural_calendar()

        if (
            self._active_cultural_event_data
            and self._active_cultural_event_end_day is not None
            and current_day > self._active_cultural_event_end_day
        ):
            self._conclude_cultural_event()

        decay = getattr(config, "CULTURAL_SPIRIT_DECAY", 0.0)
        if decay > 0:
            self.community_spirit = max(0.0, self.community_spirit - decay)

        if (
            self._active_cultural_event_data
            and self._active_cultural_event_end_day is not None
            and current_day <= self._active_cultural_event_end_day
        ):
            self._broadcast_cultural_flavor()

        for event in self.cultural_calendar:
            if event.get("has_triggered"):
                continue
            if event["day"] == current_day:
                self._begin_cultural_event(event)

        self._last_cultural_update_day = current_day

    def _begin_cultural_event(self, event: Dict[str, Any]) -> None:
        if not self.game_time:
            return

        if self._active_cultural_event_data and self._active_cultural_event_end_day is not None:
            if self.game_time.current_day <= self._active_cultural_event_end_day:
                self._conclude_cultural_event()

        event["has_triggered"] = True
        duration = max(1, int(event.get("duration", 1)))
        current_day = self.game_time.current_day
        end_day = current_day + duration - 1
        self._active_cultural_event_end_day = end_day

        self._active_cultural_event_data = deepcopy(event)
        if self._active_cultural_event_data is not None:
            self._active_cultural_event_data["last_flavor_day"] = None

        sanitized: Dict[str, Any] = {
            "key": event.get("key"),
            "name": event.get("name"),
            "season": event.get("season"),
            "description": event.get("description"),
            "start_day": current_day,
            "end_day": end_day,
            "duration": duration,
        }
        bonuses: Dict[str, int] = {}
        for template_key, label in [
            ("belonging_bonus", "belonging"),
            ("esteem_bonus", "esteem"),
            ("social_bonus", "social"),
            ("mood_bonus", "mood"),
        ]:
            value = int(event.get(template_key, 0))
            if value:
                bonuses[label] = value
        if bonuses:
            sanitized["bonuses"] = bonuses
        spirit_delta = max(0.0, float(event.get("community_spirit_delta", 0.0)))
        sanitized["community_spirit_delta"] = spirit_delta
        if spirit_delta:
            self.community_spirit = min(1.0, self.community_spirit + spirit_delta)
        self.active_cultural_event = sanitized

        effect_data: Dict[str, Any] = {"expires_day": end_day}
        has_effect = False
        travel_multiplier = event.get("travel_speed_multiplier")
        if travel_multiplier:
            effect_data["travel_speed_multiplier"] = float(travel_multiplier)
            has_effect = True
        market_adjustment = event.get("market_price_adjustment")
        if market_adjustment:
            effect_data["market_price_adjustment"] = deepcopy(market_adjustment)
            has_effect = True
        resource_bonus = event.get("resource_yield_bonus")
        if resource_bonus:
            effect_data["resource_yield_bonus"] = deepcopy(resource_bonus)
            has_effect = True
        if has_effect:
            effect_key = f"cultural_event_{event.get('key')}_{current_day}"
            event["effect_key"] = effect_key
            self.add_temporary_world_effect(effect_key, effect_data)
        else:
            event["effect_key"] = None

        for character in list(self.characters):
            if hasattr(character, "receive_cultural_event_boost"):
                character.receive_cultural_event_boost(event, self)

        description = event.get("description") or "Villagers gather for a communal celebration."
        self.add_event_log_message(f"Cultural event '{event.get('name')}' begins. {description}")
        self.add_notable_event(
            "CulturalEvent",
            {
                "summary": f"{event.get('name')} underway.",
                "name": event.get("name"),
                "season": event.get("season"),
            },
        )

        history_entry = {
            "day": current_day,
            "name": event.get("name"),
            "season": event.get("season"),
            "spirit": round(self.community_spirit, 3),
            "participants": len(self.characters),
        }
        self.cultural_history.append(history_entry)
        if len(self.cultural_history) > 25:
            self.cultural_history.pop(0)

        self._broadcast_cultural_flavor()

    def _conclude_cultural_event(self) -> None:
        if not self._active_cultural_event_data:
            self.active_cultural_event = None
            self._active_cultural_event_end_day = None
            return

        event = self._active_cultural_event_data
        message = f"{event.get('name')} winds down as the town settles back into routine."
        self.add_event_log_message(message)
        self.add_notable_event(
            "CulturalEventEnd",
            {
                "summary": message,
                "name": event.get("name"),
                "season": event.get("season"),
            },
        )
        self._active_cultural_event_data = None
        self.active_cultural_event = None
        self._active_cultural_event_end_day = None

    def _broadcast_cultural_flavor(self) -> None:
        if not self._active_cultural_event_data or not self.game_time:
            return
        last_flavor_day = self._active_cultural_event_data.get("last_flavor_day")
        if last_flavor_day == self.game_time.current_day:
            return
        flavor_lines = self._active_cultural_event_data.get("flavor") or []
        if not flavor_lines:
            return
        snippet = random.choice(flavor_lines)
        self.add_event_log_message(f"Festival mood: {snippet}")
        self._active_cultural_event_data["last_flavor_day"] = self.game_time.current_day

    def _get_upcoming_cultural_events(self, limit: int = 3) -> List[Dict[str, Any]]:
        if not self.game_time:
            return []
        current_day = self.game_time.current_day
        upcoming: List[Dict[str, Any]] = []
        for event in self.cultural_calendar:
            if event.get("has_triggered"):
                continue
            if event["day"] < current_day:
                continue
            upcoming.append(
                {
                    "key": event.get("key"),
                    "name": event.get("name"),
                    "season": event.get("season"),
                    "day": event.get("day"),
                    "description": event.get("description"),
                }
            )
            if len(upcoming) >= limit:
                break
        return upcoming

    def get_cultural_snapshot(self) -> Dict[str, Any]:
        snapshot = {
            "community_spirit": round(self.community_spirit, 3),
            "active_event": deepcopy(self.active_cultural_event) if self.active_cultural_event else None,
            "upcoming_events": self._get_upcoming_cultural_events(limit=4),
            "recent_history": deepcopy(self.cultural_history[-5:]),
        }
        return snapshot

    def daily_environment_tick(self):
        if not self.game_time:
            return

        self.update_day_phase()
        self._update_weather_event_state()

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

        self._maybe_trigger_weather_event()
        self._cleanup_world_effects()
        self._daily_cultural_tick()
        self.expire_resource_directives()
        self._recalculate_environment_effects()
        self._advance_resource_regrowth()
