# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from .building import Building
from . import config

if TYPE_CHECKING:
    from .world import World
    from .character import Character as OtherCharacter

ORDER_SPAM_PREVENTION_DAYS = 3

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: Optional[Dict[str, int]] = None,
                 x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10,
                 rank: str = "Worker"):
        self.name = name; self.personality = personality; self.traits = traits

        self.skills: Dict[str, Dict[str, Any]] = {}
        if skills:
            for skill_name, level in skills.items():
                self.skills[skill_name] = {
                    "level": level,
                    "experience": 0.0,
                    "exp_to_next_level": self._calculate_exp_for_level(level)
                }

        self.x = x; self.y = y; self.inventory = {}; self.memory = [];

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
        self.mood: int = 50

        self.current_goal = current_goal
        self.relationships = {}; self.job = job; self.max_inventory_items = max_inventory_items
        self.hauling_info: Optional[Dict] = None
        self.counting_target_stockpile_name: Optional[str] = None
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False

        self.active_build_order_id: Optional[str] = None
        self.materials_gathered_for_build: bool = False
        self.building_site_target: Optional[Tuple[int,int]] = None
        self.current_building_project: Optional[str] = None

        self.rank: str = rank
        self.assigned_tasks: List[Dict] = []
        self.performance_rating: str = "Not Evaluated"
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
        self.status_effects: List[Dict[str, Any]] = []

        self.fetch_info_for_need: Optional[Dict[str, Any]] = None
        self.target_bed_location: Optional[Tuple[int,int]] = None
        self.socialize_target_name: Optional[str] = None
        self.socialize_target_location: Optional[Tuple[int,int]] = None


    def _calculate_exp_for_level(self, level: int) -> float:
        if level == 0: return 50
        return float(int(100 * (level ** 1.2)))

    def _reset_crafting_state(self):
        self.active_work_order_id = None; self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False; self.resource_to_fetch = None
        self.crafting_progress = 0; self.hauling_info = None; self.workshop_location = None
        self.fetch_info_for_need = None

    def _reset_building_state(self):
        self.active_build_order_id = None
        self.materials_gathered_for_build = False
        self.building_site_target = None
        self.resource_to_fetch = None
        self.current_building_project = None

    def __str__(self):
        build_wo_info = f", BuildWO: {self.active_build_order_id}" if self.active_build_order_id else ""
        base_info = (f"Character(Name: {self.name}, Rank: {self.rank}, Job: {self.job}, Pos: ({self.x},{self.y}), Goal: {self.current_goal}, CraftWO: {self.active_work_order_id}{build_wo_info}, Load: {self.get_inventory_load()}/{self.max_inventory_items})")
        needs_summary = f"Needs(H:{self.needs.get('Hunger',0)} T:{self.needs.get('Thirst',0)} E:{self.needs.get('Energy',0)} S:{self.needs.get('Social',0)} C:{self.needs.get('Comfort',0)}) Mood:{self.mood}"
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

    def gather_resource(self, resource_name: str, world: 'World'):
        pass

    def build(self, structure_type: str, world: 'World') -> bool:
        return False

    def job_default_goal(self) -> str:
        if self.job == "Woodcutter": return "Perform Woodcutter Duties"
        if self.job == "Stonemason": return "Perform Stonemason Duties"
        if self.job == "Builder": return "Perform Builder Duties"
        if self.job == "Master Craftsman": return "Assess Production Needs"
        if self.job == "Manager": return "Manage Subordinates"
        if self.job == "Bookkeeper": return "Maintain Ledger"
        if self.job == "Expedition Leader": return "Oversee Expedition"
        if self.rank in ["Noble Lord", "Baron"] and not self.subordinates_names:
            return "Oversee Domain"
        elif self.rank in ["Noble Lord", "Baron"]:
            return "Manage Subordinates"
        return "Idle"

    def _execute_fetch_tool(self, world: 'World') -> bool:
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

    def _execute_generic_task(self, world: 'World', task_name: str) -> bool:
        if task_name not in JOB_TASK_DEFINITIONS: self.current_goal = "Idle"; return False
        task_def = JOB_TASK_DEFINITIONS[task_name]; tool_type = task_def.get("required_tool_type")
        if tool_type and (not self.equipped_tool or self.equipped_tool.get("tool_type") != tool_type):
            if not self.goal_before_fetching_tool : self.goal_before_fetching_tool = self.current_goal
            self.current_goal = "Fetch Tool"; self.tool_to_fetch_type = tool_type; self.task_work_progress = 0; return False

        current_progress_gain = 1.0
        work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
        mood_modifier = 1.0
        if self.mood < 25 : mood_modifier = 0.8
        elif self.mood > 75 : mood_modifier = 1.2
        current_progress_gain *= work_speed_modifier * mood_modifier

        skill_name_for_task = task_def.get("skill_used")
        if skill_name_for_task:
            skill_info = self.skills.get(skill_name_for_task)
            if not skill_info: # Initialize skill if character doesn't have it
                self.skills[skill_name_for_task] = {"level": 0, "experience": 0.0, "exp_to_next_level": self._calculate_exp_for_level(0)}
                skill_level = 0
            else:
                skill_level = skill_info.get("level", 0)
            current_progress_gain *= (1 + skill_level * 0.05)

        is_lazy_this_tick = False
        if "Lazy" in self.traits and not "Focused" in self.traits and random.random() < 0.25:
            current_progress_gain = 0
            is_lazy_this_tick = True; self.add_memory(f"Felt lazy slacking on '{task_name}'.")

        if current_progress_gain > 0: # Only apply positive traits if not slacking to zero
            if "Diligent" in self.traits and random.random() < 0.25:
                current_progress_gain += 1; self.add_memory(f"Worked diligently on '{task_name}'.")
            elif "Focused" in self.traits and random.random() < 0.10: # Focused is additive to skill/status bonus
                current_progress_gain += 1; self.add_memory(f"Remained focused on '{task_name}'.")

        self.task_work_progress += current_progress_gain
        self.needs['Energy'] = max(0, self.needs.get('Energy',100) - 1.0)

        if is_lazy_this_tick and current_progress_gain == 0: return True

        if self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            base_yield_amount = task_def.get("base_yield",1)
            final_yield_amount = float(base_yield_amount)
            if "Strong" in self.traits and res_prod in ["Wood", "Stone", "Iron Ore"] and random.random() < 0.20:
                final_yield_amount += 1; self.add_memory(f"Used strength for extra {res_prod}.")

            world_event_modifier_details = None
            if res_prod:
                modifier_key = f"yield_multiplier_{res_prod}"
                world_event_modifier_details = world.active_world_effects.get(modifier_key)
                if world_event_modifier_details and world.game_time.current_total_ticks < world_event_modifier_details.get("expires_tick", 0):
                    final_yield_amount *= world_event_modifier_details.get("multiplier", 1.0)

            final_yield_amount = int(round(final_yield_amount))
            actual_yield_taken = min(final_yield_amount, self.max_inventory_items - self.get_inventory_load())

            if actual_yield_taken > 0 and res_prod:
                self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield_taken
                tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
                event_bonus_info = ""
                if world_event_modifier_details and world.game_time.current_total_ticks < world_event_modifier_details.get("expires_tick",0):
                     event_bonus_info = f" (event x{world_event_modifier_details.get('multiplier', 1.0):.1f})"
                self.add_memory(f"Task '{task_name}': got {actual_yield_taken} {res_prod}{event_bonus_info} with {tool_name_mem}.")
            elif final_yield_amount > 0: print(f"{self.name} inventory full for {task_name}.")
            self.task_work_progress = 0

            if self.equipped_tool and tool_type:
                durability_loss = 1
                if "Careless" in self.traits and random.random() < 0.25:
                    durability_loss += 1; self.add_memory(f"Careless with {self.equipped_tool['name']}.")
                self.equipped_tool["durability"] -= durability_loss
                if self.equipped_tool["durability"] <= 0:
                    self.add_memory(f"{self.equipped_tool['name']} broke!"); self.unequip_tool()

            if task_def.get("skill_used") and actual_yield_taken > 0 :
                xp_gained = 5.0 * actual_yield_taken
                self._grant_skill_experience(task_def["skill_used"], xp_gained, world)
        return True

    def _execute_craft_order(self, world: 'World'):
        order = world.get_work_order_by_id(self.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name :
            self._reset_crafting_state(); self.current_goal=self.job_default_goal() or "Idle"; return

        item_name = order.details["item_name"]; item_qty_total = order.details["quantity"]
        blueprint = BLUEPRINTS.get(item_name)

        if self.items_crafted_for_wo:
            if not self.hauling_info and self.inventory.get(item_name, 0) > 0:
                self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = "Initiate Hauling"; self._execute_initiate_hauling(world); return
            elif self.hauling_info is None and self.inventory.get(item_name, 0) == 0:
                 order.status = "Completed"; self.add_memory(f"Completed/Stocked WO {order.order_id}."); self._reset_crafting_state(); self.current_goal = self.job_default_goal() or "Idle"; return
            return

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
            required_workshop_str = blueprint.get("required_workshop_type")
            if required_workshop_str:
                target_workshop_building = world.get_building_at(self.workshop_location[0], self.workshop_location[1]) if self.workshop_location else None
                if not target_workshop_building or target_workshop_building.structure_type != required_workshop_str or not target_workshop_building.is_operational or not target_workshop_building.is_inside(self.x, self.y):
                    suitable_workshops = world.get_operational_buildings_of_type(required_workshop_str)
                    if not suitable_workshops:
                        order.status = "Pending"; order.assigned_to = None; self._reset_crafting_state(); self.current_goal = "Idle"; return
                    new_workshop = suitable_workshops[0]
                    self.workshop_location = new_workshop.location
                    self.add_memory(f"Identified {new_workshop.display_name} for {item_name}.")
                if self.workshop_location and not (target_workshop_building and target_workshop_building.structure_type == required_workshop_str and target_workshop_building.is_inside(self.x,self.y)):
                     self.move_towards(self.workshop_location[0], self.workshop_location[1], world); return
            elif (self.x, self.y) != self.workshop_location:
                 self.move_towards(self.workshop_location[0], self.workshop_location[1], world); return

            craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)
            current_crafting_progress_gain = 1.0
            work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
            mood_modifier = 1.0
            if self.mood < 25 : mood_modifier = 0.8
            elif self.mood > 75 : mood_modifier = 1.2
            current_crafting_progress_gain *= work_speed_modifier * mood_modifier

            crafting_skill_name = blueprint.get("job_skill_needed")
            if crafting_skill_name:
                skill_info = self.skills.get(crafting_skill_name)
                if not skill_info: # Initialize skill if character doesn't have it
                    self.skills[crafting_skill_name] = {"level": 0, "experience": 0.0, "exp_to_next_level": self._calculate_exp_for_level(0)}
                    skill_level = 0
                else:
                    skill_level = skill_info.get("level", 0)
                current_crafting_progress_gain *= (1 + skill_level * 0.05)

            is_slacking_craft = False
            if "Lazy" in self.traits and not "Focused" in self.traits and random.random() < 0.25:
                current_crafting_progress_gain = 0; is_slacking_craft = True; self.add_memory(f"Slacked off crafting {item_name}.")

            if current_crafting_progress_gain > 0:
                if "Diligent" in self.traits and random.random() < 0.25: current_crafting_progress_gain += 1
                elif "Focused" in self.traits and random.random() < 0.10: current_crafting_progress_gain += 1

            self.crafting_progress += current_crafting_progress_gain
            self.needs['Energy'] = max(0, self.needs.get('Energy',100) - 1.5)

            if is_slacking_craft: return

            if self.crafting_progress >= craft_time_per_unit:
                for res, req_qty_pu in blueprint["required_resources"].items():
                    self.inventory[res] -= req_qty_pu
                    if self.inventory[res] <= 0: self.inventory.pop(res,None)
                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1

                if blueprint.get("job_skill_needed"):
                    xp_gained = float(blueprint.get("craft_time_per_unit", 5))
                    self._grant_skill_experience(blueprint["job_skill_needed"], xp_gained, world)

                item_type = blueprint.get("type")
                if item_type:
                    modifier_key = f"craft_bonus_{item_type}"
                    world_event_modifier = world.active_world_effects.get(modifier_key)
                    if world_event_modifier and world.game_time.current_total_ticks < world_event_modifier.get("expires_tick", 0):
                        bonus_details = world_event_modifier.get("bonus_details", {})
                        if "durability_multiplier" in bonus_details and blueprint.get("type") == "Tool":
                            bonus_mult = bonus_details["durability_multiplier"]
                            self.add_memory(f"Crafted {item_name} with potential event bonus (x{bonus_mult:.1f} durability).")

                self.add_memory(f"Crafted 1 {item_name}."); print(f"{self.name} CRAFTED 1 {item_name}.")
                self.crafting_progress = 0; self.materials_gathered_for_wo = False
                if self.inventory.get(item_name,0) >= item_qty_total: self.items_crafted_for_wo = True

                if not self.items_crafted_for_wo: return

        if self.items_crafted_for_wo:
            if not self.hauling_info and self.inventory.get(item_name, 0) > 0:
                self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = "Initiate Hauling"; self._execute_initiate_hauling(world); return

    def _execute_fetch_resource_for_wo(self, world:'World', blueprint:Dict): # Unchanged
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

    def _execute_assess_production_needs(self, world: 'World'): # Unchanged
        if self.job != "Master Craftsman": self.current_goal = self.job_default_goal(); return
        item_processed_this_tick = False;
        needed_structure_type = "small_workshop"
        if not world.get_operational_buildings_of_type(needed_structure_type) and \
           not any(wo.order_type == "BuildStructure" and wo.details.get("structure_type") == needed_structure_type and wo.status in ["Pending", "Approved", "InProgress"] for wo in world.work_orders):
            structure_bp = STRUCTURE_BLUEPRINTS.get(needed_structure_type)
            if structure_bp:
                build_location = None; mc_x, mc_y = self.x, self.y; search_radius = 5; found_loc = False
                for r in range(1, search_radius + 1):
                    for dx_s in range(-r, r + 1):
                        for dy_s in range(-r, r + 1):
                            if abs(dx_s) + abs(dy_s) != r: continue
                            check_x, check_y = mc_x + dx_s, mc_y + dy_s
                            can_place = True
                            for bx_offset in range(structure_bp["size"][0]):
                                for by_offset in range(structure_bp["size"][1]):
                                    tile_to_check_x, tile_to_check_y = check_x + bx_offset, check_y + by_offset
                                    if not (0 <= tile_to_check_x < world.grid_size[0] and 0 <= tile_to_check_y < world.grid_size[1]) or \
                                       world.get_tile(tile_to_check_x, tile_to_check_y) not in ["Grass"] or \
                                       world.get_building_at(tile_to_check_x, tile_to_check_y) is not None or \
                                       world.get_characters_at_location(tile_to_check_x, tile_to_check_y):
                                        can_place = False; break
                                if not can_place: break
                            if can_place: build_location = (check_x, check_y); found_loc = True; break
                        if found_loc: break
                    if found_loc: break
                if build_location:
                    order_details = {"structure_type": needed_structure_type, "location": build_location, "required_resources": structure_bp["required_resources"], "size": structure_bp["size"], "build_time": structure_bp["build_time"]}
                    new_build_order = WorkOrder(order_type="BuildStructure", details=order_details, creation_day=world.game_time.current_day, priority=1)
                    world.add_work_order(new_build_order); self.add_memory(f"Queued Build WO for {needed_structure_type} at {build_location}."); item_processed_this_tick = True
                else: print(f"{self.name} (MC) wants to build {needed_structure_type} but couldn't find a suitable location near them.")
            else: print(f"Error: MC {self.name} - No blueprint for structure {needed_structure_type}.")
        if not item_processed_this_tick and self.managed_item_targets:
            target_item_names = list(self.managed_item_targets.keys())
            if not target_item_names: self.current_goal = "Idle"; return
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
                    self.add_memory(f"Generated Craft WO for {qty_to_order} {item_name}."); item_processed_this_tick = True; self._mc_item_check_idx = (current_idx + 1) % len(target_item_names); break
        if not item_processed_this_tick: self.current_goal = "Idle"; self._mc_item_check_idx = 0

    def _execute_manage_subordinates(self, world: 'World'): # Unchanged
        is_eligible_manager = self.job == "Manager" or self.rank in ["Noble Lord", "Baron"]
        if not is_eligible_manager: self.current_goal = self.job_default_goal() or "Idle"; return
        if self.job == "Manager": self._execute_manage_work_orders_as_part_of_supervision(world)
        if not self.subordinates_names and self.job == "Manager": self.current_goal = "Idle"; #pass
        if not world.game_time: return
        for sub_name in self.subordinates_names:
            subordinate: Optional['Character'] = None
            for char_obj in world.characters:
                if char_obj.name == sub_name: subordinate = char_obj; break
            if not subordinate: continue
            review_due_day = subordinate.last_performance_review_day is None or \
                             (world.game_time.current_day - subordinate.last_performance_review_day >= config.MANAGEMENT_REVIEW_INTERVAL_DAYS)
            if review_due_day and subordinate.performance_rating != "Fired":
                self.add_memory(f"Considering review for {subordinate.name} (Last: Day {subordinate.last_performance_review_day}, Current: Day {world.game_time.current_day}).")
                self.conduct_performance_review(subordinate.name, world); self.current_goal = "Idle"; return
            relationship_to_sub = self.get_relationship_score(subordinate.name)
            should_consider_warning = (subordinate.performance_rating == "Poor" and subordinate.warning_count < config.FIRING_WARNING_THRESHOLD) or \
                                      (subordinate.performance_rating == "Needs Improvement" and subordinate.warning_count > 0)
            if should_consider_warning and subordinate.performance_rating != "Fired":
                warning_chance = 0.3; reason_for_warning = "Ongoing performance issues."
                if subordinate.performance_rating == "Poor": reason_for_warning = "Performance rated Poor."
                elif subordinate.performance_rating == "Needs Improvement": reason_for_warning = "Performance Needs Improvement, with prior warnings."
                if "Strict" in self.traits or self.personality == "Demanding": warning_chance += 0.2
                if "Forgiving" in self.traits or self.personality == "Kind": warning_chance -= 0.2
                if relationship_to_sub < -30: warning_chance += 0.15
                if relationship_to_sub > 30: warning_chance -= 0.15
                warning_chance = max(0.05, min(0.95, warning_chance))
                if random.random() < warning_chance:
                    self.add_memory(f"Considering warning for {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {warning_chance:.2f}).")
                    if subordinate.job == "Bookkeeper" and any(world.ledger.get_stockpile_last_update_day(sp.name) is None or (world.game_time.current_day - world.ledger.get_stockpile_last_update_day(sp.name) > config.STALE_THRESHOLD_DAYS + 2) for sp in world.stockpiles):
                        reason_for_warning = "Ledger maintenance remains unsatisfactory."
                    self.issue_warning(subordinate.name, world, reason_for_warning)
                    self.modify_relationship(subordinate.name, -10, world, reason=f"Issued warning for {reason_for_warning}")
                    subordinate.modify_relationship(self.name, -15, world, reason=f"Received warning about {reason_for_warning}")
                    self.current_goal = "Idle"; return
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
                    self.current_goal = "Idle"; return
        self.current_goal = "Idle"

    def _execute_manage_work_orders_as_part_of_supervision(self, world: 'World'): # Unchanged
        pending_orders = world.get_pending_work_orders()
        if not pending_orders: return
        order_to_process = pending_orders[0]
        can_approve = True; missing_notes = []; stale_concerns = False
        req_res = order_to_process.details.get("required_resources", {})
        if req_res:
            for resource, req_qty in req_res.items():
                avail = world.ledger.get_total_resource_count(resource)
                for sp_name_key in world.ledger.records.get(resource, {}).keys():
                    last_update = world.ledger.get_stockpile_last_update_day(sp_name_key)
                    if last_update is not None and world.game_time.current_day - last_update > config.STALE_THRESHOLD_DAYS: stale_concerns = True; break
                if stale_concerns: self.add_memory(f"Stale data for WO {order_to_process.order_id}, res {resource}");
                if avail < req_qty: can_approve = False; missing_notes.append(f"{resource} (need {req_qty}, has {avail})")
        if can_approve: order_to_process.status = "Approved"; order_to_process.approved_by = self.name; order_to_process.approval_day = world.game_time.current_day; self.add_memory(f"Approved WO {order_to_process.order_id}");
        else: order_to_process.status = "Denied"; order_to_process.denied_by = self.name; order_to_process.denial_reason = f"Insuff: {', '.join(missing_notes) or 'stale data'}"; self.add_memory(f"Denied WO {order_to_process.order_id}");

    def _execute_maintain_ledger(self, world: 'World'): # Unchanged
        if self.job != "Bookkeeper": self.current_goal = self.job_default_goal(); return
        stockpiles_to_check=world.stockpiles; target_sp=None; min_day=float('inf')
        if not stockpiles_to_check: self.current_goal = "Idle"; return
        for sp_obj in stockpiles_to_check:
            day=world.ledger.get_stockpile_last_update_day(sp_obj.name)
            if day is None:target_sp=sp_obj;break
            if day<world.game_time.current_day and day<min_day:min_day=day;target_sp=sp_obj
        if target_sp is None : self.current_goal="Idle";return
        self.counting_target_stockpile_name=target_sp.name;self.current_goal="Count Stockpile";self.decide_action(world)

    def _execute_count_stockpile(self, world: 'World'): # Unchanged
        if self.job != "Bookkeeper" or not self.counting_target_stockpile_name: self.current_goal = "Maintain Ledger"; self.counting_target_stockpile_name = None; self.decide_action(world); return
        stockpile_obj=world.get_stockpile_by_name(self.counting_target_stockpile_name)
        if not stockpile_obj:self.current_goal="Maintain Ledger";self.counting_target_stockpile_name=None;self.decide_action(world);return
        spot=stockpile_obj.deposit_tiles[0] if stockpile_obj.deposit_tiles else (stockpile_obj.rect[0],stockpile_obj.rect[1])
        if(self.x,self.y)==spot:
            actual_inventory = stockpile_obj.inventory.copy(); recorded_inventory = actual_inventory.copy()
            if "Careless" in self.traits:
                miscounted_items = []
                for item_name, actual_qty in actual_inventory.items():
                    if random.random() < 0.10:
                        error_amount = random.choice([-1, 1]); recorded_qty = actual_qty + error_amount
                        recorded_inventory[item_name] = max(0, recorded_qty)
                        if recorded_inventory[item_name] != actual_qty: miscounted_items.append(f"{item_name} (actual: {actual_qty}, recorded: {recorded_inventory[item_name]})")
                if miscounted_items: self.add_memory(f"Careless counting {stockpile_obj.name}. Miscounted: {', '.join(miscounted_items)}.")
            world.ledger.update_stockpile_record(stockpile_obj.name, recorded_inventory, world.game_time.current_day)
            self.add_memory(f"Counted {stockpile_obj.name}"); self.counting_target_stockpile_name=None;self.current_goal="Maintain Ledger";self.decide_action(world)
        else:self.move_towards(spot[0],spot[1],world)

    def _execute_perform_woodcutter_duties(self, world: 'World'): # Unchanged
        if self.job!="Woodcutter":self.current_goal=self.job_default_goal();return
        quota=self.needs.get("Wood",5);inv_val=self.inventory.get("Wood",0)
        if self.get_inventory_load()>=self.max_inventory_items and inv_val>0:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        elif inv_val<quota:self.current_goal="Gather Wood"
        else:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        if self.current_goal != "Perform Woodcutter Duties": self.decide_action(world)

    def _execute_perform_stonemason_duties(self, world: 'World'): # Unchanged
        if self.job != "Stonemason": self.current_goal = self.job_default_goal(); return
        quota = self.needs.get("Stone", 5); inv_val = self.inventory.get("Stone", 0)
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        elif inv_val < quota: self.current_goal = "Gather Stone"
        else: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        if self.current_goal != "Perform Stonemason Duties": self.decide_action(world)

    def _execute_initiate_hauling(self, world: 'World'): # Unchanged
        if not self.hauling_info: self.current_goal=self.job_default_goal() or "Idle"; return
        res=self.hauling_info.get("resource")
        if not res or self.inventory.get(res,0)==0: self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None; return
        qty=self.inventory.get(res,0)
        sps=[s_obj for s_obj in world.stockpiles if s_obj.is_allowed(res) and s_obj.has_space_for(res,qty)]
        if not sps:
            if BLUEPRINTS.get(res, {}).get("type") == "Tool":
                tool_shed = world.get_stockpile_by_name("ToolShed")
                if tool_shed and tool_shed.is_allowed(res) and tool_shed.has_space_for(res,qty): sps = [tool_shed]
            if not sps: print(f"{self.name} wants to haul {qty} {res} but no suitable stockpile. Wandering."); self.current_goal="Wander"; return
        sp_chosen=sps[0]
        self.hauling_info["target_stockpile_name"]=sp_chosen.name; self.hauling_info["quantity_to_haul"]=qty
        self.current_goal="Haul Resource to Stockpile"

    def _execute_haul_resource(self, world: 'World'): # Unchanged
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
            if self.hauling_info and self.hauling_info.get("is_crafted_item") and self.inventory.get(res,0) == 0:
                wo_id = self.hauling_info.get("for_wo_id")
                order = world.get_work_order_by_id(wo_id) if wo_id else None
                if order and order.assigned_to == self.name and order.status == "InProgress":
                    order.status = "Completed"; print(f"{self.name} COMPLETED and STOCKED Work Order {order.order_id} ({res})."); self.add_memory(f"Completed WO {order.order_id} ({res}).")
                self._reset_crafting_state(); self.current_goal=self.job_default_goal() or "Idle"
            else: self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None
        else:self.move_towards(spot[0],spot[1],world)

    def _execute_gather_wood(self, world: 'World'): # Unchanged
        task_loc = self.find_task_location("Chop Wood", world)
        if not task_loc : print(f"{self.name} can't find Forest for Chop Wood."); self.current_goal = "Idle"; return
        if (self.x, self.y) != task_loc: self.move_towards(task_loc[0], task_loc[1], world); return
        if not self._execute_generic_task(world, "Chop Wood"): return
        inv_wood = self.inventory.get("Wood",0); job_quota = self.needs.get("Wood",5) if self.job == "Woodcutter" else float('inf')
        if self.get_inventory_load()>=self.max_inventory_items or inv_wood >= job_quota : self.current_goal = "Perform Woodcutter Duties"

    def _execute_gather_stone(self, world: 'World'): # Unchanged
        task_loc = self.find_task_location("Mine Stone", world)
        if not task_loc : print(f"{self.name} can't find Rocks for Mine Stone."); self.current_goal = "Idle"; return
        if (self.x, self.y) != task_loc: self.move_towards(task_loc[0], task_loc[1], world); return
        if not self._execute_generic_task(world, "Mine Stone"): return
        inv_stone = self.inventory.get("Stone",0); job_quota = self.needs.get("Stone",5) if self.job == "Stonemason" else float('inf')
        if self.get_inventory_load()>=self.max_inventory_items or inv_stone >= job_quota: self.current_goal = "Perform Stonemason Duties"

    def _execute_oversee_expedition(self, world: 'World'): # Unchanged
         if self.job != "Expedition Leader": self.current_goal = self.job_default_goal(); return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = "Idle"

    def _execute_wander(self, world: 'World'): # Unchanged
        moves=[];
        for dx,dy in[(0,1),(0,-1),(1,0),(-1,0)]:
            tx,ty=self.x+dx,self.y+dy
            if 0<=tx<world.grid_size[0] and 0<=ty<world.grid_size[1] and \
                world.get_tile(tx,ty)not in["Water","Mountain","Forest","Rocks","SP_Mai","SP_Woo","SP_Sto"] and \
                not world.get_characters_at_location(tx,ty):moves.append((dx,dy))
        if moves:choice=random.choice(moves);self.move(choice[0],choice[1],world)

    # --- New Need Fulfillment Methods ---
    def _consume_item(self, item_name: str, world: 'World'):
        if self.inventory.get(item_name, 0) > 0:
            self.inventory[item_name] -= 1
            if self.inventory[item_name] <= 0:
                del self.inventory[item_name]

            blueprint = BLUEPRINTS.get(item_name)
            if blueprint and blueprint.get("type") == "Consumable" and "effects" in blueprint:
                effects_applied_msg = []
                for need_name, value_change in blueprint["effects"].items():
                    if need_name in self.needs:
                        current_need_val = self.needs[need_name]
                        max_need_val = self.max_needs.get(need_name, current_need_val + abs(value_change))
                        self.needs[need_name] = min(max_need_val, current_need_val + value_change)
                        effects_applied_msg.append(f"{need_name} by {value_change}")

                consumed_msg = f"Consumed {item_name}."
                if effects_applied_msg:
                    consumed_msg += f" Effects: {', '.join(effects_applied_msg)}."
                self.add_memory(consumed_msg)
                # print(f"{self.name} {consumed_msg}") # Keep console log for now

                # Mood boost from satisfying a strong need
                if "Hunger" in blueprint["effects"] and self.needs["Hunger"] > (self.max_needs["Hunger"] * 0.7):
                     self.mood = min(100, self.mood + random.randint(3,8))
                if "Thirst" in blueprint["effects"] and self.needs["Thirst"] > (self.max_needs["Thirst"] * 0.7):
                     self.mood = min(100, self.mood + random.randint(2,7))
            else:
                self.add_memory(f"Tried to consume {item_name}, but it's not a known consumable or has no effects.")
        else:
            self.add_memory(f"Tried to consume {item_name}, but had none.") # Should be caught by calling functions

    def _execute_fetch_item_for_need(self, item_name: str, for_need_goal: str, world: 'World'):
        if self.inventory.get(item_name, 0) > 0:
            self.current_goal = for_need_goal
            self.fetch_info_for_need = None
            # Immediately try to satisfy the need now that item is in inventory
            if for_need_goal == "Seek Food": self._execute_seek_food(world)
            elif for_need_goal == "Seek Water": self._execute_seek_water(world)
            return

        if not self.fetch_info_for_need or self.fetch_info_for_need.get("item_name") != item_name:
            self.fetch_info_for_need = {"item_name": item_name, "target_stockpile_name": None, "for_need_goal": for_need_goal}

        fetch_info = self.fetch_info_for_need
        target_sp_name = fetch_info.get("target_stockpile_name")
        sp_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None

        if not sp_to_fetch or sp_to_fetch.inventory.get(item_name, 0) == 0:
            suitable_sps = [sp for sp in world.stockpiles if sp.inventory.get(item_name, 0) > 0 and sp.is_allowed(item_name)]
            if not suitable_sps:
                self.add_memory(f"Needed {item_name} for {for_need_goal}, but none found in any stockpiles.")
                self.current_goal = "Idle"; self.fetch_info_for_need = None; return
            sp_to_fetch = random.choice(suitable_sps)
            fetch_info["target_stockpile_name"] = sp_to_fetch.name

        # Use first deposit tile of stockpile as target for simplicity
        spot = sp_to_fetch.deposit_tiles[0] if sp_to_fetch.deposit_tiles else (sp_to_fetch.rect[0], sp_to_fetch.rect[1])

        if (self.x, self.y) == spot:
            if self.get_inventory_load() < self.max_inventory_items:
                success, qty_taken = sp_to_fetch.remove_item(item_name, 1)
                if success and qty_taken > 0:
                    self.inventory[item_name] = self.inventory.get(item_name, 0) + qty_taken
                    self.add_memory(f"Fetched 1 {item_name} from {sp_to_fetch.name} for {for_need_goal}.")
                    self.current_goal = for_need_goal
                    self.fetch_info_for_need = None
                    # Immediately try to satisfy the need now that item is in inventory
                    if for_need_goal == "Seek Food": self._execute_seek_food(world)
                    elif for_need_goal == "Seek Water": self._execute_seek_water(world)
                else:
                    self.add_memory(f"Tried to get {item_name} from {sp_to_fetch.name} but failed."); fetch_info["target_stockpile_name"] = None; self.current_goal = "Idle"
            else:
                self.add_memory(f"Reached {sp_to_fetch.name} for {item_name}, but inventory full."); self.current_goal = "Idle"; self.fetch_info_for_need = None
        else:
            self.move_towards(spot[0], spot[1], world)
            if sp_to_fetch.inventory.get(item_name, 0) == 0: fetch_info["target_stockpile_name"] = None # Item taken by someone else

    def _execute_seek_food(self, world: 'World'):
        if self.inventory.get("FoodRation", 0) > 0:
            self._consume_item("FoodRation", world)
            self.current_goal = self.job_default_goal() or "Idle"
        else:
            self.current_goal = "Fetch Item for Need"
            self.fetch_info_for_need = {"item_name": "FoodRation", "target_stockpile_name": None, "for_need_goal": "Seek Food"}
            self._execute_fetch_item_for_need("FoodRation", "Seek Food", world)

    def _execute_seek_water(self, world: 'World'):
        if self.inventory.get("CleanWater", 0) > 0:
            self._consume_item("CleanWater", world)
            self.current_goal = self.job_default_goal() or "Idle"
        else:
            self.current_goal = "Fetch Item for Need"
            self.fetch_info_for_need = {"item_name": "CleanWater", "target_stockpile_name": None, "for_need_goal": "Seek Water"}
            self._execute_fetch_item_for_need("CleanWater", "Seek Water", world)

    def _execute_rest(self, world: 'World'):
        bed_found_at_current_pos = None
        current_pos_building = world.get_building_at(self.x, self.y)
        if current_pos_building and current_pos_building.structure_type == "simple_bed" and current_pos_building.is_operational:
            bed_found_at_current_pos = current_pos_building

        if not bed_found_at_current_pos and (not self.target_bed_location or (self.x,self.y) != self.target_bed_location):
            # Find a bed if not already at one or heading to a specific one
            potential_beds = [b for b in world.buildings if b.structure_type == "simple_bed" and b.is_operational]
            if potential_beds:
                potential_beds.sort(key=lambda b: abs(b.location[0] - self.x) + abs(b.location[1] - self.y))
                self.target_bed_location = potential_beds[0].location
            else: # No beds available
                self.target_bed_location = None # Rest on ground

        energy_recovery_rate = 5.0
        comfort_change = -0.5
        resting_on_bed = False

        if self.target_bed_location: # If heading to or at a specific bed
            target_bed_building = world.get_building_at(self.target_bed_location[0], self.target_bed_location[1])
            if target_bed_building and target_bed_building.structure_type == "simple_bed" and target_bed_building.is_operational:
                if target_bed_building.is_inside(self.x, self.y):
                    resting_on_bed = True
                    bed_found_at_current_pos = target_bed_building # Update if arrived
                else:
                    self.move_towards(self.target_bed_location[0], self.target_bed_location[1], world)
                    return
            else: # Target bed is gone or invalid
                self.target_bed_location = None # Will rest on ground

        if resting_on_bed and bed_found_at_current_pos:
            rest_quality = bed_found_at_current_pos.functionality.get("provides_rest_quality", 1.0)
            comfort_bonus = bed_found_at_current_pos.functionality.get("provides_comfort", 0)
            energy_recovery_rate *= rest_quality
            comfort_change = float(comfort_bonus / 2.0) # Spread comfort bonus over a few ticks
            if not hasattr(self, '_resting_memory_set') or not self._resting_memory_set:
                self.add_memory("Resting comfortably in a bed."); self._resting_memory_set = True
        else: # Resting on ground
            if not hasattr(self, '_resting_memory_set') or self._resting_memory_set :
                 self.add_memory("Resting on the ground."); self._resting_memory_set = False

        self.needs["Energy"] = min(self.max_needs["Energy"], self.needs["Energy"] + energy_recovery_rate)
        self.needs["Comfort"] = min(self.max_needs["Comfort"], max(0, self.needs["Comfort"] + comfort_change))

        if self.needs["Energy"] >= self.max_needs["Energy"]:
            self.add_memory(f"Feeling fully rested (Energy: {self.needs['Energy']:.0f}).")
            self.current_goal = self.job_default_goal() or "Idle"
            self.target_bed_location = None
            if hasattr(self, '_resting_memory_set'): delattr(self, '_resting_memory_set')
        self._update_mood(world) # Update mood after resting action

    def _update_mood(self, world: 'World'):
        """Recalculates mood based on needs, traits, and active status effects."""
        base_mood_change = 0
        mood_factors_log = [] # For debugging or detailed memory

        # 1. Needs Impact
        critical_needs_penalty = 0
        moderate_needs_penalty = 0

        # Physical Needs
        for need_name in ["Hunger", "Thirst", "Energy", "Comfort"]:
            value = self.needs.get(need_name, 100)
            max_val = self.max_needs.get(need_name, 100)
            if value < max_val * 0.15: # Critically low
                critical_needs_penalty += random.randint(10, 15)
                mood_factors_log.append(f"Critically low {need_name} (-{critical_needs_penalty} mood)")
            elif value < max_val * 0.40: # Moderately low
                moderate_needs_penalty += random.randint(5, 8)
                mood_factors_log.append(f"Low {need_name} (-{moderate_needs_penalty} mood)")

        base_mood_change -= (critical_needs_penalty + moderate_needs_penalty)

        # Social Need (less severe impact than physical)
        social_value = self.needs.get("Social", 100)
        max_social = self.max_needs.get("Social", 100)
        if social_value < max_social * 0.20: # Very lonely
            base_mood_change -= random.randint(3, 6)
            mood_factors_log.append(f"Very lonely (-{random.randint(3,6)} mood)")
        elif social_value < max_social * 0.40: # Lonely
            base_mood_change -= random.randint(1, 3)
            mood_factors_log.append(f"Lonely (-{random.randint(1,3)} mood)")

        # Slight mood recovery if all primary needs are reasonably met
        are_primary_needs_met = all(
            self.needs.get(n, 0) > self.max_needs.get(n, 100) * 0.6
            for n in ["Hunger", "Thirst", "Energy", "Comfort"]
        )
        if are_primary_needs_met and base_mood_change == 0 : # Only if no penalties from needs
            base_mood_change += random.randint(1, 3)
            mood_factors_log.append(f"Needs met (+{random.randint(1,3)} mood)")


        # 2. Status Effects Impact (placeholder for specific status effects)
        # Example: if any(status.get("type") == "negative_mood_event" for status in self.status_effects):
        #    base_mood_change -= 10
        #    mood_factors_log.append("Negative event status (-10 mood)")
        # Example: if any(status.get("name") == "Joyful" for status in self.status_effects):
        #    base_mood_change += 15
        #    mood_factors_log.append("Joyful status (+15 mood)")
        if any(s.get("name") == "Sick" for s in self.status_effects):
            base_mood_change -= random.randint(5,10)
            mood_factors_log.append(f"Sick status (-{random.randint(5,10)})")


        # 3. Traits Impact
        trait_modifier = 1.0
        if "Optimistic" in self.traits:
            if base_mood_change < 0 : trait_modifier *= 0.8 # Dampens negative changes
            else: trait_modifier *= 1.2 # Amplifies positive changes
            if self.mood < 50 : base_mood_change += random.randint(0,2) # Tendency to recover
            mood_factors_log.append("Optimistic trait influence")
        if "Pessimistic" in self.traits:
            if base_mood_change > 0 : trait_modifier *= 0.8 # Dampens positive changes
            else: trait_modifier *= 1.2 # Amplifies negative changes
            if self.mood > 50 : base_mood_change -= random.randint(0,2) # Tendency to decline
            mood_factors_log.append("Pessimistic trait influence")
        if "Content" in self.traits: # More stable mood
            trait_modifier *= 0.7
            mood_factors_log.append("Content trait (stabilizing mood)")
        if "Volatile" in self.traits: # Larger swings
             trait_modifier *= 1.5
             mood_factors_log.append("Volatile trait (amplifying swings)")

        final_mood_change = int(base_mood_change * trait_modifier)

        # Apply change and clamp
        previous_mood = self.mood
        self.mood = max(0, min(100, self.mood + final_mood_change))

        if self.mood != previous_mood and random.random() < 0.3 : # Occasionally log significant changes or factor summary
            change_amount = self.mood - previous_mood
            # For brevity, only log if mood changed by more than a little, or a summary of factors
            if abs(change_amount) > 3 or (len(mood_factors_log)>0 and random.random() < 0.1):
                 self.add_memory(f"Mood changed to {self.mood} ({change_amount:+}). Factors: {', '.join(mood_factors_log[:2])}...")


    def decide_action(self, world: 'World'):
        if not world.game_time: self.current_goal = "Idle"; return

        # --- 0. Handle ongoing multi-tick goals first ---
        if self.current_goal == "Fetch Item for Need":
            if self.fetch_info_for_need:
                 self._execute_fetch_item_for_need(self.fetch_info_for_need["item_name"], self.fetch_info_for_need["for_need_goal"], world)
            else:
                self.current_goal = "Idle"
            return

        # --- 1. Critical Needs Check ---
        critical_hunger_threshold = 15; critical_thirst_threshold = 15; critical_energy_threshold = 10
        is_currently_addressing_critical_need = self.current_goal in ["Seek Food", "Seek Water", "Seek Rest", "Fetch Item for Need"]

        # Check if a *new* critical need has arisen that isn't the one currently being addressed
        new_critical_goal_set = False
        if self.needs.get("Hunger", 100) < critical_hunger_threshold and self.current_goal != "Seek Food":
            self.current_goal = "Seek Food"; new_critical_goal_set = True
        elif self.needs.get("Thirst", 100) < critical_thirst_threshold and self.current_goal != "Seek Water":
            self.current_goal = "Seek Water"; new_critical_goal_set = True
        elif self.needs.get("Energy", 100) < critical_energy_threshold and self.current_goal != "Seek Rest":
            self.current_goal = "Seek Rest"; new_critical_goal_set = True

        if new_critical_goal_set: # If a new critical need just set the goal, execute it now
            if self.current_goal == "Seek Food": self._execute_seek_food(world); return
            if self.current_goal == "Seek Water": self._execute_seek_water(world); return
            if self.current_goal == "Seek Rest": self._execute_rest(world); return

        # --- Execute current goal if it's an ONGOING critical need or high priority task ---
        if self.current_goal == "Fetch Tool":
            if self._execute_fetch_tool(world): return
        elif self.current_goal == "Execute Craft Order" and self.active_work_order_id:
            self._execute_craft_order(world); return
        elif self.current_goal == "Execute Build Order" and self.active_build_order_id:
            self._execute_build_order(world); return
        elif self.current_goal == "Seek Food": self._execute_seek_food(world); return
        elif self.current_goal == "Seek Water": self._execute_seek_water(world); return
        elif self.current_goal == "Seek Rest": self._execute_rest(world); return
        elif self.current_task_def_name and self.current_goal in JOB_TASK_DEFINITIONS and self.current_goal not in ["Socialize"]:
            if self._execute_generic_task(world, self.current_task_def_name): return
            else: self.current_task_def_name = None; self.task_work_progress = 0

        if self.current_goal not in JOB_TASK_DEFINITIONS and self.current_task_def_name:
             self.current_task_def_name = None; self.task_work_progress = 0

        # --- 2. Opportunistic Work Order Claiming / Resuming ---
        can_look_for_wo = self.current_goal in [None, "Idle", "Wander"] or \
                          (self.current_goal == self.job_default_goal() and self.job_default_goal() == "Idle")

        if can_look_for_wo and not self.active_work_order_id and not self.active_build_order_id:
            resumed_order = False
            for order in world.work_orders:
                if order.assigned_to == self.name and order.status in ["InProgress", "Approved"]:
                    if order.order_type == "CraftItem":
                        if order.status == "Approved": order.status = "InProgress"
                        self.active_work_order_id = order.order_id; self.current_goal = "Execute Craft Order"
                        self.add_memory(f"Resuming Craft WO {order.order_id}."); resumed_order = True; break
                    elif order.order_type == "BuildStructure":
                        if order.status == "Approved": order.status = "InProgress"
                        self.active_build_order_id = order.order_id; self.current_building_project = order.details.get("structure_type")
                        self.building_site_target = order.details.get("location"); self.current_goal = "Execute Build Order"
                        self.add_memory(f"Resuming Build WO {order.order_id}."); resumed_order = True; break
            if resumed_order: self.decide_action(world); return

            if not self.active_work_order_id and not self.active_build_order_id:
                if self.skills:
                    approved_craft_orders = world.get_approved_craft_orders()
                    if approved_craft_orders:
                        for order in approved_craft_orders:
                            item_name = order.details.get("item_name")
                            if item_name and item_name in BLUEPRINTS:
                                skill_info = self.skills.get(BLUEPRINTS[item_name].get("job_skill_needed"))
                                if skill_info and skill_info.get("level",0) >= BLUEPRINTS[item_name].get("skill_level_required",0):
                                    order.status = "InProgress"; order.assigned_to = self.name
                                    self._reset_crafting_state(); self.active_work_order_id = order.order_id
                                    self.current_goal = "Execute Craft Order"; self.workshop_location = (self.x, self.y)
                                    self.add_memory(f"Claimed Craft WO {order.order_id}."); self.decide_action(world); return
            if not self.active_work_order_id and not self.active_build_order_id:
                construction_skill_level = self.skills.get("Construction", {}).get("level", 0)
                if self.job == "Builder" or construction_skill_level > 0 :
                    build_orders = world.get_approved_build_orders()
                    if build_orders:
                        order_to_take = build_orders[0]
                        order_to_take.status = "InProgress"; order_to_take.assigned_to = self.name
                        self._reset_building_state(); self.active_build_order_id = order_to_take.order_id
                        self.current_building_project = order_to_take.details.get("structure_type")
                        self.building_site_target = order_to_take.details.get("location")
                        self.current_goal = "Execute Build Order"; self.add_memory(f"Claimed Build WO {order_to_take.order_id}."); self.decide_action(world); return

        # --- 3. Less Critical Needs & Default Job Goal (if not doing critical/WO) ---
        if self.current_goal in [None, "Idle", "Wander"] or \
           (self.current_goal == self.job_default_goal() and self.job_default_goal() == "Idle"):

            social_need_threshold = 30; hunger_threshold = 40; thirst_threshold = 40; energy_threshold = 40
            goal_set_by_less_critical_need = False
            if self.needs.get("Hunger", 100) < hunger_threshold: self.current_goal = "Seek Food"; goal_set_by_less_critical_need = True
            elif self.needs.get("Thirst", 100) < thirst_threshold: self.current_goal = "Seek Water"; goal_set_by_less_critical_need = True
            elif self.needs.get("Energy", 100) < energy_threshold: self.current_goal = "Seek Rest"; goal_set_by_less_critical_need = True
            elif self.needs.get("Social", 50) < social_need_threshold:
                can_socialize = True
                if "Loner" in self.traits and random.random() < 0.75: can_socialize = False
                if can_socialize:
                    if ("Outgoing" in self.traits and self.needs.get("Social", 50) < (social_need_threshold + 20) and random.random() < 0.6) or \
                       random.random() < 0.3:
                        self.current_goal = "Socialize"; goal_set_by_less_critical_need = True

            if goal_set_by_less_critical_need:
                self.decide_action(world); return

            # If no needs pressing and no WOs, fall back to job default goal
            if self.current_goal in [None, "Idle", "Wander"]:
                 self.current_goal = self.job_default_goal()
                 if self.current_goal != "Idle":
                     self.decide_action(world); return


        # --- 4. Execute Current Goal (Dispatch for job duties / other non-critical) ---
        if self.current_goal == "Assess Production Needs": self._execute_assess_production_needs(world); return
        elif self.current_goal == "Manage Subordinates": self._execute_manage_subordinates(world); return
        elif self.current_goal == "Maintain Ledger": self._execute_maintain_ledger(world); return
        elif self.current_goal == "Count Stockpile": self._execute_count_stockpile(world); return
        elif self.current_goal == "Perform Woodcutter Duties": self._execute_perform_woodcutter_duties(world); return
        elif self.current_goal == "Perform Stonemason Duties": self._execute_perform_stonemason_duties(world); return
        elif self.current_goal == "Perform Builder Duties": self._execute_perform_builder_duties(world); return
        elif self.current_goal == "Initiate Hauling": self._execute_initiate_hauling(world); return
        elif self.current_goal == "Haul Resource to Stockpile": self._execute_haul_resource(world); return
        elif self.current_goal == "Gather Wood": self._execute_gather_wood(world); return
        elif self.current_goal == "Gather Stone": self._execute_gather_stone(world); return
        elif self.current_goal == "Oversee Expedition": self._execute_oversee_expedition(world); return
        elif self.current_goal == "Socialize": self._execute_socialize(world); return

        # --- 5. Fallback to Wander/Idle ---
        if self.current_goal is None or self.current_goal == "Idle":
            if random.random() < 0.15:
                self.current_goal = "Wander"

        if self.current_goal == "Wander": self._execute_wander(world); return

        return

