# game/time.py
from . import config # Import config to access ELECTION_CYCLE_DAYS

class Time:
    def __init__(self, ticks_per_day: int = 24): # Defaulting to 24 ticks per day
        self.current_day = 1
        self.ticks_per_day = ticks_per_day
        self.current_tick = 0
        self.days_until_election: int = config.ELECTION_CYCLE_DAYS

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

    def get_time_of_day(self) -> str:
        # Simple representation for now
        return f"Day {self.current_day}, Tick {self.current_tick}/{self.ticks_per_day}"

    def __str__(self) -> str:
        return self.get_time_of_day()
