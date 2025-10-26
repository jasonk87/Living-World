# game/housing.py
from __future__ import annotations
from collections import defaultdict, Counter
import math
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .building import Building
from .data import STRUCTURE_BLUEPRINTS, NOBLE_RANKS_OR_JOBS
from . import config

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class Housing:
    def __init__(self, world: World):
        self.world = world
        self._residential_assignments: Dict[str, Tuple[int, int]] = {}
        self.last_housing_evaluation_day: Optional[int] = None
        self._latest_household_vignettes: List[Dict[str, Any]] = []
        self._latest_neighborhood_gatherings: List[Dict[str, Any]] = []
        self._latest_household_comforts: List[Dict[str, Any]] = []
        self._latest_household_comfort_summary: Dict[str, Any] = {}
        self.latest_housing_snapshot: Dict[str, Any] = self.get_housing_snapshot()

    def _is_residential(self, building: Building) -> bool:
        tags = building.functionality.get("tags", []) if building.functionality else []
        provides = building.functionality.get("provides_shelter", 0) if building.functionality else 0
        return building.is_operational and "residential" in tags and provides

    def _get_building_tier(self, building: Building) -> str:
        if not building.functionality:
            return getattr(config, "RESIDENTIAL_FALLBACK_TIER", "modest")
        tier = building.functionality.get("wealth_tier")
        if tier:
            return tier
        return getattr(config, "RESIDENTIAL_FALLBACK_TIER", "modest")

    def claim_residential_spot(
        self,
        character: 'Character',
        preferred_tier: Optional[str] = None,
    ) -> Optional[Building]:
        existing_location = self._residential_assignments.get(character.name)
        assigned_building: Optional[Building] = None
        if existing_location:
            existing = self.world.get_building_by_location(existing_location)
            if existing and self._is_residential(existing):
                if preferred_tier and self._get_building_tier(existing) != preferred_tier:
                    existing.remove_occupant(character.name)
                    if character.name in self._residential_assignments:
                        del self._residential_assignments[character.name]
                    existing = None
                else:
                    if character.name not in existing.occupants:
                        existing.add_occupant(character.name)
                    assigned_building = existing
        if assigned_building:
            self.latest_housing_snapshot = self.get_housing_snapshot()
            if hasattr(character, "home_location"):
                character.home_location = assigned_building.location
            return assigned_building

        candidate_buildings: List[Building] = []
        if preferred_tier:
            for building in self.world.buildings:
                if self._is_residential(building) and self._get_building_tier(building) == preferred_tier:
                    candidate_buildings.append(building)
        for building in self.world.buildings:
            if not self._is_residential(building):
                continue
            if building in candidate_buildings:
                continue
            candidate_buildings.append(building)

        for building in candidate_buildings:
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
            if hasattr(character, "home_location"):
                character.home_location = assigned_building.location
        return assigned_building

    def release_residential_spot(self, character: 'Character'):
        assigned = self._residential_assignments.get(character.name)
        target_building = None
        if assigned:
            target_building = self.world.get_building_by_location(assigned)
        if not target_building:
            # Attempt to locate any building currently listing the character as an occupant
            for building in self.world.buildings:
                if character.name in building.occupants:
                    target_building = building
                    break
        if target_building:
            target_building.remove_occupant(character.name)
        if character.name in self._residential_assignments:
            del self._residential_assignments[character.name]
        if hasattr(character, "home_location"):
            character.home_location = None
        self.latest_housing_snapshot = self.get_housing_snapshot()

    def get_housing_snapshot(self) -> Dict[str, Any]:
        total_beds = 0
        claimed_beds = 0
        structures: List[Dict[str, Any]] = []
        occupant_lookup: Dict[str, str] = {}

        for building in self.world.buildings:
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
                    "tier": self._get_building_tier(building),
                    "amenities": list(getattr(building, "amenities", [])),
                    "style": getattr(building, "household_style", None),
                    "comfort": round(getattr(building, "comfort_score", 0.0), 1),
                    "comfort_state": getattr(building, "household_comfort_state", {}).copy(),
                }
            )

            for occupant_name in occupants:
                occupant_lookup[occupant_name] = building.display_name

        assignments: Dict[str, str] = {}
        for char_name, location in self._residential_assignments.items():
            building = self.world.get_building_by_location(location)
            if building and self._is_residential(building):
                assignments[char_name] = building.display_name

        homeless: List[str] = []
        for character in self.world.characters:
            home_name = assignments.get(character.name) or occupant_lookup.get(character.name)
            if home_name:
                assignments[character.name] = home_name
            else:
                homeless.append(character.name)

        resting_characters = [
            character.name
            for character in self.world.characters
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
            "household_vignettes": list(self._latest_household_vignettes),
            "neighborhood_gatherings": list(self._latest_neighborhood_gatherings),
        }
        snapshot["comfort_summary"] = self._latest_household_comfort_summary.copy()
        snapshot["comfort_events"] = self._latest_household_comforts[-8:].copy()
        return snapshot

    def _can_place_structure(
        self,
        origin: Tuple[int, int],
        size: Tuple[int, int],
        resource_tiles: set[Tuple[int, int]],
    ) -> bool:
        width, height = size
        ox, oy = origin
        for dx in range(width):
            for dy in range(height):
                tx = ox + dx
                ty = oy + dy
                if not (0 <= tx < self.world.grid_size[0] and 0 <= ty < self.world.grid_size[1]):
                    return False
                if self.world.get_building_at(tx, ty):
                    return False
                if (tx, ty) in self.world.stockpile_tiles:
                    return False
                if self.world._tile_reservations.get((tx, ty)):
                    return False
                if self.world._characters_by_tile.get((tx, ty)):
                    return False
                tile_type = self.world.grid[tx][ty]
                if tile_type in getattr(config, "IMPASSABLE_TERRAINS", set()):
                    return False
        return True

    def _find_structure_site(
        self,
        size: Tuple[int, int],
        *,
        anchor: Optional[Tuple[int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        width, height = size
        if width <= 0 or height <= 0:
            return None
        max_x = self.world.grid_size[0] - width + 1
        max_y = self.world.grid_size[1] - height + 1
        if max_x <= 0 or max_y <= 0:
            return None

        resource_tiles: set[Tuple[int, int]] = set(self.world.resource_nodes.keys())

        anchor_point = anchor or getattr(config, "RESIDENTIAL_ANCHOR", None) or self.world.market_location
        candidates: List[Tuple[Tuple[int, int], int]] = []
        for x in range(max_x):
            for y in range(max_y):
                if not self._can_place_structure((x, y), size, resource_tiles):
                    continue
                distance = abs(anchor_point[0] - x) + abs(anchor_point[1] - y)
                candidates.append(((x, y), distance))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[1], item[0][0], item[0][1]))
        return candidates[0][0]

    def _place_structure_from_blueprint(self, blueprint_key: str) -> Optional[Building]:
        blueprint = STRUCTURE_BLUEPRINTS.get(blueprint_key)
        if not blueprint:
            return None
        size = tuple(blueprint.get("size", (1, 1)))
        location = self._find_structure_site(size)
        if not location:
            return None

        building = Building(
            structure_type=blueprint_key,
            display_name=blueprint.get("display_name", blueprint_key.replace("_", " ").title()),
            location=location,
            size=size,
            required_resources=blueprint.get("required_resources", {}).copy(),
            functionality=blueprint.get("functionality", {}).copy(),
            required_skill=blueprint.get("required_skill"),
            construction_phases=blueprint.get("construction_phases"),
            map_char_initial=blueprint.get("map_char_initial", "X"),
            map_char_complete=blueprint.get("map_char_complete", "B"),
            tile_layout=blueprint.get("tile_layout"),
            tile_palette=blueprint.get("tile_palette"),
            amenities=blueprint.get("amenities"),
            household_style=blueprint.get("household_style"),
        )
        building.is_operational = True
        building.current_phase_index = len(building.phases)
        building.current_progress = building.build_time
        building.current_phase_progress = 0.0
        self.world.add_building(building)
        self.world._remove_resource_nodes_at(building.get_tiles_occupied())

        layout = building.get_tile_layout()
        if layout:
            for row_idx, row in enumerate(layout):
                for col_idx, tile_name in enumerate(row):
                    tx = building.location[0] + col_idx
                    ty = building.location[1] + row_idx
                    if 0 <= tx < self.world.grid_size[0] and 0 <= ty < self.world.grid_size[1] and tile_name:
                        self.world.grid[tx][ty] = tile_name
            self.world.map_revision += 1
        else:
            interior_tile = blueprint.get("interior_tile")
            if interior_tile:
                for tx, ty in building.get_tiles_occupied():
                    if 0 <= tx < self.world.grid_size[0] and 0 <= ty < self.world.grid_size[1]:
                        self.world.grid[tx][ty] = interior_tile
                self.world.map_revision += 1

        tier = building.functionality.get("wealth_tier") if building.functionality else None
        tier_label = tier or "residential"
        self.world.add_event_log_message(
            f"Raised {building.display_name} ({tier_label}) at {building.location} to meet housing demand."
        )
        return building

    def determine_estate_tier(self, character: 'Character') -> str:
        tier_configs = getattr(config, "RESIDENTIAL_TIER_BLUEPRINTS", [])
        available_tiers = {entry.get("status") for entry in tier_configs if entry.get("status")}
        fallback = getattr(config, "RESIDENTIAL_FALLBACK_TIER", "modest")
        noble_ranks = set(getattr(config, "NOBLE_RANKS_OR_JOBS", []) or NOBLE_RANKS_OR_JOBS)
        if character.rank in noble_ranks and "noble" in available_tiers:
            return "noble"
        status = getattr(character, "wealth_status", fallback)
        if status in available_tiers:
            return status
        if fallback in available_tiers:
            return fallback
        if tier_configs:
            return tier_configs[0].get("status", fallback)
        return fallback

    def _synchronize_estate_expectations(self, snapshot: Dict[str, Any]) -> bool:
        tier_configs = getattr(config, "RESIDENTIAL_TIER_BLUEPRINTS", [])
        if not tier_configs or not self.world.characters:
            return False

        tier_lookup = {
            entry["status"]: entry
            for entry in tier_configs
            if entry.get("status") and entry.get("blueprint")
        }
        fallback_tier = getattr(config, "RESIDENTIAL_FALLBACK_TIER", "modest")

        tier_priority = getattr(config, "RESIDENTIAL_TIER_PRIORITY", {})
        default_priority = max(tier_priority.values(), default=5) + 1

        buildings_by_tier: Dict[str, List[Building]] = defaultdict(list)
        for building in self.world.buildings:
            if not self._is_residential(building):
                continue
            tier = self._get_building_tier(building)
            buildings_by_tier[tier].append(building)

        desired_counts: Counter[str] = Counter()
        for character in self.world.characters:
            desired_tier = self.determine_estate_tier(character)
            desired_counts[desired_tier] += 1

        shortage_logged: set[str] = set()
        changed = False
        sorted_desired = sorted(
            desired_counts.items(),
            key=lambda item: tier_priority.get(item[0], default_priority),
        )
        for tier, resident_count in sorted_desired:
            config_entry = tier_lookup.get(tier) or tier_lookup.get(fallback_tier)
            if not config_entry:
                continue
            capacity = sum(
                int(building.functionality.get("provides_shelter", 0))
                for building in buildings_by_tier.get(tier, [])
            )
            while capacity < resident_count:
                new_building = self._place_structure_from_blueprint(config_entry.get("blueprint"))
                if not new_building:
                    if tier not in shortage_logged:
                        shortage_logged.add(tier)
                        self.world.add_event_log_message(
                            f"Unable to expand {tier} housing—no suitable plots remain for that estate tier."
                        )
                    break
                buildings_by_tier.setdefault(tier, []).append(new_building)
                capacity += int(new_building.functionality.get("provides_shelter", 0))
                changed = True

        for building in self.world.buildings:
            if not self._is_residential(building):
                continue
            tier = self._get_building_tier(building)
            for occupant_name in list(building.occupants):
                occupant = self.world.get_character_by_name(occupant_name)
                desired_tier = self.determine_estate_tier(occupant) if occupant else None
                if not occupant or desired_tier != tier:
                    building.remove_occupant(occupant_name)
                    if occupant_name in self._residential_assignments:
                        del self._residential_assignments[occupant_name]
                    changed = True

        sorted_characters = sorted(
            self.world.characters,
            key=lambda char: tier_priority.get(self.determine_estate_tier(char), default_priority),
        )

        for character in sorted_characters:
            preferred_tier = self.determine_estate_tier(character)
            building = self.claim_residential_spot(character, preferred_tier=preferred_tier)
            if not building:
                changed = True

        if changed:
            self.latest_housing_snapshot = self.get_housing_snapshot()

        return changed

    def _format_household_label(self, occupants: List['Character'], host: 'Character') -> str:
        others = [char.name for char in occupants if char and char.name != host.name]
        if not others:
            return host.name
        if len(others) == 1:
            return f"{host.name} and {others[0]}"
        if len(others) == 2:
            return f"{host.name}, {others[0]}, and {others[1]}"
        return f"{host.name}, {others[0]}, and {len(others) - 1} others"

    def _format_neighborhood_label(self, block_key: Tuple[int, int], block_size: int) -> str:
        block_x, block_y = block_key
        start_x = block_x * block_size
        start_y = block_y * block_size
        human_x = block_x + 1
        human_y = block_y + 1
        return f"District {human_x}-{human_y} (tiles {start_x}–{start_x + block_size - 1}, {start_y}–{start_y + block_size - 1})"

    def _maintain_household_comforts(
        self, report: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        rules = list(getattr(config, "HOUSEHOLD_COMFORT_RULES", []))
        if report is not None:
            report.setdefault("household_comforts", [])
            report.setdefault("household_comfort_summary", {})
        if not self.world.game_time or not rules:
            self._latest_household_comforts = []
            self._latest_household_comfort_summary = {}
            if report is not None:
                report["household_comforts"] = []
                report["household_comfort_summary"] = {}
            return []

        today = self.world.game_time.current_day
        base_decay = float(getattr(config, "HOUSEHOLD_COMFORT_DECAY_BASE", 0.0))
        empty_decay = float(getattr(config, "HOUSEHOLD_COMFORT_EMPTY_DECAY", base_decay))
        max_score = float(getattr(config, "HOUSEHOLD_COMFORT_MAX", 100.0))
        good_threshold = float(
            getattr(config, "HOUSEHOLD_COMFORT_GOOD_THRESHOLD", max_score * 0.6)
        )
        need_cap = getattr(config, "NEED_SCORE_MAX", 100)
        need_min = getattr(config, "NEED_SCORE_MIN", 0)

        updates: List[Dict[str, Any]] = []
        summary_counts: Counter[str] = Counter()
        comfort_scores: List[float] = []
        comfortable_households = 0
        resource_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"required": 0, "withdrawn": 0})

        for building in self.world.buildings:
            if not self._is_residential(building):
                continue

            occupants: List['Character'] = []
            for name in list(building.occupants):
                occupant = self.world.get_character_by_name(name)
                if occupant:
                    occupants.append(occupant)
                else:
                    building.remove_occupant(name)

            occupant_count = len(occupants)
            current_score = float(getattr(building, "comfort_score", 0.0))
            decay_amount = base_decay if occupant_count > 0 else max(base_decay, empty_decay)
            if decay_amount:
                current_score = max(0.0, current_score - decay_amount)
            building.comfort_score = current_score

            tier = self._get_building_tier(building)
            style = getattr(building, "household_style", None)

            for rule in rules:
                state = building.household_comfort_state.setdefault(
                    rule.get("key", "comfort"),
                    {
                        "comfort": 0.0,
                        "last_serviced_day": None,
                        "last_outcome": None,
                    },
                )
                rule_decay = float(rule.get("decay", 0.0))
                if rule_decay:
                    state["comfort"] = max(
                        0.0, float(state.get("comfort", 0.0)) - rule_decay
                    )

                interval = max(1, int(rule.get("interval_days", 1)))
                last_day = state.get("last_serviced_day")
                if (
                    occupant_count > 0
                    and last_day is not None
                    and today - int(last_day) < interval
                ):
                    continue

                resource_name = rule.get("resource")
                if not resource_name or occupant_count <= 0:
                    continue

                base_amount = float(rule.get("base_amount", 0.0))
                per_resident = float(rule.get("per_resident", 0.0))
                required_float = base_amount + per_resident * occupant_count

                style_multipliers = rule.get("style_multipliers", {}) or {}
                if style and style in style_multipliers:
                    required_float *= float(style_multipliers[style])

                tier_multipliers = rule.get("tier_multipliers", {}) or {}
                if tier and tier in tier_multipliers:
                    required_float *= float(tier_multipliers[tier])

                minimum_amount = float(rule.get("minimum", 0.0))
                if minimum_amount > 0:
                    required_float = max(required_float, minimum_amount)

                required = int(math.ceil(required_float)) if required_float > 0 else 0

                usage_entry = resource_usage[resource_name]
                usage_entry["required"] += required

                withdrawn = 0
                if required > 0:
                    withdrawn = self.world._withdraw_from_stockpiles(resource_name, required)
                usage_entry["withdrawn"] += withdrawn

                ratio = 1.0 if required == 0 else max(0.0, min(1.0, withdrawn / required))
                success_ratio = float(rule.get("success_ratio", 0.75))
                if ratio >= success_ratio:
                    outcome = "satisfied"
                elif withdrawn > 0:
                    outcome = "partial"
                else:
                    outcome = "missed"

                state["last_outcome"] = outcome
                if withdrawn > 0:
                    state["last_serviced_day"] = today

                comfort_gain = float(rule.get("comfort_gain", 0.0))
                comfort_penalty = float(rule.get("comfort_penalty", comfort_gain))
                comfort_delta = 0.0
                if outcome == "satisfied":
                    comfort_delta = comfort_gain
                elif outcome == "partial":
                    comfort_delta = (comfort_gain * ratio) - (comfort_penalty * (1 - ratio))
                else:
                    comfort_delta = -comfort_penalty

                state["comfort"] = max(
                    0.0,
                    min(max_score, float(state.get("comfort", 0.0)) + comfort_delta),
                )
                building.comfort_score = max(
                    0.0, min(max_score, building.comfort_score + comfort_delta)
                )

                mood_change = 0
                need_changes: Dict[str, int] = {}
                memory_template: Optional[str] = None
                reason_label = rule.get("name") or rule.get("key", "Household Comfort")

                if outcome == "satisfied":
                    mood_change = int(rule.get("mood_bonus", 0))
                    need_changes = {
                        key: int(value)
                        for key, value in (rule.get("need_bonus") or {}).items()
                        if value
                    }
                    memory_template = rule.get("success_memory")
                elif outcome == "partial":
                    mood_change = int(round(rule.get("mood_bonus", 0) * ratio))
                    need_changes = {
                        key: int(round(value * ratio))
                        for key, value in (rule.get("need_bonus") or {}).items()
                        if value
                    }
                    penalty_needs = {
                        key: int(round(value * (1 - ratio)))
                        for key, value in (rule.get("need_penalty") or {}).items()
                        if value
                    }
                    for need_name, delta in penalty_needs.items():
                        need_changes[need_name] = need_changes.get(need_name, 0) + delta
                    memory_template = rule.get("partial_memory") or rule.get("success_memory")
                else:
                    mood_change = int(rule.get("mood_penalty", 0))
                    need_changes = {
                        key: int(value)
                        for key, value in (rule.get("need_penalty") or {}).items()
                        if value
                    }
                    memory_template = rule.get("failure_memory")

                reason = f"{reason_label} ({outcome})"
                for occupant in occupants:
                    if mood_change:
                        occupant.update_mood_score(mood_change, reason)
                    if need_changes:
                        for need_name, delta in need_changes.items():
                            if not delta:
                                continue
                            default_attr = f"NEED_{need_name.upper()}_DEFAULT"
                            baseline = getattr(
                                config,
                                default_attr,
                                (need_cap + need_min) // 2,
                            )
                            current_value = occupant.needs.get(need_name, baseline)
                            occupant.needs[need_name] = max(
                                need_min,
                                min(need_cap, current_value + delta),
                            )
                    if memory_template:
                        occupant.add_memory(
                            memory_template.format(building=building.display_name)
                        )

                shortage = max(0, required - withdrawn)
                update_entry = {
                    "building": building.display_name,
                    "location": tuple(building.location),
                    "rule": rule.get("key", "comfort"),
                    "name": rule.get("name"),
                    "resource": resource_name,
                    "required": required,
                    "withdrawn": withdrawn,
                    "outcome": outcome,
                    "occupants": occupant_count,
                    "ratio": round(ratio, 2),
                    "comfort_score": round(building.comfort_score, 1),
                    "state_comfort": round(float(state.get("comfort", 0.0)), 1),
                }
                if shortage:
                    update_entry["shortage"] = shortage
                updates.append(update_entry)
                summary_counts[outcome] += 1

            comfort_scores.append(building.comfort_score)
            if building.comfort_score >= good_threshold:
                comfortable_households += 1

        average_score = (
            round(sum(comfort_scores) / len(comfort_scores), 1)
            if comfort_scores
            else 0.0
        )
        summary_data = {
            "average_score": average_score,
            "comfortable_households": comfortable_households,
            "total_households": len(comfort_scores),
            "satisfied": summary_counts.get("satisfied", 0),
            "partial": summary_counts.get("partial", 0),
            "missed": summary_counts.get("missed", 0),
            "resource_usage": {
                resource: dict(values) for resource, values in resource_usage.items()
            },
        }

        if summary_counts:
            parts: List[str] = []
            if summary_counts.get("satisfied"):
                parts.append(f"{summary_counts['satisfied']} cozy")
            if summary_counts.get("partial"):
                parts.append(f"{summary_counts['partial']} rationed")
            if summary_counts.get("missed"):
                parts.append(f"{summary_counts['missed']} cold")
            if parts:
                self.world.add_event_log_message(
                    f"Household comforts: {', '.join(parts)}."
                )

        self._latest_household_comforts = updates
        self._latest_household_comfort_summary = summary_data
        if report is not None:
            report["household_comforts"] = updates
            report["household_comfort_summary"] = summary_data
        return updates

    def _resolve_household_evenings(
        self,
        snapshot: Dict[str, Any],
        report: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        stories: List[Dict[str, Any]] = []
        style_moments = getattr(config, "HOUSEHOLD_STYLE_MOMENTS", {})
        default_moments = style_moments.get("general", [])

        for building in self.world.buildings:
            if hasattr(building, "latest_household_story"):
                building.latest_household_story = None

        if not self.world.game_time:
            self._latest_household_vignettes = stories
            snapshot["household_vignettes"] = stories
            return stories

        today = self.world.game_time.current_day
        for building in self.world.buildings:
            if not self._is_residential(building):
                continue

            occupant_objects = [
                self.world.get_character_by_name(name)
                for name in building.occupants
            ]
            occupants: List['Character'] = [char for char in occupant_objects if char]
            if not occupants:
                continue

            style_key = getattr(building, "household_style", None) or self._get_building_tier(building)
            options = style_moments.get(style_key, []) or default_moments
            if not options:
                continue

            moment = random.choice(options)
            host = max(occupants, key=lambda char: getattr(char, "net_worth", 0))
            if not isinstance(moment, dict):
                continue
            group_summary = moment.get("group_summary")
            solo_summary = moment.get("solo_summary")
            if len(occupants) > 1:
                summary_core = group_summary or solo_summary or "shared a quiet evening together"
                subject = self._format_household_label(occupants, host)
                summary_text = f"{subject} {summary_core} at {building.display_name}."
            else:
                summary_core = solo_summary or group_summary or "spent a reflective evening at home"
                summary_text = f"{host.name} {summary_core} at {building.display_name}."

            memory_text = moment.get("memory") or f"Evening at {building.display_name}"
            memory_detail = summary_text
            mood_bonus = int(moment.get("mood_bonus", 0) or 0)
            belonging_bonus = int(moment.get("belonging_bonus", 0) or 0)
            esteem_bonus = int(moment.get("esteem_bonus", 0) or 0)

            for occupant in occupants:
                if mood_bonus:
                    occupant.update_mood_score(mood_bonus, memory_text)
                if belonging_bonus:
                    current_belonging = occupant.needs.get("Belonging", config.NEED_BELONGING_DEFAULT)
                    occupant.needs["Belonging"] = min(
                        config.NEED_SCORE_MAX,
                        current_belonging + belonging_bonus,
                    )
                if esteem_bonus:
                    current_esteem = occupant.needs.get("Esteem", config.NEED_ESTEEM_DEFAULT)
                    occupant.needs["Esteem"] = min(
                        config.NEED_SCORE_MAX,
                        current_esteem + esteem_bonus,
                    )
                occupant.add_memory(f"{memory_text}: {memory_detail}")

            story = {
                "day": today,
                "building": building.display_name,
                "tier": self._get_building_tier(building),
                "style": getattr(building, "household_style", None),
                "summary": summary_text,
                "occupants": [char.name for char in occupants],
            }
            stories.append(story)
            if hasattr(building, "latest_household_story"):
                building.latest_household_story = story
            self.world.add_event_log_message(f"Household Highlight: {summary_text}")
            if report is not None:
                report.setdefault("housing_highlights", []).append(story)

        self._latest_household_vignettes = stories
        snapshot["household_vignettes"] = stories
        return stories

    def _resolve_neighborhood_gatherings(
        self,
        snapshot: Dict[str, Any],
        report: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        gatherings: List[Dict[str, Any]] = []
        block_size = max(1, int(getattr(config, "NEIGHBORHOOD_BLOCK_SIZE", 6)))
        min_households = max(1, int(getattr(config, "NEIGHBORHOOD_MIN_HOUSEHOLDS", 2)))
        base_chance = max(0.0, float(getattr(config, "NEIGHBORHOOD_GATHERING_BASE_CHANCE", 0.35)))
        spirit_weight = float(getattr(config, "NEIGHBORHOOD_SPIRIT_WEIGHT", 0.4))
        extra_bonus = float(getattr(config, "NEIGHBORHOOD_EXTRA_HOUSEHOLD_BONUS", 0.05))
        style_moments = getattr(config, "NEIGHBORHOOD_MOMENTS", {})
        default_moments = style_moments.get("general", [])

        for building in self.world.buildings:
            if hasattr(building, "latest_neighborhood_story"):
                building.latest_neighborhood_story = None

        snapshot["neighborhood_gatherings"] = gatherings
        self._latest_neighborhood_gatherings = gatherings

        if not self.world.game_time:
            return gatherings

        blocks: Dict[Tuple[int, int], List[Building]] = defaultdict(list)
        for building in self.world.buildings:
            if not self._is_residential(building):
                continue
            block_x = building.location[0] // block_size
            block_y = building.location[1] // block_size
            blocks[(block_x, block_y)].append(building)

        today = self.world.game_time.current_day
        community_spirit = float(getattr(self.world, "community_spirit", 0.0))

        for block_key, homes in blocks.items():
            populated_homes: List[Tuple[Building, List['Character']]] = []
            for home in homes:
                occupants = [
                    self.world.get_character_by_name(name)
                    for name in getattr(home, "occupants", [])
                ]
                valid = [char for char in occupants if char]
                if valid:
                    populated_homes.append((home, valid))

            if len(populated_homes) < min_households:
                continue

            attendee_count = sum(len(chars) for _, chars in populated_homes)
            if attendee_count < 2:
                continue

            attendance_bonus = extra_bonus * max(0, len(populated_homes) - min_households)
            trigger_chance = base_chance + community_spirit * spirit_weight + attendance_bonus
            trigger_chance = max(0.0, min(0.95, trigger_chance))
            if random.random() > trigger_chance:
                continue

            host_home, host_residents = max(
                populated_homes,
                key=lambda item: max(
                    (getattr(char, "net_worth", 0) for char in item[1]),
                    default=0,
                ),
            )
            host_character = max(
                host_residents,
                key=lambda char: getattr(char, "net_worth", 0),
            )

            style_key = getattr(host_home, "household_style", None) or self._get_building_tier(host_home)
            moment_options = style_moments.get(style_key, []) or default_moments
            if not moment_options:
                continue

            moment = random.choice(moment_options)
            if not isinstance(moment, dict):
                continue
            neighborhood_label = self._format_neighborhood_label(block_key, block_size)
            summary_template = moment.get("summary") or "Neighbors gathered near {host} in {neighborhood}."

            attendees = sorted({char.name for _, chars in populated_homes for char in chars})
            attendee_count = len(attendees)
            summary_text = summary_template.format(
                host=host_home.display_name,
                host_name=host_character.name,
                neighborhood=neighborhood_label,
                attendee_count=attendee_count,
            )

            memory_text = moment.get("memory") or "Neighborhood gathering"
            memory_detail = summary_text
            mood_bonus = int(moment.get("mood_bonus", 0) or 0)
            belonging_bonus = int(moment.get("belonging_bonus", 0) or 0)
            esteem_bonus = int(moment.get("esteem_bonus", 0) or 0)
            spirit_delta = float(moment.get("spirit_delta", 0.0) or 0.0)

            for _, chars in populated_homes:
                for character in chars:
                    if mood_bonus:
                        character.update_mood_score(mood_bonus, memory_text)
                    if belonging_bonus:
                        current_belonging = character.needs.get(
                            "Belonging",
                            config.NEED_BELONGING_DEFAULT,
                        )
                        character.needs["Belonging"] = min(
                            config.NEED_SCORE_MAX,
                            current_belonging + belonging_bonus,
                        )
                    if esteem_bonus:
                        current_esteem = character.needs.get(
                            "Esteem",
                            config.NEED_ESTEEM_DEFAULT,
                        )
                        character.needs["Esteem"] = min(
                            config.NEED_SCORE_MAX,
                            current_esteem + esteem_bonus,
                        )
                    character.add_memory(f"{memory_text}: {memory_detail}")

            if spirit_delta and hasattr(self.world, "community_spirit"):
                self.world.community_spirit = max(
                    0.0,
                    min(1.0, float(self.world.community_spirit) + spirit_delta),
                )

            gathering = {
                "day": today,
                "neighborhood": neighborhood_label,
                "neighborhood_key": block_key,
                "host": host_home.display_name,
                "host_character": host_character.name,
                "tier": self._get_building_tier(host_home),
                "style": getattr(host_home, "household_style", None),
                "summary": summary_text,
                "attendees": attendees,
                "attending_buildings": [home.display_name for home, _ in populated_homes],
            }
            gatherings.append(gathering)
            if hasattr(host_home, "latest_neighborhood_story"):
                host_home.latest_neighborhood_story = gathering

            self.world.add_event_log_message(
                f"Neighborhood Gathering: {summary_text} (attendees: {attendee_count})"
            )
            if report is not None:
                report.setdefault("neighborhood_gatherings", []).append(gathering)

        if gatherings:
            snapshot["neighborhood_gatherings"] = gatherings
            self._latest_neighborhood_gatherings = gatherings

        return gatherings

    def _evaluate_housing_daily(self, report: Dict[str, Any]) -> Dict[str, Any]:
        self._maintain_household_comforts(report)
        snapshot = self.get_housing_snapshot()
        report["housing"] = snapshot
        self.latest_housing_snapshot = snapshot

        if not self.world.game_time:
            return snapshot

        today = self.world.game_time.current_day
        if self.last_housing_evaluation_day == today:
            return snapshot

        homeless_names = snapshot.get("homeless_characters", [])
        mood_penalty = getattr(config, "MOOD_CHANGE_HOMELESS_SLEEP", -6)
        energy_penalty = getattr(config, "ENERGY_PENALTY_HOMELESS_SLEEP", 8)
        belonging_penalty = getattr(config, "BELONGING_PENALTY_HOMELESS_SLEEP", 4)
        for name in homeless_names:
            character = self.world.get_character_by_name(name)
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
                character = self.world.get_character_by_name(name)
                if not character:
                    continue
                character.update_mood_score(rest_bonus, "Recovered in warm shelter")

        if self._synchronize_estate_expectations(snapshot):
            snapshot = self.latest_housing_snapshot
            report["housing"] = snapshot

        stories = self._resolve_household_evenings(snapshot, report)
        if stories:
            report.setdefault("household_vignettes", stories)
        gatherings = self._resolve_neighborhood_gatherings(snapshot, report)
        if gatherings:
            report.setdefault("neighborhood_gatherings", gatherings)
        self.latest_housing_snapshot = snapshot

        self.last_housing_evaluation_day = today
        return snapshot

    def process_family_dynamics_daily(self) -> List[Dict[str, Any]]:
        family_events: List[Dict[str, Any]] = []

        eligible_singles = [c for c in self.world.characters if not getattr(c, 'romantic_partners', [])]

        # Avoid checking pairs twice
        for i in range(len(eligible_singles)):
            for j in range(i + 1, len(eligible_singles)):
                char1 = eligible_singles[i]
                char2 = eligible_singles[j]

                rel_score1 = char1.relationships.get(char2.name, 0)
                rel_score2 = char2.relationships.get(char1.name, 0)

                romance_threshold = getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_DATE", 25)

                if rel_score1 >= romance_threshold and rel_score2 >= romance_threshold:
                    base_chance = getattr(config, "ROMANCE_DAILY_BASE_CHANCE", 0.08)
                    if random.random() < base_chance:
                        # Start romance
                        if hasattr(char1, 'active_romances'):
                            char1.active_romances.append(char2.name)
                        if hasattr(char2, 'active_romances'):
                            char2.active_romances.append(char1.name)

                        event = {
                            "type": "romance_started",
                            "pair": sorted([char1.name, char2.name]),
                            "day": self.world.game_time.current_day if self.world.game_time else None
                        }
                        family_events.append(event)

        return family_events

    def process_daily_housing(self, daily_report: Dict[str, Any]) -> Dict[str, Any]:
        return self._evaluate_housing_daily(daily_report)