# Make sure to import SOCIAL_INTERACTION_DEFINITIONS from .data
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS, SOCIAL_INTERACTION_DEFINITIONS

class Character:
    # ... (previous code) ...
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: Optional[Dict[str, int]] = None,
                 x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10,
                 rank: str = "Worker"):
        # ... (rest of init)
        self.socialize_target_name: Optional[str] = None
        self.socialize_target_location: Optional[Tuple[int,int]] = None
        self.current_social_interaction_key: Optional[str] = None # Stores the key of the chosen interaction
        self.social_interaction_progress: int = 0


    def _execute_socialize(self, world: 'World'):
        if not self.socialize_target_name:
            # Find a target
            potential_targets = [
                char for char in world.characters
                if char.name != self.name and abs(char.x - self.x) + abs(char.y - self.y) <= 7 # Increased search radius slightly
                   and self.get_relationship_score(char.name) > -80 # Avoid deep enemies for now
            ]
            if not potential_targets:
                self.add_memory("Wanted to socialize, no one suitable nearby.")
                self.current_goal = self.job_default_goal() or "Idle"
                self.needs["Social"] = max(0, self.needs.get("Social", 50) - random.randint(1,3)) # Slight penalty for failed attempt
                return

            target_char = random.choice(potential_targets)
            self.socialize_target_name = target_char.name
            self.socialize_target_location = (target_char.x, target_char.y)
            self.social_interaction_progress = 0

            # Choose an interaction type
            valid_interactions = []
            for key, definition in SOCIAL_INTERACTION_DEFINITIONS.items():
                preconditions = definition.get("preconditions", {})
                passes_preconditions = True
                if "target_mood_less_than" in preconditions and target_char.mood >= preconditions["target_mood_less_than"]:
                    passes_preconditions = False
                if "relationship_less_than" in preconditions and self.get_relationship_score(target_char.name) >= preconditions["relationship_less_than"]:
                    passes_preconditions = False
                # Add more precondition checks here (e.g., item requirements)

                if passes_preconditions:
                    valid_interactions.append(key)

            if not valid_interactions: # Should always have GenericSocialize if others fail
                self.current_social_interaction_key = "GenericSocialize"
            else:
                self.current_social_interaction_key = random.choice(valid_interactions)

            chosen_interaction_def = SOCIAL_INTERACTION_DEFINITIONS.get(self.current_social_interaction_key)
            if chosen_interaction_def:
                 self.add_memory(f"Decided to '{chosen_interaction_def['display_name']}' with {self.socialize_target_name}.")
            else: # Should not happen if GenericSocialize is a fallback
                 self.add_memory(f"Error: Could not find interaction definition for {self.current_social_interaction_key}.")
                 self.current_goal = self.job_default_goal() or "Idle"; return


        target_character_obj = next((c for c in world.characters if c.name == self.socialize_target_name), None)
        interaction_def = SOCIAL_INTERACTION_DEFINITIONS.get(self.current_social_interaction_key)

        if not target_character_obj or not interaction_def:
            self.add_memory(f"Socialization target {self.socialize_target_name} or interaction {self.current_social_interaction_key} became invalid.")
            self._reset_socialization_state(); return

        # Move towards target if not adjacent
        if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 1:
            self.socialize_target_location = (target_character_obj.x, target_character_obj.y) # Update target location
            self.move_towards(self.socialize_target_location[0], self.socialize_target_location[1], world)
            # Check if target moved too far away or became unsuitable (e.g., started a critical task)
            if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 8 or \
               (target_character_obj.current_goal not in ["Socialize", "Idle", "Wander", None] and not target_character_obj.active_work_order_id):
                self.add_memory(f"{self.socialize_target_name} moved too far or got busy. Aborting '{interaction_def['display_name']}'.")
                self._reset_socialization_state(); return
            return # Still moving

        # Adjacent: Proceed with interaction
        self.social_interaction_progress += 1

        if self.social_interaction_progress >= interaction_def.get("base_duration", 5):
            # --- Apply Effects ---
            # Relationship
            rel_change_init = random.randint(interaction_def["base_relationship_change_initiator"]["min"], interaction_def["base_relationship_change_initiator"]["max"])
            rel_change_target = random.randint(interaction_def["base_relationship_change_target"]["min"], interaction_def["base_relationship_change_target"]["max"])

            # Mood
            mood_change_init = random.randint(interaction_def["mood_effect_initiator"]["min"], interaction_def["mood_effect_initiator"]["max"])
            mood_change_target = random.randint(interaction_def["mood_effect_target"]["min"], interaction_def["mood_effect_target"]["max"])

            # Trait Modifiers
            for modifier in interaction_def.get("trait_modifiers", []):
                applies_to_initiator = any(trait == modifier["trait"] for trait in self.traits)
                applies_to_target_char = any(trait == modifier["trait"] for trait in target_character_obj.traits)

                # Conditional application (e.g. "if_target_mood_below")
                condition_passes = True
                if "if_target_mood_below" in modifier and target_character_obj.mood >= modifier["if_target_mood_below"]:
                    condition_passes = False

                if condition_passes:
                    if modifier["target_component"] == "relationship_initiator" and applies_to_initiator : rel_change_init += modifier["value_add"]
                    if modifier["target_component"] == "relationship_target" and applies_to_initiator : rel_change_target += modifier["value_add"] # Initiator's trait affecting target's gain
                    if modifier["target_component"] == "relationship_target" and applies_to_target_char : rel_change_target += modifier["value_add"] # Target's trait affecting their own gain

                    if modifier["target_component"] == "mood_initiator" and applies_to_initiator : mood_change_init += modifier["value_add"]
                    if modifier["target_component"] == "mood_target" and applies_to_initiator : mood_change_target += modifier["value_add"]
                    if modifier["target_component"] == "mood_target" and applies_to_target_char : mood_change_target += modifier["value_add"]

                    # Backfire logic
                    if "backfire_chance" in modifier and random.random() < modifier["backfire_chance"]:
                        if (applies_to_initiator and "initiator" in modifier["target_component"]) or \
                           (applies_to_target_char and "target" in modifier["target_component"]):
                            self.add_memory(f"'{interaction_def['display_name']}' with {target_character_obj.name} backfired due to '{modifier['trait']}' trait!")
                            if "backfire_effect_rel_target" in modifier and modifier["target_component"] == "relationship_target": rel_change_target += modifier["backfire_effect_rel_target"]
                            if "backfire_effect_mood_target" in modifier and modifier["target_component"] == "mood_target": mood_change_target += modifier["backfire_effect_mood_target"]
                            # Add other backfire effects as needed

            self.modify_relationship(target_character_obj.name, rel_change_init, world, reason=f"Initiated '{interaction_def['display_name']}'")
            target_character_obj.modify_relationship(self.name, rel_change_target, world, reason=f"Target of '{interaction_def['display_name']}'")

            # Needs
            for need, change in interaction_def.get("initiator_need_changes", {}).items():
                self.needs[need] = min(self.max_needs.get(need, 100), max(0, self.needs.get(need, 0) + change))
            for need, change in interaction_def.get("target_need_changes", {}).items():
                target_character_obj.needs[need] = min(target_character_obj.max_needs.get(need, 100), max(0, target_character_obj.needs.get(need, 0) + change))

            # Mood (direct effect from interaction)
            self.mood = max(0, min(100, self.mood + mood_change_init))
            target_character_obj.mood = max(0, min(100, target_character_obj.mood + mood_change_target))

            # Final mood update call to consolidate other factors like needs
            self._update_mood(world)
            target_character_obj._update_mood(world)

            # Logging and Dialogue
            log_message = interaction_def.get("description_template", "{initiator_name} interacted with {target_name}.").format(initiator_name=self.name, target_name=target_character_obj.name)
            self.add_memory(log_message)
            target_character_obj.add_memory(log_message) # Target also remembers

            dialogue_key = interaction_def.get("dialogue_context_key", "social_chat_neutral")
            if config.USE_LLM:
                # Pass more context if needed, like the specific interaction key
                initiator_dialogue = generate_dialogue(self.name, target_character_obj.name, f"{dialogue_key}_initiator", world, self.personality, self.traits, target_character_obj.personality, target_character_obj.traits, self.get_relationship_score(target_character_obj.name))
                self.add_memory(f"Said to {target_character_obj.name}: \"{initiator_dialogue}\"")
                target_character_obj.add_memory(f"Heard from {self.name}: \"{initiator_dialogue}\"")
            else:
                self.add_memory(f"[LLM Off] ({interaction_def['display_name']}) with {target_character_obj.name}")
                target_character_obj.add_memory(f"[LLM Off] ({interaction_def['display_name']}) with {self.name}")

            self._reset_socialization_state()

        else: # Interaction in progress, check if target is still valid/present
            if abs(self.x - target_character_obj.x) + abs(self.y - target_character_obj.y) > 2 or \
               (target_character_obj.current_goal not in ["Socialize", "Idle", "Wander", None] and not target_character_obj.active_work_order_id):
                self.add_memory(f"Social interaction '{interaction_def['display_name']}' with {self.socialize_target_name} cut short.")
                self._reset_socialization_state()
                # Small social need recovery for the attempt
                self.needs["Social"] = min(self.max_needs["Social"], self.needs.get("Social", 50) + random.randint(1,3))


    def _reset_socialization_state(self):
        self.current_goal = self.job_default_goal() or "Idle"
        self.socialize_target_name = None
        self.socialize_target_location = None
        self.current_social_interaction_key = None
        self.social_interaction_progress = 0
        if self.current_task_def_name == "Socialize": # Ensure generic task state is also reset
            self.current_task_def_name = None
            self.task_work_progress = 0


    def _execute_perform_builder_duties(self, world: 'World'): # Unchanged
        if self.job != "Builder" and self.skills.get("Construction", {}).get("level",0) == 0 :
            self.current_goal = self.job_default_goal() or "Idle"; return
        if not self.active_build_order_id: self.current_goal = "Idle"; return
        else: self.current_goal = "Execute Build Order"

    def _execute_fetch_resource_for_build(self, world: 'World'): # Unchanged
        if not self.resource_to_fetch: return
        res_name = self.resource_to_fetch["name"]
        quantity_needed_for_project_for_this_type = self.resource_to_fetch["quantity"]
        if quantity_needed_for_project_for_this_type <= 0: self.resource_to_fetch = None; return
        target_sp_name = self.resource_to_fetch.get("target_stockpile_name")
        sp_to_fetch = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None
        if not sp_to_fetch or sp_to_fetch.inventory.get(res_name, 0) == 0:
            suitable_sps = [sp for sp in world.get_stockpiles_for_resource(res_name) if sp.inventory.get(res_name, 0) > 0]
            if not suitable_sps: print(f"{self.name} needs {res_name} for building, but none in stockpiles. Waiting."); return
            sp_to_fetch = suitable_sps[0]; self.resource_to_fetch["target_stockpile_name"] = sp_to_fetch.name
        spot = (sp_to_fetch.rect[0], sp_to_fetch.rect[1])
        if (self.x, self.y) != spot: self.move_towards(spot[0], spot[1], world); return
        max_can_carry_this_trip = self.max_inventory_items - self.get_inventory_load()
        qty_to_attempt_take = min(quantity_needed_for_project_for_this_type, sp_to_fetch.inventory.get(res_name,0), max_can_carry_this_trip)
        if qty_to_attempt_take <= 0: return
        s, qty_taken = sp_to_fetch.remove_item(res_name, qty_to_attempt_take)
        if s and qty_taken > 0:
            self.inventory[res_name] = self.inventory.get(res_name, 0) + qty_taken
            self.add_memory(f"Fetched {qty_taken} {res_name} from {sp_to_fetch.name} for building.")
            self.resource_to_fetch["quantity"] -= qty_taken
            if self.resource_to_fetch["quantity"] <= 0: self.resource_to_fetch = None

    def _execute_build_order(self, world: 'World'): # Modified for skill/status/energy impact
        if not self.active_build_order_id or not self.current_building_project or not self.building_site_target:
            self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"; return
        order = world.get_work_order_by_id(self.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name:
            self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"; return

        if self.needs.get("Energy", 100) <= 0: # Too tired to work
            self.add_memory(f"Too tired to work on {self.current_building_project}. Need to rest.")
            self.current_goal = "Seek Rest"; return

        structure_blueprint_name = order.details["structure_type"]
        structure_bp = STRUCTURE_BLUEPRINTS.get(structure_blueprint_name)
        if not structure_bp:
            order.status = "Denied"; order.denial_reason = f"Unknown blueprint {structure_blueprint_name}"; self._reset_building_state(); self.current_goal = "Idle"; return
        required_resources_total = structure_bp["required_resources"]
        if not self.materials_gathered_for_build:
            if self.resource_to_fetch:
                if self.get_inventory_load() >= self.max_inventory_items: self.resource_to_fetch = None
                else:
                    self._execute_fetch_resource_for_build(world)
                    if self.resource_to_fetch and self.resource_to_fetch.get("name"): return
            all_project_materials_in_inventory = True; resource_type_to_target_next = None
            for res, total_qty_needed in required_resources_total.items():
                if self.inventory.get(res, 0) < total_qty_needed:
                    all_project_materials_in_inventory = False; resource_type_to_target_next = res; break
            if all_project_materials_in_inventory: self.materials_gathered_for_build = True; self.resource_to_fetch = None
            elif resource_type_to_target_next:
                if self.get_inventory_load() < self.max_inventory_items:
                    self.resource_to_fetch = {"name": resource_type_to_target_next, "quantity": required_resources_total[resource_type_to_target_next] - self.inventory.get(resource_type_to_target_next, 0), "for_wo_id": order.order_id, "target_type": "build"}
                    self._execute_fetch_resource_for_build(world); return
            else:
                if self.get_inventory_load() == 0 : self.current_goal = "Idle"; return

        if (self.x, self.y) != self.building_site_target:
            self.move_towards(self.building_site_target[0], self.building_site_target[1], world); return

        target_building: Optional[Building] = None
        for b in world.buildings:
            if b.location == self.building_site_target and b.structure_type == structure_blueprint_name and not b.is_operational:
                target_building = b; break
        if not target_building:
            target_building = Building(structure_type=structure_blueprint_name, display_name=structure_bp["display_name"], location=self.building_site_target, size=structure_bp["size"], required_resources=structure_bp["required_resources"], build_time=structure_bp["build_time"], functionality=structure_bp.get("functionality"), required_skill=structure_bp.get("required_skill"))
            world.add_building(target_building)
            temp_inv_copy = self.inventory.copy(); resources_consumed_this_session = {}
            for res_name, res_needed_total in required_resources_total.items():
                if res_name in temp_inv_copy:
                    qty_to_use = temp_inv_copy[res_name]
                    self.inventory[res_name] -= qty_to_use
                    if self.inventory[res_name] <= 0: del self.inventory[res_name]
                    resources_consumed_this_session[res_name] = qty_to_use
            if resources_consumed_this_session: self.add_memory(f"Used {resources_consumed_this_session} for {structure_blueprint_name}.")

        if target_building and not target_building.is_operational:
            task_def = JOB_TASK_DEFINITIONS.get("Construct Building")
            if not task_def: self.current_goal = "Idle"; return
            progress_this_tick = float(task_def.get("base_yield", 1))
            work_speed_modifier = self.get_status_modifier("work_speed_multiplier", 1.0)
            mood_modifier = 1.0
            if self.mood < 25 : mood_modifier = 0.8
            elif self.mood > 75 : mood_modifier = 1.2
            progress_this_tick *= work_speed_modifier * mood_modifier
            construction_skill_info = self.skills.get("Construction")
            if not construction_skill_info : # Initialize if missing
                self.skills["Construction"] = {"level": 0, "experience": 0.0, "exp_to_next_level": self._calculate_exp_for_level(0)}
                construction_skill_level = 0
            else:
                construction_skill_level = construction_skill_info.get("level",0)
            progress_this_tick *= (1 + construction_skill_level * 0.05)

            actual_progress_applied = target_building.work_on(progress_this_tick)
            self.needs['Energy'] = max(0, self.needs.get('Energy',100) - 2.0)

            if actual_progress_applied > 0:
                self._grant_skill_experience("Construction", float(actual_progress_applied) * 1.0, world)
            self.add_memory(f"Worked on {target_building.display_name} (+{actual_progress_applied:.1f} prog).")
            if target_building.is_operational:
                order.status = "Completed"; self.add_memory(f"Completed Build WO {order.order_id}."); self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"
                if self.building_site_target: # Move off logic
                    for dx_try, dy_try in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                        check_x, check_y = self.building_site_target[0] + dx_try, self.building_site_target[1] + dy_try
                        if world.get_tile(check_x,check_y) not in ["Mountain", "Water"] and not world.get_characters_at_location(check_x,check_y) and not any((check_x, check_y) == bt for b_obj in world.buildings if b_obj.location == self.building_site_target for bt in b_obj.get_tiles_occupied()):
                            self.move_towards(check_x, check_y, world); break
                return
        elif target_building and target_building.is_operational:
            order.status = "Completed"; self._reset_building_state(); self.current_goal = self.job_default_goal() or "Idle"; return

    def conduct_performance_review(self, subordinate_char_name: str, world: 'World'): # Unchanged
        if self.name == subordinate_char_name: self.add_memory("Cannot self-review."); return
        subordinate = next((c for c in world.characters if c.name == subordinate_char_name), None)
        if not subordinate or subordinate.supervisor_name != self.name: self.add_memory(f"Cannot review {subordinate_char_name}."); return
        if not world.game_time: self.add_memory("Game time not available for review."); return
        objective_rating = "Needs Improvement"; review_notes = []
        if subordinate.job == "Bookkeeper":
            is_diligent = True
            if not world.stockpiles: review_notes.append("No stockpiles to check.")
            else:
                for sp in world.stockpiles:
                    last_update = world.ledger.get_stockpile_last_update_day(sp.name)
                    if last_update is None or (world.game_time.current_day - last_update > config.STALE_THRESHOLD_DAYS + 2):
                        is_diligent = False; review_notes.append(f"Ledger for {sp.name} stale."); break
            if is_diligent and world.stockpiles: objective_rating = "Good"; review_notes.append("Ledger up-to-date.")
            elif not world.stockpiles and is_diligent: objective_rating = "Not Evaluated"
        final_rating = objective_rating; rating_modifier_score = 0
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
        if final_rating != objective_rating: review_notes.append(f"Supervisor's discretion adjusted rating from {objective_rating} to {final_rating}.")
        subordinate.performance_rating = final_rating; subordinate.last_performance_review_day = world.game_time.current_day
        relationship_change_value = 0
        if final_rating == "Excellent": relationship_change_value = 10
        elif final_rating == "Good": relationship_change_value = 5
        elif final_rating == "Satisfactory": relationship_change_value = 1
        elif final_rating == "Needs Improvement": relationship_change_value = -5
        elif final_rating == "Poor": relationship_change_value = -10
        if relationship_change_value != 0:
            self.modify_relationship(subordinate.name, relationship_change_value // 2, world, reason=f"Performance review: {final_rating}")
            subordinate.modify_relationship(self.name, relationship_change_value, world, reason=f"Performance review from {self.name}: {final_rating}")
        if final_rating not in ["Poor", "Needs Improvement"] and subordinate.warning_count > 0:
             review_notes.append(f"Past warnings ({subordinate.warning_count}) cleared."); subordinate.warning_count = 0
        elif final_rating == "Poor" and subordinate.warning_count == 0 :
            subordinate.warning_count = 1; review_notes.append("Poor review counts as warning.")
        review_summary = f"Review for {subordinate.name}: {final_rating}. Notes: {'; '.join(review_notes) or 'General.'}"
        self.add_memory(review_summary); subordinate.add_memory(f"Review with {self.name}: {final_rating}.")

    def issue_warning(self, subordinate_char_name: str, world: 'World', reason_message: str): # Unchanged
        subordinate = next((c for c in world.characters if c.name == subordinate_char_name), None)
        if not subordinate or subordinate.supervisor_name != self.name : return
        subordinate.warning_count += 1
        self.add_memory(f"Issued warning to {subordinate.name} for: {reason_message}. Total: {subordinate.warning_count}.")
        subordinate.add_memory(f"Received warning from {self.name} for: {reason_message}.")
        if subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD and subordinate.performance_rating != "Poor":
            subordinate.performance_rating = "Poor"; self.add_memory(f"{subordinate.name}'s performance set to Poor due to warnings.")

    def fire_subordinate(self, subordinate_char_name: str, world: 'World'): # Unchanged
        subordinate = next((c for c in world.characters if c.name == subordinate_char_name), None)
        if not subordinate or subordinate.supervisor_name != self.name: return
        if subordinate.name in self.subordinates_names: self.remove_subordinate(subordinate.name)
        original_job = subordinate.job
        subordinate.supervisor_name = None; subordinate.job = "Unemployed"; subordinate.rank = "Commoner"
        subordinate.current_goal = "Idle"; subordinate.assigned_tasks = []; subordinate.performance_rating = "Fired"; subordinate.warning_count = 0
        if subordinate.active_work_order_id:
            wo = world.get_work_order_by_id(subordinate.active_work_order_id)
            if wo and wo.status == "InProgress" and wo.assigned_to == subordinate.name:
                wo.status = "Pending"; wo.assigned_to = None
            subordinate._reset_crafting_state()
        self.add_memory(f"Fired {subordinate.name} from job as {original_job}.")
        subordinate.add_memory(f"Was fired by {self.name} from job {original_job}.")

    def get_relationship_score(self, target_char_name: str) -> int: # Unchanged
        return self.relationships.get(target_char_name, 0)

    def modify_relationship(self, target_char_name: str, value_change: int, world: 'World', reason: Optional[str] = None): # Unchanged
        if self.name == target_char_name: return
        current_score = self.relationships.get(target_char_name, 0)
        new_score = max(-100, min(100, current_score + value_change))
        self.relationships[target_char_name] = new_score
        if reason: self.add_memory(f"Rel with {target_char_name} -> {new_score} ({value_change:+}). Reason: {reason}")

    def _grant_skill_experience(self, skill_name: str, amount: float, world: 'World'): # Unchanged
        if skill_name not in self.skills:
            self.skills[skill_name] = {"level": 0, "experience": 0.0, "exp_to_next_level": self._calculate_exp_for_level(0)}
        self.skills[skill_name]["experience"] += amount
        print(f"DEBUG_XP: {self.name} gained {amount:.1f} XP in {skill_name}. Total: {self.skills[skill_name]['experience']:.1f}/{self.skills[skill_name]['exp_to_next_level']:.0f}")
        self._check_skill_level_up(skill_name, world)

    def _check_skill_level_up(self, skill_name: str, world: 'World'): # Unchanged
        if skill_name not in self.skills: return
        while self.skills[skill_name]["experience"] >= self.skills[skill_name]["exp_to_next_level"]:
            exp_needed = self.skills[skill_name]["exp_to_next_level"]
            self.skills[skill_name]["level"] += 1
            self.skills[skill_name]["experience"] -= exp_needed
            new_level = self.skills[skill_name]["level"]
            self.skills[skill_name]["exp_to_next_level"] = self._calculate_exp_for_level(new_level)
            level_up_message = f"{self.name}'s {skill_name} skill increased to level {new_level}!"
            self.add_memory(level_up_message)
            if world: world.add_event_log_message(level_up_message)
            print(level_up_message)

    def apply_status_effect(self, status_data: Dict[str, Any], world: 'World'): # Unchanged
        status_name = status_data.get("status_name")
        if not status_name: return
        existing_status = next((se for se in self.status_effects if se.get("name") == status_name), None)
        if existing_status:
            new_duration_days = status_data.get("duration_days", 0)
            new_duration_ticks = new_duration_days * world.game_time.ticks_per_day
            current_remaining = existing_status.get("duration_remaining_ticks", 0)
            if new_duration_ticks > current_remaining or new_duration_ticks == 0:
                existing_status["duration_remaining_ticks"] = new_duration_ticks
                existing_status["modifiers"] = status_data.get("modifiers", {})
                self.add_memory(f"Status '{status_name}' refreshed."); return
        new_status = {"name": status_name, "duration_remaining_ticks": status_data.get("duration_days", 0) * world.game_time.ticks_per_day, "modifiers": status_data.get("modifiers", {}), "applied_tick": world.game_time.current_total_ticks}
        self.status_effects.append(new_status); self.add_memory(f"Affected by '{status_name}'.")
        print(f"{self.name} is now affected by '{status_name}' for {status_data.get('duration_days',0)} days (Modifiers: {new_status['modifiers']}).")

    def process_status_effects(self, world: 'World'): # Unchanged
        effects_to_remove = []
        for status in self.status_effects:
            status["duration_remaining_ticks"] -= 1
            if status["duration_remaining_ticks"] <= 0:
                effects_to_remove.append(status)
                self.add_memory(f"Status '{status['name']}' has worn off.")
                print(f"{self.name}'s status '{status['name']}' has worn off.")
        for eff in effects_to_remove: self.status_effects.remove(eff)

    def get_status_modifier(self, modifier_key: str, default_value: float = 1.0) -> float: # Unchanged
        current_value = default_value
        for status in self.status_effects:
            if modifier_key in status.get("modifiers", {}):
                current_value *= status["modifiers"][modifier_key]
        return current_value