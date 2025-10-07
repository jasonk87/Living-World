# game/world.py
from __future__ import annotations

import random
from collections import Counter, defaultdict
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
        self._characters_by_name: Dict[str, 'Character'] = {}
        self._characters_by_tile: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        self.stockpiles: List[Stockpile] = []
        self.stockpile_tiles: Dict[Tuple[int, int], str] = {}
        self.buildings: List[Building] = [] # Re-added
        # self.furniture: List[Furniture] = [] # Re-added, but keep commented if not used by this test
        self.ledger: Ledger = Ledger()
        self.game_time: Optional[Time] = game_time_ref
        self.work_orders: List[WorkOrder] = []
        self.event_log: List[str] = []
        self.businesses: Dict[str, Dict[str, Any]] = {}
        self._business_counter: int = 0
        self.latest_wealth_snapshot: Dict[str, Any] = {}
        self._last_wealth_tension_day: Optional[int] = None
        self.active_world_effects: Dict[str, Any] = {}
        self.recent_notable_events: List[Dict[str, Any]] = [] # For rumor spreading
        self.rumors: List[Rumor] = [] # Added for rumor system
        self.base_market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_location: Tuple[int, int] = (5, 5) # Central market location
        self.resource_yield_multipliers: Dict[str, float] = {
            "Wood": 1.0,
            "Stone": 1.0,
            "Iron Ore": 1.0,
            "Lumber": 1.0,
            "Furniture": 1.0,
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
        self.law_petitions: List[Dict[str, Any]] = []
        self.active_laws: Dict[str, Dict[str, Any]] = {}
        self.law_history: List[Dict[str, Any]] = []
        self.pending_interviews: List[Dict[str, Any]] = []
        self.interview_history: Dict[str, List[Dict[str, Any]]] = {}
        self._law_counter: int = 0
        self._law_petition_counter: int = 0
        self._interview_counter: int = 0
        self.family_profiles: Dict[str, Dict[str, Any]] = {}
        self._family_lookup: Dict[str, str] = {}
        self.family_history: List[Dict[str, Any]] = []
        self._character_lineage: Dict[str, Dict[str, Set[str]]] = {}

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

        occupants = self._characters_by_tile.get((x, y))
        if occupants:
            for occupant in occupants:
                if occupant in ignore_set:
                    continue
                if goal_override:
                    continue
                return False

        return True

    def reserve_tile(self, character_name: str, coords: Tuple[int, int]) -> bool:
        current_holder = self._tile_reservations.get(coords)
        if current_holder and current_holder != character_name:
            return False

        occupants = self._characters_by_tile.get(coords)
        if occupants:
            for occupant in occupants:
                if occupant != character_name:
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

    def update_character_position(
        self,
        character: 'Character',
        old_coords: Optional[Tuple[int, int]],
        new_coords: Optional[Tuple[int, int]],
    ) -> None:
        """Refresh spatial indexes when a citizen moves."""

        if old_coords:
            occupants = self._characters_by_tile.get(old_coords)
            if occupants and character.name in occupants:
                occupants.discard(character.name)
                if not occupants:
                    del self._characters_by_tile[old_coords]

        if new_coords:
            self._characters_by_tile[new_coords].add(character.name)
            self._characters_by_name[character.name] = character
        else:
            # Character removed from the world entirely.
            self._characters_by_name.pop(character.name, None)

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

    def _spawn_new_citizen(
        self,
        profile: Dict[str, Any],
        *,
        arrival_reason: str,
        suppress_arrival_event: bool = False,
    ) -> Optional['Character']:
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
        if suppress_arrival_event and hasattr(character, "_life_event_flags"):
            character._life_event_flags.add("arrival")
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
        self.update_character_position(character, None, (character.x, character.y))
        self.clear_reservations_for_character(character.name)
        if hasattr(character, "arrival_day") and character.arrival_day is None and self.game_time:
            character.arrival_day = self.game_time.current_day
        lineage_entry = self._ensure_lineage_entry(character.name)
        for kin_name in character.family_members:
            if not kin_name or kin_name == character.name:
                continue
            lineage_entry.setdefault("kin", set()).add(kin_name)
            other_entry = self._ensure_lineage_entry(kin_name)
            other_entry.setdefault("kin", set()).add(character.name)
        self._register_character_demographics(character)
        self._update_population_stats(delta=1)
        self._rebuild_family_profiles()
        if hasattr(character, "life_history"):
            self._seed_family_history_for_character(character)
        if hasattr(character, "record_life_event") and "arrival" not in getattr(character, "_life_event_flags", set()):
            role_text = character.job or "traveller"
            origin_text = character.origin or "unknown lands"
            summary = f"Arrived in the settlement as a {role_text}, hailing from {origin_text}."
            character.record_life_event(
                self,
                "arrival",
                summary,
                related=[origin_text],
                tags=["arrival", "milestone"],
                significance=3,
                propagate_to_family=True,
                details={"origin": origin_text, "job": character.job},
            )
            character._life_event_flags.add("arrival")

    def remove_character(self, character: 'Character'):
        if character not in self.characters:
            return
        if hasattr(character, "business_roles"):
            for business_id, role in list(character.business_roles.items()):
                self._handle_character_departure_from_business(business_id, character.name, role == "owner")
        self.characters.remove(character)
        self.update_character_position(character, (character.x, character.y), None)
        self.clear_reservations_for_character(character.name)
        if character.name in self._resident_registry:
            del self._resident_registry[character.name]
        self._purge_lineage_links(character.name)
        self._update_population_stats(delta=-1)
        self._rebuild_family_profiles()

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

    def _ensure_lineage_entry(self, name: str) -> Dict[str, Set[str]]:
        entry = self._character_lineage.get(name)
        if entry is None:
            entry = {
                "parents": set(),
                "children": set(),
                "siblings": set(),
                "partners": set(),
                "kin": set(),
            }
            self._character_lineage[name] = entry
        else:
            for key in ("parents", "children", "siblings", "partners", "kin"):
                entry.setdefault(key, set())
        return entry

    def _purge_lineage_links(self, name: str) -> None:
        if name in self._character_lineage:
            self._character_lineage.pop(name, None)
        for entry in self._character_lineage.values():
            for relatives in entry.values():
                if isinstance(relatives, set):
                    relatives.discard(name)

    @staticmethod
    def _canonical_family_role(role: str) -> str:
        mapping = {
            "parent": "parents",
            "parents": "parents",
            "mother": "parents",
            "father": "parents",
            "child": "children",
            "children": "children",
            "son": "children",
            "daughter": "children",
            "sibling": "siblings",
            "brother": "siblings",
            "sister": "siblings",
            "partner": "partners",
            "partners": "partners",
            "spouse": "partners",
            "husband": "partners",
            "wife": "partners",
            "kin": "kin",
        }
        lowered = role.lower()
        return mapping.get(lowered, lowered)

    def _export_lineage_for_members(self, members: Iterable[str]) -> Dict[str, Dict[str, List[str]]]:
        snapshot: Dict[str, Dict[str, List[str]]] = {}
        for name in members:
            if not name:
                continue
            entry = self._ensure_lineage_entry(name)
            member_snapshot: Dict[str, List[str]] = {}
            for role, relatives in entry.items():
                if not isinstance(relatives, set) or not relatives:
                    continue
                member_snapshot[role] = sorted(relatives)
            if member_snapshot:
                snapshot[name] = member_snapshot
        return snapshot

    def _refresh_family_lineage_for_family(self, family_id: str) -> None:
        profile = self.family_profiles.get(family_id)
        if not profile:
            return
        members = profile.get("members", [])
        profile["lineage"] = self._export_lineage_for_members(members)

    def register_family_link(
        self,
        subject_name: str,
        relative_name: str,
        relation_type: str,
        *,
        refresh_profiles: bool = True,
    ) -> bool:
        if not subject_name or not relative_name or not relation_type:
            return False

        subject = self.get_character_by_name(subject_name)
        relative = self.get_character_by_name(relative_name)
        if not subject or not relative:
            return False

        canonical_role = self._canonical_family_role(relation_type)
        mirror_map = {
            "parents": "children",
            "children": "parents",
            "siblings": "siblings",
            "partners": "partners",
            "kin": "kin",
        }
        mirror_role = mirror_map.get(canonical_role, canonical_role)

        if relative_name not in subject.family_members:
            subject.family_members.append(relative_name)
        if subject.name not in relative.family_members:
            relative.family_members.append(subject.name)

        subject.register_family_role(canonical_role, relative.name)
        relative.register_family_role(mirror_role, subject.name)

        subject_entry = self._ensure_lineage_entry(subject.name)
        relative_entry = self._ensure_lineage_entry(relative.name)

        if canonical_role == "parents":
            subject_entry["parents"].add(relative.name)
            relative_entry["children"].add(subject.name)
        elif canonical_role == "children":
            subject_entry["children"].add(relative.name)
            relative_entry["parents"].add(subject.name)
        elif canonical_role == "siblings":
            subject_entry["siblings"].add(relative.name)
            relative_entry["siblings"].add(subject.name)
        elif canonical_role == "partners":
            subject_entry["partners"].add(relative.name)
            relative_entry["partners"].add(subject.name)
        else:
            subject_entry.setdefault(canonical_role, set()).add(relative.name)
            relative_entry.setdefault(mirror_role, set()).add(subject.name)

        if refresh_profiles:
            self._rebuild_family_profiles()
        else:
            family_ids = {
                self._family_lookup.get(subject.name),
                self._family_lookup.get(relative.name),
            }
            for fam_id in family_ids:
                if fam_id:
                    self._refresh_family_lineage_for_family(fam_id)
        return True

    def _summarize_lineage(self, members: Iterable[str]) -> List[str]:
        lineage = self._export_lineage_for_members(members)
        preview: List[str] = []
        ordered_names = sorted(lineage.keys())
        for name in ordered_names:
            entry = lineage[name]
            fragments: List[str] = []
            for key in ("partners", "children", "parents", "siblings"):
                related = entry.get(key)
                if related:
                    label = key[:-1] if key.endswith("s") else key
                    fragments.append(f"{label.capitalize()}: {', '.join(related)}")
            if not fragments:
                continue
            preview.append(f"{name}: {'; '.join(fragments)}")
            if len(preview) >= 4:
                break
        return preview

    def record_birth(
        self,
        parent_name: str,
        *,
        other_parent: Optional[str] = None,
        child_profile: Optional[Dict[str, Any]] = None,
        announcement: Optional[str] = None,
    ) -> Optional['Character']:
        parent = self.get_character_by_name(parent_name)
        if not parent:
            return None

        if child_profile is None:
            child_profile = self._generate_citizen_profile(
                job="Child",
                age=0,
                needs=dict(config.DEFAULT_CHILD_NEEDS),
                traits=["Innocent"],
                personality="Curious",
                origin=f"Born to {parent.name}",
            )
        else:
            child_profile = deepcopy(child_profile)

        child_profile["job"] = child_profile.get("job", "Child")
        child_profile["age"] = 0
        child_profile.setdefault("needs", dict(config.DEFAULT_CHILD_NEEDS))
        child_profile["x"], child_profile["y"] = parent.x, parent.y

        announcement_text = announcement or f"A new child, {child_profile['name']}, is born into {parent.name}'s household."
        child = self._spawn_new_citizen(
            child_profile,
            arrival_reason=announcement_text,
            suppress_arrival_event=True,
        )
        if not child:
            return None

        other_parent_char = self.get_character_by_name(other_parent) if other_parent else None

        detail_parents = [parent.name]
        if other_parent_char:
            detail_parents.append(other_parent_char.name)

        if hasattr(child, "record_life_event"):
            child.record_life_event(
                self,
                "birth",
                f"Born to {' and '.join(detail_parents)}.",
                related=detail_parents,
                tags=["family", "birth", "milestone"],
                significance=4,
                propagate_to_family=False,
                details={"parents": detail_parents},
                dedupe_key=f"birth:{child.name}",
            )

        summary_parent = f"Welcomed a child named {child.name}."
        if other_parent_char:
            summary_parent = f"Welcomed {child.name} with {other_parent_char.name}."

        if hasattr(parent, "record_life_event"):
            parent.record_life_event(
                self,
                "welcomed_child",
                summary_parent,
                related=[child.name] + ([other_parent_char.name] if other_parent_char else []),
                tags=["family", "birth"],
                significance=4,
                propagate_to_family=True,
                details={"child": child.name, "co_parent": other_parent_char.name if other_parent_char else None},
                dedupe_key=f"welcomed_child:{child.name}:{parent.name}",
            )

        if other_parent_char and hasattr(other_parent_char, "record_life_event"):
            other_parent_char.record_life_event(
                self,
                "welcomed_child",
                f"Welcomed {child.name} with {parent.name}.",
                related=[child.name, parent.name],
                tags=["family", "birth"],
                significance=4,
                propagate_to_family=True,
                details={"child": child.name, "co_parent": parent.name},
                dedupe_key=f"welcomed_child:{child.name}:{other_parent_char.name}",
            )

        self.register_family_link(parent.name, child.name, "child", refresh_profiles=False)
        if other_parent_char:
            self.register_family_link(other_parent_char.name, child.name, "child", refresh_profiles=False)
            self.register_family_link(parent.name, other_parent_char.name, "partner", refresh_profiles=False)

        self._rebuild_family_profiles()

        return child

    def _record_bereavement_events(
        self,
        patient: Optional['Character'],
        outcome: str,
        witnesses: Optional[Iterable[str]] = None,
    ) -> None:
        if not patient or outcome not in {"deceased", "fatal"}:
            return

        cause_label = outcome.replace("_", " ")
        unique_witnesses: List[str] = []
        if witnesses:
            for name in witnesses:
                if not name or name == "System":
                    continue
                if name not in unique_witnesses:
                    unique_witnesses.append(name)

        for witness_name in unique_witnesses:
            witness = self.get_character_by_name(witness_name)
            if not witness or witness.name == patient.name:
                continue
            if hasattr(witness, "record_life_event"):
                witness.record_life_event(
                    self,
                    "witnessed_tragedy",
                    f"Witnessed {patient.name} {cause_label}.",
                    related=[patient.name],
                    tags=["loss", "witness", "grief"],
                    significance=3,
                    propagate_to_family=True,
                    details={"subject": patient.name, "outcome": outcome},
                    dedupe_key=f"witnessed_loss:{patient.name}:{outcome}:{witness.name}",
                )

        family_id = self._family_lookup.get(patient.name)
        grief_event = {
            "type": "loss",
            "summary": f"{patient.name} {cause_label}.",
            "focus": patient.name,
            "source": patient.name,
            "details": {"outcome": outcome},
        }
        if family_id:
            self.record_family_event(family_id, grief_event)

        for kin_name in getattr(patient, "family_members", []) or []:
            if kin_name == patient.name:
                continue
            kin = self.get_character_by_name(kin_name)
            if not kin or not hasattr(kin, "record_life_event"):
                continue
            kin.record_life_event(
                self,
                "family_loss",
                f"Mourned the loss of {patient.name}.",
                related=[patient.name],
                tags=["family", "loss", "bereavement"],
                significance=4,
                propagate_to_family=False,
                details={"relative": patient.name, "outcome": outcome},
                dedupe_key=f"family_loss:{patient.name}:{kin.name}",
            )

    def register_union(
        self,
        partner_one: str,
        partner_two: str,
        *,
        ceremony_name: Optional[str] = None,
        witnesses: Optional[Iterable[str]] = None,
    ) -> bool:
        partner_a = self.get_character_by_name(partner_one)
        partner_b = self.get_character_by_name(partner_two)
        if not partner_a or not partner_b:
            return False

        self.register_family_link(partner_a.name, partner_b.name, "partner", refresh_profiles=False)
        self._rebuild_family_profiles()

        ceremony_label = ceremony_name or "a union ceremony"
        if hasattr(partner_a, "record_life_event"):
            partner_a.record_life_event(
                self,
                "marriage",
                f"Joined with {partner_b.name} during {ceremony_label}.",
                related=[partner_b.name],
                tags=["family", "marriage", "milestone"],
                significance=4,
                propagate_to_family=True,
                details={"partner": partner_b.name, "ceremony": ceremony_label},
                dedupe_key=f"marriage:{partner_a.name}:{partner_b.name}",
            )

        if hasattr(partner_b, "record_life_event"):
            partner_b.record_life_event(
                self,
                "marriage",
                f"Joined with {partner_a.name} during {ceremony_label}.",
                related=[partner_a.name],
                tags=["family", "marriage", "milestone"],
                significance=4,
                propagate_to_family=True,
                details={"partner": partner_a.name, "ceremony": ceremony_label},
                dedupe_key=f"marriage:{partner_b.name}:{partner_a.name}",
            )

        if witnesses:
            for name in witnesses:
                witness = self.get_character_by_name(name)
                if not witness or not hasattr(witness, "record_life_event"):
                    continue
                witness.record_life_event(
                    self,
                    "witnessed_union",
                    f"Witnessed the union of {partner_a.name} and {partner_b.name} during {ceremony_label}.",
                    related=[partner_a.name, partner_b.name],
                    tags=["family", "celebration"],
                    significance=2,
                    propagate_to_family=False,
                    details={"partners": [partner_a.name, partner_b.name], "ceremony": ceremony_label},
                    dedupe_key=f"witnessed_union:{partner_a.name}:{partner_b.name}:{witness.name}",
                )

        return True

    def _rebuild_family_profiles(self) -> None:
        if not self.characters:
            self.family_profiles = {}
            self._family_lookup = {}
            return

        adjacency: Dict[str, Set[str]] = {}
        for char in self.characters:
            related = set(char.family_members or [])
            related.add(char.name)
            adjacency[char.name] = related
            for relative in related:
                adjacency.setdefault(relative, set()).add(char.name)

        visited: Set[str] = set()
        components: List[Set[str]] = []
        for name in adjacency:
            if name in visited:
                continue
            stack = [name]
            component: Set[str] = set()
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        stack.append(neighbor)
            if component:
                components.append(component)

        for char in self.characters:
            if char.name not in adjacency:
                components.append({char.name})

        old_profiles = self.family_profiles
        old_lookup = self._family_lookup
        new_profiles: Dict[str, Dict[str, Any]] = {}
        new_lookup: Dict[str, str] = {}

        for component in components:
            members = sorted(component)
            family_id = "|".join(members)
            matched_profile: Optional[Dict[str, Any]] = None
            for member in members:
                previous_id = old_lookup.get(member)
                if not previous_id:
                    continue
                previous_profile = old_profiles.get(previous_id)
                if previous_profile and set(previous_profile.get("members", [])) == component:
                    matched_profile = deepcopy(previous_profile)
                    break

            if matched_profile is None:
                matched_profile = {
                    "family_id": family_id,
                    "members": members,
                    "events": [],
                    "tagline": "",
                    "last_updated_day": self.game_time.current_day if self.game_time else 0,
                }

            matched_profile["family_id"] = family_id
            matched_profile["members"] = members
            matched_profile["tagline"] = self._generate_family_tagline(component)
            matched_profile["lineage"] = self._export_lineage_for_members(members)
            new_profiles[family_id] = matched_profile
            for member in members:
                new_lookup[member] = family_id

        self.family_profiles = new_profiles
        self._family_lookup = new_lookup
        for family_id in self.family_profiles:
            self._refresh_family_lineage_for_family(family_id)

    def _generate_family_tagline(self, member_names: Iterable[str]) -> str:
        members = list(member_names)
        if not members:
            return "Household"

        jobs: List[str] = []
        ages: List[int] = []
        for name in members:
            char = self.get_character_by_name(name)
            if not char:
                continue
            if getattr(char, "job", None):
                jobs.append(char.job)
            age_val = getattr(char, "age_years", None)
            if isinstance(age_val, (int, float)):
                ages.append(int(age_val))

        if ages:
            average_age = sum(ages) / len(ages)
            if average_age < 20:
                age_band = "Young"
            elif average_age < 45:
                age_band = "Working"
            else:
                age_band = "Seasoned"
        else:
            age_band = "Rooted"

        if jobs:
            job_counts = Counter(jobs)
            top_job, top_count = job_counts.most_common(1)[0]
            job_phrase = f"{top_job} household" if top_count == len(members) else f"{top_job}-led household"
        else:
            job_phrase = "Generalist household"

        return f"{age_band} {job_phrase}"

    def record_family_event(self, family_id: str, event: Dict[str, Any]) -> None:
        if not family_id:
            return

        profile = self.family_profiles.get(family_id)
        if not profile:
            self._rebuild_family_profiles()
            profile = self.family_profiles.get(family_id)
            if not profile:
                return

        event_copy = deepcopy(event)
        if "day" not in event_copy or event_copy.get("day") is None:
            event_copy["day"] = self.game_time.current_day if self.game_time else 0
        event_copy.setdefault("source", event_copy.get("source") or event_copy.get("focus"))

        profile.setdefault("events", []).append(event_copy)
        max_events = getattr(config, "FAMILY_HISTORY_MAX_EVENTS", 80)
        profile["events"] = profile["events"][-max_events:]
        profile["last_updated_day"] = event_copy["day"]

        self.family_history.append(
            {
                "family_id": family_id,
                "summary": event_copy.get("summary"),
                "day": event_copy.get("day"),
                "type": event_copy.get("type"),
                "source": event_copy.get("source"),
            }
        )
        self.family_history = self.family_history[-max_events:]

    def share_family_event(self, source_char: 'Character', event: Dict[str, Any]) -> None:
        if not source_char:
            return

        family_id = self._family_lookup.get(source_char.name)
        if not family_id:
            self._rebuild_family_profiles()
            family_id = self._family_lookup.get(source_char.name)
        if not family_id:
            return

        event_payload = deepcopy(event)
        event_payload["source"] = source_char.name
        self.record_family_event(family_id, event_payload)

        profile = self.family_profiles.get(family_id)
        if not profile:
            return

        for member_name in profile.get("members", []):
            if member_name == source_char.name:
                continue
            relative = self.get_character_by_name(member_name)
            if relative and hasattr(relative, "receive_family_event"):
                relative.receive_family_event(self, source_char.name, event_payload)

    def _seed_family_history_for_character(self, character: 'Character') -> None:
        profile = self.get_family_profile_for_character(character.name)
        if not profile:
            return

        existing_signatures = {
            (evt.get("day"), evt.get("summary"), evt.get("source"))
            for evt in character.life_history
            if evt.get("is_family_echo")
        }

        for event in profile.get("latest_events", []):
            source = event.get("source")
            if not source or source == character.name:
                continue
            signature = (event.get("day"), event.get("summary"), source)
            if signature in existing_signatures:
                continue
            character.receive_family_event(self, source, event)

    def get_family_profile_for_character(self, char_name: str) -> Optional[Dict[str, Any]]:
        if not char_name:
            return None

        family_id = self._family_lookup.get(char_name)
        if not family_id:
            self._rebuild_family_profiles()
            family_id = self._family_lookup.get(char_name)
            if not family_id:
                return None

        profile = self.family_profiles.get(family_id)
        if not profile:
            return None

        character = self.get_character_by_name(char_name)
        role_snapshot: Dict[str, List[str]] = {}
        if character and hasattr(character, "get_family_roles_snapshot"):
            role_snapshot = character.get_family_roles_snapshot()

        return {
            "family_id": family_id,
            "tagline": profile.get("tagline"),
            "members": list(profile.get("members", [])),
            "latest_events": [deepcopy(evt) for evt in profile.get("events", [])[-5:]],
            "lineage": deepcopy(profile.get("lineage", {})),
            "role_snapshot": role_snapshot,
        }

    def get_family_snapshot(self) -> Dict[str, Any]:
        families: List[Dict[str, Any]] = []
        for profile in self.family_profiles.values():
            families.append(
                {
                    "family_id": profile.get("family_id"),
                    "tagline": profile.get("tagline"),
                    "members": list(profile.get("members", [])),
                    "latest_events": [deepcopy(evt) for evt in profile.get("events", [])[-3:]],
                    "lineage_preview": self._summarize_lineage(profile.get("members", [])),
                }
            )

        families.sort(key=lambda fam: (-len(fam.get("members", [])), fam.get("family_id", "")))

        return {
            "families": families[:8],
            "recent_history": [deepcopy(evt) for evt in self.family_history[-10:]],
        }

    def get_characters_at_location(self, x: int, y: int) -> List['Character']:
        occupants = self._characters_by_tile.get((x, y))
        if not occupants:
            return []
        found: List['Character'] = []
        for name in occupants:
            character = self._characters_by_name.get(name)
            if character:
                found.append(character)
        return found

    def get_nearby_characters(self, character: 'Character', radius: int = 1) -> List['Character']:
        if radius <= 0:
            return []

        origin = (character.x, character.y)
        seen: Set[str] = set()
        neighbors: List['Character'] = []

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) > radius:
                    continue
                tile = (origin[0] + dx, origin[1] + dy)
                occupants = self._characters_by_tile.get(tile)
                if not occupants:
                    continue
                for name in occupants:
                    if name == character.name or name in seen:
                        continue
                    other = self._characters_by_name.get(name)
                    if other:
                        neighbors.append(other)
                        seen.add(name)

        return neighbors

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
        return self._characters_by_name.get(name)

    def _next_crime_id(self) -> str:
        self._crime_incident_counter += 1
        return f"crime_{self._crime_incident_counter}"

    def _next_law_id(self) -> str:
        self._law_counter += 1
        return f"law_{self._law_counter:03d}"

    def _next_petition_id(self) -> str:
        self._law_petition_counter += 1
        return f"petition_{self._law_petition_counter:03d}"

    def _next_interview_id(self) -> str:
        self._interview_counter += 1
        return f"interview_{self._interview_counter:04d}"

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

    # --- Governance & Civic Law Management ---

    def get_law_by_id(self, law_id: str) -> Optional[Dict[str, Any]]:
        if law_id in self.active_laws:
            return self.active_laws[law_id]
        for record in reversed(self.law_history):
            if record.get("id") == law_id:
                return record
        return None

    def has_law_for_offense(self, offense_type: Optional[str]) -> bool:
        if not offense_type:
            return False
        for law in self.active_laws.values():
            if law.get("status") == "active" and law.get("offense_type") == offense_type:
                return True
        return False

    def register_law_petition(
        self,
        issue_type: str,
        summary: str,
        requested_by: str,
        *,
        incident_count: int = 0,
        severity: int = 1,
        support: Optional[float] = None,
    ) -> Dict[str, Any]:
        petition_id = self._next_petition_id()
        today = self.game_time.current_day if self.game_time else 0
        severity = max(1, min(5, severity))
        if support is None:
            base_support = 0.28 + 0.09 * max(0, incident_count - 1)
            support = max(0.2, min(0.9, base_support))
        title = f"{issue_type.title()} Ordinance"
        petition = {
            "id": petition_id,
            "issue_type": issue_type,
            "title": title,
            "summary": summary,
            "requested_by": requested_by,
            "status": "pending",
            "support": round(support, 3),
            "incident_count": incident_count,
            "created_day": today,
            "severity": severity,
            "last_reviewed_day": None,
            "last_reviewed_by": None,
        }
        self.law_petitions.append(petition)
        self.add_event_log_message(
            f"Citizens submit {title}: {summary} (support {petition['support']:.0%})."
        )
        self.add_notable_event(
            "LawPetition",
            {
                "petition_id": petition_id,
                "title": title,
                "support": petition["support"],
                "issue_type": issue_type,
            },
        )
        return petition

    def get_petition_by_id(self, petition_id: str) -> Optional[Dict[str, Any]]:
        for petition in self.law_petitions:
            if petition.get("id") == petition_id:
                return petition
        return None

    def peek_priority_law_petition(self) -> Optional[Dict[str, Any]]:
        pending = [p for p in self.law_petitions if p.get("status") == "pending"]
        if not pending:
            return None
        pending.sort(
            key=lambda entry: (
                entry.get("support", 0.0),
                entry.get("severity", 0),
                -(entry.get("created_day", 0) or 0),
            ),
            reverse=True,
        )
        return pending[0]

    def record_petition_review(
        self,
        petition_id: str,
        reviewer: str,
        decision: str,
    ) -> Optional[Dict[str, Any]]:
        petition = self.get_petition_by_id(petition_id)
        if not petition:
            return None
        today = self.game_time.current_day if self.game_time else 0
        petition["last_reviewed_day"] = today
        petition["last_reviewed_by"] = reviewer
        if decision == "draft":
            petition["status"] = "drafting"
            self.add_event_log_message(
                f"Mayor {reviewer} orders legal drafts for {petition.get('title')}."
            )
        elif decision == "defer":
            petition["status"] = "pending"
            petition["support"] = max(0.15, petition.get("support", 0.0) - 0.05)
            self.add_event_log_message(
                f"Mayor {reviewer} delays action on {petition.get('title')} to gather more input."
            )
        return petition

    def draft_law_from_petition(
        self,
        petition_id: str,
        sponsor: str,
    ) -> Optional[Dict[str, Any]]:
        petition = self.get_petition_by_id(petition_id)
        if not petition:
            return None
        if petition.get("status") == "enacted":
            return self.get_law_by_id(petition.get("draft_law_id", ""))

        today = self.game_time.current_day if self.game_time else 0
        self.record_petition_review(petition_id, sponsor, "draft")

        law_id = petition.get("draft_law_id") or self._next_law_id()
        fine_amount = config.LAW_BASE_FINE_AMOUNT + 5 * max(0, petition.get("severity", 1) - 1)
        requires_interviews = petition.get("support", 0.0) >= config.LAW_INTERVIEW_SUPPORT_THRESHOLD
        baseline_evidence = max(
            config.LAW_CASE_PREP_BASELINE,
            min(1.0, 0.25 + 0.1 * petition.get("incident_count", 0)),
        )
        law_record = {
            "id": law_id,
            "title": petition.get("title"),
            "description": petition.get("summary"),
            "offense_type": petition.get("issue_type"),
            "penalty": {"type": "fine", "amount": fine_amount},
            "requires_trial": True,
            "requires_interviews": requires_interviews,
            "status": "draft",
            "drafted_day": today,
            "sponsor": sponsor,
            "petition_id": petition_id,
            "support": petition.get("support", 0.0),
            "severity": petition.get("severity", 1),
            "evidence_strength": baseline_evidence,
        }
        petition["draft_law_id"] = law_id
        self.law_history.append(law_record)
        self.add_event_log_message(
            f"{sponsor} drafts {law_record['title']} targeting {law_record['offense_type']}."
        )
        return law_record

    def get_pending_law_draft_for(self, sponsor: str) -> Optional[Dict[str, Any]]:
        for record in reversed(self.law_history):
            if (
                record.get("status") == "draft"
                and record.get("sponsor") == sponsor
                and record.get("id") not in self.active_laws
            ):
                return record
        return None

    def enact_law(self, law_id: str, enacted_by: str) -> Optional[Dict[str, Any]]:
        law = self.get_law_by_id(law_id)
        if not law:
            return None
        if law.get("status") == "active":
            return law
        today = self.game_time.current_day if self.game_time else 0
        law["status"] = "active"
        law["enacted_day"] = today
        law["enacted_by"] = enacted_by
        law.setdefault("enforcement_history", [])
        self.active_laws[law_id] = law
        petition_id = law.get("petition_id")
        if petition_id:
            petition = self.get_petition_by_id(petition_id)
            if petition:
                petition["status"] = "enacted"
                petition["enacted_day"] = today
        self.add_event_log_message(
            f"Mayor {enacted_by} enacts {law.get('title')} (penalty {law.get('penalty', {}).get('amount', 0)}c)."
        )
        self.add_notable_event(
            "LawEnacted",
            {
                "law_id": law_id,
                "title": law.get("title"),
                "offense": law.get("offense_type"),
                "penalty": law.get("penalty"),
            },
        )
        return law

    def repeal_law(self, law_id: str, repealed_by: str) -> Optional[Dict[str, Any]]:
        law = self.get_law_by_id(law_id)
        if not law:
            return None
        if law.get("status") != "active":
            return law
        today = self.game_time.current_day if self.game_time else 0
        law["status"] = "repealed"
        law["repealed_day"] = today
        law["repealed_by"] = repealed_by
        self.active_laws.pop(law_id, None)
        self.add_event_log_message(f"{repealed_by} repeals {law.get('title')}.")
        return law

    def identify_applicable_law(self, crime: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        offense = crime.get("type")
        if not offense:
            return None
        candidates: List[Tuple[int, int, Dict[str, Any]]] = []
        for law in self.active_laws.values():
            if law.get("status") != "active":
                continue
            if law.get("offense_type") != offense:
                continue
            enacted_day = law.get("enacted_day", 0) or 0
            severity = law.get("severity", 1)
            candidates.append((severity, enacted_day, law))
        if not candidates:
            return None
        candidates.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
        return candidates[0][2]

    def _select_witnesses_for_case(self, case: Dict[str, Any], count: int = 2) -> List[str]:
        excluded = {name for name in [case.get("defendant"), case.get("prosecutor"), case.get("presiding_officer")] if name}
        available = [char.name for char in self.characters if char.name not in excluded]
        random.shuffle(available)
        return available[:count]

    def plan_case_interviews(self, case: Dict[str, Any], law: Optional[Dict[str, Any]] = None) -> None:
        if not law or not law.get("requires_interviews"):
            return
        case.setdefault("interview_plan", [])
        case.setdefault("interview_statements", [])
        planned: List[str] = []
        for witness in self._select_witnesses_for_case(case, count=2):
            assignment_id = self._next_interview_id()
            assignment = {
                "id": assignment_id,
                "case_id": case.get("case_id"),
                "law_id": law.get("id"),
                "witness": witness,
                "status": "queued",
                "requested_day": self.game_time.current_day if self.game_time else 0,
                "topic": law.get("title"),
            }
            self.pending_interviews.append(assignment)
            case["interview_plan"].append(assignment_id)
            planned.append(witness)
        if planned:
            self.add_event_log_message(
                f"Witness interviews queued for case {case.get('case_id')}: {', '.join(planned)}."
            )

    def assign_investigative_interview(self, officer_name: str) -> Optional[Dict[str, Any]]:
        today = self.game_time.current_day if self.game_time else 0
        for assignment in self.pending_interviews:
            if assignment.get("status") == "assigned" and assignment.get("assigned_to") == officer_name:
                return assignment
        for assignment in self.pending_interviews:
            if assignment.get("status") != "queued":
                continue
            assignment["status"] = "assigned"
            assignment["assigned_to"] = officer_name
            assignment["assigned_day"] = today
            self.add_event_log_message(
                f"{officer_name} assigned to interview {assignment.get('witness')} for case {assignment.get('case_id')}"
            )
            return assignment
        return None

    def get_interview_assignment_by_id(self, assignment_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not assignment_id:
            return None
        for assignment in self.pending_interviews:
            if assignment.get("id") == assignment_id:
                return assignment
        return None

    def record_interview_result(
        self,
        assignment_id: str,
        officer_name: str,
        quality: float,
        notes: str,
    ) -> Optional[Dict[str, Any]]:
        assignment = self.get_interview_assignment_by_id(assignment_id)
        if not assignment:
            return None
        today = self.game_time.current_day if self.game_time else 0
        assignment["status"] = "completed"
        assignment["completed_day"] = today
        assignment["assigned_to"] = assignment.get("assigned_to") or officer_name
        assignment["quality"] = max(0.0, min(1.0, quality))
        assignment["notes"] = notes

        case = self.get_case_by_id(assignment.get("case_id"))
        if case:
            case.setdefault("interview_statements", [])
            statement = {
                "witness": assignment.get("witness"),
                "officer": officer_name,
                "quality": assignment["quality"],
                "notes": notes,
                "day": today,
            }
            case["interview_statements"].append(statement)
            bonus = config.LAW_INTERVIEW_EVIDENCE_BONUS * assignment["quality"]
            case["evidence_strength"] = min(1.0, case.get("evidence_strength", 0.0) + bonus)
            case["preparedness"] = min(1.0, case.get("preparedness", 0.0) + 0.12 * assignment["quality"])
            self.interview_history.setdefault(case.get("case_id"), []).append(statement)
            self.add_event_log_message(
                f"{officer_name} records testimony from {assignment.get('witness')} for case {case.get('case_id')} (quality {assignment['quality']:.0%})."
            )
        return assignment

    def get_governance_snapshot(self) -> Dict[str, Any]:
        laws_snapshot = [
            {
                "id": law.get("id"),
                "title": law.get("title"),
                "offense": law.get("offense_type"),
                "penalty": law.get("penalty"),
                "status": law.get("status"),
                "enacted_day": law.get("enacted_day"),
                "support": law.get("support"),
            }
            for law in self.law_history
            if law.get("status") in {"draft", "active"}
        ]
        petitions_snapshot = [
            {
                "id": petition.get("id"),
                "title": petition.get("title"),
                "support": petition.get("support"),
                "status": petition.get("status"),
                "created_day": petition.get("created_day"),
                "incident_count": petition.get("incident_count"),
            }
            for petition in self.law_petitions
        ]
        interviews_snapshot = [
            {
                "id": assignment.get("id"),
                "case_id": assignment.get("case_id"),
                "witness": assignment.get("witness"),
                "status": assignment.get("status"),
                "assigned_to": assignment.get("assigned_to"),
                "topic": assignment.get("topic"),
            }
            for assignment in self.pending_interviews
            if assignment.get("status") in {"queued", "assigned"}
        ]
        return {
            "laws": laws_snapshot,
            "petitions": petitions_snapshot,
            "interviews": interviews_snapshot,
        }

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
            "law_id": None,
            "penalty": None,
            "requires_interviews": False,
            "interview_plan": [],
            "interview_statements": [],
        }

        applicable_law = self.identify_applicable_law(crime)
        if applicable_law:
            case["law_id"] = applicable_law.get("id")
            case["charge"] = applicable_law.get("title", case["charge"])
            case["penalty"] = deepcopy(applicable_law.get("penalty"))
            case["requires_interviews"] = bool(applicable_law.get("requires_interviews"))
            case["evidence_strength"] = max(
                case["evidence_strength"], applicable_law.get("evidence_strength", config.LAW_CASE_PREP_BASELINE)
            )

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

        if applicable_law:
            self.plan_case_interviews(case, applicable_law)

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
                if hasattr(defendant, "record_life_event"):
                    defendant.record_life_event(
                        self,
                        "trial_verdict",
                        f"Found guilty of {case.get('charge', 'charges')} in case {case.get('case_id')} (fine {fine_amount}).",
                        related=[name for name in [case.get("prosecutor"), case.get("presiding_officer")] if name],
                        tags=["justice", "trial", "verdict"],
                        significance=3,
                        propagate_to_family=True,
                        details={"case_id": case.get("case_id"), "verdict": verdict, "sentence": "fine"},
                    )
            if prosecutor:
                prosecutor.update_mood_score(6, "Secured conviction at trial")
                prosecutor.add_memory(
                    f"Verdict: {case.get('defendant')} found guilty in case {case.get('case_id')}."
                )
                if hasattr(prosecutor, "record_life_event"):
                    prosecutor.record_life_event(
                        self,
                        "trial_verdict",
                        f"Secured guilty verdict against {case.get('defendant')} in case {case.get('case_id')}.",
                        related=[case.get("defendant")],
                        tags=["justice", "trial"],
                        significance=2,
                        propagate_to_family=False,
                        details={"case_id": case.get("case_id"), "verdict": verdict},
                    )
            if presiding:
                presiding.add_memory(
                    f"Presided over guilty verdict for case {case.get('case_id')}."
                )
                if hasattr(presiding, "record_life_event"):
                    presiding.record_life_event(
                        self,
                        "trial_verdict",
                        f"Oversaw guilty verdict in case {case.get('case_id')} against {case.get('defendant')}.",
                        related=[case.get("defendant"), case.get("prosecutor")],
                        tags=["justice", "trial"],
                        significance=2,
                        propagate_to_family=False,
                        details={"case_id": case.get("case_id"), "verdict": verdict},
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
                if hasattr(defendant, "record_life_event"):
                    defendant.record_life_event(
                        self,
                        "trial_verdict",
                        f"Acquitted of {case.get('charge', 'charges')} in case {case.get('case_id')}.",
                        related=[name for name in [case.get("prosecutor"), case.get("presiding_officer")] if name],
                        tags=["justice", "trial", "verdict"],
                        significance=3,
                        propagate_to_family=True,
                        details={"case_id": case.get("case_id"), "verdict": verdict},
                    )
            if prosecutor:
                prosecutor.update_mood_score(-4, "Case dismissed at trial")
                prosecutor.add_memory(
                    f"Verdict: {case.get('defendant')} acquitted in case {case.get('case_id')}."
                )
                if hasattr(prosecutor, "record_life_event"):
                    prosecutor.record_life_event(
                        self,
                        "trial_verdict",
                        f"Saw {case.get('defendant')} acquitted in case {case.get('case_id')}.",
                        related=[case.get("defendant")],
                        tags=["justice", "trial"],
                        significance=1,
                        propagate_to_family=False,
                        details={"case_id": case.get("case_id"), "verdict": verdict},
                    )
            if presiding:
                presiding.add_memory(
                    f"Presided over acquittal for case {case.get('case_id')}."
                )
                if hasattr(presiding, "record_life_event"):
                    presiding.record_life_event(
                        self,
                        "trial_verdict",
                        f"Oversaw acquittal for {case.get('defendant')} in case {case.get('case_id')}.",
                        related=[case.get("defendant"), case.get("prosecutor")],
                        tags=["justice", "trial"],
                        significance=2,
                        propagate_to_family=False,
                        details={"case_id": case.get("case_id"), "verdict": verdict},
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
            if hasattr(character, "record_life_event"):
                character.record_life_event(
                    self,
                    "trial_summons",
                    f"Summoned to attend trial {case.get('case_id')} at the courthouse.",
                    related=[name for name in [case.get("defendant"), case.get("prosecutor"), case.get("presiding_officer")] if name and name != character.name],
                    tags=["justice", "trial", "duty"],
                    significance=2,
                    propagate_to_family=False,
                    details={"case_id": case.get("case_id"), "role": role_key},
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
        if hasattr(patient, "record_life_event"):
            patient.record_life_event(
                self,
                "medical_case_opened",
                f"Diagnosed with {condition} (severity {severity:.1f}).",
                related=[reporter] if reporter else None,
                tags=["health", "medical"],
                significance=2 if severity >= 4 else 1,
                propagate_to_family=True,
                details={"case_id": case_id, "condition": condition, "severity": severity},
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

        caregiver_char = self.get_character_by_name(caregiver)
        if caregiver_char and hasattr(caregiver_char, "record_life_event"):
            treatment_summary = (
                f"Tended to {case.get('patient')} for {case.get('condition')} (severity now {case['severity']:.1f})."
            )
            caregiver_char.record_life_event(
                self,
                "medical_treatment",
                treatment_summary,
                related=[case.get("patient")],
                tags=["health", "medical", "care"],
                significance=2 if success else 1,
                propagate_to_family=False,
                details={"case_id": case_id, "success": success, "severity": case["severity"]},
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
        patient = self.get_character_by_name(case.get("patient", ""))
        if patient and hasattr(patient, "record_life_event"):
            outcome_label = outcome.replace("_", " ")
            summary = f"Medical case {case_id} {outcome_label}."
            if notes:
                summary += f" {notes}"
            significance = 3 if outcome in {"deceased", "fatal"} else 2 if outcome in {"recovered", "stabilized"} else 1
            patient.record_life_event(
                self,
                "medical_case_resolved",
                summary,
                tags=["health", "medical", "outcome"],
                significance=significance,
                propagate_to_family=True,
                details={"case_id": case_id, "outcome": outcome},
            )
            witness_list = [
                note.get("reporter")
                for note in case.get("reports", [])
                if isinstance(note, dict) and note.get("reporter")
            ]
            self._record_bereavement_events(patient, outcome, witness_list)
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

    def _get_stockpile_quantity(self, resource_name: str) -> int:
        return sum(stockpile.inventory.get(resource_name, 0) for stockpile in self.stockpiles)

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
        resources_to_check = [
            "Wood",
            "Stone",
            "Iron Ore",
            "Lumber",
            "Furniture",
            "Herbs",
            "Food",
            "Water",
        ]
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

    def _next_business_id(self) -> str:
        self._business_counter += 1
        return f"biz_{self._business_counter}"

    def launch_business(
        self,
        owner: 'Character',
        template: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if owner is None:
            return None

        templates = list(getattr(config, "BUSINESS_TEMPLATES", []))
        if template is None:
            if not templates:
                return None
            template = random.choice(templates)

        startup_cost = int(template.get("startup_cost", getattr(config, "BUSINESS_STARTUP_COST", 0)))
        if owner.money < startup_cost:
            return None

        owner.money -= startup_cost
        business_id = self._next_business_id()
        display_name = template.get("display_name", template.get("key", "Enterprise"))
        business_name = f"{owner.name}'s {display_name}"
        base_capital = int(template.get("base_capital", startup_cost))
        revenue_range = template.get("revenue_range") or getattr(config, "BUSINESS_DAILY_REVENUE_RANGE", (4, 9))
        business = {
            "id": business_id,
            "name": business_name,
            "owner": owner.name,
            "industry": template.get("industry", "general"),
            "capital": base_capital,
            "revenue_range": tuple(revenue_range),
            "status": "active",
            "founded_day": self.game_time.current_day if self.game_time else 0,
            "employees": [],
            "cash_reserve": 0,
            "history": [],
        }
        self.businesses[business_id] = business

        owner.assign_business_role(business_id, "owner")
        owner.add_memory(f"Invested {startup_cost} coins to establish {business_name}.")
        owner.record_life_event(
            self,
            "business_founded",
            f"Founded {business_name} in the {business['industry']} trade.",
            tags=["business"],
            significance=3,
            details={"business_id": business_id, "industry": business["industry"]},
        )
        owner.update_mood_score(getattr(config, "MOOD_CHANGE_STARTED_PROJECT", 5), f"Founded {business_name}")
        owner.update_reputation(getattr(config, "BUSINESS_REPUTATION_BONUS", 0), f"Founded {business_name}", self)

        self.add_event_log_message(f"{owner.name} establishes {business_name} ({business['industry']}).")
        self.add_notable_event(
            "BusinessFounded",
            {
                "summary": f"{owner.name} opened {business_name}.",
                "owner": owner.name,
                "industry": business["industry"],
                "business_id": business_id,
            },
        )

        max_employees = getattr(config, "BUSINESS_MAX_EMPLOYEES", 0)
        if max_employees > 0:
            candidate_pool: List['Character'] = []
            for character in self.characters:
                if character.name == owner.name:
                    continue
                if getattr(character, "retired", False):
                    continue
                if business_id in getattr(character, "business_roles", {}):
                    continue
                if character.job in {"Unemployed", "Laborer", "Apprentice", None}:
                    candidate_pool.append(character)
            random.shuffle(candidate_pool)
            for candidate in candidate_pool:
                if len(business["employees"]) >= max_employees:
                    break
                business["employees"].append(candidate.name)
                candidate.assign_business_role(business_id, "employee")
                candidate.add_memory(f"Hired to work at {business_name}.")
                candidate.record_life_event(
                    self,
                    "business_employment",
                    f"Began working at {business_name}.",
                    tags=["business", "employment"],
                    significance=2,
                    details={"business_id": business_id, "role": "employee"},
                )

        return business

    def _handle_character_departure_from_business(
        self,
        business_id: str,
        character_name: str,
        owner_departure: bool = False,
    ) -> None:
        business = self.businesses.get(business_id)
        if not business:
            return

        if owner_departure:
            self._close_business(business, f"owner {character_name} departed")
            return

        if character_name in business.get("employees", []):
            business["employees"] = [name for name in business["employees"] if name != character_name]
            employee = self.get_character_by_name(character_name)
            if employee:
                employee.leave_business_role(business_id, f"Left employment at {business['name']}.")

    def _close_business(self, business: Dict[str, Any], reason: str) -> None:
        if business.get("status") == "closed":
            return

        business["status"] = "closed"
        business["closed_day"] = self.game_time.current_day if self.game_time else 0
        owner = self.get_character_by_name(business.get("owner", ""))
        if owner:
            owner.handle_business_closure(business["id"], self, f"{business['name']} closed ({reason}).")
        for employee_name in list(business.get("employees", [])):
            employee = self.get_character_by_name(employee_name)
            if employee:
                employee.handle_business_closure(business["id"], self, f"{business['name']} closed ({reason}).")
        business["employees"] = []
        business["cash_reserve"] = 0
        self.add_event_log_message(f"{business['name']} closed: {reason}.")
        self.add_notable_event(
            "BusinessClosed",
            {
                "summary": f"{business['name']} closed due to {reason}.",
                "business_id": business.get("id"),
                "owner": business.get("owner"),
                "reason": reason,
            },
        )

    def _update_businesses(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.businesses:
            report["business_events"] = events
            return events

        revenue_variance = getattr(config, "BUSINESS_REVENUE_VARIANCE", 0.0)
        retention = getattr(config, "BUSINESS_CAPITAL_RETENTION", 0.5)
        base_cost = getattr(config, "BUSINESS_BASE_OPERATING_COST", 2)
        wage = getattr(config, "BUSINESS_EMPLOYEE_WAGE", 3)
        owner_draw_limit = getattr(config, "BUSINESS_OWNER_DRAW", 0)
        capital_factor = getattr(config, "BUSINESS_CAPITAL_PROFIT_FACTOR", 0.0)
        failure_threshold = getattr(config, "BUSINESS_FAILURE_THRESHOLD", -15)
        recovery_bonus = getattr(config, "BUSINESS_RECOVERY_BONUS", 0.0)
        reputation_bonus = getattr(config, "BUSINESS_REPUTATION_BONUS", 0)

        for business_id, business in list(self.businesses.items()):
            if business.get("status") != "active":
                continue

            revenue_range = business.get("revenue_range") or getattr(
                config, "BUSINESS_DAILY_REVENUE_RANGE", (4, 9)
            )
            revenue_low, revenue_high = revenue_range
            if revenue_low > revenue_high:
                revenue_low, revenue_high = revenue_high, revenue_low

            gross = random.randint(int(revenue_low), int(revenue_high))
            gross += int(business.get("capital", 0) * capital_factor)
            if revenue_variance:
                gross = max(0, int(gross * random.uniform(1 - revenue_variance, 1 + revenue_variance)))

            payroll_total = 0
            paid_workers: List[str] = []
            for employee_name in list(business.get("employees", [])):
                employee = self.get_character_by_name(employee_name)
                if not employee or getattr(employee, "retired", False):
                    continue
                employee.receive_income(wage, f"work at {business['name']}")
                payroll_total += wage
                paid_workers.append(employee.name)

            expenses = base_cost + payroll_total
            owner_draw = 0
            owner = self.get_character_by_name(business.get("owner", ""))
            if owner and gross > expenses and owner_draw_limit > 0:
                available_profit = gross - expenses
                owner_draw = min(owner_draw_limit, available_profit)
                if owner_draw > 0:
                    owner.receive_income(owner_draw, f"profits from {business['name']}")
                    expenses += owner_draw

            net_profit = gross - expenses
            if net_profit >= 0:
                retained = int(net_profit * retention)
                bonus = int(gross * recovery_bonus)
                business["capital"] = business.get("capital", 0) + retained + bonus
            else:
                business["capital"] = business.get("capital", 0) + net_profit
            business["cash_reserve"] = max(0, business.get("cash_reserve", 0) + net_profit)

            if owner and net_profit > 0 and reputation_bonus:
                owner.update_reputation(reputation_bonus, f"Profitable day at {business['name']}", self)

            history_entry = {
                "day": self.game_time.current_day if self.game_time else -1,
                "gross": gross,
                "net": net_profit,
                "payroll": payroll_total,
                "owner_draw": owner_draw,
            }
            business.setdefault("history", []).append(history_entry)
            business["history"] = business["history"][-14:]

            if business.get("capital", 0) <= failure_threshold:
                self._close_business(business, "insolvency")
                events.append(
                    {
                        "id": business_id,
                        "name": business.get("name"),
                        "status": "closed",
                        "net": net_profit,
                        "reason": "insolvency",
                    }
                )
                continue

            events.append(
                {
                    "id": business_id,
                    "name": business.get("name"),
                    "gross": gross,
                    "net": net_profit,
                    "payroll": payroll_total,
                    "owner_draw": owner_draw,
                    "status": "active",
                    "employees_paid": paid_workers,
                }
            )

        report["business_events"] = events
        return events

    def _update_character_wealth(self, report: Dict[str, Any]) -> Dict[str, Any]:
        wealth_events: List[Dict[str, Any]] = []
        wealth_entries: List[Dict[str, Any]] = []
        for character in self.characters:
            if not hasattr(character, "evaluate_daily_wealth"):
                continue
            updates = character.evaluate_daily_wealth(self)
            net = updates.get("net_worth", getattr(character, "net_worth", character.money))
            wealth_entries.append(
                {
                    "name": character.name,
                    "net_worth": net,
                    "status": getattr(character, "wealth_status", "modest"),
                }
            )
            event_payload = {k: v for k, v in updates.items() if k not in {"net_worth", "previous_net_worth"}}
            if event_payload:
                wealth_events.append({"character": character.name, **event_payload})

        wealth_entries.sort(key=lambda entry: entry["net_worth"])
        richest = sorted(wealth_entries, key=lambda entry: entry["net_worth"], reverse=True)[:3]
        poorest = wealth_entries[:3]

        snapshot = {
            "entries": wealth_entries,
            "richest": richest,
            "poorest": poorest,
        }
        self.latest_wealth_snapshot = snapshot
        report["wealth_snapshot"] = snapshot
        if wealth_events:
            report["wealth_events"] = wealth_events
        return snapshot

    def _evaluate_wealth_tensions(
        self,
        report: Dict[str, Any],
        wealth_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.game_time:
            return
        if wealth_data is None:
            wealth_data = self.latest_wealth_snapshot
        if not wealth_data:
            return

        today = self.game_time.current_day
        if self._last_wealth_tension_day == today:
            return
        threshold = getattr(config, "WEALTH_JEALOUSY_THRESHOLD", 0)
        if threshold <= 0:
            return

        richest = wealth_data.get("richest", [])
        jealousy_records: List[Dict[str, Any]] = []
        for character in self.characters:
            if not hasattr(character, "net_worth"):
                continue
            target_name = None
            gap_value = 0
            for entry in richest:
                if entry["name"] == character.name:
                    continue
                diff = entry["net_worth"] - getattr(character, "net_worth", character.money)
                if diff > gap_value:
                    gap_value = diff
                    target_name = entry["name"]
            if target_name and gap_value >= threshold:
                if character._last_jealousy_day == today:
                    continue
                character._last_jealousy_day = today
                character.add_memory(
                    f"Jealous of {target_name}'s fortune (gap {gap_value} coins)."
                )
                character.update_mood_score(
                    getattr(config, "WEALTH_JEALOUSY_MOOD_PENALTY", -3),
                    f"Jealous of {target_name}'s wealth",
                )
                character.modify_relationship(
                    target_name,
                    getattr(config, "WEALTH_JEALOUSY_RELATIONSHIP_HIT", -2),
                    self,
                    reason="Envious of their wealth",
                )
                jealousy_records.append(
                    {"character": character.name, "target": target_name, "gap": gap_value}
                )

        if jealousy_records:
            report.setdefault("wealth_tensions", []).extend(jealousy_records)
            self._last_wealth_tension_day = today

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
            if self.latest_wealth_snapshot:
                richest_list = self.latest_wealth_snapshot.get("richest", [])
                richest_entry = next(
                    (entry for entry in richest_list if entry.get("name") != character.name),
                    None,
                )
                if richest_entry:
                    wealth_gap = richest_entry.get("net_worth", 0) - getattr(
                        character, "net_worth", character.money
                    )
                    if wealth_gap > 0:
                        jealousy_pressure = getattr(config, "JEALOUSY_THEFT_PRESSURE", 0.0)
                        threshold = getattr(config, "WEALTH_JEALOUSY_THRESHOLD", 1)
                        desperation += (wealth_gap / max(1, threshold)) * jealousy_pressure
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
            inputs_required = definition.get("inputs") or {}
            discrete_output_flag = definition.get("discrete_output")
            discrete_output = (
                discrete_output_flag
                if discrete_output_flag is not None
                else bool(inputs_required)
            )
            inputs_consumed: Dict[str, int] = {}
            input_shortage = False
            input_shortage_details: Dict[str, int] = {}
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

            if inputs_required:
                raw_output_units = int(sector_output)
                if discrete_output:
                    sector_output = float(int(sector_output))
                max_units_possible: Optional[int] = None
                for resource_name, amount_per_unit in inputs_required.items():
                    if amount_per_unit <= 0:
                        continue
                    available = self._get_stockpile_quantity(resource_name)
                    if available < amount_per_unit:
                        input_shortage_details[resource_name] = amount_per_unit - available
                    possible_units = available // amount_per_unit
                    if max_units_possible is None or possible_units < max_units_possible:
                        max_units_possible = possible_units
                if max_units_possible is None:
                    max_units_possible = int(sector_output) if discrete_output else int(sector_output)
                if max_units_possible <= 0:
                    if workers:
                        input_shortage = True
                    sector_output = 0.0
                else:
                    if discrete_output:
                        sector_output = float(min(int(sector_output), max_units_possible))
                    else:
                        sector_output = min(sector_output, float(max_units_possible))
                actual_units = int(sector_output)
                if actual_units > 0:
                    min_supported_units = actual_units
                    for resource_name, amount_per_unit in inputs_required.items():
                        if amount_per_unit <= 0:
                            continue
                        needed = actual_units * amount_per_unit
                        consumed = self._withdraw_from_stockpiles(resource_name, needed)
                        inputs_consumed[resource_name] = consumed
                        if consumed < needed:
                            shortage_amount = needed - consumed
                            if shortage_amount > 0:
                                input_shortage_details[resource_name] = shortage_amount
                            supported = consumed // amount_per_unit if amount_per_unit else actual_units
                        else:
                            supported = consumed // amount_per_unit if amount_per_unit else actual_units
                        if supported < min_supported_units:
                            min_supported_units = supported
                    if min_supported_units < actual_units:
                        actual_units = min_supported_units
                    sector_output = float(actual_units)
                if raw_output_units > actual_units and raw_output_units > 0:
                    input_shortage = True
                    for resource_name, amount_per_unit in inputs_required.items():
                        if amount_per_unit <= 0:
                            continue
                        missing_amount = (raw_output_units - actual_units) * amount_per_unit
                        if missing_amount > 0:
                            input_shortage_details.setdefault(resource_name, missing_amount)
                if (int(sector_output) <= 0) and workers:
                    input_shortage = True

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

            if inputs_consumed:
                crew_entry["inputs_consumed"] = inputs_consumed

            if not workers and backlog_existing <= 0:
                crew_entry.setdefault("notes", []).append("No crew reported for duty.")
            elif not workers and backlog_existing > 0:
                crew_entry.setdefault("notes", []).append(
                    "Haulers awaiting gathered stock from previous days."
                )

            if input_shortage:
                shortage_parts = [
                    f"{amount} {resource_name}"
                    for resource_name, amount in inputs_required.items()
                    if amount > 0
                ]
                shortage_specifics = [
                    f"{missing} {resource_name}"
                    for resource_name, missing in input_shortage_details.items()
                    if missing > 0
                ]
                if shortage_specifics:
                    shortage_text = ", ".join(shortage_specifics)
                else:
                    shortage_text = ", ".join(shortage_parts)
                if shortage_text:
                    crew_entry.setdefault("notes", []).append(
                        f"Awaiting inputs ({shortage_text})."
                    )
                    alerts.append(
                        f"{definition.get('title', key.title())} needs {shortage_text} to resume work."
                    )
                else:
                    crew_entry.setdefault("notes", []).append("Awaiting input deliveries.")
                    alerts.append(
                        f"{definition.get('title', key.title())} lacks production inputs."
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
        business_events = self._update_businesses(report)
        wealth_snapshot = self._update_character_wealth(report)
        self._resolve_theft_attempts(report)
        self._evaluate_wealth_tensions(report, wealth_snapshot)
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
        for business_event in business_events:
            if business_event.get("status") == "closed":
                self.add_event_log_message(
                    f"Business closed: {business_event.get('name')} ({business_event.get('reason', 'closure')})."
                )
            else:
                net = business_event.get("net", 0)
                self.add_event_log_message(
                    f"{business_event.get('name')} netted {net} coin{'s' if net != 1 else ''} after payroll."
                )
        for crime_event in report.get("crime_events", []):
            self.add_event_log_message(f"Security report: {crime_event['description']}.")

        if report["surplus_trades"]:
            trade_summaries = ", ".join(
                f"{trade['quantity']} {trade['resource']} (+{trade['revenue']}c)"
                for trade in report["surplus_trades"]
            )
            self.add_event_log_message(f"Trade ledger: {trade_summaries} exported to market.")

        for wealth_event in report.get("wealth_events", []):
            if "business_started" in wealth_event:
                started = wealth_event["business_started"]
                self.add_event_log_message(
                    f"{wealth_event['character']} opened {started.get('name')} ({started.get('industry')})."
                )
            if "retired" in wealth_event:
                retired = wealth_event["retired"]
                self.add_event_log_message(
                    f"{wealth_event['character']} retires from {retired.get('former_job')} with {retired.get('net_worth')} coins saved."
                )
            if "nobility" in wealth_event:
                nobility = wealth_event["nobility"]
                self.add_event_log_message(
                    f"{wealth_event['character']} earns the title {nobility.get('title')} through amassed wealth."
                )
        if report.get("wealth_tensions"):
            for tension in report["wealth_tensions"]:
                self.add_event_log_message(
                    f"Jealousy simmers: {tension['character']} eyes {tension['target']}'s fortune (gap {tension['gap']}c)."
                )

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

    def process_governance_daily(self) -> None:
        if not self.game_time:
            return
        today = self.game_time.current_day
        window = getattr(config, "LAW_PETITION_CRIME_WINDOW", 6)
        threshold = getattr(config, "LAW_PETITION_THRESHOLD", 3)

        recent_incidents = [
            report
            for report in self.crime_reports
            if report.get("day") is not None and today - report["day"] <= window
        ]
        tallies = Counter(report.get("type") for report in recent_incidents if report.get("type"))
        for offense, count in tallies.items():
            if not offense or count < threshold:
                continue
            if self.has_law_for_offense(offense):
                continue
            existing = next(
                (
                    petition
                    for petition in self.law_petitions
                    if petition.get("issue_type") == offense
                    and petition.get("status") in {"pending", "drafting"}
                ),
                None,
            )
            if existing:
                existing["incident_count"] = max(existing.get("incident_count", 0), count)
                continue
            summary = (
                f"Residents demand stronger action against {offense} after {count} incidents in {window} days."
            )
            self.register_law_petition(
                offense,
                summary,
                "Civic Council",
                incident_count=count,
                severity=min(5, count),
            )

        for petition in self.law_petitions:
            if petition.get("status") != "pending":
                continue
            last_review = petition.get("last_reviewed_day")
            if last_review is not None and today <= last_review:
                continue
            previous_support = petition.get("support", 0.0)
            petition["support"] = min(1.0, previous_support + config.LAW_SUPPORT_ESCALATION)
            if previous_support < 0.5 <= petition["support"]:
                self.add_event_log_message(
                    f"Support surges for {petition.get('title')} (now {petition['support']:.0%})."
                )

        retention_window = max(2, window)
        self.pending_interviews = [
            assignment
            for assignment in self.pending_interviews
            if assignment.get("status") in {"queued", "assigned"}
            or (
                assignment.get("status") == "completed"
                and assignment.get("completed_day") is not None
                and today - assignment.get("completed_day", today) <= retention_window
            )
        ]

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
