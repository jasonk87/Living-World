# game/building.py
from typing import Tuple, Dict, Optional, List, Any

class Building:
    def __init__(
        self,
        structure_type: str,
        display_name: str,
        location: Tuple[int, int],
        size: Tuple[int, int],
        required_resources: Dict[str, int],
        functionality: Optional[Dict[str, Any]],
        required_skill: Optional[Dict[str, Any]],
        construction_phases: Optional[List[Dict[str, Any]]] = None,  # For phased construction
        map_char_initial: str = 'X',  # Default map character while construction is underway
        map_char_complete: str = 'B',  # Default for completed building
        build_time: int = 0,  # build_time might be deprecated if phases define all work
        tile_layout: Optional[List[Any]] = None,
        tile_palette: Optional[Dict[str, str]] = None,
        amenities: Optional[List[str]] = None,
        household_style: Optional[str] = None,
    ):

        self.structure_type = structure_type
        self.display_name = display_name
        self.location = location
        self.size = size
        self.required_resources = required_resources
        self.functionality = functionality if functionality is not None else {}
        self.required_skill = required_skill if required_skill is not None else {}

        self.phases = []
        if construction_phases:
            self.phases = construction_phases
        elif build_time > 0 : # Fallback if old build_time is provided and no phases
            self.phases = [{"name": "Completion", "work_required": build_time, "map_char_during": map_char_initial}]
        else: # Default if neither phases nor build_time specified
            self.phases = [{"name": "Completion", "work_required": 1, "map_char_during": map_char_initial}]

        self.current_phase_index = 0
        self.current_phase_progress = 0.0

        # Calculate total build time from phases if not already set by old system
        if construction_phases or not build_time: # Prioritize phases for build_time calculation
            self.build_time = sum(phase.get("work_required", 0) for phase in self.phases)
            if self.build_time == 0 and self.phases: # Ensure at least 1 total work if phases exist but sum to 0
                self.build_time = 1
                if self.phases[0]: self.phases[0]["work_required"] = 1
        else: # Use provided build_time if phases are not defined (legacy support)
             self.build_time = build_time


        self.current_progress = 0.0  # Overall progress across all phases
        self.is_operational = False
        self.occupants: List[str] = []

        # These are set by the blueprint but stored on instance for get_current_map_char
        self.map_char_initial = map_char_initial
        self.map_char_complete = map_char_complete

        self.tile_palette: Dict[str, str] = dict(tile_palette or {})
        self.tile_layout: List[List[str]] = self._normalize_tile_layout(tile_layout, self.tile_palette)
        self.amenities: List[str] = list(amenities or [])
        self.household_style: Optional[str] = household_style
        self.latest_household_story: Optional[Dict[str, Any]] = None
        self.latest_neighborhood_story: Optional[Dict[str, Any]] = None


    def __str__(self):
        phase_info = ""
        if not self.is_operational and self.current_phase_index < len(self.phases):
            current_phase = self.phases[self.current_phase_index]
            phase_name = current_phase.get('name', f'Phase {self.current_phase_index + 1}')
            phase_work = current_phase.get('work_required', 0)
            phase_info = f" (Phase: {phase_name} {self.current_phase_progress:.1f}/{phase_work:.1f})"

        # Ensure build_time is not zero to avoid division by zero if progress is also zero
        total_work_display = self.build_time if self.build_time > 0 else 1.0

        return (f"{self.display_name} at {self.location} "
                f"({self.current_progress:.1f}/{total_work_display:.1f} built{phase_info}, Op: {self.is_operational})")

    def work_on(self, amount: float) -> float:
        if self.is_operational:
            return 0.0

        work_applied_this_tick = 0.0

        while amount > 0 and not self.is_operational:
            if self.current_phase_index >= len(self.phases): # Should not happen if is_operational is set correctly
                self.is_operational = True # Ensure it's set if phases are exhausted
                print(f"Warning: {self.display_name} at {self.location} ran out of phases but wasn't operational. Marking operational.")
                break

            current_phase_def = self.phases[self.current_phase_index]
            work_needed_for_current_phase = current_phase_def.get("work_required", 1) - self.current_phase_progress

            can_apply_to_phase = min(amount, work_needed_for_current_phase)

            self.current_phase_progress += can_apply_to_phase
            self.current_progress += can_apply_to_phase
            work_applied_this_tick += can_apply_to_phase
            amount -= can_apply_to_phase

            if self.current_phase_progress >= current_phase_def.get("work_required", 1):
                self.current_phase_progress = current_phase_def.get("work_required", 1)

                # Log phase completion (could be moved to Character or World for better context)
                # print(f"Phase '{current_phase_def.get('name', 'Unnamed')}' for {self.display_name} completed.")

                self.current_phase_index += 1
                self.current_phase_progress = 0.0 # Reset for next phase

                if self.current_phase_index >= len(self.phases):
                    self.is_operational = True
                    self.current_progress = self.build_time # Ensure overall progress is maxed out
                    # print(f"{self.display_name} at {self.location} is now complete and operational!")
                    break

        return work_applied_this_tick

    def get_current_map_char(self) -> str:
        if self.is_operational:
            return self.map_char_complete
        elif self.current_phase_index < len(self.phases):
            current_phase = self.phases[self.current_phase_index]
            return current_phase.get("map_char_during", self.map_char_initial)
        else:
            # This case means phases are done, building should be operational.
            # If somehow it's not, return complete char. Or could be an error/fallback.
            return self.map_char_complete

    def get_current_phase_name(self) -> str:
        if self.is_operational:
            return "Completed"
        if self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index].get("name", f"Phase {self.current_phase_index + 1}")
        return "Unknown Phase"

    def get_tiles_occupied(self) -> List[Tuple[int, int]]:
        tiles = []
        x_base, y_base = self.location
        width, height = self.size
        for r_offset in range(height):
            for c_offset in range(width):
                tiles.append((x_base + c_offset, y_base + r_offset))
        return tiles

    def get_tile_label(self, x: int, y: int) -> Optional[str]:
        if not self.tile_layout:
            return None
        offset_x = x - self.location[0]
        offset_y = y - self.location[1]
        if offset_y < 0 or offset_y >= len(self.tile_layout):
            return None
        row = self.tile_layout[offset_y]
        if offset_x < 0 or offset_x >= len(row):
            return None
        label = row[offset_x]
        if label in self.tile_palette:
            return self.tile_palette[label]
        return label

    def get_tile_layout(self) -> List[List[str]]:
        return [list(row) for row in self.tile_layout]

    def is_inside(self, char_x: int, char_y: int) -> bool:
        building_tiles = self.get_tiles_occupied()
        return (char_x, char_y) in building_tiles

    def add_occupant(self, char_name: str):
        if char_name not in self.occupants:
            self.occupants.append(char_name)

    def remove_occupant(self, char_name: str):
        if char_name in self.occupants:
            self.occupants.remove(char_name)

    def to_dict(self):
        """Converts the building object to a dictionary for serialization."""
        return {
            "structure_type": self.structure_type,
            "display_name": self.display_name,
            "location": self.location,
            "size": self.size,
            "is_operational": self.is_operational,
            "current_progress": self.current_progress,
            "build_time": self.build_time,
            "map_char": self.get_current_map_char(),
            "current_phase_name": self.get_current_phase_name(),
            "occupants": self.occupants,
            "tile_layout": self.get_tile_layout(),
            "amenities": list(self.amenities),
            "household_style": self.household_style,
        }

    @staticmethod
    def _normalize_tile_layout(
        layout: Optional[List[Any]],
        palette: Optional[Dict[str, str]] = None,
    ) -> List[List[str]]:
        if not layout:
            return []
        normalized: List[List[str]] = []
        for row in layout:
            if isinstance(row, str):
                entries = list(row)
            else:
                entries = list(row)
            normalized_row: List[str] = []
            for entry in entries:
                if isinstance(entry, str) and palette and entry in palette:
                    normalized_row.append(palette[entry])
                else:
                    normalized_row.append(entry)
            normalized.append(normalized_row)
        return normalized
