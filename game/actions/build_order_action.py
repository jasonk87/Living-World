from __future__ import annotations
from typing import TYPE_CHECKING
from .action import Action, ActionStatus
from .. import config
from ..data import STRUCTURE_BLUEPRINTS
from ..building import Building

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class BuildOrderAction(Action):
    """
    An action for a character to execute a build order.
    This is a complex action that involves multiple steps:
    1. Gathering materials
    2. Moving to the build site
    3. Constructing the building
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        if not self.character.active_build_order_id or not self.character.current_building_project or not self.character.building_site_target:
            self.character._reset_building_state()
            return ActionStatus.FAILED

        order = world.get_work_order_by_id(self.character.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.character.name:
            self.character._reset_building_state()
            return ActionStatus.FAILED

        structure_blueprint_key = order.details["structure_type"]
        structure_bp_data = STRUCTURE_BLUEPRINTS.get(structure_blueprint_key)
        if not structure_bp_data:
            order.status = "Denied"
            order.denial_reason = f"Unknown blueprint {structure_blueprint_key}"
            self.character._reset_building_state()
            return ActionStatus.FAILED

        if not self.character.materials_gathered_for_build:
            return self._gather_materials(world, structure_bp_data)
        else:
            return self._construct_building(world, order, structure_bp_data)

    def _gather_materials(self, world: World, structure_bp_data: dict) -> ActionStatus:
        current_project_mats_fully_in_inventory = True
        next_resource_to_target_for_project = None
        for res_name, total_quantity_needed_for_project in structure_bp_data["required_resources"].items():
            if self.character.inventory.get(res_name, 0) < total_quantity_needed_for_project:
                current_project_mats_fully_in_inventory = False
                next_resource_to_target_for_project = res_name
                break

        if current_project_mats_fully_in_inventory:
            self.character.materials_gathered_for_build = True
            self.character.add_memory(f"All materials for {self.character.current_building_project} now in inventory.")
            return ActionStatus.RUNNING # Continue to construction phase

        if next_resource_to_target_for_project:
            if self.character.get_inventory_load() >= self.character.max_inventory_items:
                if (self.character.x, self.character.y) != self.character.building_site_target:
                    self.character.add_memory(f"Inventory full. Have some materials for {self.character.current_building_project}, heading to site.")
                    self.character.move_towards(self.character.building_site_target[0], self.character.building_site_target[1], world)
                    return ActionStatus.RUNNING
                else:
                    self.character.add_memory(f"At site with full inventory, but still need more materials.")
                    return ActionStatus.RUNNING # Stuck for now

            needed_qty_of_this_type = structure_bp_data["required_resources"][next_resource_to_target_for_project] - self.character.inventory.get(next_resource_to_target_for_project, 0)
            self.character.resource_to_fetch = {
                "name": next_resource_to_target_for_project,
                "quantity": needed_qty_of_this_type,
                "target_stockpile_name": None
            }
            return self._fetch_resource(world)

        return ActionStatus.RUNNING

    def _fetch_resource(self, world: World) -> ActionStatus:
        if not self.character.resource_to_fetch:
            return ActionStatus.FAILED

        res_name = self.character.resource_to_fetch["name"]
        needed_qty = self.character.resource_to_fetch["quantity"]

        target_sp_name = self.character.resource_to_fetch.get("target_stockpile_name")
        stockpile_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None

        if not stockpile_to_fetch or stockpile_to_fetch.inventory.get(res_name, 0) == 0:
            suitable_stockpiles = [sp for sp in world.stockpiles if sp.inventory.get(res_name, 0) > 0 and sp.is_allowed(res_name)]
            if not suitable_stockpiles:
                self.character.add_memory(f"Need {res_name} for building, but no stockpile has it.")
                return ActionStatus.RUNNING # Stuck until resources are available
            stockpile_to_fetch = suitable_stockpiles[0]
            self.character.resource_to_fetch["target_stockpile_name"] = stockpile_to_fetch.name

        stockpile_pos = (stockpile_to_fetch.rect[0], stockpile_to_fetch.rect[1])

        if (self.character.x, self.character.y) != stockpile_pos:
            self.character.move_towards(stockpile_pos[0], stockpile_pos[1], world)
            if stockpile_to_fetch.inventory.get(res_name, 0) == 0:
                self.character.resource_to_fetch["target_stockpile_name"] = None
            return ActionStatus.RUNNING

        can_carry_now = self.character.max_inventory_items - self.character.get_inventory_load()
        qty_to_take_this_trip = min(needed_qty, stockpile_to_fetch.inventory.get(res_name, 0), can_carry_now)

        if qty_to_take_this_trip > 0:
            success, actual_taken = stockpile_to_fetch.remove_item(res_name, qty_to_take_this_trip)
            if success and actual_taken > 0:
                self.character.inventory[res_name] = self.character.inventory.get(res_name, 0) + actual_taken
                self.character.resource_to_fetch["quantity"] -= actual_taken
                if self.character.resource_to_fetch["quantity"] <= 0:
                    self.character.resource_to_fetch = None

        return ActionStatus.RUNNING

    def _construct_building(self, world: World, order, structure_bp_data: dict) -> ActionStatus:
        if (self.character.x, self.character.y) != self.character.building_site_target:
            self.character.move_towards(self.character.building_site_target[0], self.character.building_site_target[1], world)
            return ActionStatus.RUNNING

        target_building = world.get_building_at(self.character.building_site_target[0], self.character.building_site_target[1])

        if not target_building:
            committed_resources_display = {}
            for res_name, res_needed_total in structure_bp_data["required_resources"].items():
                if self.character.inventory.get(res_name, 0) < res_needed_total:
                    self.character.materials_gathered_for_build = False
                    self.character.resource_to_fetch = None
                    return ActionStatus.RUNNING

                self.character.inventory[res_name] -= res_needed_total
                if self.character.inventory[res_name] <= 0: del self.character.inventory[res_name]
                committed_resources_display[res_name] = res_needed_total

            target_building = Building(
                structure_type=order.details["structure_type"],
                display_name=structure_bp_data["display_name"],
                location=self.character.building_site_target,
                size=structure_bp_data["size"],
                required_resources_for_blueprint=structure_bp_data["required_resources"].copy(),
                functionality=structure_bp_data.get("functionality"),
                required_skill=structure_bp_data.get("required_skill"),
                construction_phases=structure_bp_data.get("construction_phases"),
                map_char_initial=structure_bp_data.get("map_char_initial", "?"),
                map_char_complete=structure_bp_data.get("map_char_complete", "B")
            )
            world.add_building(target_building)

        if target_building and not target_building.is_operational:
            base_build_progress = 1.0
            mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.character.mood, 1.0)
            progress_this_tick = base_build_progress * mood_productivity_modifier
            construction_skill_level = self.character.skills.get("Construction", {}).get("level", 0)
            progress_this_tick *= (1 + construction_skill_level * 0.1)
            actual_progress = target_building.work_on(max(0, progress_this_tick))
            if actual_progress > 0:
                self.character._grant_skill_experience("Construction", actual_progress * 0.5, world)

            if target_building.is_operational:
                order.status = "Completed"
                self.character._reset_building_state()
                return ActionStatus.COMPLETED

        return ActionStatus.RUNNING
