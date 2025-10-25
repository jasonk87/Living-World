from __future__ import annotations
import random
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .world import World

class Animal:
    def __init__(self, name: str, x: int, y: int, health: int, resources: Dict[str, int], speed: int, map_char: str):
        self.name = name
        self.x = x
        self.y = y
        self.health = health
        self.resources = resources
        self.speed = speed
        self.map_char = map_char

    @classmethod
    def from_blueprint(cls, blueprint: Dict, x: int, y: int) -> Animal:
        return cls(
            name=blueprint["name"],
            x=x,
            y=y,
            health=blueprint["health"],
            resources=blueprint["resources"],
            speed=blueprint["speed"],
            map_char=blueprint["map_char"]
        )

    def move(self, world: World):
        for _ in range(self.speed):
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            new_x, new_y = self.x + dx, self.y + dy

            if world.is_walkable(new_x, new_y):
                self.x = new_x
                self.y = new_y
