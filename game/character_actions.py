# game/character_actions.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any
import random

from .llm_integration import generate_dialogue
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from . import config
from .goal import Goal, GoalType, DEFAULT_IDLE_GOAL, create_goal_from_job
from .work_order import WorkOrder
from .rumor import Rumor
from .building import Building
from .events import Event, EventType

if TYPE_CHECKING:
    from .world import World
    from .character import Character


class CharacterActionsMixin:
    """
    A mixin class to hold all the _execute_* methods for the Character class.
    This separates the action logic from the character's state definition.
    """

    def _execute_fetch_resource_for_build(self, world: 'World'):
        if not self.resource_to_fetch or not self.resource_to_fetch.get("name") or self.resource_to_fetch.get("quantity", 0) <= 0:
            self.resource_to_fetch = None # Invalid state or nothing to fetch
            return

        res_name = self.resource_to_fetch["name"]
        needed_qty = self.resource_to_fetch["quantity"]

        # Find a stockpile that has the resource
        target_sp_name = self.resource_to_fetch.get("target_stockpile_name")
        stockpile_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None

        if not stockpile_to_fetch or stockpile_to_fetch.inventory.get(res_name, 0) == 0:
            # Find a new stockpile if current one is invalid or empty
            suitable_stockpiles = [sp for sp in world.stockpiles if sp.inventory.get(res_name, 0) > 0 and sp.is_allowed(res_name)]
            if not suitable_stockpiles:
                self.add_memory(f"Need {res_name} for building, but no stockpile has it.")
                # Cannot proceed with this resource, _execute_build_order will be stuck on it.
                return
            stockpile_to_fetch = suitable_stockpiles[0] # Simplistic: take the first one
            self.resource_to_fetch["target_stockpile_name"] = stockpile_to_fetch.name

        stockpile_pos = (stockpile_to_fetch.rect[0], stockpile_to_fetch.rect[1]) # Assuming rect[0],rect[1] is access point

        if (self.x, self.y) != stockpile_pos:
            self.move_towards(stockpile_pos[0], stockpile_pos[1], world)
            # If stockpile emptied while character was moving
            if stockpile_to_fetch.inventory.get(res_name, 0) == 0:
                self.resource_to_fetch["target_stockpile_name"] = None # Will find new one next tick
            return

        # At the stockpile
        can_carry_now = self.max_inventory_items - self.get_inventory_load()
        qty_to_take_this_trip = min(needed_qty, stockpile_to_fetch.inventory.get(res_name, 0), can_carry_now)

        if qty_to_take_this_trip <= 0:
            if can_carry_now <= 0:
                self.add_memory(f"Inventory still full when trying to take {res_name}.")
            # else: (stockpile empty or needed_qty met by current inv - latter shouldn't happen due to initial check)
            # This means either inv is full, or stockpile just emptied.
            # If inv full, _execute_build_order needs to handle it.
            # If stockpile empty, it will be re-targeted next tick.
            return

        success, actual_taken = stockpile_to_fetch.remove_item(res_name, qty_to_take_this_trip)
        if success and actual_taken > 0:
            self.inventory[res_name] = self.inventory.get(res_name, 0) + actual_taken
            self.resource_to_fetch["quantity"] -= actual_taken
            self.add_memory(f"Fetched {actual_taken} {res_name} from {stockpile_to_fetch.name}. (Remaining for type: {self.resource_to_fetch['quantity']})")

            if self.resource_to_fetch["quantity"] <= 0:
                self.add_memory(f"Finished gathering all required {res_name} for the project.")
                self.resource_to_fetch = None # Done with this resource type for the project
        elif not success:
            self.add_memory(f"Failed to take {res_name} from {stockpile_to_fetch.name} (was available).")
            self.resource_to_fetch["target_stockpile_name"] = None # Force re-evaluation of stockpile

    def _execute_build_order(self, world: 'World'):
        if not self.active_build_order_id or not self.current_building_project or not self.building_site_target:
            self._reset_building_state()
            self.current_goal = create_goal_from_job(self.job, self.name) or DEFAULT_IDLE_GOAL(self.name)
            return

        order = world.get_work_order_by_id(self.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name:
            self._reset_building_state()
            self.current_goal = create_goal_from_job(self.job, self.name) or DEFAULT_IDLE_GOAL(self.name)
            return

        structure_blueprint_key = order.details["structure_type"]
        structure_bp_data = STRUCTURE_BLUEPRINTS.get(structure_blueprint_key)
        if not structure_bp_data:
            order.status = "Denied"; order.denial_reason = f"Unknown blueprint {structure_blueprint_key}"
            self._reset_building_state(); self.current_goal = DEFAULT_IDLE_GOAL(self.name); return

        if not self.materials_gathered_for_build:
            current_project_mats_fully_in_inventory = True
            next_resource_to_target_for_project = None
            for res_name, total_quantity_needed_for_project in structure_bp_data["required_resources"].items():
                if self.inventory.get(res_name, 0) < total_quantity_needed_for_project:
                    current_project_mats_fully_in_inventory = False
                    next_resource_to_target_for_project = res_name
                    break

            if current_project_mats_fully_in_inventory:
                self.materials_gathered_for_build = True
                self.resource_to_fetch = None
                self.add_memory(f"All materials for {self.current_building_project} now in inventory.")
            elif next_resource_to_target_for_project:
                if self.get_inventory_load() >= self.max_inventory_items:
                    if (self.x, self.y) != self.building_site_target:
                        self.add_memory(f"Inventory full. Have some materials for {self.current_building_project}, heading to site.")
                        self.move_towards(self.building_site_target[0], self.building_site_target[1], world)
                        return
                    else:
                        self.add_memory(f"At site ({self.x},{self.y}) with full inventory. Still need {next_resource_to_target_for_project} for {self.current_building_project}. Heading to gather more.")
                        needed_qty_of_this_type = structure_bp_data["required_resources"][next_resource_to_target_for_project] - self.inventory.get(next_resource_to_target_for_project, 0)
                        self.resource_to_fetch = {
                            "name": next_resource_to_target_for_project,
                            "quantity": needed_qty_of_this_type,
                            "target_stockpile_name": None
                        }
                        self._execute_fetch_resource_for_build(world)
                        return
                else:
                    needed_qty_of_this_type = structure_bp_data["required_resources"][next_resource_to_target_for_project] - self.inventory.get(next_resource_to_target_for_project, 0)
                    self.resource_to_fetch = {
                        "name": next_resource_to_target_for_project,
                        "quantity": needed_qty_of_this_type,
                        "target_stockpile_name": None
                    }
                    self.add_memory(f"Targeting {needed_qty_of_this_type} {next_resource_to_target_for_project} for {self.current_building_project}.")
                    self._execute_fetch_resource_for_build(world)
                    return
            return

        if self.materials_gathered_for_build:
            if (self.x, self.y) != self.building_site_target:
                self.move_towards(self.building_site_target[0], self.building_site_target[1], world)
                return

            target_building = world.get_building_at(self.building_site_target[0], self.building_site_target[1])

            if not target_building:
                committed_resources_display = {}
                for res_name, res_needed_total in structure_bp_data["required_resources"].items():
                    if self.inventory.get(res_name, 0) < res_needed_total:
                        self.add_memory(f"CRITICAL ERROR: materials_gathered_for_build is true, but missing {res_name} for {structure_blueprint_key}. Resetting gather flag.")
                        self.materials_gathered_for_build = False
                        self.resource_to_fetch = None
                        return

                    self.inventory[res_name] -= res_needed_total
                    if self.inventory[res_name] <= 0: del self.inventory[res_name]
                    committed_resources_display[res_name] = res_needed_total

                self.add_memory(f"Committed all materials {committed_resources_display} to start {self.current_building_project}.")

                target_building = Building(
                    structure_type=structure_blueprint_key, display_name=structure_bp_data["display_name"],
                    location=self.building_site_target, size=structure_bp_data["size"],
                    required_resources_for_blueprint=structure_bp_data["required_resources"].copy(),
                    functionality=structure_bp_data.get("functionality"), required_skill=structure_bp_data.get("required_skill"),
                    construction_phases=structure_bp_data.get("construction_phases"),
                    map_char_initial=structure_bp_data.get("map_char_initial", "?"),
                    map_char_complete=structure_bp_data.get("map_char_complete", "B")
                )
                world.add_building(target_building)
                self.add_memory(f"Laid foundation for {target_building.display_name} at {self.building_site_target}.")
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Laid foundation for {target_building.display_name}")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 4)
                self.add_memory(f"Laying foundation for {target_building.display_name} boosted my esteem. Esteem: {self.needs['Esteem']}")

            if target_building and not target_building.is_operational:
                base_build_progress = 1.0
                mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
                progress_this_tick = base_build_progress * mood_productivity_modifier
                if mood_productivity_modifier != 1.0:
                    self.add_memory(f"My mood ({self.mood}) is affecting my work on {target_building.display_name} (Modifier: {mood_productivity_modifier:.2f}).")

                construction_skill_level = self.skills.get("Construction", {}).get("level", 0)
                progress_this_tick *= (1 + construction_skill_level * 0.1)

                prev_phase_idx = target_building.current_phase_index
                actual_progress = target_building.work_on(max(0, progress_this_tick))

                if actual_progress > 0:
                    self._grant_skill_experience("Construction", actual_progress * 0.5, world)

                self.add_memory(f"Worked on {target_building.display_name} (Phase: {target_building.get_current_phase_name()}, +{actual_progress:.1f} prog).")

                if target_building.current_phase_index != prev_phase_idx:
                    self.add_memory(f"{target_building.display_name} advanced to phase: {target_building.get_current_phase_name()}.")

                if target_building.is_operational:
                    order.status = "Completed"
                    self.add_memory(f"Completed Build WO {order.order_id} for {target_building.display_name}.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR, f"Completed building {target_building.display_name}")
                    self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 10)
                    self.add_memory(f"Completing the building {target_building.display_name} greatly boosted my esteem. Esteem: {self.needs['Esteem']}")
                    self._reset_building_state()
                    self.current_goal = self.get_default_goal()
                    return
            elif target_building and target_building.is_operational:
                if order.status != "Completed":
                    order.status = "Completed"
                    self.add_memory(f"Found Build WO {order.order_id} for {target_building.display_name} was already completed.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR / 2, f"Found building {target_building.display_name} already complete")
                self._reset_building_state()
                self.current_goal = self.get_default_goal()
                return

    def _execute_fetch_tool(self, world: 'World') -> bool:
        if not self.tool_to_fetch_type:
            self.current_goal = self.goal_before_fetching_tool or self.get_default_goal()
            self.goal_before_fetching_tool = None
            return False
        target_tool_name, stockpile_to_search = None, None
        if self.fetching_tool_info:
            target_tool_name = self.fetching_tool_info.get("name_to_fetch"); sp_name = self.fetching_tool_info.get("stockpile_name")
            if sp_name: stockpile_to_search = world.get_stockpile_by_name(sp_name)
            if stockpile_to_search and target_tool_name and stockpile_to_search.inventory.get(target_tool_name, 0) == 0: self.fetching_tool_info = None
        if not self.fetching_tool_info:
            for sp in world.stockpiles:
                for item, qty in sp.inventory.items():
                    if qty > 0 and item in BLUEPRINTS and BLUEPRINTS[item].get("tool_type") == self.tool_to_fetch_type:
                        self.fetching_tool_info = {"name_to_fetch": item, "stockpile_name": sp.name}; stockpile_to_search, target_tool_name = sp, item; break
                if self.fetching_tool_info: break
            if not self.fetching_tool_info:
                print(f"{self.name} needs a {self.tool_to_fetch_type} but none are available!")
                self.current_goal = self.goal_before_fetching_tool or self.get_default_goal()
                self.tool_to_fetch_type = None; self.goal_before_fetching_tool = None
                return False
        if not stockpile_to_search or not target_tool_name:
            self.current_goal = self.goal_before_fetching_tool or self.get_default_goal()
            self.tool_to_fetch_type = None; self.goal_before_fetching_tool = None
            return False
        spot = (stockpile_to_search.rect[0], stockpile_to_search.rect[1])
        if (self.x, self.y) == spot:
            s, qr = stockpile_to_search.remove_item(target_tool_name, 1)
            if s and qr > 0:
                if self.equip_tool(target_tool_name):
                    self.current_goal = self.goal_before_fetching_tool or self.get_default_goal()
                    self.tool_to_fetch_type = None; self.fetching_tool_info = None; self.goal_before_fetching_tool = None
                    return False
                else:
                    self.current_goal = self.goal_before_fetching_tool or DEFAULT_IDLE_GOAL(self.name)
                    self.tool_to_fetch_type = None; self.fetching_tool_info = None; self.goal_before_fetching_tool = None
                    return False
            else:
                self.fetching_tool_info = None
                return True
        else:
            self.move_towards(spot[0], spot[1], world)
            return True

    def _execute_generic_task(self, world: 'World', task_name: str) -> bool:
        if task_name not in JOB_TASK_DEFINITIONS:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return False
        task_def = JOB_TASK_DEFINITIONS[task_name]; tool_type = task_def.get("required_tool_type")
        if tool_type and (not self.equipped_tool or self.equipped_tool.get("tool_type") != tool_type):
            if not self.goal_before_fetching_tool : self.goal_before_fetching_tool = self.current_goal
            self.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=self.name, originator_id=self.name, parameters={"tool_type": tool_type})
            self.tool_to_fetch_type = tool_type
            self.task_work_progress = 0
            return False

        base_progress_per_tick = 1.0
        mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
        current_progress_gain = base_progress_per_tick * mood_productivity_modifier
        if mood_productivity_modifier != 1.0:
            self.add_memory(f"My mood ({self.mood}) is affecting my work on {task_name} (Modifier: {mood_productivity_modifier:.2f}).")

        is_lazy_this_tick = False
        if self.is_sick:
            severity_modifier = 1.0
            if self.sickness_severity > 7: severity_modifier = 0.1
            elif self.sickness_severity > 3: severity_modifier = 0.5
            else: severity_modifier = 0.8
            current_progress_gain *= severity_modifier
            if severity_modifier < 1.0: self.add_memory(f"Feeling sick, working slowly on {task_name} (S_Sev: {self.sickness_severity}, Mod: {severity_modifier:.2f}).")

        if self.is_injured:
            severity_modifier = 1.0
            if self.injury_severity > 7: severity_modifier = 0.05
            elif self.injury_severity > 3: severity_modifier = 0.4
            else: severity_modifier = 0.75
            current_progress_gain *= severity_modifier
            if severity_modifier < 1.0: self.add_memory(f"Working with difficulty due to injury on {task_name} (I_Sev: {self.injury_severity}, Mod: {severity_modifier:.2f}).")

        if "Lazy" in self.traits and not "Focused" in self.traits:
            if random.random() < 0.25:
                current_progress_gain = 0
                is_lazy_this_tick = True
                self.add_memory(f"Felt lazy and decided to slack off for a bit while working on '{task_name}'.")

        if current_progress_gain > 0 and not is_lazy_this_tick:
            if "Diligent" in self.traits:
                if random.random() < 0.25:
                    current_progress_gain += 0.5 * base_progress_per_tick
                    self.add_memory(f"Worked with extra diligence on '{task_name}'.")
            elif "Focused" in self.traits:
                if random.random() < 0.10:
                    current_progress_gain += 0.25 * base_progress_per_tick
                    self.add_memory(f"Remained focused and made good progress on '{task_name}'.")

        current_progress_gain = max(0, current_progress_gain)
        self.task_work_progress += current_progress_gain

        if is_lazy_this_tick and current_progress_gain == 0:
            return True

        if self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            base_yield_amount = task_def.get("base_yield",1)

            final_yield_amount = base_yield_amount
            if "Strong" in self.traits and res_prod in ["Wood", "Stone", "Iron Ore"]:
                if random.random() < 0.20:
                    final_yield_amount += 1
                    self.add_memory(f"Put my strength into '{task_name}' and got a bit extra {res_prod}.")

            can_add_to_inv = self.max_inventory_items - self.get_inventory_load()
            actual_yield_taken = min(final_yield_amount, can_add_to_inv)

            if actual_yield_taken > 0 and res_prod:
                self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield_taken
                tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
                self.add_memory(f"Task '{task_name}': got {actual_yield_taken} {res_prod} (base: {base_yield_amount}) with {tool_name_mem}.")
                print(f"{self.name} task '{task_name}' yielded {actual_yield_taken} {res_prod} (base: {base_yield_amount}).")
            elif final_yield_amount > 0:
                 print(f"{self.name} inventory full for {task_name} (tried to yield {final_yield_amount} {res_prod}).")

            self.task_work_progress = 0

            if self.equipped_tool and tool_type:
                durability_loss = 1
                if "Careless" in self.traits:
                    if random.random() < 0.25:
                        durability_loss += 1
                        self.add_memory(f"Was a bit careless with my {self.equipped_tool['name']} during '{task_name}'.")

                self.equipped_tool["durability"] -= durability_loss
                if self.equipped_tool["durability"] <= 0:
                    self.add_memory(f"{self.equipped_tool['name']} broke!"); print(f"Oh no! {self.name}'s {self.equipped_tool['name']} BROKE!")
                    self.update_mood_score(config.MOOD_CHANGE_TOOL_BROKE, f"My {self.equipped_tool['name']} broke during task '{task_name}'")
                    self.needs['Safety'] = max(config.NEED_SCORE_MIN, self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 10)
                    self.add_memory(f"Tool breaking made me feel less safe. Safety: {self.needs['Safety']}")
                    self.unequip_tool()

            if actual_yield_taken > 0 and res_prod:
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Successfully gathered {res_prod} from task '{task_name}'")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 2)
                self.add_memory(f"Successfully completing part of '{task_name}' boosted my esteem. Esteem: {self.needs['Esteem']}")
        return True

    def _execute_craft_order(self, world: 'World'):
        order = world.get_work_order_by_id(self.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name :
            self._reset_crafting_state()
            self.current_goal = self.get_default_goal()
            return
        item_name = order.details["item_name"]; item_qty_total = order.details["quantity"]; blueprint = BLUEPRINTS.get(item_name)
        if not self.materials_gathered_for_wo:
            all_mats_one_unit = True
            for res, req_qty_pu in blueprint["required_resources"].items():
                if self.inventory.get(res, 0) < req_qty_pu:
                    all_mats_one_unit = False; self.resource_to_fetch = {"name": res, "quantity": req_qty_pu - self.inventory.get(res, 0), "for_wo_id": order.order_id}; break
            if all_mats_one_unit: self.materials_gathered_for_wo = True; self.resource_to_fetch = None
            else: self._execute_fetch_resource_for_wo(world, blueprint); return
        if self.resource_to_fetch: self._execute_fetch_resource_for_wo(world, blueprint); return
        if self.materials_gathered_for_wo and not self.items_crafted_for_wo:
            if not self.workshop_location: self.workshop_location = (self.x, self.y)
            if (self.x, self.y) != self.workshop_location: self.move_towards(self.workshop_location[0], self.workshop_location[1], world); return

            craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)
            base_craft_progress = 1.0
            mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
            current_crafting_progress_gain = base_craft_progress * mood_productivity_modifier
            if mood_productivity_modifier != 1.0:
                 self.add_memory(f"My mood ({self.mood}) is affecting my crafting of {item_name} (Modifier: {mood_productivity_modifier:.2f}).")

            is_slacking_craft = False
            if "Lazy" in self.traits and not "Focused" in self.traits:
                if random.random() < 0.25:
                    current_crafting_progress_gain = 0
                    is_slacking_craft = True
                    self.add_memory(f"Felt lazy and slacked off while crafting {item_name} for WO {order.order_id}.")

            if current_crafting_progress_gain > 0 and not is_slacking_craft:
                if "Diligent" in self.traits:
                    if random.random() < 0.25:
                        current_crafting_progress_gain += 0.5 * base_craft_progress
                        self.add_memory(f"Worked with extra diligence crafting {item_name}.")
                elif "Focused" in self.traits:
                    if random.random() < 0.10:
                        current_crafting_progress_gain += 0.25 * base_craft_progress
                        self.add_memory(f"Remained focused while crafting {item_name}.")

            current_crafting_progress_gain = max(0, current_crafting_progress_gain)
            self.crafting_progress += current_crafting_progress_gain

            if is_slacking_craft and current_crafting_progress_gain == 0:
                return

            if self.crafting_progress >= craft_time_per_unit:
                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    self.inventory[res] -= req_qty_per_unit
                    if self.inventory[res] <= 0: self.inventory.pop(res,None)
                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1 ; self.add_memory(f"Crafted 1 {item_name} for WO {order.order_id}.")
                print(f"{self.name} CRAFTED 1 {item_name}. Inv has: {self.inventory.get(item_name,0)}/{item_qty_total} for WO {order.order_id}.")
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Crafted a {item_name}")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 3)
                self.add_memory(f"Crafting {item_name} boosted my esteem. Esteem: {self.needs['Esteem']}")
                self.crafting_progress = 0; self.materials_gathered_for_wo = False
                if self.inventory.get(item_name,0) >= item_qty_total:
                    self.items_crafted_for_wo = True
                    self.add_memory(f"All {item_qty_total} {item_name}(s) for WO {order.order_id} crafted.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR / 2, f"Finished crafting all items for WO {order.order_id}")
                    self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5)
                    self.add_memory(f"Completing all crafting for WO {order.order_id} greatly boosted my esteem. Esteem: {self.needs['Esteem']}")
            return
        if self.items_crafted_for_wo:
            items_to_haul_qty = self.inventory.get(item_name, 0)

            if items_to_haul_qty > 0:
                haul_params = {"resource":item_name, "quantity":items_to_haul_qty, "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters=haul_params)
                return
            else:
                 order.status = "Completed"
                 self.add_memory(f"Completed and Stocked all items for WO {order.order_id} ({item_name}).")
                 print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name}).")
                 self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR, f"Fully completed WO {order.order_id}")
                 self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 8)
                 self.add_memory(f"Fully completing and stocking WO {order.order_id} gave a major boost to my esteem. Esteem: {self.needs['Esteem']}")
                 self._reset_crafting_state()
                 self.current_goal = self.get_default_goal()
                 return

    def _execute_fetch_resource_for_wo(self, world:'World', blueprint:Dict):
        if not self.resource_to_fetch: return
        res_name = self.resource_to_fetch["name"]
        if self.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]: self.resource_to_fetch = None; return
        target_sp_name = self.resource_to_fetch.get("target_stockpile_name")
        sp_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None
        if not sp_to_fetch or sp_to_fetch.inventory.get(res_name, 0) == 0:
            suitable_sps = [sp for sp in world.get_stockpiles_for_resource(res_name) if sp.inventory.get(res_name, 0) > 0]
            if not suitable_sps: print(f"{self.name} needs {res_name}, but none in stockpiles. Waiting."); return
            sp_to_fetch = suitable_sps[0]; self.resource_to_fetch["target_stockpile_name"] = sp_to_fetch.name
        spot = (sp_to_fetch.rect[0], sp_to_fetch.rect[1])
        if (self.x, self.y) == spot:
            max_can_carry = self.max_inventory_items - self.get_inventory_load()
            needed_for_this_res = blueprint["required_resources"][res_name] - self.inventory.get(res_name,0)
            qty_to_take = min(needed_for_this_res, sp_to_fetch.inventory.get(res_name,0), max_can_carry )
            if qty_to_take <= 0 : self.resource_to_fetch = None; return
            s, qty_taken = sp_to_fetch.remove_item(res_name, qty_to_take)
            if s and qty_taken > 0:
                self.inventory[res_name] = self.inventory.get(res_name, 0) + qty_taken
                self.add_memory(f"Fetched {qty_taken} {res_name} from {sp_to_fetch.name} for WO.")
                if self.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]: self.resource_to_fetch = None
        else: self.move_towards(spot[0], spot[1], world)

    def _execute_assess_production_needs(self, world: 'World'):
        if self.job != "Master Craftsman":
            self.current_goal = self.get_default_goal()
            return
        item_processed_this_tick = False;
        if not self.managed_item_targets:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        target_item_names = list(self.managed_item_targets.keys())
        if not target_item_names:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        for i in range(len(target_item_names)):
            current_idx = (self._mc_item_check_idx + i) % len(target_item_names)
            item_name = target_item_names[current_idx]; target_qty = self.managed_item_targets[item_name]
            last_ordered_day = self.order_cooldown.get(item_name, -config.ORDER_SPAM_PREVENTION_DAYS - 1)
            if world.game_time.current_day - last_ordered_day < config.ORDER_SPAM_PREVENTION_DAYS: continue
            pending_or_approved_count = 0; stock_from_ledger = world.ledger.get_total_resource_count(item_name)
            for wo in world.work_orders:
                if wo.details.get("item_name") == item_name and wo.status in ["Pending", "Approved", "InProgress"]:
                    pending_or_approved_count += wo.details.get("quantity", 1)
            effective_available = stock_from_ledger + pending_or_approved_count
            if effective_available < target_qty:
                blueprint = BLUEPRINTS.get(item_name);
                if not blueprint: print(f"Error: MC {self.name} - No blueprint for {item_name}."); continue
                qty_to_order = target_qty - effective_available
                total_req_res_for_order = {res: qty * qty_to_order for res, qty in blueprint["required_resources"].items()}
                order_details = {"item_name": item_name, "quantity": qty_to_order, "required_resources": total_req_res_for_order}
                new_order = WorkOrder(order_type="CraftItem", details=order_details, creation_day=world.game_time.current_day, priority=2)
                world.add_work_order(new_order); self.order_cooldown[item_name] = world.game_time.current_day
                self.add_memory(f"Generated WO for {qty_to_order} {item_name}."); print(f"{self.name} (MC) generated WO for {qty_to_order} {item_name}(s).")
                item_processed_this_tick = True; self._mc_item_check_idx = (current_idx + 1) % len(target_item_names); break
        if not item_processed_this_tick:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            self._mc_item_check_idx = 0

    def _execute_manage_subordinates(self, world: 'World'):
        if not (self.job == "Manager" or self.rank in ["Noble Lord", "Baron"]) or not self.subordinates_names:
            self.current_goal = self.get_default_goal()
            return

        if self.job == "Manager":
            self._execute_manage_work_orders_as_part_of_supervision(world)

        if not world.game_time: return

        for sub_name in self.subordinates_names:
            subordinate: Optional['Character'] = None
            for char_obj in world.characters:
                if char_obj.name == sub_name: subordinate = char_obj; break

            if not subordinate: continue

            review_due_day = subordinate.last_performance_review_day is None or \
                             (world.game_time.current_day - subordinate.last_performance_review_day >= config.MANAGEMENT_REVIEW_INTERVAL_DAYS)

            if review_due_day and subordinate.performance_rating != "Fired":
                self.add_memory(f"Considering performance review for {subordinate.name} (Last review: Day {subordinate.last_performance_review_day}, Current Day: {world.game_time.current_day}).")
                self.conduct_performance_review(subordinate.name, world)
                self.current_goal = DEFAULT_IDLE_GOAL(self.name)
                return

            relationship_to_sub = self.get_relationship_score(subordinate.name)
            should_consider_warning = (subordinate.performance_rating == "Poor" and subordinate.warning_count < config.FIRING_WARNING_THRESHOLD) or \
                                      (subordinate.performance_rating == "Needs Improvement" and subordinate.warning_count > 0)

            if should_consider_warning and subordinate.performance_rating != "Fired":
                warning_chance = 0.3
                reason_for_warning = "Ongoing performance issues."
                if subordinate.performance_rating == "Poor": reason_for_warning = "Performance rated Poor."
                elif subordinate.performance_rating == "Needs Improvement": reason_for_warning = "Performance Needs Improvement, with prior warnings."

                if "Strict" in self.traits or self.personality == "Demanding": warning_chance += 0.2
                if "Forgiving" in self.traits or self.personality == "Kind": warning_chance -= 0.2
                if relationship_to_sub < -30: warning_chance += 0.15
                if relationship_to_sub > 30: warning_chance -= 0.15
                warning_chance = max(0.05, min(0.95, warning_chance))

                if random.random() < warning_chance:
                    self.add_memory(f"Considering issuing warning to {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {warning_chance:.2f}).")
                    if subordinate.job == "Bookkeeper" and any(world.ledger.get_stockpile_last_update_day(sp.name) is None or (world.game_time.current_day - world.ledger.get_stockpile_last_update_day(sp.name) > config.STALE_THRESHOLD_DAYS + 2) for sp in world.stockpiles):
                        reason_for_warning = "Ledger maintenance remains unsatisfactory."

                    self.issue_warning(subordinate.name, world, reason_for_warning)
                    self.modify_relationship(subordinate.name, -10, world, reason=f"Issued warning to them for {reason_for_warning}")
                    subordinate.modify_relationship(self.name, -15, world, reason=f"Received warning from them about {reason_for_warning}")
                    self.current_goal = DEFAULT_IDLE_GOAL(self.name)
                    return

            if subordinate.performance_rating == "Poor" and \
               subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD and \
               subordinate.performance_rating != "Fired":

                firing_chance = 0.5
                if "Ruthless" in self.traits or self.personality == "Stern": firing_chance += 0.25
                if "Compassionate" in self.traits or self.personality == "Kind": firing_chance -= 0.25
                if relationship_to_sub < -50: firing_chance += 0.20
                elif relationship_to_sub > 50: firing_chance -= 0.30

                firing_chance = max(0.01, min(0.99, firing_chance))

                self.add_memory(f"Considering firing {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {firing_chance:.2f}).")
                if random.random() < firing_chance:
                    self.fire_subordinate(subordinate.name, world)
                    self.modify_relationship(subordinate.name, -100, world, reason="Fired them.")
                    self.current_goal = DEFAULT_IDLE_GOAL(self.name)
                    return

        self.current_goal = DEFAULT_IDLE_GOAL(self.name)

    def _execute_manage_work_orders_as_part_of_supervision(self, world: 'World'):
        pending_orders = world.get_pending_work_orders()
        if not pending_orders: return

        order_to_process = pending_orders[0]; can_approve = True; missing_notes = []; stale_concerns = False
        req_res = order_to_process.details.get("required_resources", {})
        if req_res:
            for resource, req_qty in req_res.items():
                avail = world.ledger.get_total_resource_count(resource)
                for sp_name_key in world.ledger.records.get(resource, {}).keys():
                    last_update = world.ledger.get_stockpile_last_update_day(sp_name_key)
                    if last_update is not None and world.game_time.current_day - last_update > config.STALE_THRESHOLD_DAYS: stale_concerns = True; break
                if stale_concerns: self.add_memory(f"Stale data for WO {order_to_process.order_id}, res {resource}");
                if avail < req_qty: can_approve = False; missing_notes.append(f"{resource} (need {req_qty}, has {avail})")
        if stale_concerns and not can_approve: print(f"{self.name} (Manager) notes stale data for {order_to_process.order_id}, and resources confirmed insufficient.")
        elif stale_concerns: print(f"{self.name} (Manager) notes stale data for {order_to_process.order_id}, proceeding with caution.")
        if can_approve: order_to_process.status = "Approved"; order_to_process.approved_by = self.name; order_to_process.approval_day = world.game_time.current_day; self.add_memory(f"Approved WO {order_to_process.order_id}"); print(f"{self.name} (Manager) APPROVED {order_to_process.order_id[:8]}.")
        else: order_to_process.status = "Denied"; order_to_process.denied_by = self.name; order_to_process.denial_reason = f"Insuff: {', '.join(missing_notes) or 'stale data'}"; self.add_memory(f"Denied WO {order_to_process.order_id}"); print(f"{self.name} (Manager) DENIED {order_to_process.order_id[:8]}. Reason: {order_to_process.denial_reason}")

    def _execute_maintain_ledger(self, world: 'World'):
        if self.job != "Bookkeeper":
            self.current_goal = self.get_default_goal()
            return
        stockpiles_to_check=world.stockpiles; target_sp=None; min_day=float('inf')
        if not stockpiles_to_check:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        for sp_obj in stockpiles_to_check:
            day=world.ledger.get_stockpile_last_update_day(sp_obj.name)
            if day is None:target_sp=sp_obj;break
            if day<world.game_time.current_day and day<min_day:min_day=day;target_sp=sp_obj
        if target_sp is None :
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        self.current_goal = Goal(GoalType.COUNT_STOCKPILE, assignee_id=self.name, originator_id=self.name, parameters={"stockpile_name": target_sp.name})
        self.decide_action(world)

    def _execute_count_stockpile(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or not self.current_goal.parameters.get("stockpile_name"):
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or DEFAULT_IDLE_GOAL(self.name)
            self.decide_action(world)
            return

        target_stockpile_name = self.current_goal.parameters.get("stockpile_name")
        if self.job != "Bookkeeper" or not target_stockpile_name :
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or DEFAULT_IDLE_GOAL(self.name)
            self.decide_action(world)
            return

        stockpile_obj=world.get_stockpile_by_name(target_stockpile_name)

        if not stockpile_obj:
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or DEFAULT_IDLE_GOAL(self.name)
            self.decide_action(world)
            return
        spot=stockpile_obj.deposit_tiles[0] if stockpile_obj.deposit_tiles else (stockpile_obj.rect[0],stockpile_obj.rect[1])
        if(self.x,self.y)==spot:
            actual_inventory = stockpile_obj.inventory.copy()
            recorded_inventory = actual_inventory.copy()

            if "Careless" in self.traits:
                miscounted_items = []
                for item_name, actual_qty in actual_inventory.items():
                    if random.random() < 0.10:
                        error_amount = random.choice([-1, 1])
                        recorded_qty = actual_qty + error_amount
                        recorded_inventory[item_name] = max(0, recorded_qty)
                        if recorded_inventory[item_name] != actual_qty:
                             miscounted_items.append(f"{item_name} (actual: {actual_qty}, recorded: {recorded_inventory[item_name]})")
                if miscounted_items:
                    self.add_memory(f"Careless counting {target_stockpile_name}. Miscounted: {', '.join(miscounted_items)}.")

            world.ledger.update_stockpile_record(target_stockpile_name, recorded_inventory, world.game_time.current_day)
            self.add_memory(f"Counted {target_stockpile_name}"); print(f"{self.name} (Bookkeeper) finished counting {target_stockpile_name}. Ledger updated with: {recorded_inventory}. Day: {world.game_time.current_day}.")
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or DEFAULT_IDLE_GOAL(self.name)
            self.decide_action(world)
        else:self.move_towards(spot[0],spot[1],world)

    def _execute_perform_woodcutter_duties(self, world: 'World'):
        if self.job!="Woodcutter":
            self.current_goal = self.get_default_goal()
            return
        quota=self.needs.get("Wood",5);inv_val=self.inventory.get("Wood",0)
        if self.current_goal and self.current_goal.parameters.get("quota"):
            quota = self.current_goal.parameters["quota"]

        next_goal_type = None
        params_for_next_goal = {}
        if self.get_inventory_load()>=self.max_inventory_items and inv_val>0:
            next_goal_type = GoalType.INITIATE_HAULING
            params_for_next_goal={"resource":"Wood"}
        elif inv_val<quota:
            next_goal_type = GoalType.GATHER_RESOURCE
            params_for_next_goal = {"resource_name": "Wood", "task_name": "Chop Wood", "quota": quota}
        else:
            next_goal_type = GoalType.INITIATE_HAULING
            params_for_next_goal={"resource":"Wood"}

        if next_goal_type:
            self.current_goal = Goal(next_goal_type, assignee_id=self.name, originator_id=self.name, parameters=params_for_next_goal)
            self.decide_action(world)

    def _execute_perform_stonemason_duties(self, world: 'World'):
        if self.job != "Stonemason":
            self.current_goal = self.get_default_goal()
            return
        quota = self.current_goal.parameters.get("quota", self.needs.get("Stone",5))
        inv_val = self.inventory.get("Stone", 0)

        next_goal_type = None
        params_for_next_goal = {}
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0:
            next_goal_type = GoalType.INITIATE_HAULING
            params_for_next_goal = {"resource": "Stone"}
        elif inv_val < quota:
            next_goal_type = GoalType.GATHER_RESOURCE
            params_for_next_goal = {"resource_name": "Stone", "task_name": "Mine Stone", "quota": quota}
        else:
            next_goal_type = GoalType.INITIATE_HAULING
            params_for_next_goal = {"resource": "Stone"}

        if next_goal_type:
            self.current_goal = Goal(next_goal_type, assignee_id=self.name, originator_id=self.name, parameters=params_for_next_goal)
            self.decide_action(world)

    def _execute_initiate_hauling(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters:
            self.current_goal = self.get_default_goal()
            return

        current_params = self.current_goal.parameters
        res = current_params.get("resource")

        if not res or self.inventory.get(res,0) == 0:
            self.current_goal = self.get_default_goal()
            self.decide_action(world)
            return

        qty = self.inventory.get(res,0)
        sps = [s_obj for s_obj in world.get_stockpiles_for_resource(res) if s_obj.has_space_for(res,1)]
        if not sps:
            self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name)
            return

        sp_chosen = sps[0]
        new_params = current_params.copy()
        new_params["target_stockpile_name"] = sp_chosen.name
        new_params["quantity_to_haul"] = qty
        self.current_goal = Goal(GoalType.HAUL_RESOURCE_TO_STOCKPILE, assignee_id=self.name, originator_id=self.name, parameters=new_params)
        self.decide_action(world)

    def _execute_haul_resource(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters:
            self.current_goal = self.get_default_goal()
            return

        current_params = self.current_goal.parameters
        sp_name = current_params.get("target_stockpile_name")
        res = current_params.get("resource")

        if not res or self.inventory.get(res,0) == 0:
            self.current_goal = self.get_default_goal()
            self.decide_action(world)
            return

        sp_obj = world.get_stockpile_by_name(sp_name)
        if not sp_obj:
            self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name)
            return

        spot = sp_obj.deposit_tiles[0] if sp_obj.deposit_tiles else (sp_obj.rect[0],sp_obj.rect[1])
        if not spot:
            self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name)
            return

        if (self.x,self.y) == spot:
            qty_dep = self.inventory.get(res,0)
            s_success, qty_add = sp_obj.add_item(res,qty_dep)
            if s_success and qty_add > 0:
                self.inventory[res] -= qty_add
                self.add_memory(f"Hauled {qty_add} {res} to {sp_obj.name}.")

            if self.inventory.get(res,0) <= 0 and res in self.inventory:
                del self.inventory[res]

            is_crafted_item_haul = current_params.get("is_crafted_item", False)
            for_wo_id = current_params.get("for_wo_id")

            if is_crafted_item_haul and self.inventory.get(res,0) == 0 and for_wo_id:
                order = world.get_work_order_by_id(for_wo_id)
                if order and order.assigned_to == self.name and order.status == "InProgress":
                    order.status = "Completed"
                    self.add_memory(f"Completed WO {order.order_id} ({res}).")
                self._reset_crafting_state()
            self.current_goal = self.get_default_goal()
        else:
            self.move_towards(spot[0],spot[1],world)

    def _execute_gather_resource(self, world: 'World'):
        resource_name = self.current_goal.parameters.get("resource_name")
        if resource_name == "Wood":
            self._execute_gather_wood(world)
        elif resource_name == "Stone":
            self._execute_gather_stone(world)
        elif resource_name == "Herbs":
            self._execute_gather_herbs(world)
        else:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)

    def _execute_gather_wood(self, world: 'World'):
        task_loc = self.find_task_location("Chop Wood", world)
        if not task_loc :
            print(f"{self.name} can't find Forest for Chop Wood.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return
        if not self._execute_generic_task(world, "Chop Wood"):
            return

        inv_wood = self.inventory.get("Wood",0)
        job_quota = self.current_goal.parameters.get("quota", self.needs.get("Wood",5) if self.job == "Woodcutter" else float('inf'))

        if self.get_inventory_load()>=self.max_inventory_items or inv_wood >= job_quota :
            self.current_goal = create_goal_from_job("Perform Woodcutter Duties", self.name) or self.get_default_goal()

    def _execute_gather_stone(self, world: 'World'):
        task_loc = self.find_task_location("Mine Stone", world)
        if not task_loc :
            print(f"{self.name} can't find Rocks for Mine Stone.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return
        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return
        if not self._execute_generic_task(world, "Mine Stone"):
            return

        inv_stone = self.inventory.get("Stone",0)
        job_quota = self.current_goal.parameters.get("quota", self.needs.get("Stone",5) if self.job == "Stonemason" else float('inf'))

        if self.get_inventory_load()>=self.max_inventory_items or inv_stone >= job_quota:
            self.current_goal = create_goal_from_job("Perform Stonemason Duties", self.name) or self.get_default_goal()

    def _execute_gather_herbs(self, world: 'World'):
        task_loc = self.find_task_location("Gather Herbs", world)
        if not task_loc:
            self.add_memory("No specific herb location found, trying generic Forest.")
            found_forest_tile = None
            for r_idx in range(world.grid_size[0]):
                for c_idx in range(world.grid_size[1]):
                    if world.get_tile(r_idx, c_idx) == "Forest":
                        found_forest_tile = (r_idx, c_idx)
                        break
                if found_forest_tile:
                    break
            task_loc = found_forest_tile

        if not task_loc:
            self.add_memory(f"Cannot find a location to gather herbs (e.g., Forest).")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return

        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return

        if not self._execute_generic_task(world, "Gather Herbs"):
            return

        if self.get_inventory_load() >= self.max_inventory_items:
            self.add_memory("Inventory full of herbs.")
            self.current_goal = self.get_default_goal()

    def _execute_oversee_medical_operations(self, world: 'World'):
        if self.job != "Chief Medical Officer":
            self.current_goal = self.get_default_goal()
            return

        self.add_memory(f"CMO {self.name} is overseeing medical operations.")

        patient_found = False
        for char in world.characters:
            if char.is_sick or char.is_injured:
                patient_found = True
                self.add_memory(f"Patient detected: {char.name} (Sick: {char.is_sick}, Injured: {char.is_injured}, S_Sev: {char.sickness_severity}, I_Sev: {char.injury_severity})")
        if not patient_found:
            self.add_memory("No patients currently require attention.")

        medical_supplies_to_check = ["Herbs", "Bandages"]
        if world.ledger:
            for supply_name in medical_supplies_to_check:
                total_count = world.ledger.get_total_resource_count(supply_name)
                self.add_memory(f"Supply check: Current {supply_name} stock is {total_count}.")
                if total_count < getattr(config, "MEDICAL_SUPPLY_LOW_THRESHOLD", 5):
                    self.add_memory(f"CMO {self.name} notes: {supply_name} levels are low ({total_count}). Should request more.")
        else:
            self.add_memory(f"CMO {self.name} cannot check medical supplies: Ledger not available.")

        if random.random() < 0.1:
             self.add_memory(f"CMO {self.name} reviews medical protocols and staff readiness.")
        return

    def _execute_provide_medical_care(self, world: 'World'):
        if self.job != "Medic":
            self.current_goal = self.get_default_goal()
            return

        target_patient: Optional['Character'] = None
        for char in world.characters:
            if char.name != self.name and (char.is_sick or char.is_injured):
                target_patient = char
                break

        if not target_patient:
            self.add_memory("No patients currently require medical care. Standing by.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return

        self.add_memory(f"Medic {self.name} assigned to patient {target_patient.name} at ({target_patient.x},{target_patient.y}).")

        patient_loc = (target_patient.x, target_patient.y)
        if (self.x, self.y) != patient_loc:
            self.move_towards(patient_loc[0], patient_loc[1], world)
            self.add_memory(f"Moving towards patient {target_patient.name}.")
            return

        self.add_memory(f"Medic {self.name} is treating {target_patient.name}.")

        item_used_for_treatment = None
        if self.inventory.get("Bandages", 0) > 0:
            self.inventory["Bandages"] -= 1
            if self.inventory["Bandages"] <= 0: del self.inventory["Bandages"]
            item_used_for_treatment = "Bandages"
            self.add_memory(f"Used 1 Bandage on {target_patient.name}.")
        elif self.inventory.get("Herbs", 0) > 0:
            self.inventory["Herbs"] -= 1
            if self.inventory["Herbs"] <= 0: del self.inventory["Herbs"]
            item_used_for_treatment = "Herbs"
            self.add_memory(f"Used 1 Herb on {target_patient.name}.")
        else:
            self.add_memory(f"No medical supplies (Bandages/Herbs) to treat {target_patient.name}. Need to restock.")
            return

        treatment_successful_this_tick = False
        if item_used_for_treatment == "Bandages" and target_patient.is_injured:
            reduction = random.randint(2, 3)
            if self.skills.get("Medicine", {}).get("level", 0) > 2: reduction += random.choice([0,1])
            target_patient.injury_severity -= reduction
            self.add_memory(f"Applied Bandages to {target_patient.name}'s injuries, severity reduced by {reduction} to {max(0, target_patient.injury_severity)}.")
            treatment_successful_this_tick = True
            if target_patient.injury_severity <= 0:
                target_patient.is_injured = False; target_patient.injury_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their injuries!")
                world.add_event_log_message(f"{target_patient.name} recovered from injuries thanks to {self.name}.")

        elif item_used_for_treatment == "Herbs" and target_patient.is_sick:
            reduction = random.randint(1, 2)
            if self.skills.get("Medicine", {}).get("level", 0) > 1: reduction += random.choice([0,1])
            target_patient.sickness_severity -= reduction
            self.add_memory(f"Administered Herbs to {target_patient.name} for sickness, severity reduced by {reduction} to {max(0, target_patient.sickness_severity)}.")
            treatment_successful_this_tick = True
            if target_patient.sickness_severity <= 0:
                target_patient.is_sick = False; target_patient.sickness_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their sickness!")
                world.add_event_log_message(f"{target_patient.name} recovered from sickness thanks to {self.name}.")

        elif item_used_for_treatment:
            self.add_memory(f"Tried to use {item_used_for_treatment} on {target_patient.name}, but it wasn't effective for their current condition.")

        if treatment_successful_this_tick:
            self._grant_skill_experience("Medicine", 1.5, world)
        else:
            self._grant_skill_experience("Medicine", 0.2, world)

        self.current_goal = self.get_default_goal()
        return

    def _execute_oversee_expedition(self, world: 'World'):
         if self.job != "Expedition Leader":
            self.current_goal = self.get_default_goal()
            return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = DEFAULT_IDLE_GOAL(self.name)

    def _execute_oversee_settlement(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
            return
        self.add_memory(f"{self.name} the Mayor is assessing the overall resource status of the settlement.")
        key_resources = ["Wood", "Stone"]
        if world.ledger:
            for resource_name in key_resources:
                total_count = world.ledger.get_total_resource_count(resource_name)
                self.add_memory(f"Ledger check: Current {resource_name} stock is {total_count}.")
                if total_count < config.MAYOR_RESOURCE_LOW_THRESHOLD:
                    self.add_memory(f"Mayor {self.name} notes: {resource_name} levels are low ({total_count}). Action may be needed.")
                elif total_count > config.MAYOR_RESOURCE_HIGH_THRESHOLD:
                    self.add_memory(f"Mayor {self.name} notes: {resource_name} levels are abundant ({total_count}).")
        else:
            self.add_memory(f"Mayor {self.name} cannot assess resource status: Ledger not available.")

        if random.random() < 0.15:
            self.add_memory(f"Mayor {self.name} spends time contemplating the settlement's long-term strategy and development.")

        if random.random() < 0.1:
            if self.job == "Mayor":
                self._execute_manage_appointments(world)

        if random.random() < 0.02:
            self.add_memory(f"Mayor {self.name} feels it's time to address the populace.")
            self.current_goal = Goal(GoalType.GIVE_SPEECH, assignee_id=self.name, originator_id=self.name)
            return

        if random.random() < 0.05:
            project_structure_type = "wooden_hut"
            structure_bp = STRUCTURE_BLUEPRINTS.get(project_structure_type)
            if structure_bp and world.game_time:
                build_location: Optional[Tuple[int,int]] = None
                for r in range(world.grid_size[0] - structure_bp["size"][1] + 1):
                    for c in range(world.grid_size[1] - structure_bp["size"][0] + 1):
                        can_place = True
                        for dr in range(structure_bp["size"][1]):
                            for dc in range(structure_bp["size"][0]):
                                if world.get_tile(c + dc, r + dr) != "Grass" or world.get_building_at(c + dc, r + dr):
                                    can_place = False; break
                            if not can_place: break
                        if can_place:
                            build_location = (c, r)
                            break
                    if build_location: break

                if build_location:
                    project_name = f"Mayoral Project: Construct {structure_bp['display_name']}"
                    self.add_memory(f"Decreeing new project: {project_name} at {build_location}.")
                    order_details = { "structure_type": project_structure_type, "location": build_location, "required_resources": structure_bp["required_resources"].copy(), "initiated_by_mayor": True }
                    new_build_order = WorkOrder(order_type="BuildStructure", details=order_details, priority=3, creation_day=world.game_time.current_day)
                    world.add_work_order(new_build_order)
                    self.add_memory(f"Issued Work Order {new_build_order.order_id} for {project_name}. Expecting Managers to handle assignment.")
                else:
                    self.add_memory(f"Considered initiating a {project_structure_type} project, but could not find a suitable location.")
            elif not structure_bp:
                 self.add_memory(f"Wanted to initiate a {project_structure_type} project, but blueprint is missing.")
        return

    def _execute_manage_appointments(self, world: 'World'):
        if self.job != "Mayor":
            return

        self.add_memory(f"Mayor {self.name} is reviewing key settlement appointments.")
        key_positions = ["Sheriff", "Chief Medical Officer", "Manager"]

        for position_job_title in key_positions:
            current_holder: Optional['Character'] = None
            for char in world.characters:
                if char.job == position_job_title:
                    current_holder = char
                    break

            if not current_holder:
                self.add_memory(f"Position of {position_job_title} is vacant. Seeking candidate.")
                candidate: Optional['Character'] = None
                potential_candidates: List['Character'] = []
                for char_to_check in world.characters:
                    if char_to_check.job not in key_positions and char_to_check.job != "Mayor" and char_to_check.rank != "Noble Lord":
                        required_skill_for_job = {"Sheriff": "Security", "Chief Medical Officer": "Medicine", "Manager": "Leadership"}.get(position_job_title)
                        if required_skill_for_job and char_to_check.skills.get(required_skill_for_job, {}).get("level", 0) > 0:
                            potential_candidates.append(char_to_check)
                        elif not required_skill_for_job:
                            potential_candidates.append(char_to_check)

                if potential_candidates:
                    relevant_skill = {"Sheriff": "Security", "Chief Medical Officer": "Medicine", "Manager": "Leadership"}.get(position_job_title)
                    if relevant_skill:
                        potential_candidates.sort(key=lambda c: c.skills.get(relevant_skill, {}).get("level", 0), reverse=True)
                    candidate = potential_candidates[0]

                    self.add_memory(f"Appointing {candidate.name} (Skill: {candidate.skills.get(relevant_skill, {}).get('level', 0) if relevant_skill else 'N/A'}) as the new {position_job_title}.")
                    if candidate.supervisor_name:
                        supervisor = world.get_character_by_name(candidate.supervisor_name)
                        if supervisor: supervisor.remove_subordinate(candidate.name)

                    candidate.job = position_job_title
                    candidate.supervisor_name = self.name
                    candidate.appointed_by = self.name
                    if candidate.rank == "Worker": candidate.rank = "Skilled Worker"
                    self.add_subordinate(candidate.name)
                    candidate.add_memory(f"I have been appointed as {position_job_title} by Mayor {self.name}.")
                else:
                    self.add_memory(f"Could not find a suitable candidate for {position_job_title} at this time.")
            else:
                base_firing_consideration_chance = 0.02
                if "Strict" in self.traits: base_firing_consideration_chance *= 1.5
                if "Impatient" in self.traits: base_firing_consideration_chance *= 1.5
                if "Forgiving" in self.traits: base_firing_consideration_chance *= 0.5

                if random.random() < base_firing_consideration_chance:
                    self.add_memory(f"Considering the performance of {current_holder.name}, the current {position_job_title}.")
                    actual_firing_chance = 0.25
                    if "Ruthless" in self.traits: actual_firing_chance = 0.5
                    if "Forgiving" in self.traits and "Ruthless" not in self.traits: actual_firing_chance = 0.1

                    if random.random() < actual_firing_chance:
                        self.add_memory(f"Decided to relieve {current_holder.name} of their duties as {position_job_title} due to perceived unsatisfactory performance.")
                        current_holder.add_memory(f"I have been fired from my position as {position_job_title} by Mayor {self.name}.")
                        current_holder.job = "Unemployed"
                        current_holder.current_goal = DEFAULT_IDLE_GOAL(current_holder.name)
                        current_holder.appointed_by = None
                        if current_holder.supervisor_name == self.name : current_holder.supervisor_name = None
                        if current_holder.name in self.subordinates_names: self.remove_subordinate(current_holder.name)
                    else:
                        self.add_memory(f"{current_holder.name}'s performance as {position_job_title} is deemed acceptable for now.")
        return

    def _execute_maintain_peace(self, world: 'World'):
        if self.job != "Sheriff":
            self.current_goal = self.get_default_goal()
            return
        self.add_memory(f"Sheriff {self.name} is maintaining peace in the settlement.")
        if random.random() < 0.2:
            self.add_memory("Surveying the surroundings for any disturbances.")
        if random.random() < 0.1:
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0:
                self.add_memory(f"Sheriff {self.name} moves to a new vantage point.")
                self.move(dx, dy, world)
        return

    def _execute_patrol_area(self, world: 'World'):
        if self.job != "Deputy":
            self.current_goal = self.get_default_goal()
            return
        self.add_memory(f"Deputy {self.name} is patrolling their assigned area.")
        if random.random() < 0.3:
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0:
                if self.move(dx, dy, world):
                    self.add_memory(f"Patrolling... moved to ({self.x},{self.y}).")
                else:
                    self.add_memory(f"Patrolling... tried to move but was blocked.")
            else:
                self.add_memory("Patrolling... surveying current location.")
        else:
            self.add_memory("Patrolling... observing the area.")
        return

    def _execute_seek_medical_attention(self, world: 'World'):
        self.add_memory("Feeling unwell, seeking medical attention.")
        medical_personnel: List['Character'] = []
        for char in world.characters:
            if char.job in ["Medic", "Chief Medical Officer"] and char.name != self.name:
                medical_personnel.append(char)

        if not medical_personnel:
            self.add_memory("Cannot find any medical personnel. Resting and hoping for the best.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return

        closest_medic: Optional['Character'] = None
        min_dist = float('inf')
        for medic in medical_personnel:
            dist = abs(self.x - medic.x) + abs(self.y - medic.y)
            if dist < min_dist:
                min_dist = dist
                closest_medic = medic

        if closest_medic:
            if (self.x, self.y) == (closest_medic.x, closest_medic.y):
                self.add_memory(f"Reached {closest_medic.name} for medical help.")
                self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            else:
                self.add_memory(f"Moving towards {closest_medic.name} at ({closest_medic.x},{closest_medic.y}) for help.")
                self.move_towards(closest_medic.x, closest_medic.y, world)
        else:
            self.add_memory("Could not determine closest medic. Resting.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
        return

    def _execute_give_speech(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
            return

        speech_topic = "the general state of the settlement and future prospects"
        generated_speech_snippet = ""
        if config.USE_LLM:
            prompt = (f"You are {self.name}, the Mayor of a small, developing settlement. "
                      f"Your personality is {self.personality} and you have traits: {', '.join(self.traits)}. "
                      f"Briefly generate a snippet of a speech you are giving to your populace about {speech_topic}. "
                      f"Keep it under 50 words.")
            generated_speech_snippet = generate_dialogue(prompt, self.name)

        if generated_speech_snippet:
            self.add_memory(f"Gave a speech: \"{generated_speech_snippet}\"")
            world.add_event_log_message(f"Mayor {self.name} addresses the populace: \"{generated_speech_snippet}\"")
        else:
            self.add_memory(f"Practiced a speech about {speech_topic}.")
            world.add_event_log_message(f"Mayor {self.name} clears their throat, preparing a speech about {speech_topic}.")

        self.current_goal = self.get_default_goal()
        return

    def _execute_wander(self, world: 'World'):
        moves=[];
        for dx,dy in[(0,1),(0,-1),(1,0),(-1,0)]:
            tx,ty=self.x+dx,self.y+dy
            if 0<=tx<world.grid_size[0] and 0<=ty<world.grid_size[1] and \
                world.get_tile(tx,ty)not in["Water","Mountain","Forest","Rocks","SP_Mai","SP_Woo","SP_Sto"] and \
                not world.get_characters_at_location(tx,ty):moves.append((dx,dy))
        if moves:choice=random.choice(moves);self.move(choice[0],choice[1],world)

    def _execute_perform_builder_duties(self, world: 'World'):
        if self.active_build_order_id:
            if self.current_goal.type != GoalType.EXECUTE_BUILD_ORDER:
                self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                         parameters={"order_id": self.active_build_order_id, "structure_type": self.current_building_project, "location": self.building_site_target})
            return

        approved_build_orders = world.get_approved_build_orders()
        if approved_build_orders:
            order_to_take = approved_build_orders[0]
            order_to_take.status = "InProgress"
            order_to_take.assigned_to = self.name
            self._reset_building_state()
            self.active_build_order_id = order_to_take.order_id
            self.current_building_project = order_to_take.details.get("structure_type")
            self.building_site_target = order_to_take.details.get("location")
            self.materials_gathered_for_build = False
            self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                     parameters={"order_id": self.active_build_order_id, "structure_type": self.current_building_project, "location": self.building_site_target})
            self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {self.current_building_project}.")
        else:
            self.add_memory("No build orders available for Builder Duties.")
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)

    def conduct_performance_review(self, subordinate_char_name: str, world: 'World'):
        if self.name == subordinate_char_name:
            self.add_memory("Attempted to conduct self-performance review. This is not allowed."); return

        subordinate: Optional['Character'] = None
        for char_obj in world.characters:
            if char_obj.name == subordinate_char_name:
                subordinate = char_obj; break

        if not subordinate:
            self.add_memory(f"Could not find subordinate {subordinate_char_name} for performance review."); return

        if subordinate.supervisor_name != self.name:
            self.add_memory(f"Attempted to review {subordinate_char_name}, but I am not their supervisor."); return

        if not world.game_time:
            self.add_memory(f"Cannot conduct review for {subordinate_char_name}, game time not available."); return

        objective_rating = "Needs Improvement"
        review_notes = []

        if subordinate.job == "Bookkeeper":
            is_diligent = True
            if not world.stockpiles: review_notes.append("No stockpiles for Bookkeeper to check.")
            else:
                for sp in world.stockpiles:
                    last_update = world.ledger.get_stockpile_last_update_day(sp.name)
                    if last_update is None or (world.game_time.current_day - last_update > config.STALE_THRESHOLD_DAYS + 2):
                        is_diligent = False; review_notes.append(f"Ledger for {sp.name} stale (Day {last_update})."); break
            if is_diligent and world.stockpiles: objective_rating = "Good"; review_notes.append("Ledger up-to-date.")
            elif not world.stockpiles and is_diligent: objective_rating = "Not Evaluated"; review_notes.append("No stockpiles to manage.")

        elif subordinate.job == "Woodcutter":
            if subordinate.inventory.get("Wood", 0) >= 3:
                objective_rating = "Good"; review_notes.append("Carrying a good amount of Wood.")
            elif subordinate.inventory.get("Wood", 0) > 0:
                objective_rating = "Satisfactory"; review_notes.append("Carrying some Wood.")
            else:
                review_notes.append("Not carrying Wood. Performance based on recent deposits not yet tracked.")

        final_rating = objective_rating
        rating_modifier_score = 0

        if "Strict" in self.traits or self.personality == "Demanding": rating_modifier_score -= 1
        if "Kind" in self.traits or self.personality == "Forgiving": rating_modifier_score += 1
        if "Lazy" in self.traits and random.random() < 0.3: rating_modifier_score +=1

        relationship_to_sub = self.get_relationship_score(subordinate.name)
        if relationship_to_sub > 50: rating_modifier_score += 1
        elif relationship_to_sub < -50: rating_modifier_score -= 1

        rating_scale = {"Poor": -2, "Needs Improvement": -1, "Satisfactory": 0, "Good": 1, "Excellent": 2, "Not Evaluated": 0}
        objective_score = rating_scale.get(objective_rating, 0)
        final_score = max(-2, min(2, objective_score + rating_modifier_score))

        for r_name, r_val in rating_scale.items():
            if r_val == final_score: final_rating = r_name; break
        if objective_rating == "Not Evaluated": final_rating = "Not Evaluated"

        if final_rating != objective_rating:
            review_notes.append(f"Supervisor's discretion ({self.personality}, Rel: {relationship_to_sub}) adjusted rating from {objective_rating} to {final_rating}.")

        subordinate.performance_rating = final_rating
        subordinate.last_performance_review_day = world.game_time.current_day

        relationship_change_value = 0
        if final_rating == "Excellent": relationship_change_value = 10
        elif final_rating == "Good": relationship_change_value = 5
        elif final_rating == "Satisfactory": relationship_change_value = 1
        elif final_rating == "Needs Improvement": relationship_change_value = -5
        elif final_rating == "Poor": relationship_change_value = -10

        if relationship_change_value != 0:
            self.modify_relationship(subordinate.name, relationship_change_value // 2, world, reason=f"Performance review outcome: {final_rating}")
            subordinate.modify_relationship(self.name, relationship_change_value, world, reason=f"Performance review outcome from {self.name}: {final_rating}")

        manager_mood_change = 0
        if final_rating in ["Excellent", "Good"]: manager_mood_change = 3
        elif final_rating in ["Poor"]: manager_mood_change = -3
        if "Strict" in self.traits and final_rating == "Poor": manager_mood_change -=2
        if "Compassionate" in self.traits and final_rating == "Poor": manager_mood_change +=1
        self.update_mood_score(manager_mood_change, f"Conducted review for {subordinate.name} (Rated: {final_rating})")

        sub_mood_change = {"Excellent": config.MOOD_CHANGE_PROMOTED, "Good": 10, "Satisfactory": 2, "Needs Improvement": -8, "Poor": config.MOOD_CHANGE_RECEIVED_WARNING}.get(final_rating,0)
        subordinate.update_mood_score(sub_mood_change, f"Performance review: {final_rating}")

        esteem_change = 0
        if final_rating == "Excellent": esteem_change = 15
        elif final_rating == "Good": esteem_change = 10
        elif final_rating == "Satisfactory": esteem_change = 2
        elif final_rating == "Needs Improvement": esteem_change = -5
        elif final_rating == "Poor": esteem_change = -10

        if esteem_change != 0:
            subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, min(config.NEED_SCORE_MAX, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + esteem_change))
            subordinate.add_memory(f"My performance review ({final_rating}) changed my esteem by {esteem_change}. Esteem: {subordinate.needs['Esteem']}")

        if final_rating not in ["Poor", "Needs Improvement"]:
             if subordinate.warning_count > 0:
                review_notes.append(f"Past warnings ({subordinate.warning_count}) cleared due to improved review.")
                subordinate.warning_count = 0
        elif final_rating == "Poor" and subordinate.warning_count == 0 :
            subordinate.warning_count = 1
            review_notes.append("Performance rated Poor, counts as a warning.")

        review_summary = f"Performance review for {subordinate.name}: {final_rating}. Notes: {'; '.join(review_notes) or 'General review.'}"
        self.add_memory(review_summary)
        print(f"{self.name} ({self.personality}) reviewed {subordinate.name}. Objective: {objective_rating}, Final: {final_rating}. Rel: {relationship_to_sub}.")
        subordinate.add_memory(f"Had performance review with {self.name} ({self.personality}). Rated: {final_rating}. My rel with them: {subordinate.get_relationship_score(self.name)}")

    def issue_warning(self, subordinate_char_name: str, world: 'World', reason_message: str):
        if self.name == subordinate_char_name:
            self.add_memory("Attempted to issue self-warning. This is not allowed."); return

        subordinate: Optional['Character'] = None
        for char_obj in world.characters:
            if char_obj.name == subordinate_char_name:
                subordinate = char_obj; break

        if not subordinate:
            self.add_memory(f"Could not find subordinate {subordinate_char_name} to issue warning."); return

        if subordinate.supervisor_name != self.name:
            self.add_memory(f"Attempted to warn {subordinate_char_name}, but I am not their supervisor."); return

        subordinate.warning_count += 1
        warning_memory = f"Issued warning to {subordinate.name} for: {reason_message}. Total warnings: {subordinate.warning_count}."
        self.add_memory(warning_memory)
        print(f"{self.name} issued WARNING to {subordinate.name} for '{reason_message}'. Total warnings: {subordinate.warning_count}.")

        subordinate.add_memory(f"Received warning from {self.name} regarding: {reason_message}. Current warnings: {subordinate.warning_count}.")
        subordinate.update_mood_score(config.MOOD_CHANGE_RECEIVED_WARNING, f"Received warning: {reason_message}")
        subordinate.needs['Belonging'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 8)
        subordinate.add_memory(f"Receiving a warning made me feel less accepted. Belonging: {subordinate.needs['Belonging']}")
        subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 7)
        subordinate.add_memory(f"Receiving a warning also damaged my esteem. Esteem: {subordinate.needs['Esteem']}")

        manager_mood_hit = -5
        if "Strict" in self.traits: manager_mood_hit -=2
        elif "Forgiving" in self.traits: manager_mood_hit +=2
        self.update_mood_score(manager_mood_hit, f"Issued warning to {subordinate.name}")

        if subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD:
            if subordinate.performance_rating != "Poor":
                subordinate.performance_rating = "Poor"
                self.add_memory(f"{subordinate.name}'s performance set to Poor due to {subordinate.warning_count} warnings (Threshold: {config.FIRING_WARNING_THRESHOLD}).")
                subordinate.add_memory(f"Performance automatically set to Poor due to reaching {subordinate.warning_count} warnings.")
                print(f"{subordinate.name}'s performance automatically set to Poor due to {subordinate.warning_count} warnings.")
                subordinate.update_mood_score(-10, "Performance set to Poor due to warnings")
                subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 10)
                subordinate.add_memory(f"Performance being set to Poor further damaged my esteem. Esteem: {subordinate.needs['Esteem']}")

    def fire_subordinate(self, subordinate_char_name: str, world: 'World'):
        if self.name == subordinate_char_name:
            self.add_memory("Attempted to fire self. This is not allowed."); return

        subordinate: Optional['Character'] = None
        sub_idx = -1
        for idx, char_obj in enumerate(world.characters):
            if char_obj.name == subordinate_char_name:
                subordinate = char_obj; sub_idx = idx; break

        if not subordinate:
            self.add_memory(f"Could not find subordinate {subordinate_char_name} to fire."); return

        if subordinate.supervisor_name != self.name:
            self.add_memory(f"Attempted to fire {subordinate_char_name}, but I am not their supervisor."); return

        manager_mood_change = -10
        if "Ruthless" in self.traits: manager_mood_change += 8
        elif "Compassionate" in self.traits: manager_mood_change -= 5
        self.update_mood_score(manager_mood_change, f"Fired {subordinate.name}")

        if subordinate.name in self.subordinates_names:
            self.remove_subordinate(subordinate.name)

        original_job = subordinate.job
        subordinate.supervisor_name = None
        subordinate.job = "Unemployed"
        subordinate.rank = "Commoner"
        subordinate.current_goal = DEFAULT_IDLE_GOAL(subordinate.name)
        subordinate.assigned_tasks = []
        subordinate.performance_rating = "Fired"
        subordinate.update_mood_score(config.MOOD_CHANGE_FIRED, f"Fired from job as {original_job}")
        subordinate.needs['Belonging'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 25)
        subordinate.add_memory(f"Being fired made me lose my sense of belonging with my work group. Belonging: {subordinate.needs['Belonging']}")
        subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 30)
        subordinate.add_memory(f"Being fired crushed my esteem. Esteem: {subordinate.needs['Esteem']}")

        rep_change_reason = f"Was fired from job as {original_job} by {self.name}"
        subordinate.update_reputation(config.REPUTATION_CHANGE_FIRED, rep_change_reason)
        if abs(config.REPUTATION_CHANGE_FIRED) >= config.REPUTATION_FOR_RUMOR_THRESHOLD and world.game_time:
            rumor_content_key = "was_fired_negative"
            rumor_strength = config.RUMOR_INITIAL_STRENGTH_SIGNIFICANT_EVENT
            new_rumor = Rumor(
                subject_char_id=subordinate.name,
                content_key=rumor_content_key,
                initial_strength=rumor_strength,
                creation_day=world.game_time.current_day,
                is_positive=False,
                original_source_char_id=self.name
            )
            world.event_bus.post(Event(EventType.RUMOR_CREATED, {"rumor": new_rumor}))
            subordinate.known_rumor_ids.add(new_rumor.rumor_id)
            self.known_rumor_ids.add(new_rumor.rumor_id)
            subordinate.add_memory(f"Being fired by {self.name} will likely start negative rumors ({new_rumor.rumor_id[:4]}) about me.")
            self.add_memory(f"Firing {subordinate.name} might cause rumors ({new_rumor.rumor_id[:4]}).")

        subordinate.warning_count = 0
        if subordinate.active_work_order_id:
            wo = world.get_work_order_by_id(subordinate.active_work_order_id)
            if wo and wo.status == "InProgress" and wo.assigned_to == subordinate.name:
                wo.status = "Pending"
                wo.assigned_to = None
                subordinate.add_memory(f"Work order {subordinate.active_work_order_id} unassigned due to termination.")
                print(f"Work order {subordinate.active_work_order_id} unassigned from {subordinate.name} due to termination.")
            subordinate._reset_crafting_state()

        fire_memory = f"Fired {subordinate.name} from their job as {original_job}."
        self.add_memory(fire_memory)
        print(f"{self.name} FIRED {subordinate.name} who was a {original_job}.")
        subordinate.add_memory(f"Was fired by {self.name} from job {original_job}. Now Unemployed.")

    def _update_relationship_from_opinions(self, target_name: str, world: 'World'):
        if target_name not in self.opinions:
            return

        opinion_tags = self.opinions.get(target_name, {})
        if not opinion_tags:
            return

        overall_impression_score = sum(opinion_tags.values())
        adjustment_factor = 0.1
        relationship_adjustment = int(round(overall_impression_score * adjustment_factor))
        max_adjustment_per_call = 1
        relationship_adjustment = max(-max_adjustment_per_call, min(max_adjustment_per_call, relationship_adjustment))

        if relationship_adjustment != 0:
            self.modify_relationship(target_name, relationship_adjustment, world,
                                     reason=f"General impression ({overall_impression_score}) led to adjustment.")

    def _process_nearby_listeners(self, world: 'World', target_char: 'Character', interaction_type: str, initiator_traits: List[str], target_traits: List[str]):
        listener_radius = 2
        social_goals = [GoalType.GREET_CHARACTER, GoalType.INTRODUCE_SELF_TO_STRANGER, GoalType.SMALL_TALK, GoalType.SHARE_POSITIVE_NEWS, GoalType.OFFER_COMFORT]

        for listener in world.characters:
            if listener.name == self.name or listener.name == target_char.name:
                continue

            if listener.current_goal.type not in [GoalType.IDLE, GoalType.WANDER] or listener.current_goal.type in social_goals:
                continue

            distance_to_initiator = abs(listener.x - self.x) + abs(listener.y - self.y)
            distance_to_target = abs(listener.x - target_char.x) + abs(listener.y - target_char.y)

            if distance_to_initiator <= listener_radius or distance_to_target <= listener_radius:
                listener.add_memory(f"Overheard {self.name} and {target_char.name} interacting ({interaction_type}).")

                if self.name not in listener.opinions: listener.opinions[self.name] = {}
                observed_tag_initiator = f"observed_{interaction_type}_style"
                opinion_change_initiator = 0
                if "Friendly" in initiator_traits: opinion_change_initiator += 1
                if "Grumpy" in initiator_traits: opinion_change_initiator -=1
                listener.opinions[self.name][observed_tag_initiator] = max(-5, min(5, listener.opinions[self.name].get(observed_tag_initiator, 0) + opinion_change_initiator))

                if target_char.name not in listener.opinions: listener.opinions[target_char.name] = {}
                observed_tag_target = f"observed_{interaction_type}_response_style"
                opinion_change_target = 0
                if "Friendly" in target_traits: opinion_change_target += 1
                if "Grumpy" in target_traits: opinion_change_target -=1
                listener.opinions[target_char.name][observed_tag_target] = max(-5, min(5, listener.opinions[target_char.name].get(observed_tag_target, 0) + opinion_change_target))

                if interaction_type not in ["Offer Comfort"]:
                    listener.needs['Social'] = min(100, listener.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_LISTEN_POSITIVE)
                    listener.add_memory(f"Social need slightly up from overhearing conversation.")

    def _execute_greet_character(self, world: 'World'): pass
    def _execute_formal_apology(self, world: 'World'): pass
    def _execute_share_secret(self, world: 'World'): pass
    def _execute_argue(self, world: 'World'): pass
    def _execute_ask_for_help(self, world: 'World'): pass
    def _execute_offer_comfort(self, world: 'World'): pass
    def _execute_share_positive_news(self, world: 'World'): pass
    def _execute_small_talk(self, world: 'World'): pass
    def _execute_introduce_self(self, world: 'World'): pass
    def _reset_building_state(self): pass
    def _reset_crafting_state(self): pass
