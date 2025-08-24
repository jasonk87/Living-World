from __future__ import annotations
import random
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from ..goal import Goal, GoalType
from ..work_order import WorkOrder
from ..data import STRUCTURE_BLUEPRINTS
from .. import config

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class OverseeSettlementAction(Action):
    """
    An action for a mayor to oversee the settlement.
    This involves checking resources, managing appointments, and initiating projects.
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        if self.character.job != "Mayor":
            return ActionStatus.FAILED

        if random.random() < 0.1:
            self._check_resources(world)

        if random.random() < 0.05:
            self._manage_appointments(world)

        if random.random() < 0.02:
            self._initiate_project(world)

        return ActionStatus.COMPLETED # This is an ongoing task

    def _check_resources(self, world: World):
        key_resources = ["Wood", "Stone"]
        if world.ledger:
            for resource_name in key_resources:
                total_count = world.ledger.get_total_resource_count(resource_name)
                if total_count < config.MAYOR_RESOURCE_LOW_THRESHOLD:
                    self.character.add_memory(f"Mayor {self.character.name} notes: {resource_name} levels are low ({total_count}).")

    def _manage_appointments(self, world: World):
        key_positions = ["Sheriff", "Chief Medical Officer", "Manager"]
        for position_job_title in key_positions:
            current_holder = None
            for char in world.characters:
                if char.job == position_job_title:
                    current_holder = char
                    break
            if not current_holder:
                # Simplified hiring logic
                for char_to_check in world.characters:
                    if char_to_check.job == "Unemployed":
                        char_to_check.job = position_job_title
                        self.character.add_subordinate(char_to_check.name)
                        char_to_check.set_supervisor(self.character.name)
                        break

    def _initiate_project(self, world: World):
        project_structure_type = "wooden_hut"
        structure_bp = STRUCTURE_BLUEPRINTS.get(project_structure_type)
        if structure_bp and world.game_time:
            build_location = None
            for r in range(world.grid_size[0] - structure_bp["size"][1] + 1):
                for c in range(world.grid_size[1] - structure_bp["size"][0] + 1):
                    can_place = True
                    for dr in range(structure_bp["size"][1]):
                        for dc in range(structure_bp["size"][0]):
                            if world.get_tile(c + dc, r + dr) != "Grass" or world.get_building_at(c + dc, r + dr):
                                can_place = False
                                break
                        if not can_place:
                            break
                    if can_place:
                        build_location = (c, r)
                        break
                if build_location:
                    break

            if build_location:
                order_details = {
                    "structure_type": project_structure_type,
                    "location": build_location,
                    "required_resources": structure_bp["required_resources"].copy()
                }
                new_build_order = WorkOrder(order_type="BuildStructure", details=order_details,
                                            priority=3, creation_day=world.game_time.current_day)
                world.add_work_order(new_build_order)
