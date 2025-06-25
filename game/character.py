# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any # Added Any
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS # Added STRUCTURE_BLUEPRINTS
from .building import Building # Added Building
from . import config # Import config

if TYPE_CHECKING:
    from .world import World
    from .character import Character as OtherCharacter

# STALE_THRESHOLD_DAYS = 2 # Now in config
ORDER_SPAM_PREVENTION_DAYS = 3

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: dict[str, int], x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10,
                 rank: str = "Worker"): # Added rank parameter
        self.name = name; self.personality = personality; self.traits = traits

        # Initialize skills with new structure
        self.skills: Dict[str, Dict[str, Any]] = {}
        if skills: # Ensure skills is not None before iterating
            for skill_name, level in skills.items(): # Convert initial skills
                self.skills[skill_name] = {
                    "level": level,
                    "experience": 0.0,
                    "exp_to_next_level": self._calculate_exp_for_level(level)
                }

        self.x = x; self.y = y; self.inventory = {}; self.memory = [];

        # Needs System
        self.needs = needs if needs else {}
        default_needs = {
            "Hunger": 100, "Thirst": 100, "Energy": 100,
            "Social": 50, "Comfort": 50
        }
        for need_name, default_value in default_needs.items():
            if need_name not in self.needs:
                self.needs[need_name] = default_value

        self.max_needs: Dict[str, int] = {
            "Hunger": 100, "Thirst": 100, "Energy": 100,
            "Social": 100, "Comfort": 100
        }
        self.mood: int = 50 # Range 0-100, 50 is neutral

        self.current_goal = current_goal
        self.relationships = {}; self.job = job; self.max_inventory_items = max_inventory_items
        self.hauling_info: Optional[Dict] = None
        self.counting_target_stockpile_name: Optional[str] = None
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False

        # Attributes for building
        self.active_build_order_id: Optional[str] = None
        self.materials_gathered_for_build: bool = False
        self.building_site_target: Optional[Tuple[int,int]] = None
        self.current_building_project: Optional[str] = None # structure_type of current project

        # New attributes for hierarchy and accountability
        self.rank: str = rank  # Use parameter, default to "Worker"
        self.assigned_tasks: List[Dict] = []  # Tasks assigned by a supervisor
        self.performance_rating: str = "Not Evaluated"  # e.g., "Excellent", "Good", "Needs Improvement", "Poor"
        self.last_performance_review_day: Optional[int] = None
        self.warning_count: int = 0
        self.resource_to_fetch: Optional[Dict] = None; self.workshop_location: Optional[Tuple[int,int]] = None
        self.equipped_tool: Optional[Dict] = None
        self.task_work_progress: int = 0
        self.tool_to_fetch_type: Optional[str] = None
        self.fetching_tool_info: Optional[Dict] = None
        self.goal_before_fetching_tool: Optional[str] = None
        self.current_task_def_name: Optional[str] = None
        self._mc_item_check_idx: int = 0
        self.status_effects: List[Dict[str, Any]] = [] # For events & challenges

    def _calculate_exp_for_level(self, level: int) -> float:
        """Calculates the experience needed to reach the next level."""
        # Example formula: 100 * (current_level ^ 1.2) or 100 * 1.5^(level-1)
        if level == 0: return 50 # Special case for level 0 to 1
        return float(int(100 * (level ** 1.2)))


    def _reset_crafting_state(self):
        self.active_work_order_id = None; self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False; self.resource_to_fetch = None
        self.crafting_progress = 0; self.hauling_info = None; self.workshop_location = None

    def _reset_building_state(self):
        self.active_build_order_id = None
        self.materials_gathered_for_build = False
        self.building_site_target = None
        self.resource_to_fetch = None # Clear fetching state as well
        self.current_building_project = None

    def __str__(self):
        build_wo_info = f", BuildWO: {self.active_build_order_id}" if self.active_build_order_id else ""
        base_info = (f"Character(Name: {self.name}, Rank: {self.rank}, Job: {self.job}, Pos: ({self.x},{self.y}), Goal: {self.current_goal}, CraftWO: {self.active_work_order_id}{build_wo_info}, Load: {self.get_inventory_load()}/{self.max_inventory_items})")
        needs_summary = f"Needs(H:{self.needs.get('Hunger',0)} T:{self.needs.get('Thirst',0)} E:{self.needs.get('Energy',0)} S:{self.needs.get('Social',0)}) Mood:{self.mood}"
        supervisor_info = f"  Supervisor: {self.supervisor_name if self.supervisor_name else 'None'}"
        subordinates_info = f"  Subordinates: {len(self.subordinates_names)}"
        performance_info = f"  Performance: {self.performance_rating} (Warnings: {self.warning_count}, Last Review: Day {self.last_performance_review_day if self.last_performance_review_day is not None else 'N/A'})"
        equipped_tool_info = "None";
        if self.equipped_tool: equipped_tool_info = f"{self.equipped_tool['name']} ({self.equipped_tool['durability']}/{self.equipped_tool['max_durability']})"
        tool_info_str = f"  Equipped Tool: {equipped_tool_info}"
        return f"{base_info}\n  {needs_summary}\n{supervisor_info}; {subordinates_info}\n{performance_info}\n{tool_info_str}"
    def set_supervisor(self, s: Optional[str]): self.supervisor_name=s
    def add_subordinate(self, s: str): self.subordinates_names.append(s) if s not in self.subordinates_names else None
    def remove_subordinate(self, s: str): self.subordinates_names.remove(s) if s in self.subordinates_names else None
    def get_inventory_load(self) -> int: return sum(self.inventory.values())
    def add_memory(self, e: str): self.memory.append(e); self.memory=self.memory[-20:]
    def interact(self, o: 'OtherCharacter', w: 'World'): pass

    def move(self, dx: int, dy: int, world: 'World') -> bool:
        new_x, new_y = self.x + dx, self.y + dy
        can_move = True
        if not (0 <= new_x < world.grid_size[0] and 0 <= new_y < world.grid_size[1]): can_move = False
        if can_move:
            tile_type_at_new_loc = world.get_tile(new_x, new_y)
            if tile_type_at_new_loc in ["Mountain", "Water"]: can_move = False
            if can_move:
                other_chars_at_new_loc = [char for char in world.get_characters_at_location(new_x, new_y) if char.name != self.name]
                if other_chars_at_new_loc: can_move = False
        if can_move: self.x = new_x; self.y = new_y; return True
        return False

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx = target_x - self.x; dy = target_y - self.y
        norm_dx, norm_dy = 0, 0
        if dx > 0: norm_dx = 1
        elif dx < 0: norm_dx = -1
        if dy > 0: norm_dy = 1
        elif dy < 0: norm_dy = -1

        if norm_dx == 0 and norm_dy == 0: return
        if self.move(norm_dx, norm_dy, world): return
        if norm_dx != 0 and norm_dy != 0:
            if self.move(norm_dx, 0, world): return
            if self.move(0, norm_dy, world): return

    def equip_tool(self, tool_item_name: str) -> bool:
        if self.equipped_tool and self.equipped_tool["name"] == tool_item_name: return True
        if self.equipped_tool: self.unequip_tool()
        blueprint = BLUEPRINTS.get(tool_item_name)
        if not blueprint or blueprint.get("type") != "Tool": return False
        tool_type = blueprint.get("tool_type"); max_durability = blueprint.get("max_durability")
        if not tool_type or max_durability is None: return False
        self.equipped_tool = {"name": tool_item_name, "durability": max_durability, "max_durability": max_durability, "tool_type": tool_type}
        self.add_memory(f"Equipped {tool_item_name}"); print(f"{self.name} equipped {tool_item_name} (Dur: {max_durability}).")
        return True
    def unequip_tool(self):
        if self.equipped_tool: self.add_memory(f"Unequipped {self.equipped_tool['name']}."); print(f"{self.name} unequipped {self.equipped_tool['name']}."); self.equipped_tool = None

    def find_task_location(self, task_name: str, world: 'World') -> Optional[Tuple[int,int]]:
        task_def = JOB_TASK_DEFINITIONS.get(task_name);
        if not task_def: return None
        res_prod = task_def.get("resource_produced"); tile_to_find = None
        if res_prod == "Wood": tile_to_find = "Forest"
        elif res_prod == "Stone": tile_to_find = "Rocks"
        elif res_prod == "Iron Ore": tile_to_find = "Rocks"
        else: return None
        for r_idx in range(world.grid_size[0]):
            for c_idx in range(world.grid_size[1]):
                if world.get_tile(r_idx,c_idx) == tile_to_find:
                    if res_prod in world.resources and (r_idx,c_idx) in world.resources.get(res_prod,[]): return (r_idx,c_idx)
                    elif res_prod not in world.resources and not task_def.get("needs_specific_resource_item", True) : return (r_idx,c_idx)
        return None
    def gather_resource(self, resource_name: str, world: 'World'): pass
    def build(self, structure_type: str, world: 'World') -> bool: return False

    def job_default_goal(self) -> str:
        if self.job == "Woodcutter": return "Perform Woodcutter Duties"
        if self.job == "Stonemason": return "Perform Stonemason Duties"
        if self.job == "Builder": return "Perform Builder Duties" # Added Builder job
        if self.job == "Master Craftsman": return "Assess Production Needs"
        if self.job == "Manager": return "Manage Subordinates" # Changed from "Manage Work Orders"
        if self.job == "Bookkeeper": return "Maintain Ledger"
        if self.job == "Expedition Leader": return "Oversee Expedition"
        # Add a check for rank if we want Nobles who aren't "Manager" to also manage
        if self.rank in ["Noble Lord", "Baron"] and not self.subordinates_names: # Example: A noble without a specific job might just idle or have other duties
            return "Oversee Domain" # Placeholder for other noble tasks
        elif self.rank in ["Noble Lord", "Baron"]:
            return "Manage Subordinates"
        return "Idle"

    def _execute_fetch_tool(self, world: 'World') -> bool: # True if still fetching, False if done/failed
        if not self.tool_to_fetch_type: self.current_goal = self.goal_before_fetching_tool or self.job_default_goal(); self.goal_before_fetching_tool = None; return False
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
            if not self.fetching_tool_info: print(f"{self.name} needs a {self.tool_to_fetch_type} but none are available!"); self.current_goal = self.goal_before_fetching_tool or self.job_default_goal(); self.tool_to_fetch_type = None; self.goal_before_fetching_tool = None; return False
        if not stockpile_to_search or not target_tool_name : self.current_goal = self.goal_before_fetching_tool or self.job_default_goal(); self.tool_to_fetch_type = None; self.goal_before_fetching_tool = None; return False
        spot = (stockpile_to_search.rect[0], stockpile_to_search.rect[1])
        if (self.x, self.y) == spot:
            s, qr = stockpile_to_search.remove_item(target_tool_name, 1)
            if s and qr > 0:
                if self.equip_tool(target_tool_name): self.current_goal = self.goal_before_fetching_tool or self.job_default_goal(); self.tool_to_fetch_type = None; self.fetching_tool_info = None; self.goal_before_fetching_tool = None; return False
                else: self.current_goal = self.goal_before_fetching_tool or "Idle"; self.tool_to_fetch_type = None; self.fetching_tool_info = None; self.goal_before_fetching_tool = None; return False
            else: self.fetching_tool_info = None; return True
        else: self.move_towards(spot[0], spot[1], world); return True

    def _execute_generic_task(self, world: 'World', task_name: str) -> bool: # True if task action taken, False if tool fetch needed
        if task_name not in JOB_TASK_DEFINITIONS: self.current_goal = "Idle"; return False
        task_def = JOB_TASK_DEFINITIONS[task_name]; tool_type = task_def.get("required_tool_type")
        # self.current_task_def_name = task_name # This is already set by the calling gather function
        if tool_type and (not self.equipped_tool or self.equipped_tool.get("tool_type") != tool_type):
            if not self.goal_before_fetching_tool : self.goal_before_fetching_tool = self.current_goal
            self.current_goal = "Fetch Tool"; self.tool_to_fetch_type = tool_type; self.task_work_progress = 0; return False

        # --- Trait Effects on Progress ---
        current_progress_gain = 1 # Base progress per tick for this task type

        # Apply character status effect modifiers (e.g., "Sick" reduces work speed)
        work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
        current_progress_gain *= work_speed_modifier

        # Apply skill level modifier to progress gain
        skill_name_for_task = task_def.get("skill_used")
        if skill_name_for_task:
            skill_level = self.skills.get(skill_name_for_task, {}).get("level", 0)
            # Ensure current_progress_gain is float before multiplication if it might be int
            current_progress_gain = float(current_progress_gain) * (1 + skill_level * 0.05) # 5% increase per level

        is_lazy_this_tick = False

        if "Lazy" in self.traits and not "Focused" in self.traits:
            if random.random() < 0.25: # 25% chance to be lazy
                current_progress_gain = 0 # Overrides other progress gains for this tick if lazy
                is_lazy_this_tick = True
                self.add_memory(f"Felt lazy and decided to slack off for a bit while working on '{task_name}'.")

        if current_progress_gain > 0: # Don't apply positive progress traits if slacked off
            if "Diligent" in self.traits:
                if random.random() < 0.25: # 25% chance for bonus progress
                    current_progress_gain += 1
                    self.add_memory(f"Worked with extra diligence on '{task_name}'.")
            elif "Focused" in self.traits: # Focused but not Diligent, and not Lazy (or Lazy was overridden)
                if random.random() < 0.10: # 10% chance for smaller bonus
                    current_progress_gain += 1
                    self.add_memory(f"Remained focused and made good progress on '{task_name}'.")

        self.task_work_progress += current_progress_gain

        if is_lazy_this_tick and current_progress_gain == 0: # If slacked, end tick here
            return True

        # --- Task Completion and Yield ---
        if self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            base_yield_amount = task_def.get("base_yield",1)

            # Trait Effect on Yield (e.g., Strong)
            final_yield_amount = float(base_yield_amount) # Start with float for multipliers
            if "Strong" in self.traits and res_prod in ["Wood", "Stone", "Iron Ore"]: # Assuming Strong applies to these
                if random.random() < 0.20: # 20% chance for +1 bonus
                    final_yield_amount += 1
                    self.add_memory(f"Put my strength into '{task_name}' and got a bit extra {res_prod}.")

            # Apply world event yield modifiers
            if res_prod: # Check if the task actually produces a resource
                modifier_key = f"yield_multiplier_{res_prod}"
                world_event_modifier = world.active_world_effects.get(modifier_key)
                if world_event_modifier and world.game_time.current_total_ticks < world_event_modifier.get("expires_tick", 0):
                    final_yield_amount *= world_event_modifier.get("multiplier", 1.0)
                    # self.add_memory(f"Benefited from '{world_event_modifier.get('event_id', 'world event')}' yielding more {res_prod}.")
                    # This memory might be too spammy, log event globally.

            final_yield_amount = int(round(final_yield_amount)) # Convert to int after all multipliers

            can_add_to_inv = self.max_inventory_items - self.get_inventory_load()
            actual_yield_taken = min(final_yield_amount, can_add_to_inv)

            if actual_yield_taken > 0 and res_prod:
                self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield_taken
                tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
                event_bonus_info = f" (event mult: x{world.active_world_effects.get(modifier_key, {}).get('multiplier', 1.0):.2f})" if world_event_modifier and world.game_time.current_total_ticks < world_event_modifier.get("expires_tick",0) else ""
                self.add_memory(f"Task '{task_name}': got {actual_yield_taken} {res_prod} (base: {base_yield_amount}{event_bonus_info}) with {tool_name_mem}.")
                print(f"{self.name} task '{task_name}' yielded {actual_yield_taken} {res_prod} (base: {base_yield_amount}{event_bonus_info}).")
            elif final_yield_amount > 0: # Tried to yield something but inventory was full
                 print(f"{self.name} inventory full for {task_name} (tried to yield {final_yield_amount} {res_prod}).")

            self.task_work_progress = 0 # Reset progress for next unit

            # Tool Durability
            if self.equipped_tool and tool_type:
                durability_loss = 1
                # Trait Effect on Tool Wear (e.g., Careless)
                if "Careless" in self.traits:
                    if random.random() < 0.25: # 25% chance for extra wear
                        durability_loss += 1
                        self.add_memory(f"Was a bit careless with my {self.equipped_tool['name']} during '{task_name}'.")

                self.equipped_tool["durability"] -= durability_loss
                if self.equipped_tool["durability"] <= 0:
                    self.add_memory(f"{self.equipped_tool['name']} broke!"); print(f"Oh no! {self.name}'s {self.equipped_tool['name']} BROKE!")
                    self.unequip_tool()

            # Grant skill experience
            if task_def.get("skill_used") and actual_yield_taken > 0 : # Only grant XP if skill is used and yield was positive
                # XP amount could be based on base_yield, task difficulty, etc.
                xp_gained = 5.0 * actual_yield_taken # Example: 5 XP per unit yielded
                self._grant_skill_experience(task_def["skill_used"], xp_gained, world)

        return True

    def _execute_craft_order(self, world: 'World'):
        order = world.get_work_order_by_id(self.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name :
            self._reset_crafting_state()
            self.current_goal=self.job_default_goal() or "Idle"
            return

        item_name = order.details["item_name"]
        item_qty_total = order.details["quantity"]
        blueprint = BLUEPRINTS.get(item_name)

        # If all items for the order are already crafted, transition to hauling or complete.
        if self.items_crafted_for_wo:
            if not self.hauling_info and self.inventory.get(item_name, 0) > 0: # Items are crafted and in inventory
                self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = "Initiate Hauling"
                print(f"DEBUG: {self.name} (already crafted {item_name} for WO {order.order_id}) -> Initiate Hauling. Inv: {self.inventory}")
                self._execute_initiate_hauling(world) # Call directly
                return
            elif self.hauling_info is None and self.inventory.get(item_name, 0) == 0: # All items crafted AND already hauled
                 order.status = "Completed"; self.add_memory(f"Completed/Stocked WO {order.order_id} ({item_name})."); print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name})."); self._reset_crafting_state(); self.current_goal = self.job_default_goal() or "Idle"; return
            else:
                # This case means items_crafted_for_wo is true, but either hauling_info is already set (so should be in a hauling goal)
                # or item is not in inventory (which is an issue).
                # If already hauling, this function shouldn't be called. If item missing, it's an error.
                # For safety, if goal is still Execute Craft Order, try to re-initiate hauling.
                if self.current_goal == "Execute Craft Order": # Stuck in this goal despite items crafted
                    if self.inventory.get(item_name, 0) > 0 : # If item still there, try hauling again
                         self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                         self.current_goal = "Initiate Hauling"
                         print(f"DEBUG: {self.name} (stuck in ExecuteCraftOrder with crafted items) -> Re-Initiate Hauling. Inv: {self.inventory}")
                    else: # Items crafted but not in inventory, and not hauled. Problem.
                         print(f"ERROR: {self.name} has items_crafted_for_wo for {item_name} but item not in inventory and not hauled.")
                         order.status = "Denied"; order.denial_reason = "Crafted item disappeared before hauling."
                         self._reset_crafting_state(); self.current_goal = "Idle"
                return

        # --- Material Gathering & Crafting (only if not self.items_crafted_for_wo) ---
        if not self.materials_gathered_for_wo:
            all_mats_one_unit = True # Check for materials for ONE unit
            for res, req_qty_pu in blueprint["required_resources"].items():
                if self.inventory.get(res, 0) < req_qty_pu:
                    all_mats_one_unit = False; self.resource_to_fetch = {"name": res, "quantity": req_qty_pu - self.inventory.get(res, 0), "for_wo_id": order.order_id}; break
            if all_mats_one_unit: self.materials_gathered_for_wo = True; self.resource_to_fetch = None
            else: self._execute_fetch_resource_for_wo(world, blueprint); return
        if self.resource_to_fetch: self._execute_fetch_resource_for_wo(world, blueprint); return
        if self.materials_gathered_for_wo and not self.items_crafted_for_wo:
            if not self.workshop_location: # Default workshop location to current spot if not set
                self.workshop_location = (self.x, self.y)

            # Check for required workshop type
            required_workshop_str = blueprint.get("required_workshop_type")
            if required_workshop_str:
                # Check if current workshop_location hosts an operational building of the required type
                building_at_loc = world.get_building_at(self.workshop_location[0], self.workshop_location[1])
                if not building_at_loc or not building_at_loc.is_operational or building_at_loc.structure_type != required_workshop_str:
                    # Try to find a suitable workshop
                    suitable_workshops = world.get_operational_buildings_of_type(required_workshop_str)
                    if not suitable_workshops:
                        self.add_memory(f"Cannot craft {item_name}: requires {required_workshop_str}, none available or operational.")
                        print(f"{self.name} cannot craft {item_name}: no operational '{required_workshop_str}' found. WO {order.order_id} stalled.")
                        # Potentially change WO status to Pending/Denied or character to Idle
                        order.status = "Pending" # Re-queue
                        order.assigned_to = None # Unassign
                        self._reset_crafting_state()
                        self.current_goal = "Idle"
                        return

                    # Found a suitable workshop, set it as new workshop_location
                    # For simplicity, pick the first one. Could be closest, least crowded, etc. later.
                    new_workshop = suitable_workshops[0]
                    self.workshop_location = new_workshop.location
                    # if self.name == "Carl_Crafter" and order and order.details.get("item_name") == "Iron Pickaxe": # DEBUG
                    #     print(f"CARL_DEBUG_CRAFT_ORDER: self.workshop_location just set to {self.workshop_location} (actual new_workshop.location is {new_workshop.location}) inside _execute_craft_order / workshop finding block.")
                    self.add_memory(f"Identified {new_workshop.display_name} at {new_workshop.location} for crafting {item_name}.")
                    print(f"{self.name} needs to go to {new_workshop.display_name} at {new_workshop.location} for {item_name}.")

            # Check if character is inside the designated workshop building
            # self.workshop_location should point to the main location of the correct workshop building
            target_workshop_building = None
            if self.workshop_location: # Ensure workshop_location is set
                 target_workshop_building = world.get_building_at(self.workshop_location[0], self.workshop_location[1])

            # If a specific workshop building is required and the character is not inside it, move towards it.
            # Also handles if target_workshop_building is None (e.g. self.workshop_location was None or pointed to empty space)
            if required_workshop_str and (not target_workshop_building or target_workshop_building.structure_type != required_workshop_str or not target_workshop_building.is_inside(self.x, self.y)):
                if self.workshop_location: # Should always be set if required_workshop_str is true and we passed earlier checks
                    self.move_towards(self.workshop_location[0], self.workshop_location[1], world)
                else: # Fallback, though should ideally not be reached if logic is correct
                    print(f"ERROR: {self.name} needs workshop {required_workshop_str} but self.workshop_location is None.")
                    self.current_goal = "Idle"
                return
            elif not required_workshop_str and (self.x, self.y) != self.workshop_location:
                # No specific workshop type, but still move to the generic workshop_location if not there
                # This handles crafting items that don't need a special building, done at current spot unless workshop_location was set differently
                 self.move_towards(self.workshop_location[0], self.workshop_location[1], world)
                 return


            # Now at the (potentially required and verified) workshop location, or inside the required workshop building
            craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)

            # --- Trait Effects on Crafting Progress ---
            current_crafting_progress_gain = 1 # Base progress

            # Apply character status effect modifiers (e.g., "Sick" reduces work speed)
            work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
            current_crafting_progress_gain *= work_speed_modifier

            # Apply skill level modifier to crafting progress gain
            crafting_skill_name = blueprint.get("job_skill_needed")
            if crafting_skill_name:
                skill_level = self.skills.get(crafting_skill_name, {}).get("level", 0)
                current_crafting_progress_gain = float(current_crafting_progress_gain) * (1 + skill_level * 0.05) # 5% increase per level

            is_slacking_craft = False

            if "Lazy" in self.traits and not "Focused" in self.traits:
                if random.random() < 0.25: # 25% chance to be lazy
                    current_crafting_progress_gain = 0
                    is_slacking_craft = True
                    self.add_memory(f"Felt lazy and slacked off while crafting {item_name} for WO {order.order_id}.")

            if current_crafting_progress_gain > 0: # Don't apply positive progress traits if slacked
                if "Diligent" in self.traits:
                    if random.random() < 0.25: # 25% chance for bonus progress
                        current_crafting_progress_gain += 1
                        self.add_memory(f"Worked with extra diligence crafting {item_name}.")
                elif "Focused" in self.traits: # Focused but not Diligent, and not Lazy (or Lazy overridden)
                    if random.random() < 0.10: # 10% chance for smaller bonus
                        current_crafting_progress_gain += 1
                        self.add_memory(f"Remained focused while crafting {item_name}.")

            self.crafting_progress += current_crafting_progress_gain

            if is_slacking_craft and current_crafting_progress_gain == 0:
                return # End tick here if slacked off

            if self.crafting_progress >= craft_time_per_unit:
                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    self.inventory[res] -= req_qty_per_unit
                    if self.inventory[res] <= 0: self.inventory.pop(res,None)

                # Add item to inventory
                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1

                # Grant skill experience for crafting
                if blueprint.get("job_skill_needed"):
                    # XP amount could be based on item complexity (e.g. craft_time_per_unit or resource cost)
                    xp_gained = float(blueprint.get("craft_time_per_unit", 5)) # Example: XP = craft time
                    self._grant_skill_experience(blueprint["job_skill_needed"], xp_gained, world)

                # Apply crafting output bonuses from events (e.g., for tools)
                # This is a bit simplified; ideally, the item itself would store its properties and bonuses would modify those upon creation.
                # For now, if it's a tool, we check for durability bonus.
                # This part is tricky because inventory just stores counts. Tools with varying durability need richer representation.
                # For now, let's assume the *next* tool of this type equipped gets this bonus, which is not ideal.
                # A proper fix would involve changing how tools are stored/tracked.
                # SHORT TERM: We can log that a bonus *would* apply.
                item_type = blueprint.get("type") # e.g., "Tool", "Furniture"
                if item_type:
                    modifier_key = f"craft_bonus_{item_type}"
                    world_event_modifier = world.active_world_effects.get(modifier_key)
                    if world_event_modifier and world.game_time.current_total_ticks < world_event_modifier.get("expires_tick", 0):
                        bonus_details = world_event_modifier.get("bonus_details", {})
                        if "durability_multiplier" in bonus_details and blueprint.get("type") == "Tool":
                            bonus_mult = bonus_details["durability_multiplier"]
                            self.add_memory(f"Crafted {item_name} with potential event bonus (x{bonus_mult:.1f} durability) due to '{world_event_modifier.get('event_id', 'world event')}'.")
                            print(f"{self.name} crafted {item_name} with potential x{bonus_mult:.1f} durability bonus from event.")
                        # Other bonuses like quality, etc. could be handled here

                self.add_memory(f"Crafted 1 {item_name} for WO {order.order_id}.")
                print(f"{self.name} CRAFTED 1 {item_name}. Inv has: {self.inventory.get(item_name,0)}/{item_qty_total} for WO {order.order_id}.")
                self.crafting_progress = 0; self.materials_gathered_for_wo = False
                if self.inventory.get(item_name,0) >= item_qty_total:
                    self.items_crafted_for_wo = True

                # If items_crafted_for_wo just became true, don't return, fall through to hauling logic.
                # Only return if still crafting (more quantity needed or not enough progress for current unit).
                if not self.items_crafted_for_wo:
                    return # Still crafting more units or current unit not finished.

        if self.items_crafted_for_wo: # Check if all units for the WO are crafted
            if not self.hauling_info and self.inventory.get(item_name, 0) > 0: # And items are in inventory
                self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = "Initiate Hauling"
                print(f"DEBUG: {self.name} finished crafting {item_name} for WO {order.order_id}, now needs to Haul. Inv: {self.inventory}")
                self._execute_initiate_hauling(world) # Call directly
                return
            elif self.hauling_info is None and self.inventory.get(item_name, 0) == 0: # All items crafted AND hauled (inventory empty of this item)
                 order.status = "Completed"; self.add_memory(f"Completed/Stocked WO {order.order_id} ({item_name})."); print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name})."); self._reset_crafting_state(); self.current_goal = self.job_default_goal() or "Idle"; return
            # If self.hauling_info is set, the character is already in hauling process, which is handled by other goals.

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
        if self.job != "Master Craftsman": self.current_goal = self.job_default_goal(); return
        item_processed_this_tick = False;

        # Check for needed workshops first (e.g., if no small_workshop exists)
        # This is a simplified check; could be more sophisticated based on game needs.
        needed_structure_type = "small_workshop" # Example
        if not world.get_operational_buildings_of_type(needed_structure_type) and \
           not any(wo.order_type == "BuildStructure" and wo.details.get("structure_type") == needed_structure_type and wo.status in ["Pending", "Approved", "InProgress"] for wo in world.work_orders):

            structure_bp = STRUCTURE_BLUEPRINTS.get(needed_structure_type)
            if structure_bp:
                # Find a suitable location (very basic: first available 3x2 space near MC)
                # This location finding needs to be much better in a real scenario.
                build_location = None
                mc_x, mc_y = self.x, self.y
                search_radius = 5
                found_loc = False
                for r in range(1, search_radius + 1):
                    for dx_s in range(-r, r + 1):
                        for dy_s in range(-r, r + 1):
                            if abs(dx_s) + abs(dy_s) != r: continue # Only check perimeter of search square
                            check_x, check_y = mc_x + dx_s, mc_y + dy_s

                            # Check if area is clear for the building footprint
                            can_place = True
                            for bx_offset in range(structure_bp["size"][0]):
                                for by_offset in range(structure_bp["size"][1]):
                                    tile_to_check_x, tile_to_check_y = check_x + bx_offset, check_y + by_offset
                                    if not (0 <= tile_to_check_x < world.grid_size[0] and 0 <= tile_to_check_y < world.grid_size[1]) or \
                                       world.get_tile(tile_to_check_x, tile_to_check_y) not in ["Grass"] or \
                                       world.get_building_at(tile_to_check_x, tile_to_check_y) is not None or \
                                       world.get_characters_at_location(tile_to_check_x, tile_to_check_y): # Basic check
                                        can_place = False; break
                                if not can_place: break
                            if can_place:
                                build_location = (check_x, check_y)
                                found_loc = True; break
                        if found_loc: break
                    if found_loc: break

                if build_location:
                    order_details = {
                        "structure_type": needed_structure_type,
                        "location": build_location,
                        "required_resources": structure_bp["required_resources"],
                        "size": structure_bp["size"], # For reference in WO
                        "build_time": structure_bp["build_time"] # For reference
                    }
                    # Check resource availability (optional, manager might approve later)
                    # For now, let MC queue it directly if location found.
                    new_build_order = WorkOrder(order_type="BuildStructure", details=order_details, creation_day=world.game_time.current_day, priority=1) # High priority for essential buildings
                    world.add_work_order(new_build_order)
                    self.add_memory(f"Queued Build WO for {needed_structure_type} at {build_location}.")
                    print(f"{self.name} (MC) queued Build WO for {needed_structure_type} at {build_location}.")
                    item_processed_this_tick = True # Count this as an action for the tick
                else:
                    print(f"{self.name} (MC) wants to build {needed_structure_type} but couldn't find a suitable location near them.")
            else:
                print(f"Error: MC {self.name} - No blueprint for structure {needed_structure_type}.")

        # Original logic for crafting item WOs
        if not item_processed_this_tick and self.managed_item_targets:
            target_item_names = list(self.managed_item_targets.keys())
            if not target_item_names: self.current_goal = "Idle"; return # Should be caught by self.managed_item_targets check

            for i in range(len(target_item_names)):
                current_idx = (self._mc_item_check_idx + i) % len(target_item_names)
                item_name = target_item_names[current_idx]; target_qty = self.managed_item_targets[item_name]
                last_ordered_day = self.order_cooldown.get(item_name, -ORDER_SPAM_PREVENTION_DAYS - 1)
                if world.game_time.current_day - last_ordered_day < ORDER_SPAM_PREVENTION_DAYS: continue

                pending_or_approved_count = 0; stock_from_ledger = world.ledger.get_total_resource_count(item_name)
                for wo in world.work_orders:
                    if wo.order_type == "CraftItem" and wo.details.get("item_name") == item_name and wo.status in ["Pending", "Approved", "InProgress"]:
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
                    self.add_memory(f"Generated Craft WO for {qty_to_order} {item_name}."); print(f"{self.name} (MC) generated Craft WO for {qty_to_order} {item_name}(s).")
                    item_processed_this_tick = True; self._mc_item_check_idx = (current_idx + 1) % len(target_item_names); break

        if not item_processed_this_tick: self.current_goal = "Idle"; self._mc_item_check_idx = 0


    # Renamed from _execute_manage_work_orders to _execute_manage_subordinates
    def _execute_manage_subordinates(self, world: 'World'):
        # A character must have the "Manager" job or be a managing rank to perform these duties.
        is_eligible_manager = self.job == "Manager" or self.rank in ["Noble Lord", "Baron"]
        if not is_eligible_manager:
            self.current_goal = self.job_default_goal() or "Idle"
            return

        # Manager-specific task: Process Work Orders
        if self.job == "Manager": # Only those with the actual "Manager" job process WOs this way for now
            self._execute_manage_work_orders_as_part_of_supervision(world)
            # If _execute_manage_work_orders_as_part_of_supervision took an action that changed the goal or returned, respect that.
            # For now, assume it might have processed one, and we can continue to subordinate mgmt if applicable.
            # A more robust system might have these as separate exclusive actions per tick.

        # Subordinate Management (if character has subordinates)
        if not self.subordinates_names:
            if self.job == "Manager": # If a manager has no subordinates, and processed WOs, they can idle.
                self.current_goal = "Idle" # Or a new goal like "Recruit Subordinates"
            # If a Noble Lord without subordinates, they might do other things or just idle.
            # If current_goal wasn't changed by WO management, and no subs, then idle.
            # This 'Idle' might be premature if WO management is supposed to be the primary action for a tick.
            # Let's assume for now a manager tries to manage WOs *and then* if they have time/no subs, they might idle.
            # The goal setting to Idle at the end of this function will handle it if no other action is taken.
            pass # Continue, might just idle if no other actions taken by WO mgmt

        if not world.game_time: return # Need game time for reviews (relevant for subordinate part)

        # If no subordinates, the loop below won't run.
        # The manager might have already processed a WO.
        # If they did, their goal might be "Idle" from that function or they continue.
        # If they didn't process a WO and have no subordinates, they will fall through to Idle at the end.

        action_taken_this_cycle = False # Track if a subordinate management action occurred

        for sub_name in self.subordinates_names:
            subordinate: Optional['Character'] = None
            for char_obj in world.characters: # Find subordinate object
                if char_obj.name == sub_name: subordinate = char_obj; break

            if not subordinate: continue

            # 1. Performance Review Logic
            review_due_day = subordinate.last_performance_review_day is None or \
                             (world.game_time.current_day - subordinate.last_performance_review_day >= config.MANAGEMENT_REVIEW_INTERVAL_DAYS)

            if review_due_day and subordinate.performance_rating != "Fired":
                self.add_memory(f"Considering performance review for {subordinate.name} (Last review: Day {subordinate.last_performance_review_day}, Current Day: {world.game_time.current_day}).")
                self.conduct_performance_review(subordinate.name, world)
                # After a review, the supervisor might be "done" for this cycle of Manage Subordinates.
                # Or they could continue to check other subordinates. For now, one action is enough.
                self.current_goal = "Idle" # Re-evaluate next tick; prevents multiple manager actions in one tick
                return

            # 2. Warning/Firing Logic (if review not just conducted or if performance dictates immediate action)
            relationship_to_sub = self.get_relationship_score(subordinate.name)

            # --- Warning Logic ---
            # Condition for considering a warning: performance is "Poor" or "Needs Improvement" with existing warnings.
            should_consider_warning = (subordinate.performance_rating == "Poor" and subordinate.warning_count < config.FIRING_WARNING_THRESHOLD) or \
                                      (subordinate.performance_rating == "Needs Improvement" and subordinate.warning_count > 0)

            if should_consider_warning and subordinate.performance_rating != "Fired":
                warning_chance = 0.3 # Base chance
                reason_for_warning = "Ongoing performance issues."
                if subordinate.performance_rating == "Poor": reason_for_warning = "Performance rated Poor."
                elif subordinate.performance_rating == "Needs Improvement": reason_for_warning = "Performance Needs Improvement, with prior warnings."

                if "Strict" in self.traits or self.personality == "Demanding": warning_chance += 0.2
                if "Forgiving" in self.traits or self.personality == "Kind": warning_chance -= 0.2
                if relationship_to_sub < -30: warning_chance += 0.15 # Bad relationship increases chance
                if relationship_to_sub > 30: warning_chance -= 0.15  # Good relationship decreases chance
                warning_chance = max(0.05, min(0.95, warning_chance)) # Clamp chance

                if random.random() < warning_chance:
                    self.add_memory(f"Considering issuing warning to {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {warning_chance:.2f}).")
                    if subordinate.job == "Bookkeeper" and any(world.ledger.get_stockpile_last_update_day(sp.name) is None or (world.game_time.current_day - world.ledger.get_stockpile_last_update_day(sp.name) > config.STALE_THRESHOLD_DAYS + 2) for sp in world.stockpiles):
                        reason_for_warning = "Ledger maintenance remains unsatisfactory."

                    self.issue_warning(subordinate.name, world, reason_for_warning)
                    # Issuing a warning affects relationships
                    self.modify_relationship(subordinate.name, -10, world, reason=f"Issued warning to them for {reason_for_warning}")
                    subordinate.modify_relationship(self.name, -15, world, reason=f"Received warning from them about {reason_for_warning}")
                    self.current_goal = "Idle" # Action taken
                    return

            # --- Firing Logic ---
            # Condition for considering firing: performance is "Poor" AND at/above warning threshold.
            if subordinate.performance_rating == "Poor" and \
               subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD and \
               subordinate.performance_rating != "Fired":

                firing_chance = 0.5 # Base chance
                if "Ruthless" in self.traits or self.personality == "Stern": firing_chance += 0.25
                if "Compassionate" in self.traits or self.personality == "Kind": firing_chance -= 0.25
                if relationship_to_sub < -50: firing_chance += 0.20 # Very bad relationship
                elif relationship_to_sub > 50: firing_chance -= 0.30 # Very good relationship might save them

                firing_chance = max(0.01, min(0.99, firing_chance)) # Clamp chance

                self.add_memory(f"Considering firing {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {firing_chance:.2f}).")
                if random.random() < firing_chance:
                    self.fire_subordinate(subordinate.name, world)
                    # Firing drastically affects relationship (mostly for the record now)
                    self.modify_relationship(subordinate.name, -100, world, reason="Fired them.")
                    # No need for subordinate to update relationship, they are 'gone' in terms of this dynamic with this supervisor
                    self.current_goal = "Idle" # Action taken
                    return

        # If no specific management action taken for any subordinate, manager might do other things or idle.
        # Or, if they just managed work orders, they might still want to check subordinates in the same tick if logic allows.
        # For now, one significant management action (review, warn, fire) or WO approval per "Manage Subordinates" cycle.
        # For now, just idle and wait for next cycle.
        self.current_goal = "Idle"


    def _execute_manage_work_orders_as_part_of_supervision(self, world: 'World'):
        # This is the original _execute_manage_work_orders logic, refactored slightly
        # It's called if the character is a Manager AND is in "Manage Subordinates" goal.
        # This allows a manager to still do their primary job of managing WOs.
        pending_orders = world.get_pending_work_orders()
        print(f"DEBUG: {self.name} (Manager) checking pending_orders. Count: {len(pending_orders)}") # DEBUG
        if not pending_orders: return # No orders to manage, main function will continue to subordinate mgmt

        order_to_process = pending_orders[0]
        print(f"DEBUG: {self.name} (Manager) processing order: {order_to_process.order_id} ({order_to_process.order_type} for {order_to_process.details.get('item_name') or order_to_process.details.get('structure_type')})") # DEBUG

        can_approve = True; missing_notes = []; stale_concerns = False
        req_res = order_to_process.details.get("required_resources", {})
        if req_res:
            print(f"DEBUG: {self.name} (Manager) checking resources for {order_to_process.order_id}: {req_res}") # DEBUG
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
        if self.job != "Bookkeeper": self.current_goal = self.job_default_goal(); return
        stockpiles_to_check=world.stockpiles; target_sp=None; min_day=float('inf')
        if not stockpiles_to_check: self.current_goal = "Idle"; return
        for sp_obj in stockpiles_to_check:
            day=world.ledger.get_stockpile_last_update_day(sp_obj.name)
            if day is None:target_sp=sp_obj;break
            if day<world.game_time.current_day and day<min_day:min_day=day;target_sp=sp_obj
        if target_sp is None : self.current_goal="Idle";return
        self.counting_target_stockpile_name=target_sp.name;self.current_goal="Count Stockpile";self.decide_action(world)
    def _execute_count_stockpile(self, world: 'World'):
        if self.job != "Bookkeeper" or not self.counting_target_stockpile_name: self.current_goal = "Maintain Ledger"; self.counting_target_stockpile_name = None; self.decide_action(world); return
        stockpile_obj=world.get_stockpile_by_name(self.counting_target_stockpile_name)
        if not stockpile_obj:self.current_goal="Maintain Ledger";self.counting_target_stockpile_name=None;self.decide_action(world);return
        spot=stockpile_obj.deposit_tiles[0] if stockpile_obj.deposit_tiles else (stockpile_obj.rect[0],stockpile_obj.rect[1])
        if(self.x,self.y)==spot:
            actual_inventory = stockpile_obj.inventory.copy()
            recorded_inventory = actual_inventory.copy() # Start with the correct inventory

            if "Careless" in self.traits:
                miscounted_items = []
                for item_name, actual_qty in actual_inventory.items():
                    if random.random() < 0.10: # 10% chance to miscount this item type
                        error_amount = random.choice([-1, 1])
                        recorded_qty = actual_qty + error_amount

                        # Ensure recorded quantity doesn't go below zero
                        recorded_inventory[item_name] = max(0, recorded_qty)

                        if recorded_inventory[item_name] != actual_qty:
                             miscounted_items.append(f"{item_name} (actual: {actual_qty}, recorded: {recorded_inventory[item_name]})")

                if miscounted_items:
                    self.add_memory(f"Was a bit careless counting stockpile {stockpile_obj.name}. Might have miscounted: {', '.join(miscounted_items)}.")
                    print(f"{self.name} (Bookkeeper, Careless) may have miscounted {stockpile_obj.name}. Actual: {actual_inventory}, Recorded for Ledger: {recorded_inventory}")

            world.ledger.update_stockpile_record(stockpile_obj.name, recorded_inventory, world.game_time.current_day)
            self.add_memory(f"Counted {stockpile_obj.name}"); print(f"{self.name} (Bookkeeper) finished counting {stockpile_obj.name}. Ledger updated with: {recorded_inventory}. Day: {world.game_time.current_day}.")
            self.counting_target_stockpile_name=None;self.current_goal="Maintain Ledger";self.decide_action(world)
        else:self.move_towards(spot[0],spot[1],world)
    def _execute_perform_woodcutter_duties(self, world: 'World'):
        if self.job!="Woodcutter":self.current_goal=self.job_default_goal();return
        quota=self.needs.get("Wood",5);inv_val=self.inventory.get("Wood",0)
        if self.get_inventory_load()>=self.max_inventory_items and inv_val>0:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        elif inv_val<quota:self.current_goal="Gather Wood"
        else:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        if self.current_goal != "Perform Woodcutter Duties": self.decide_action(world)
    def _execute_perform_stonemason_duties(self, world: 'World'):
        if self.job != "Stonemason": self.current_goal = self.job_default_goal(); return
        quota = self.needs.get("Stone", 5); inv_val = self.inventory.get("Stone", 0)
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        elif inv_val < quota: self.current_goal = "Gather Stone"
        else: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        if self.current_goal != "Perform Stonemason Duties": self.decide_action(world)

    def _execute_initiate_hauling(self, world: 'World'):
        # print(f"DEBUG_HAUL_INIT: {self.name} starting _execute_initiate_hauling. Hauling info: {self.hauling_info}") # DEBUG
        if not self.hauling_info:
            # print(f"DEBUG_HAUL_INIT: {self.name} no hauling info. Goal to default/Idle.") # DEBUG
            self.current_goal=self.job_default_goal() or "Idle"; return
        res=self.hauling_info.get("resource")
        # print(f"DEBUG_HAUL_INIT: {self.name} hauling resource: {res}") # DEBUG
        if not res or self.inventory.get(res,0)==0:
            # print(f"DEBUG_HAUL_INIT: {self.name} resource {res} not in inventory or no res. Goal to default/Idle. Inv: {self.inventory}") # DEBUG
            self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None; return # Removed decide_action(world)

        qty=self.inventory.get(res,0)
        # Get stockpiles that allow the resource AND have space for the quantity being hauled
        sps=[s_obj for s_obj in world.stockpiles if s_obj.is_allowed(res) and s_obj.has_space_for(res,qty)]
        # print(f"DEBUG_HAUL_INIT: {self.name} looking for stockpile for {qty} {res}. Initial sps count: {len(sps)}. SPs: {[s.name for s in sps]}") # DEBUG

        if not sps:
            # If it's a tool and no specific stockpile was found, try the ToolShed explicitly if it allows it.
            if BLUEPRINTS.get(res, {}).get("type") == "Tool":
                # print(f"DEBUG_HAUL_INIT: {res} is a tool. Explicitly checking ToolShed.") # DEBUG
                tool_shed = world.get_stockpile_by_name("ToolShed")
                if tool_shed and tool_shed.is_allowed(res) and tool_shed.has_space_for(res,qty):
                    sps = [tool_shed]
                    # print(f"DEBUG_HAUL_INIT: Found ToolShed for {res}.") # DEBUG

            if not sps: # Still no stockpile after checking specific + ToolShed fallback
                print(f"{self.name} wants to haul {qty} {res} but no suitable stockpile found. Will Wander.")
                self.current_goal="Wander"; return

        sp_chosen=sps[0] # Could be more sophisticated in choosing (e.g. closest, most space)
        self.hauling_info["target_stockpile_name"]=sp_chosen.name
        self.hauling_info["quantity_to_haul"]=qty
        self.current_goal="Haul Resource to Stockpile"
        # print(f"DEBUG_HAUL_INIT: {self.name} chose stockpile {sp_chosen.name} for {qty} {res}. Goal set to: {self.current_goal}") # DEBUG
        # self.decide_action(world) # Not needed here, current_goal change is enough for next tick

    def _execute_haul_resource(self, world: 'World'):
        if not self.hauling_info: self.current_goal = self.job_default_goal() or "Idle"; return
        sp_name=self.hauling_info.get("target_stockpile_name");res=self.hauling_info.get("resource")
        if not res or self.inventory.get(res,0)==0:self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None;self.decide_action(world);return
        sp_obj=world.get_stockpile_by_name(sp_name)
        if not sp_obj:self.current_goal="Wander";self.hauling_info=None;return
        spot=sp_obj.deposit_tiles[0]if sp_obj.deposit_tiles else None
        if not spot:self.current_goal="Wander";self.hauling_info=None;return
        if(self.x,self.y)==spot:
            qty_dep=self.inventory.get(res,0);s_success,qty_add=sp_obj.add_item(res,qty_dep)
            if s_success and qty_add>0: self.inventory[res]-=qty_add; self.add_memory(f"Hauled {qty_add} {res} to {sp_obj.name}.")
            current_res_in_inv = self.inventory.get(res,0)
            if current_res_in_inv <= 0 :
                if res in self.inventory: del self.inventory[res]
            if self.hauling_info and self.hauling_info.get("is_crafted_item") and self.inventory.get(res,0) == 0: # Check specific resource hauled
                wo_id = self.hauling_info.get("for_wo_id")
                order = world.get_work_order_by_id(wo_id) if wo_id else None
                if order and order.assigned_to == self.name and order.status == "InProgress":
                    order.status = "Completed"; print(f"{self.name} COMPLETED and STOCKED Work Order {order.order_id} ({res})."); self.add_memory(f"Completed WO {order.order_id} ({res}).")
                self._reset_crafting_state(); self.current_goal=self.job_default_goal() or "Idle"
            else: self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None
        else:self.move_towards(spot[0],spot[1],world)
    def _execute_gather_wood(self, world: 'World'):
        task_loc = self.find_task_location("Chop Wood", world)
        if not task_loc : print(f"{self.name} can't find Forest for Chop Wood."); self.current_goal = "Idle"; return
        if (self.x, self.y) != task_loc: self.move_towards(task_loc[0], task_loc[1], world); return
        if not self._execute_generic_task(world, "Chop Wood"): return
        inv_wood = self.inventory.get("Wood",0); job_quota = self.needs.get("Wood",5) if self.job == "Woodcutter" else float('inf')
        if self.get_inventory_load()>=self.max_inventory_items or inv_wood >= job_quota : self.current_goal = "Perform Woodcutter Duties"
    def _execute_gather_stone(self, world: 'World'):
        task_loc = self.find_task_location("Mine Stone", world)
        if not task_loc : print(f"{self.name} can't find Rocks for Mine Stone."); self.current_goal = "Idle"; return
        if (self.x, self.y) != task_loc: self.move_towards(task_loc[0], task_loc[1], world); return
        if not self._execute_generic_task(world, "Mine Stone"): return
        inv_stone = self.inventory.get("Stone",0); job_quota = self.needs.get("Stone",5) if self.job == "Stonemason" else float('inf')
        if self.get_inventory_load()>=self.max_inventory_items or inv_stone >= job_quota: self.current_goal = "Perform Stonemason Duties"
    def _execute_oversee_expedition(self, world: 'World'):
         if self.job != "Expedition Leader": self.current_goal = self.job_default_goal(); return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = "Idle"
    def _execute_wander(self, world: 'World'):
        moves=[];
        for dx,dy in[(0,1),(0,-1),(1,0),(-1,0)]:
            tx,ty=self.x+dx,self.y+dy
            if 0<=tx<world.grid_size[0] and 0<=ty<world.grid_size[1] and \
                world.get_tile(tx,ty)not in["Water","Mountain","Forest","Rocks","SP_Mai","SP_Woo","SP_Sto"] and \
                not world.get_characters_at_location(tx,ty):moves.append((dx,dy))
        if moves:choice=random.choice(moves);self.move(choice[0],choice[1],world)

    def decide_action(self, world: 'World'): # Main entry point
        if not world.game_time: print(f"CRITICAL ERROR for {self.name}: world.game_time not set."); self.current_goal = "Idle"; return

        # 0. Handle ongoing multi-tick goals first
        if self.current_goal == "Fetch Tool":
            if self._execute_fetch_tool(world): return # Still fetching
            # If fetching done (returned False), new goal is set by _execute_fetch_tool, re-evaluate.
            self.decide_action(world); return
        elif self.current_goal == "Execute Craft Order" and self.active_work_order_id:
            self._execute_craft_order(world); return
        elif self.current_task_def_name and self.current_goal in JOB_TASK_DEFINITIONS:
            if self._execute_generic_task(world, self.current_task_def_name):
                # Check if the overarching goal (e.g. Perform Woodcutter Duties) is complete due to this task.
                # This check is now mostly within the _execute_gather_X methods themselves.
                return
            else: # False from _execute_generic_task means tool fetch was initiated.
                  # current_goal is now "Fetch Tool", let main loop re-evaluate.
                  self.current_task_def_name = None; self.task_work_progress = 0;
                  self.decide_action(world); return

        # If goal changed from a generic task (e.g. tool broke, now current_goal is "Fetch Tool")
        # but we didn't return above, ensure task tracking is reset.
        # This is now handled because Fetch Tool is at the top. If _execute_generic_task sets Fetch Tool, it returns False,
        # and the recursive call in decide_action will then hit the Fetch Tool block.
        if self.current_goal not in JOB_TASK_DEFINITIONS and self.current_task_def_name: # If goal changed away from a generic task
             self.current_task_def_name = None; self.task_work_progress = 0

        # 1. Interaction Check (if not busy with an active craft order or fetching tool)
        # Simplified for now, can be expanded
        # other_chars_here = [c for c in world.get_characters_at_location(self.x, self.y) if c.name != self.name]
        # if other_chars_here and self.current_goal in ["Wander", "Idle", None] and not self.active_work_order_id :
        #     self.interact(other_chars_here[0], world); return

        # 2. Opportunistic Work Order Claiming / Resuming
        # Check if character is available (idle, wandering, or their job allows picking up WOs)
        can_look_for_wo = self.current_goal in [None, "Idle", "Wander"] or \
                          (self.job in ["Master Craftsman", "Expedition Leader", "Manager"] and self.current_goal in ["Assess Production Needs", "Oversee Expedition", "Manage Work Orders", "Idle", None])

        if can_look_for_wo:
            # First, check if there's an InProgress or Approved order already assigned to this character that they dropped
            if not self.active_work_order_id and not self.active_build_order_id: # Only if not already on one
                resumed_order = False
                for order in world.work_orders:
                    if order.assigned_to == self.name and order.status in ["InProgress", "Approved"]:
                        if order.order_type == "CraftItem":
                            if order.status == "Approved": # Set to InProgress if resuming an Approved order
                                order.status = "InProgress"
                            self.active_work_order_id = order.order_id
                            self.current_goal = "Execute Craft Order"
                            # self.workshop_location might need reset or re-evaluation here if resuming
                            # For now, _execute_craft_order handles workshop finding.
                            self.add_memory(f"Resuming Craft WO {order.order_id} for {order.details.get('item_name')}.")
                            print(f"{self.name} RESUMING Craft Work Order {order.order_id} ({order.details.get('item_name')}).")
                            self._execute_craft_order(world); resumed_order = True; break
                        elif order.order_type == "BuildStructure":
                            if order.status == "Approved": # Set to InProgress
                                order.status = "InProgress"
                            self.active_build_order_id = order.order_id
                            self.current_building_project = order.details.get("structure_type")
                            self.building_site_target = order.details.get("location")
                            self.current_goal = "Execute Build Order"
                            self.add_memory(f"Resuming Build WO {order.order_id} for {order.details.get('structure_type')}.")
                            print(f"{self.name} RESUMING Build Work Order {order.order_id} ({order.details.get('structure_type')}).")
                            self._execute_build_order(world); resumed_order = True; break
                if resumed_order: return

            # If no order resumed, try to claim a NEW Craft order
            if not self.active_work_order_id and not self.active_build_order_id: # Still no active WO
                if self.skills:
                    approved_craft_orders = world.get_approved_craft_orders() # These are unassigned
                    if approved_craft_orders:
                        for order in approved_craft_orders:
                            # No need to check order.assigned_to is None, as get_approved_craft_orders handles it
                            item_name = order.details.get("item_name")
                            if item_name and item_name in BLUEPRINTS:
                                required_skill_type = BLUEPRINTS[item_name].get("job_skill_needed")
                                if required_skill_type and self.skills.get(required_skill_type, 0) > 0:
                                    order.status = "InProgress"; order.assigned_to = self.name
                                    self._reset_crafting_state(); self.active_work_order_id = order.order_id
                                    self.current_goal = "Execute Craft Order"; self.workshop_location = (self.x, self.y)
                                    self.add_memory(f"Claimed Craft WO {order.order_id} for {item_name}.")
                                    print(f"{self.name} CLAIMED Craft Work Order {order.order_id} ({item_name}) skill: {required_skill_type}.")
                                    self._execute_craft_order(world); return

            # If no CRAFT order was claimed or resumed, try to claim a NEW BUILD order
            if not self.active_work_order_id and not self.active_build_order_id:
                if self.job == "Builder" or self.skills.get("Construction", 0) > 0:
                    build_orders = world.get_approved_build_orders() # These are unassigned

                    if build_orders:
                        order_to_take = build_orders[0]
                        structure_bp_name = order_to_take.details.get("structure_type")
                        if structure_bp_name and structure_bp_name in STRUCTURE_BLUEPRINTS: # Use direct import
                            bp = STRUCTURE_BLUEPRINTS[structure_bp_name]
                        req_skill_dict = bp.get("required_skill", {})
                        can_build = True
                        if req_skill_dict:
                            for skill_name, level_needed in req_skill_dict.items():
                                if self.skills.get(skill_name, 0) < level_needed:
                                    can_build = False; break

                        if can_build:
                            order_to_take.status = "InProgress"; order_to_take.assigned_to = self.name
                            self._reset_building_state(); self.active_build_order_id = order_to_take.order_id
                            self.current_building_project = structure_bp_name
                            self.building_site_target = order_to_take.details.get("location")
                            self.current_goal = "Execute Build Order"
                            self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {structure_bp_name} at {self.building_site_target}.")
                            print(f"{self.name} CLAIMED Build Work Order {order_to_take.order_id} ({structure_bp_name} at {self.building_site_target}).")
                            self._execute_build_order(world); return # Start immediately


        # 3. Check for Needs-Driven Goals (like Socializing)
        # This should come before falling back to default job goal if idle.
        if self.current_goal in [None, "Idle", "Wander"] and not self.active_work_order_id and not self.active_build_order_id:
            # Check Social Need
            social_need_threshold = 20 # Example threshold
            if self.needs.get("Social", 50) < social_need_threshold:
                # Trait influences on deciding to socialize
                can_socialize_based_on_trait = True
                if "Loner" in self.traits:
                    if random.random() < 0.75: # 75% chance a Loner will NOT socialize even if need is low
                        can_socialize_based_on_trait = False

                if can_socialize_based_on_trait:
                    # Higher chance for Outgoing characters if their need isn't critically low yet
                    if "Outgoing" in self.traits and self.needs.get("Social", 50) < (social_need_threshold + 15):
                         if random.random() < 0.5: # 50% chance for Outgoing to socialize a bit earlier
                            self.current_goal = "Socialize"
                            # self.decide_action(world) # Re-evaluate to execute Socialize
                            # No, don't recurse here. Let the main goal execution part handle it.
                    elif "Outgoing" not in self.traits or random.random() < 0.2: # Non-outgoing or less chance for outgoing if need not critical
                        self.current_goal = "Socialize"

            # If Socialize wasn't chosen, then fall back to job default goal
            if not self.current_goal or self.current_goal in [None, "Idle", "Wander"]: # Check if goal was set to Socialize
                 self.current_goal = self.job_default_goal()


        # 4. Execute Current Goal
        # Handle multi-tick goals that were set directly (like Execute Build/Craft Order)
        if self.current_goal == "Execute Craft Order" and self.active_work_order_id: # Already handled at top
            pass # self._execute_craft_order(world) was called if this was just set
        elif self.current_goal == "Execute Build Order" and self.active_build_order_id:
            self._execute_build_order(world); return


        if self.current_goal == "Assess Production Needs": self._execute_assess_production_needs(world); return
        elif self.current_goal == "Manage Subordinates": self._execute_manage_subordinates(world); return
        elif self.current_goal == "Manage Work Orders": self._execute_manage_work_orders_as_part_of_supervision(world); return
        elif self.current_goal == "Maintain Ledger": self._execute_maintain_ledger(world); return
        elif self.current_goal == "Count Stockpile": self._execute_count_stockpile(world); return
        elif self.current_goal == "Perform Woodcutter Duties": self._execute_perform_woodcutter_duties(world); return
        elif self.current_goal == "Perform Stonemason Duties": self._execute_perform_stonemason_duties(world); return
        elif self.current_goal == "Perform Builder Duties": self._execute_perform_builder_duties(world); return # New
        elif self.current_goal == "Initiate Hauling": self._execute_initiate_hauling(world); return
        elif self.current_goal == "Haul Resource to Stockpile": self._execute_haul_resource(world); return
        elif self.current_goal == "Gather Wood": self._execute_gather_wood(world); return
        elif self.current_goal == "Gather Stone": self._execute_gather_stone(world); return
        elif self.current_goal == "Oversee Expedition": self._execute_oversee_expedition(world); return
        elif self.current_goal == "Socialize": self._execute_socialize(world); return

        # 5. Fallback to Wander/Idle
        if self.current_goal is None or self.current_goal == "Idle":
            if random.random() < 0.05: self.current_goal = "Wander" # Low chance if truly has nothing else to do
            else: return # Remain Idle for this tick

        if self.current_goal == "Wander": self._execute_wander(world); return

        # Failsafe: If goal is somehow not covered, set to Idle to prevent loops
        # print(f"Warning: {self.name} has unhandled goal '{self.current_goal}'. Setting to Idle.")
        # self.current_goal = "Idle"
        return

    def _execute_socialize(self, world: 'World'):
        task_def = JOB_TASK_DEFINITIONS.get("Socialize")
        if not task_def:
            print(f"CRITICAL: 'Socialize' task definition not found for {self.name}.")
            self.current_goal = "Idle"; return

        socialize_duration = task_def.get("base_time_per_yield", 5)

        # Targeting Logic (Simplified for now)
        if not hasattr(self, 'socialize_target_name') or not self.socialize_target_name:
            potential_targets = []
            for char in world.characters:
                if char.name == self.name: continue
                # Basic proximity check (e.g., within 5 tiles)
                if abs(char.x - self.x) + abs(char.y - self.y) <= 5:
                    # Avoid targeting those with very poor relationships, unless specific traits dictate otherwise (e.g. "Confrontational")
                    if self.get_relationship_score(char.name) > -75: # Example threshold
                        potential_targets.append(char)

            if not potential_targets:
                self.add_memory("Wanted to socialize, but no one suitable was nearby.")
                self.current_goal = "Idle" # Or Wander
                # Consider a small penalty to social need for failed attempt
                self.needs["Social"] = max(0, self.needs.get("Social", 50) - 2)
                return

            # Pick a target (e.g., random, or closest, or best relationship)
            # For now, random among suitable.
            target_char = random.choice(potential_targets)
            self.socialize_target_name = target_char.name
            self.socialize_target_location = (target_char.x, target_char.y) # Store initial target loc
            self.task_work_progress = 0 # Reset progress for new interaction
            self.add_memory(f"Decided to try and socialize with {self.socialize_target_name}.")
            print(f"{self.name} is attempting to socialize with {self.socialize_target_name}.")

        # Ensure target still exists and is valid
        target_character_obj = None
        for char_obj_check in world.characters:
            if char_obj_check.name == self.socialize_target_name:
                target_character_obj = char_obj_check
                break

        if not target_character_obj:
            self.add_memory(f"Target {self.socialize_target_name} for socialization is no longer available.")
            self.current_goal = "Idle"
            self.socialize_target_name = None
            self.task_work_progress = 0
            return

        # Movement: Move towards target if not adjacent (or on same tile)
        # Using a simple adjacency check for interaction
        if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 1 : # Not adjacent or same tile
            # Update target location if they moved
            self.socialize_target_location = (target_character_obj.x, target_character_obj.y)
            self.move_towards(self.socialize_target_location[0], self.socialize_target_location[1], world)
            # Check if target moved too far or became invalid during approach
            if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 7: # Target moved too far
                 self.add_memory(f"{self.socialize_target_name} moved too far away to socialize.")
                 self.current_goal = "Idle"; self.socialize_target_name = None; self.task_work_progress = 0; return
            return # Still moving

        # Interaction Phase (once adjacent or on same tile)
        # print(f"DEBUG: {self.name} is now close enough to {target_character_obj.name} to socialize. Progress: {self.task_work_progress}/{socialize_duration}")
        self.task_work_progress += 1

        if self.task_work_progress >= socialize_duration:
            # --- Determine Interaction Outcome ---
            base_change_initiator = random.randint(1, 3)
            base_change_target = random.randint(0, 2)

            # Initiator's trait effects
            if "Friendly" in self.traits: base_change_initiator += 2
            if "Grumpy" in self.traits: base_change_initiator -= 2
            if "Charismatic" in self.traits: base_change_initiator = int(base_change_initiator * 1.5)

            # Target's trait effects on how they perceive initiator
            if "Friendly" in target_character_obj.traits: base_change_initiator += 1 # They are more receptive
            if "Grumpy" in target_character_obj.traits: base_change_initiator -= 1 # They are less receptive

            # Existing relationship influence
            initiator_rel_to_target = self.get_relationship_score(target_character_obj.name)
            if initiator_rel_to_target > 50: base_change_initiator += 2
            elif initiator_rel_to_target < -50: base_change_initiator -= 5 # High chance of bad outcome

            # Modify relationships
            interaction_description = "a neutral chat"
            if base_change_initiator > 3: interaction_description = "a pleasant chat"
            elif base_change_initiator < 0: interaction_description = "an awkward/tense interaction"

            self.modify_relationship(target_character_obj.name, base_change_initiator, world, reason=f"Had {interaction_description} with them.")
            # Target's perception of the interaction (could be different)
            # For simplicity now, let's make target's change a fraction of initiator's, influenced by their own traits
            target_rel_change = base_change_target
            if "Grumpy" in target_character_obj.traits: target_rel_change -=1
            if "Friendly" in target_character_obj.traits: target_rel_change +=1
            if self.get_relationship_score(target_character_obj.name) < -50 : target_rel_change -=2 # If target dislikes initiator a lot

            target_character_obj.modify_relationship(self.name, target_rel_change, world, reason=f"They had {interaction_description} with me.")

            # Memories
            self.add_memory(f"Socialized with {target_character_obj.name}. It was {interaction_description}.")
            target_character_obj.add_memory(f"{self.name} socialized with me. It was {interaction_description}.")
            print(f"{self.name} finished socializing with {target_character_obj.name}. Rel change for {self.name}: {base_change_initiator}, for {target_character_obj.name}: {target_rel_change}")

            # Update Social Need
            self.needs["Social"] = min(100, self.needs.get("Social", 50) + random.randint(15, 30)) # Significant boost
            target_character_obj.needs["Social"] = min(100, target_character_obj.needs.get("Social", 50) + random.randint(10, 20))

            # Dialogue Snippets
            dialogue_context_key = "social_chat_neutral" # Default
            if base_change_initiator > 3: dialogue_context_key = "social_chat_positive"
            elif base_change_initiator < 0: dialogue_context_key = "social_chat_negative"

            if config.USE_LLM:
                # Initiator's perspective/utterance
                initiator_dialogue = generate_dialogue(self.name, target_character_obj.name, f"{dialogue_context_key}_initiator", world, self.personality, self.traits, target_character_obj.personality, target_character_obj.traits, initiator_rel_to_target)
                self.add_memory(f"Said to {target_character_obj.name}: \"{initiator_dialogue}\"")
                target_character_obj.add_memory(f"Heard from {self.name}: \"{initiator_dialogue}\"")

                # Target's perspective/response (could be a separate call or inferred)
                # For simplicity, let's assume a brief response could also be generated or templated
                # target_response = generate_dialogue(target_character_obj.name, self.name, f"{dialogue_context_key}_target_response", world, ...)
                # target_character_obj.add_memory(f"Replied to {self.name}: \"{target_response}\"")
                # self.add_memory(f"Heard from {target_character_obj.name}: \"{target_response}\"")
            else:
                # Simple template if LLM is off
                placeholder_dialogue = f"Exchanged pleasantries with {target_character_obj.name}."
                if dialogue_context_key == "social_chat_negative":
                    placeholder_dialogue = f"Had a tense exchange with {target_character_obj.name}."
                elif dialogue_context_key == "social_chat_positive":
                    placeholder_dialogue = f"Had a nice chat with {target_character_obj.name}."
                self.add_memory(f"[LLM Off] {placeholder_dialogue}")
                target_character_obj.add_memory(f"[LLM Off] {placeholder_dialogue}")


            # Reset for next potential socialization
            self.current_goal = "Idle" # Or back to job_default_goal
            self.socialize_target_name = None
            self.task_work_progress = 0
        else:
            # Interaction ongoing, check if target is still valid and willing
            if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 2 or \
               (target_character_obj.current_goal not in ["Socialize", "Idle", "Wander", None] and not target_character_obj.active_work_order_id): # Target moved or got busy
                self.add_memory(f"Social interaction with {self.socialize_target_name} was cut short.")
                print(f"{self.name}'s social interaction with {self.socialize_target_name} cut short.")
                self.current_goal = "Idle"
                self.socialize_target_name = None
                self.task_work_progress = 0
                # Smaller social need recovery for incomplete interaction
                self.needs["Social"] = min(100, self.needs.get("Social", 50) + random.randint(1,5))


    def _execute_perform_builder_duties(self, world: 'World'):
        if self.job != "Builder" and self.skills.get("Construction", 0) == 0 : # Must be a builder or have construction skill
            self.current_goal = self.job_default_goal() or "Idle"
            return

        if not self.active_build_order_id:
            # Try to claim a build order (logic is already in decide_action, so this might just set to Idle if none found)
            # For now, if no active order, let decide_action try to pick one up next tick or set to Idle.
            # If we want proactive searching, it would mirror the logic in decide_action's WO claiming section.
            self.current_goal = "Idle" # Will re-evaluate in decide_action
            return
        else: # Has an active build order
            self.current_goal = "Execute Build Order"
            # self.decide_action(world) # Let main loop call _execute_build_order

    def _execute_fetch_resource_for_build(self, world: 'World'):
        if not self.resource_to_fetch:
            # This case should ideally be handled by the caller ensuring resource_to_fetch is set.
            # If it's None, it means we believe we have this item, or can't get it.
            return

        res_name = self.resource_to_fetch["name"]
        # Quantity in self.resource_to_fetch is the *remaining amount needed for this resource type for the project*
        quantity_needed_for_project_for_this_type = self.resource_to_fetch["quantity"]

        if quantity_needed_for_project_for_this_type <= 0: # Already gathered enough of this type
            self.resource_to_fetch = None
            return

        # Determine stockpile
        target_sp_name = self.resource_to_fetch.get("target_stockpile_name")
        sp_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None

        if not sp_to_fetch or sp_to_fetch.inventory.get(res_name, 0) == 0:
            # Find a new stockpile if current one is invalid or empty for this resource
            suitable_sps = [sp for sp in world.get_stockpiles_for_resource(res_name) if sp.inventory.get(res_name, 0) > 0]
            if not suitable_sps:
                print(f"{self.name} needs {res_name} for building, but none in any stockpiles. Waiting.")
                # Don't clear resource_to_fetch, still need it. Character will pause.
                return
            sp_to_fetch = suitable_sps[0]
            self.resource_to_fetch["target_stockpile_name"] = sp_to_fetch.name

        # Move to stockpile
        spot = (sp_to_fetch.rect[0], sp_to_fetch.rect[1])
        if (self.x, self.y) != spot:
            self.move_towards(spot[0], spot[1], world)
            return

        # At stockpile: try to take items
        max_can_carry_this_trip = self.max_inventory_items - self.get_inventory_load()

        # How much to take: minimum of what's needed for this type for project, what's available in SP, and what char can carry now
        qty_to_attempt_take = min(quantity_needed_for_project_for_this_type,
                                  sp_to_fetch.inventory.get(res_name,0),
                                  max_can_carry_this_trip)

        if qty_to_attempt_take <= 0:
            # Cannot take any. Either full, or SP is empty for this item (should have been caught earlier unless race condition).
            # If full (max_can_carry_this_trip == 0), the main build logic should transition to going to site.
            # For now, this function's job is done for this tick if it can't pick up.
            # The self.resource_to_fetch remains, indicating the need is still there.
            return

        s, qty_taken = sp_to_fetch.remove_item(res_name, qty_to_attempt_take)
        if s and qty_taken > 0:
            self.inventory[res_name] = self.inventory.get(res_name, 0) + qty_taken
            self.add_memory(f"Fetched {qty_taken} {res_name} from {sp_to_fetch.name} for building.")

            # Reduce the overall remaining quantity needed for this resource type
            self.resource_to_fetch["quantity"] -= qty_taken
            if self.resource_to_fetch["quantity"] <= 0:
                self.resource_to_fetch = None # All of this specific resource type has been gathered for the project
        # If failed to take or took 0, self.resource_to_fetch remains, will retry or be re-evaluated.


    def _execute_build_order(self, world: 'World'):
        # current_time_str = str(world.game_time.current_total_ticks) if world.game_time else "N/A_TIME" # DEBUG
        # print(f"TOP_DEBUG {self.name} tick {current_time_str}: Goal='{self.current_goal}', BuildWO='{self.active_build_order_id}', Pos:({self.x},{self.y}), TargetSite:{self.building_site_target}, MatsGathered:{self.materials_gathered_for_build}, InvLoad:{self.get_inventory_load()}/{self.max_inventory_items}, ResToFetch:{self.resource_to_fetch}") # DEBUG

        if not self.active_build_order_id or not self.current_building_project or not self.building_site_target:
            self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"; return

        order = world.get_work_order_by_id(self.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name:
            self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"; return

        structure_blueprint_name = order.details["structure_type"]
        structure_bp = STRUCTURE_BLUEPRINTS.get(structure_blueprint_name)
        if not structure_bp:
            print(f"Error: Unknown structure blueprint {structure_blueprint_name} for WO {order.order_id}.")
            order.status = "Denied"; order.denial_reason = f"Unknown structure blueprint {structure_blueprint_name}"
            self._reset_building_state(); self.current_goal = "Idle"; return

        required_resources_total = structure_bp["required_resources"]

        # 1. Material Gathering Phase
        if not self.materials_gathered_for_build:
            # A. Are we currently trying to fetch something specific?
            if self.resource_to_fetch:
                # If inventory is full, stop fetching this specific item for now and allow logic to proceed.
                # This might mean going to the site if other conditions determine that.
                if self.get_inventory_load() >= self.max_inventory_items:
                    # print(f"DEBUG: {self.name} is full while self.resource_to_fetch is {self.resource_to_fetch['name']}. Clearing to allow site move.")
                    self.resource_to_fetch = None
                    # Fall through to re-evaluate overall needs / decide to move to site
                else:
                    self._execute_fetch_resource_for_build(world) # Try to fetch
                    # If still actively fetching (e.g., moving to SP, or got some but not all of this type needed yet and not full)
                    if self.resource_to_fetch and self.resource_to_fetch.get("name"):
                        return # Continue fetching next tick
                    # If self.resource_to_fetch is None here, it means all of *this type* is gathered. Fall through to check overall.

            # B. Determine if all project materials are gathered, or what to fetch next.
            # This block is reached if not initially fetching OR finished fetching one type OR was full and cleared self.resource_to_fetch.
            all_project_materials_in_inventory = True
            resource_type_to_target_next = None

            for res, total_qty_needed in required_resources_total.items():
                if self.inventory.get(res, 0) < total_qty_needed:
                    all_project_materials_in_inventory = False
                    resource_type_to_target_next = res # This is the next type we need to get
                    break

            if all_project_materials_in_inventory:
                self.materials_gathered_for_build = True
                self.resource_to_fetch = None # Ensure cleared
                print(f"{self.name} has all materials ({self.inventory}) for {structure_blueprint_name} for WO {order.order_id}.")
                # Fall through to site movement & work phase
            elif resource_type_to_target_next:
                # We need more of 'resource_type_to_target_next'.
                # If inventory is already full, we must go to site (fall through to Phase 2).
                if self.get_inventory_load() < self.max_inventory_items:
                    # Not full, so set up to fetch this next resource type.
                    # print(f"DEBUG: {self.name} needs {resource_type_to_target_next}, inventory not full. Setting fetch target.")
                    self.resource_to_fetch = {
                        "name": resource_type_to_target_next,
                        "quantity": required_resources_total[resource_type_to_target_next] - self.inventory.get(resource_type_to_target_next, 0),
                        "for_wo_id": order.order_id, "target_type": "build"
                    }
                    self._execute_fetch_resource_for_build(world) # Start/continue fetching it
                    return # Done for this tick, fetching in progress.
                # else: Inventory is full. Fall through to Phase 2 (Go to Build Site).
                # print(f"DEBUG: {self.name} needs {resource_type_to_target_next}, but inventory IS full. Will fall through to move to site.")
            else:
                # This state implies not all materials are gathered, but no specific next one was identified.
                # This could happen if required_resources_total is empty, or some logic error.
                # Or, if all_project_materials_in_inventory was false but the loop didn't find a specific missing item.
                print(f"Warning: {self.name} in build order ({order.order_id}), materials_gathered_for_build is False, but no specific next resource identified. Inventory: {self.inventory}. Required: {required_resources_total}")
                # To prevent loops, if we are in this ambiguous state, and inventory is not empty, try going to site.
                if self.get_inventory_load() > 0:
                    pass # Fall through to attempt moving to site
                else: # No materials and stuck, probably idle.
                    self.current_goal = "Idle"
                    return

        # Phase 2: Go to Build Site
        # Ensure world.game_time is available before trying to access current_total_ticks
        current_time_str_phase2 = "N/A_TIME_P2"
        if world.game_time:
            current_time_str_phase2 = str(world.game_time.current_total_ticks)
        print(f"PRINT_DEBUG: {self.name} tick {current_time_str_phase2}: Trying Phase 2. Pos:({self.x},{self.y}) Target:{self.building_site_target} FullInv:{self.get_inventory_load() >= self.max_inventory_items} MatsGathered:{self.materials_gathered_for_build} ResToFetch:{self.resource_to_fetch}")

        if (self.x, self.y) != self.building_site_target:
            self.move_towards(self.building_site_target[0], self.building_site_target[1], world)
            return

        # Phase 3: At Build Site: Find or Create Building Object & Work
        target_building: Optional[Building] = None
        for b in world.buildings: # Try to find existing building project at location
            if b.location == self.building_site_target and b.structure_type == structure_blueprint_name and not b.is_operational:
                target_building = b
                break

        if not target_building: # If building doesn't exist yet, create it (first time working on it)
            print(f"First work on {structure_blueprint_name} at {self.building_site_target}. Creating building object.")
            target_building = Building(
                structure_type=structure_blueprint_name,
                display_name=structure_bp["display_name"],
                location=self.building_site_target,
                size=structure_bp["size"],
                required_resources=structure_bp["required_resources"], # For reference, actual consumption below
                build_time=structure_bp["build_time"],
                functionality=structure_bp.get("functionality"),
                required_skill=structure_bp.get("required_skill")
            )
            world.add_building(target_building)

            # Consume all resources from inventory now that work is starting at the site
            # This is a simplification; could be incremental.
            # This should only consume what's available, up to what's needed.
            # And only if materials_gathered_for_build is TRUE, or if this is a partial delivery.
            # For now, this consumes based on required_resources_total, which is wrong for partial.
            # This needs to be smarter - consume only what's IN inventory for this trip.

            # Let's change this: the Building object itself should store what it still needs.
            # For now, the character just "works" and we assume materials are magically there if they arrived.
            # The "Used resources" printout should reflect what's *actually used* from inventory for this work session.

            # Corrected consumption: Consume what's in inventory relevant to the project
            temp_inv_copy = self.inventory.copy() # To iterate while modifying
            resources_consumed_this_session = {}
            for res_name, res_needed_total in required_resources_total.items():
                # How much does the building *still* need of this, if we were to track it on the building?
                # For now, assume this first work session tries to use up all relevant held materials.
                if res_name in temp_inv_copy:
                    qty_to_use = temp_inv_copy[res_name] # Use all of this type currently held
                    # In a more advanced model, check against building.remaining_needed[res_name]

                    self.inventory[res_name] -= qty_to_use
                    if self.inventory[res_name] <= 0:
                        del self.inventory[res_name]
                    resources_consumed_this_session[res_name] = qty_to_use

            if resources_consumed_this_session:
                 self.add_memory(f"Used {resources_consumed_this_session} for {structure_blueprint_name} at {self.building_site_target}.")
                 print(f"{self.name} used resources {resources_consumed_this_session} for {structure_blueprint_name} at {self.building_site_target}. Inv: {self.inventory}")
            else:
                 print(f"{self.name} at build site for {structure_blueprint_name}, but no relevant materials in inventory to consume. Inv: {self.inventory}")


        if target_building and not target_building.is_operational:
            # Use "Construct Building" task definition for work rate
            task_def = JOB_TASK_DEFINITIONS.get("Construct Building")
            if not task_def:
                print(f"CRITICAL: 'Construct Building' task definition not found for {self.name}.")
                self.current_goal = "Idle"; return

            # Apply work (progress gain can be modified by traits/skills later)
            # For now, simple base_yield from task_def
            progress_this_tick = float(task_def.get("base_yield", 1)) # Start as float for multipliers

            # Apply character status effect modifiers (e.g., "Sick" reduces work speed)
            work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
            progress_this_tick *= work_speed_modifier

            # Apply Construction skill level modifier
            construction_skill_level = self.skills.get("Construction", {}).get("level", 0)
            progress_this_tick *= (1 + construction_skill_level * 0.05) # 5% increase per level

            # TODO: Add trait effects on construction speed (Diligent, Lazy, Focused) - can further modify progress_this_tick
            # Similar to _execute_generic_task or _execute_craft_order. For now, skill and status are main drivers.

            actual_progress_applied = target_building.work_on(progress_this_tick) # work_on should return actual progress

            # Grant Construction XP based on actual progress made
            if actual_progress_applied > 0:
                # Ensure "Construction" skill exists or is initialized by _grant_skill_experience
                self._grant_skill_experience("Construction", float(actual_progress_applied) * 1.0, world) # Example: 1 XP per unit of progress

            self.add_memory(f"Worked on {target_building.display_name} (+{actual_progress_applied:.1f} progress). Total: {target_building.current_progress:.1f}/{target_building.build_time}")
            # print(f"{self.name} worked on {target_building.display_name} (+{actual_progress_applied:.1f}). Prog: {target_building.current_progress:.1f}/{target_building.build_time}")


            if target_building.is_operational:
                order.status = "Completed"
                self.add_memory(f"Completed Build WO {order.order_id} for {target_building.display_name}.")
                print(f"{self.name} COMPLETED Build Work Order {order.order_id} for {target_building.display_name} at {target_building.location}.")
                self._reset_building_state()
                # Check if all materials were truly gathered, if not, this is an issue.
                # For now, assume if building is operational, all materials must have been used.
                self.materials_gathered_for_build = True # Ensure this is set if somehow missed
                self.current_goal = self.job_default_goal() or "Idle"
                # Make character move off the construction site to allow others or clear space
                if self.building_site_target:
                    # Attempt to move to an adjacent free tile
                    adj_free_tile = None
                    for dx_try, dy_try in [(0, -1), (0, 1), (-1, 0), (1, 0)]: # Check adjacent N, S, W, E
                        check_x, check_y = self.building_site_target[0] + dx_try, self.building_site_target[1] + dy_try
                        # Check if tile is within bounds and not a blocking type
                        if 0 <= check_x < world.grid_size[0] and 0 <= check_y < world.grid_size[1] and \
                           world.grid[check_x][check_y] not in ["Mountain", "Water"] and \
                           not world.get_characters_at_location(check_x, check_y):
                             # Also ensure it's not part of the building itself
                            is_part_of_building = any( (check_x, check_y) == b_tile for b_obj in world.buildings if b_obj.location == self.building_site_target for b_tile in b_obj.get_tiles_occupied())
                            if not is_part_of_building: # Check if the proposed move-to tile is part of any building at the site.
                                adj_free_tile = (check_x, check_y)
                                break
                    if adj_free_tile:
                        self.move_towards(adj_free_tile[0], adj_free_tile[1], world)
                    else:
                        pass
                return
        elif target_building and target_building.is_operational:
            print(f"Error: Building {target_building.display_name} for WO {order.order_id} is already operational but order not complete?")
            order.status = "Completed"
            self._reset_building_state()
            self.current_goal = self.job_default_goal() or "Idle"
            return

    # --- END OF DECIDE_ACTION and HELPER _execute_ METHODS ---

    # --- Management Actions ---
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

        if not world.game_time: # Should always be set, but good practice
            self.add_memory(f"Cannot conduct review for {subordinate_char_name}, game time not available."); return

        # --- Base Performance Assessment ---
        objective_rating = "Needs Improvement" # Default if no specific positive criteria met
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
            if subordinate.inventory.get("Wood", 0) >= 3: # Arbitrary threshold for "Good"
                objective_rating = "Good"; review_notes.append("Carrying a good amount of Wood.")
            elif subordinate.inventory.get("Wood", 0) > 0:
                objective_rating = "Satisfactory"; review_notes.append("Carrying some Wood.")
            else:
                review_notes.append("Not carrying Wood. Performance based on recent deposits not yet tracked.")
        # Add more job-specific checks here for objective_rating: "Excellent", "Good", "Satisfactory", "Needs Improvement", "Poor"

        # --- Supervisor's Subjective Modifiers ---
        final_rating = objective_rating
        rating_modifier_score = 0 # -2 to +2 scale for simplicity

        # Personality/Traits based modifier
        if "Strict" in self.traits or self.personality == "Demanding": rating_modifier_score -= 1
        if "Kind" in self.traits or self.personality == "Forgiving": rating_modifier_score += 1
        if "Lazy" in self.traits and random.random() < 0.3: rating_modifier_score +=1 # Lazy supervisor might inflate rating

        # Relationship based modifier
        relationship_to_sub = self.get_relationship_score(subordinate.name)
        if relationship_to_sub > 50: rating_modifier_score += 1
        elif relationship_to_sub < -50: rating_modifier_score -= 1

        # Apply modifier score to objective rating
        # Define rating scale: Poor (-2), Needs Improvement (-1), Satisfactory (0), Good (1), Excellent (2)
        rating_scale = {"Poor": -2, "Needs Improvement": -1, "Satisfactory": 0, "Good": 1, "Excellent": 2, "Not Evaluated": 0}
        objective_score = rating_scale.get(objective_rating, 0)

        final_score = max(-2, min(2, objective_score + rating_modifier_score)) # Clamp final score

        for r_name, r_val in rating_scale.items(): # Convert score back to string rating
            if r_val == final_score: final_rating = r_name; break
        if objective_rating == "Not Evaluated": final_rating = "Not Evaluated" # Preserve this specific state

        if final_rating != objective_rating:
            review_notes.append(f"Supervisor's discretion ({self.personality}, Rel: {relationship_to_sub}) adjusted rating from {objective_rating} to {final_rating}.")

        # --- Update Subordinate & Log ---
        subordinate.performance_rating = final_rating
        subordinate.last_performance_review_day = world.game_time.current_day

        relationship_change_value = 0
        if final_rating == "Excellent": relationship_change_value = 10
        elif final_rating == "Good": relationship_change_value = 5
        elif final_rating == "Satisfactory": relationship_change_value = 1
        elif final_rating == "Needs Improvement": relationship_change_value = -5
        elif final_rating == "Poor": relationship_change_value = -10

        if relationship_change_value != 0:
            # Supervisor's feeling towards subordinate might change less, or be more dispositional
            # For now, let's make it a smaller, more tempered change for the supervisor
            self.modify_relationship(subordinate.name, relationship_change_value // 2, world, reason=f"Performance review outcome: {final_rating}")
            # Subordinate's feeling towards supervisor
            subordinate.modify_relationship(self.name, relationship_change_value, world, reason=f"Performance review outcome from {self.name}: {final_rating}")

        # Reset warnings only if performance is not "Poor" or "Needs Improvement" as a result of this review.
        if final_rating not in ["Poor", "Needs Improvement"]:
             if subordinate.warning_count > 0:
                review_notes.append(f"Past warnings ({subordinate.warning_count}) cleared due to improved review.")
                subordinate.warning_count = 0
        elif final_rating == "Poor" and subordinate.warning_count == 0 : # A Poor review itself acts as a first warning
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

        if subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD: # Threshold for automatic performance degradation
            if subordinate.performance_rating != "Poor":
                subordinate.performance_rating = "Poor"
                self.add_memory(f"{subordinate.name}'s performance set to Poor due to {subordinate.warning_count} warnings (Threshold: {config.FIRING_WARNING_THRESHOLD}).")
                subordinate.add_memory(f"Performance automatically set to Poor due to reaching {subordinate.warning_count} warnings.")
                print(f"{subordinate.name}'s performance automatically set to Poor due to {subordinate.warning_count} warnings.")

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

        # Remove from supervisor's list
        if subordinate.name in self.subordinates_names:
            self.remove_subordinate(subordinate.name) # Uses existing method

        # Update subordinate's status
        original_job = subordinate.job
        subordinate.supervisor_name = None
        subordinate.job = "Unemployed"
        subordinate.rank = "Commoner" # Or some other default non-noble/non-worker rank
        subordinate.current_goal = "Idle" # Or "Find New Job" in the future
        subordinate.assigned_tasks = []
        subordinate.performance_rating = "Fired"
        subordinate.warning_count = 0
        # Consider if active work order should be dropped/cancelled
        if subordinate.active_work_order_id:
            wo = world.get_work_order_by_id(subordinate.active_work_order_id)
            if wo and wo.status == "InProgress" and wo.assigned_to == subordinate.name:
                wo.status = "Pending" # Re-queue it
                wo.assigned_to = None
                subordinate.add_memory(f"Work order {subordinate.active_work_order_id} unassigned due to termination.")
                print(f"Work order {subordinate.active_work_order_id} unassigned from {subordinate.name} due to termination.")
            subordinate._reset_crafting_state()


        fire_memory = f"Fired {subordinate.name} from their job as {original_job}."
        self.add_memory(fire_memory)
        print(f"{self.name} FIRED {subordinate.name} who was a {original_job}.")

        subordinate.add_memory(f"Was fired by {self.name} from job {original_job}. Now Unemployed.")

        # Optional: Remove from world or mark inactive. For now, they become "Unemployed".
        # If you want to remove them from the simulation entirely:
        # world.characters.pop(sub_idx)
        # print(f"{subordinate.name} has been removed from the world.")
        # However, this could cause issues if other parts of the code expect the character to exist.
        # Keeping them as "Unemployed" is safer for now.

    def get_relationship_score(self, target_char_name: str) -> int:
        """Returns the relationship score towards the target character, default 0."""
        return self.relationships.get(target_char_name, 0)

    def modify_relationship(self, target_char_name: str, value_change: int, world: 'World', reason: Optional[str] = None):
        """Modifies the relationship score with the target character."""
        if self.name == target_char_name: return # Cannot have a relationship with oneself

        current_score = self.relationships.get(target_char_name, 0)
        new_score = current_score + value_change

        # Clamp score between -100 and 100
        new_score = max(-100, min(100, new_score))

        self.relationships[target_char_name] = new_score

        if reason:
            self.add_memory(f"My relationship with {target_char_name} changed by {value_change} to {new_score}. Reason: {reason}")
            # print(f"DEBUG: {self.name}'s relationship with {target_char_name} changed by {value_change} to {new_score}. Reason: {reason}")

        # Optionally, have the target character reciprocate or have their own view change (more complex social model)
        # For now, relationships are one-way perspectives.
        # However, the event CAUSER (e.g. supervisor doing review) might trigger a separate call
        # for the TARGET's relationship change towards the CAUSER.

        # Example: If a supervisor reviews poorly, supervisor's relationship to subordinate might not change much,
        # but subordinate's relationship to supervisor likely worsens. This would be handled by the calling function.

    def _grant_skill_experience(self, skill_name: str, amount: float, world: 'World'):
        """Grants experience to a skill and checks for level up."""
        if skill_name not in self.skills:
            # If character doesn't have the skill, initialize it at level 0
            self.skills[skill_name] = {
                "level": 0,
                "experience": 0.0,
                "exp_to_next_level": self._calculate_exp_for_level(0)
            }

        self.skills[skill_name]["experience"] += amount
        # self.add_memory(f"Gained {amount:.1f} XP in {skill_name} (Total: {self.skills[skill_name]['experience']:.1f}/{self.skills[skill_name]['exp_to_next_level']}).") # Can be spammy
        print(f"DEBUG_XP: {self.name} gained {amount:.1f} XP in {skill_name}. Total: {self.skills[skill_name]['experience']:.1f}/{self.skills[skill_name]['exp_to_next_level']:.0f}")

        # _check_skill_level_up will be implemented in Step 2 and called here
        self._check_skill_level_up(skill_name, world)

    def _check_skill_level_up(self, skill_name: str, world: 'World'):
        """Checks if a skill has enough experience to level up, and handles the level-up."""
        if skill_name not in self.skills:
            return # Should not happen if _grant_skill_experience initializes it

        # Loop to handle multiple level-ups from a single XP gain
        while self.skills[skill_name]["experience"] >= self.skills[skill_name]["exp_to_next_level"]:
            current_level = self.skills[skill_name]["level"]
            exp_needed = self.skills[skill_name]["exp_to_next_level"]

            self.skills[skill_name]["level"] += 1
            self.skills[skill_name]["experience"] -= exp_needed # Carry over excess

            new_level = self.skills[skill_name]["level"]
            self.skills[skill_name]["exp_to_next_level"] = self._calculate_exp_for_level(new_level)

            level_up_message = f"{self.name}'s {skill_name} skill increased to level {new_level}!"
            self.add_memory(level_up_message)
            if world: # world might be None in some testing contexts, though unlikely here
                world.add_event_log_message(level_up_message) # Log globally
            print(level_up_message) # Also print to console for immediate visibility during testing


    def apply_status_effect(self, status_data: Dict[str, Any], world: 'World'):
        """Applies a status effect to the character."""
        # Check if a similar status effect is already active; potentially refresh or stack, or ignore.
        # For now, let's assume they don't stack if the same name. Refresh duration.
        status_name = status_data.get("status_name")
        if not status_name:
            print(f"Error: apply_status_effect called for {self.name} without status_name.")
            return

        existing_status = None
        for i, se in enumerate(self.status_effects):
            if se.get("name") == status_name:
                existing_status = se
                # Refresh duration if new duration is longer or it's a non-timed status being re-applied
                new_duration_days = status_data.get("duration_days", 0)
                new_duration_ticks = new_duration_days * world.game_time.ticks_per_day

                current_remaining = existing_status.get("duration_remaining_ticks", 0)
                if new_duration_ticks > current_remaining or new_duration_ticks == 0: # 0 duration could mean indefinite until removed by another event
                    existing_status["duration_remaining_ticks"] = new_duration_ticks
                    existing_status["modifiers"] = status_data.get("modifiers", {}) # Update modifiers too
                    self.add_memory(f"Status '{status_name}' was refreshed/updated.")
                    print(f"{self.name}'s status '{status_name}' refreshed. Duration ticks: {new_duration_ticks}")
                return # Status refreshed/updated

        # If not existing, add new status effect
        duration_days = status_data.get("duration_days", 0)
        new_status = {
            "name": status_name,
            "duration_remaining_ticks": duration_days * world.game_time.ticks_per_day,
            "modifiers": status_data.get("modifiers", {}), # e.g., {"work_speed_multiplier": 0.8}
            "applied_tick": world.game_time.current_total_ticks
        }
        self.status_effects.append(new_status)
        self.add_memory(f"Affected by '{status_name}'.")
        print(f"{self.name} is now affected by '{status_name}' for {duration_days} days (Modifiers: {new_status['modifiers']}).")

    def process_status_effects(self, world: 'World'):
        """Processes active status effects, applies them, and removes expired ones. Called each tick."""
        effects_to_remove = []
        for status in self.status_effects:
            status["duration_remaining_ticks"] -= 1
            # If duration_remaining_ticks was calculated from a positive duration_days, it should expire.
            # Indefinite statuses (if duration_days was 0 or not specified leading to 0 duration_ticks)
            # would need another mechanism to be removed, or rely on duration_ticks being set to a very large number initially.
            # For now, any status with a tick counter reaching zero will be removed.
            if status["duration_remaining_ticks"] <= 0:
                effects_to_remove.append(status)
                self.add_memory(f"Status '{status['name']}' has worn off.")
                print(f"{self.name}'s status '{status['name']}' has worn off.")
            else:
                # Apply ongoing effects of the status (e.g., need decay multipliers)
                modifiers = status.get("modifiers", {})
                if "social_need_decay_multiplier" in modifiers and 'Social' in self.needs:
                    # This is tricky, decay usually happens daily. This implies per-tick or needs adjustment
                    # For now, let's assume daily decay is handled in main loop, and this can augment it if needed
                    # Or, this modifier is read by the daily decay logic.
                    pass
                if "energy_decay_multiplier" in modifiers and 'Energy' in self.needs: # Assuming an 'Energy' need
                    # Example: self.needs['Energy'] = max(0, self.needs['Energy'] - (1 * modifiers["energy_decay_multiplier"]))
                    pass


        for eff in effects_to_remove:
            self.status_effects.remove(eff)

    def get_status_modifier(self, modifier_key: str, default_value: float = 1.0) -> float:
        """Gets a combined modifier value from all active status effects."""
        # E.g., get_status_modifier("work_speed_multiplier") might return 0.8 if Sick.
        # If multiple effects modify the same key, how they stack (multiplicative, additive, take worst) needs decision.
        # For now, let's assume multiplicative, starting from default_value.
        current_value = default_value
        for status in self.status_effects:
            if modifier_key in status.get("modifiers", {}):
                current_value *= status["modifiers"][modifier_key]
        return current_value