from __future__ import annotations
from typing import TYPE_CHECKING
import random
from .action import Action, ActionStatus
from .. import config
from ..data import BLUEPRINTS
from ..goal import Goal, GoalType

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World

class CraftOrderAction(Action):
    """
    An action for a character to execute a craft order.
    This is a complex action that involves multiple steps:
    1. Gathering materials
    2. Moving to a workshop (or current location)
    3. Crafting the item(s)
    4. Hauling the item(s) to a stockpile
    """
    def __init__(self, character: Character):
        super().__init__(character)

    def execute(self, world: World) -> ActionStatus:
        order = world.get_work_order_by_id(self.character.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.character.name:
            self.character._reset_crafting_state()
            return ActionStatus.FAILED

        item_name = order.details["item_name"]
        item_qty_total = order.details["quantity"]
        blueprint = BLUEPRINTS.get(item_name)
        if not blueprint:
            order.status = "Denied"
            order.denial_reason = f"Unknown blueprint for {item_name}"
            self.character._reset_crafting_state()
            return ActionStatus.FAILED

        if not self.character.materials_gathered_for_wo:
            return self._gather_materials(world, blueprint)

        if not self.character.items_crafted_for_wo:
            return self._craft_items(world, blueprint, item_name, item_qty_total)

        if self.character.items_crafted_for_wo:
            return self._haul_items(world, order, item_name)

        return ActionStatus.RUNNING

    def _gather_materials(self, world: World, blueprint: dict) -> ActionStatus:
        for res, req_qty_pu in blueprint["required_resources"].items():
            if self.character.inventory.get(res, 0) < req_qty_pu:
                self.character.resource_to_fetch = {"name": res, "quantity": req_qty_pu - self.character.inventory.get(res, 0)}
                return self._fetch_resource(world, blueprint)

        self.character.materials_gathered_for_wo = True
        self.character.resource_to_fetch = None
        return ActionStatus.RUNNING

    def _fetch_resource(self, world: World, blueprint: dict) -> ActionStatus:
        if not self.character.resource_to_fetch:
            return ActionStatus.FAILED

        res_name = self.character.resource_to_fetch["name"]
        if self.character.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]:
            self.character.resource_to_fetch = None
            return ActionStatus.RUNNING

        target_sp_name = self.character.resource_to_fetch.get("target_stockpile_name")
        sp_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None

        if not sp_to_fetch or sp_to_fetch.inventory.get(res_name, 0) == 0:
            suitable_sps = [sp for sp in world.get_stockpiles_for_resource(res_name) if sp.inventory.get(res_name, 0) > 0]
            if not suitable_sps:
                return ActionStatus.RUNNING # Stuck
            sp_to_fetch = suitable_sps[0]
            self.character.resource_to_fetch["target_stockpile_name"] = sp_to_fetch.name

        spot = (sp_to_fetch.rect[0], sp_to_fetch.rect[1])
        if (self.character.x, self.character.y) != spot:
            self.character.move_towards(spot[0], spot[1], world)
            return ActionStatus.RUNNING

        max_can_carry = self.character.max_inventory_items - self.character.get_inventory_load()
        needed_for_this_res = blueprint["required_resources"][res_name] - self.character.inventory.get(res_name, 0)
        qty_to_take = min(needed_for_this_res, sp_to_fetch.inventory.get(res_name, 0), max_can_carry)

        if qty_to_take > 0:
            s, qty_taken = sp_to_fetch.remove_item(res_name, qty_to_take)
            if s and qty_taken > 0:
                self.character.inventory[res_name] = self.character.inventory.get(res_name, 0) + qty_taken
                if self.character.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]:
                    self.character.resource_to_fetch = None

        return ActionStatus.RUNNING

    def _craft_items(self, world: World, blueprint: dict, item_name: str, item_qty_total: int) -> ActionStatus:
        if not self.character.workshop_location:
            self.character.workshop_location = (self.character.x, self.character.y)

        if (self.character.x, self.character.y) != self.character.workshop_location:
            self.character.move_towards(self.character.workshop_location[0], self.character.workshop_location[1], world)
            return ActionStatus.RUNNING

        progress_this_tick = 1
        # Trait-based modifications to work speed
        if "Lazy" in self.character.traits and "Focused" not in self.character.traits:
            if random.random() < config.LAZY_TRAIT_SKIP_CHANCE:
                progress_this_tick = 0
                self.character.add_memory("Felt lazy and slacked off during crafting.")

        if "Diligent" in self.character.traits:
            if random.random() < config.DILIGENT_TRAIT_BONUS_CHANCE:
                progress_this_tick += 1
                self.character.add_memory("Felt diligent and made extra progress on my craft.")

        self.character.crafting_progress += progress_this_tick

        craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)

        if self.character.crafting_progress >= craft_time_per_unit:
            for res, req_qty_per_unit in blueprint["required_resources"].items():
                self.character.inventory[res] -= req_qty_per_unit
                if self.character.inventory[res] <= 0: self.character.inventory.pop(res, None)

            self.character.inventory[item_name] = self.character.inventory.get(item_name, 0) + 1
            self.character.crafting_progress = 0  # Reset for next item or just reset overflow
            self.character.materials_gathered_for_wo = False # Need to re-gather for next unit

            if self.character.inventory.get(item_name, 0) >= item_qty_total:
                self.character.items_crafted_for_wo = True

        return ActionStatus.RUNNING

    def _haul_items(self, world: World, order, item_name: str) -> ActionStatus:
        items_to_haul_qty = self.character.inventory.get(item_name, 0)
        if items_to_haul_qty > 0:
            haul_params = {"resource": item_name, "quantity": items_to_haul_qty, "for_wo_id": order.order_id, "is_crafted_item": True}
            self.character.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.character.name, originator_id=self.character.name, parameters=haul_params)
            return ActionStatus.COMPLETED # Let the new goal be handled
        else:
            order.status = "Completed"
            self.character._reset_crafting_state()
            return ActionStatus.COMPLETED
