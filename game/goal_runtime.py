from enum import IntEnum, auto, Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .goal import Goal, GoalStatus

class GoalPriority(IntEnum):
    CRITICAL = 1
    HIGH = 3
    AMBITION = 4
    MEDIUM_HIGH = 5
    MEDIUM = 6
    ROUTINE = 7
    LOW = 8
    IDLE = 10

class GoalProgress(Enum):
    IN_PROGRESS = auto()
    COMPLETED   = auto()
    FAILED      = auto()

class GoalRecord:
    def __init__(self, goal: 'Goal', start_tick: int, timeout_tick: Optional[int] = None):
        self.goal = goal
        from .goal import GoalStatus
        self.status: GoalStatus = GoalStatus.IN_PROGRESS
        self.start_tick = start_tick
        self.last_update_tick = start_tick
        self.timeout_tick = timeout_tick

    def is_timed_out(self, current_tick: int) -> bool:
        if self.timeout_tick is None:
            return False
        return current_tick >= self.timeout_tick
