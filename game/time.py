# game/time.py
from typing import Dict, Any, List

from . import config # Import config to access ELECTION_CYCLE_DAYS

_DEFAULT_DAY_PHASES: List[Dict[str, Any]] = [
    {"key": "day", "name": "Day", "start_tick": 0, "description": "Generic daylight hours."},
]

class Time:
    def __init__(self, ticks_per_day: int = 24): # Defaulting to 24 ticks per day
        self.current_day = 1
        self.ticks_per_day = ticks_per_day
        self.current_tick = 0
        self.days_until_election: int = config.ELECTION_CYCLE_DAYS
        self._phase_schedule: List[Dict[str, Any]] = self._build_phase_schedule()
        self._cached_phase: Dict[str, Any] = self._phase_schedule[0]
        self._just_set_time_to_new_day = False

    def tick(self) -> bool:
        self.current_tick += 1
        new_day_started = False
        if self.current_tick >= self.ticks_per_day:
            self.current_tick = 0
            self.current_day += 1
            new_day_started = True
            if self.days_until_election > 0: # Ensure it doesn't go indefinitely negative if not reset
                self.days_until_election -= 1
        return new_day_started

    def set_time(self, day: int, tick: int):
        """Sets the game time to a specific day and tick."""
        self.current_day = day
        self.current_tick = tick
        if self.current_tick == 0:
            self._just_set_time_to_new_day = True

        # Recalculate days_until_election
        days_passed = self.current_day - 1
        days_into_cycle = days_passed % config.ELECTION_CYCLE_DAYS
        self.days_until_election = config.ELECTION_CYCLE_DAYS - days_into_cycle

    def is_new_day(self) -> bool:
        """Checks if the current tick is the start of a new day."""
        if getattr(self, "_just_set_time_to_new_day", False):
            self._just_set_time_to_new_day = False
            return True
        return self.current_tick == 0

    def get_time_of_day(self) -> str:
        # Simple representation for now
        return f"Day {self.current_day}, Tick {self.current_tick}/{self.ticks_per_day}"

    def get_absolute_tick(self) -> int:
        """Returns the total number of ticks elapsed since the start of the simulation."""
        return (self.current_day - 1) * self.ticks_per_day + self.current_tick

    def advance_ticks(self, num_ticks: int):
        """Advances the game time by a specified number of ticks."""
        for _ in range(num_ticks):
            self.tick()

    # --- Phase Helpers ---

    def _build_phase_schedule(self) -> List[Dict[str, Any]]:
        configured_phases = getattr(config, "DAY_PHASE_CONFIG", _DEFAULT_DAY_PHASES)
        if not configured_phases:
            return list(_DEFAULT_DAY_PHASES)
        ordered = sorted(configured_phases, key=lambda entry: entry.get("start_tick", 0))
        return ordered

    def refresh_phase_schedule(self) -> None:
        self._phase_schedule = self._build_phase_schedule()

    def get_phase(self) -> Dict[str, Any]:
        if not self._phase_schedule:
            self.refresh_phase_schedule()

        selected_phase = self._phase_schedule[0]
        for phase in self._phase_schedule:
            if self.current_tick >= phase.get("start_tick", 0):
                selected_phase = phase
            else:
                break

        if selected_phase != self._cached_phase:
            self._cached_phase = selected_phase
        return selected_phase

    def get_phase_name(self) -> str:
        return self.get_phase().get("name", "")

    def get_phase_key(self) -> str:
        return self.get_phase().get("key", "")

    def set_phase(self, phase_key: str):
        for phase in self._phase_schedule:
            if phase.get("key") == phase_key:
                self.current_tick = phase.get("start_tick", 0)
                self._cached_phase = phase
                return

    def __str__(self) -> str:
        return self.get_time_of_day()
