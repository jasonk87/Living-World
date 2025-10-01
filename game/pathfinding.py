"""Grid pathfinding helpers used by character navigation."""
from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappush, heappop
from typing import Iterable, List, Optional, Protocol, Sequence, Set, Tuple

Coord = Tuple[int, int]


@dataclass(slots=True)
class Pathfinder:
    """A reusable A* search helper for characters navigating the world grid."""

    max_iterations: int = 5000
    allow_diagonal: bool = True
    _directions: Sequence[Tuple[int, int]] = field(default_factory=lambda: (
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ))

    def find_path(
        self,
        world: "WorldProtocol",
        start: Coord,
        goal: Coord,
        ignore_characters: Optional[Iterable[str]] = None,
    ) -> List[Coord]:
        """Return a path (inclusive) from ``start`` to ``goal`` using A* search.

        ``world`` must expose ``grid_size`` and an ``is_walkable`` helper that
        understands map bounds, terrain, and occupied tiles.
        """

        if start == goal:
            return [start]

        if not self._within_bounds(start, world.grid_size) or not self._within_bounds(goal, world.grid_size):
            return []

        ignore_set: Set[str] = set(ignore_characters or [])

        open_heap: List[Tuple[float, Coord]] = []
        heappush(open_heap, (0.0, start))

        g_costs: dict[Coord, float] = {start: 0.0}
        came_from: dict[Coord, Coord] = {}

        iterations = 0
        goal_reached: Optional[Coord] = None

        while open_heap and iterations < self.max_iterations:
            iterations += 1
            _, current = heappop(open_heap)

            if current == goal:
                goal_reached = current
                break

            for neighbour, step_cost in self._neighbours(world, current, goal, ignore_set):
                tentative_cost = g_costs[current] + step_cost
                if tentative_cost >= g_costs.get(neighbour, float("inf")):
                    continue

                came_from[neighbour] = current
                g_costs[neighbour] = tentative_cost
                priority = tentative_cost + self._heuristic(neighbour, goal)
                heappush(open_heap, (priority, neighbour))

        if goal_reached is None:
            return []

        return self._reconstruct_path(came_from, goal_reached)

    def _neighbours(
        self,
        world: "WorldProtocol",
        current: Coord,
        goal: Coord,
        ignore_characters: Set[str],
    ) -> List[Tuple[Coord, float]]:
        neighbours: List[Tuple[Coord, float]] = []
        dirs = self._directions if self.allow_diagonal else self._directions[:4]
        for dx, dy in dirs:
            nx, ny = current[0] + dx, current[1] + dy
            if not self._within_bounds((nx, ny), world.grid_size):
                continue
            if not world.is_walkable(nx, ny, ignore_characters=ignore_characters, goal=goal):
                continue
            if dx != 0 and dy != 0:
                step_cost = 1.41421356237  # sqrt(2) for diagonals
            else:
                step_cost = 1.0
            neighbours.append(((nx, ny), step_cost))
        return neighbours

    @staticmethod
    def _heuristic(a: Coord, b: Coord) -> float:
        # Octile distance to account for diagonals
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return max(dx, dy) + (2 ** 0.5 - 1) * min(dx, dy)

    @staticmethod
    def _reconstruct_path(came_from: dict[Coord, Coord], goal: Coord) -> List[Coord]:
        path: List[Coord] = [goal]
        current = goal
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    @staticmethod
    def _within_bounds(coord: Coord, grid_size: Tuple[int, int]) -> bool:
        x, y = coord
        return 0 <= x < grid_size[0] and 0 <= y < grid_size[1]


class WorldProtocol(Protocol):
    """Minimal interface expected by :class:`Pathfinder`."""

    grid_size: Tuple[int, int]

    def is_walkable(
        self,
        x: int,
        y: int,
        ignore_characters: Optional[Iterable[str]] = None,
        goal: Optional[Coord] = None,
    ) -> bool:
        """Return ``True`` if the tile can be occupied by the mover."""
