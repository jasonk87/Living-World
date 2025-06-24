# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS
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
        self.name = name; self.personality = personality; self.traits = traits; self.skills = skills
        self.x = x; self.y = y; self.inventory = {}; self.memory = [];
        self.needs = needs if needs else {}; self.current_goal = current_goal
        self.relationships = {}; self.job = job; self.max_inventory_items = max_inventory_items
        self.hauling_info: Optional[Dict] = None
        self.counting_target_stockpile_name: Optional[str] = None
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False

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

    def _reset_crafting_state(self):
        self.active_work_order_id = None; self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False; self.resource_to_fetch = None
        self.crafting_progress = 0; self.hauling_info = None; self.workshop_location = None

    def __str__(self):
        base_info = (f"Character(Name: {self.name}, Rank: {self.rank}, Job: {self.job}, Pos: ({self.x},{self.y}), Goal: {self.current_goal}, WO: {self.active_work_order_id}, Load: {self.get_inventory_load()}/{self.max_inventory_items})")
        supervisor_info = f"  Supervisor: {self.supervisor_name if self.supervisor_name else 'None'}"
        subordinates_info = f"  Subordinates: {len(self.subordinates_names)}"
        performance_info = f"  Performance: {self.performance_rating} (Warnings: {self.warning_count}, Last Review: Day {self.last_performance_review_day if self.last_performance_review_day is not None else 'N/A'})"
        equipped_tool_info = "None";
        if self.equipped_tool: equipped_tool_info = f"{self.equipped_tool['name']} ({self.equipped_tool['durability']}/{self.equipped_tool['max_durability']})"
        tool_info_str = f"  Equipped Tool: {equipped_tool_info}"
        return f"{base_info}\n{supervisor_info}; {subordinates_info}\n{performance_info}\n{tool_info_str}"
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
        self.task_work_progress += 1
        if self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced"); yield_amt = task_def.get("base_yield",1)
            can_add = self.max_inventory_items - self.get_inventory_load(); actual_yield = min(yield_amt, can_add)
            if actual_yield > 0 and res_prod:
                self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield
                tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
                self.add_memory(f"Task '{task_name}': got {actual_yield} {res_prod} with {tool_name_mem}.")
                print(f"{self.name} task '{task_name}' yielded {actual_yield} {res_prod}.")
            elif yield_amt > 0: print(f"{self.name} inventory full for {task_name}.")
            self.task_work_progress = 0
            if self.equipped_tool and tool_type:
                self.equipped_tool["durability"] -= 1
                if self.equipped_tool["durability"] <= 0:
                    self.add_memory(f"{self.equipped_tool['name']} broke!"); print(f"Oh no! {self.name}'s {self.equipped_tool['name']} BROKE!")
                    self.unequip_tool()
        return True

    def _execute_craft_order(self, world: 'World'):
        order = world.get_work_order_by_id(self.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name : self._reset_crafting_state(); self.current_goal=self.job_default_goal() or "Idle"; return
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
            self.crafting_progress += 1
            if self.crafting_progress >= craft_time_per_unit:
                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    self.inventory[res] -= req_qty_per_unit
                    if self.inventory[res] <= 0: self.inventory.pop(res,None)
                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1 ; self.add_memory(f"Crafted 1 {item_name} for WO {order.order_id}.")
                print(f"{self.name} CRAFTED 1 {item_name}. Inv has: {self.inventory.get(item_name,0)}/{item_qty_total} for WO {order.order_id}.")
                self.crafting_progress = 0; self.materials_gathered_for_wo = False
                if self.inventory.get(item_name,0) >= item_qty_total: self.items_crafted_for_wo = True
            return
        if self.items_crafted_for_wo:
            if not self.hauling_info and self.inventory.get(item_name, 0) > 0:
                self.hauling_info = {"resource":item_name, "quantity":self.inventory.get(item_name,0), "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = "Initiate Hauling"; return
            elif self.hauling_info is None and self.inventory.get(item_name, 0) == 0:
                 order.status = "Completed"; self.add_memory(f"Completed/Stocked WO {order.order_id} ({item_name})."); print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name})."); self._reset_crafting_state(); self.current_goal = self.job_default_goal() or "Idle"; return

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
        if not self.managed_item_targets: self.current_goal = "Idle"; return
        target_item_names = list(self.managed_item_targets.keys())
        if not target_item_names: self.current_goal = "Idle"; return
        for i in range(len(target_item_names)):
            current_idx = (self._mc_item_check_idx + i) % len(target_item_names)
            item_name = target_item_names[current_idx]; target_qty = self.managed_item_targets[item_name]
            last_ordered_day = self.order_cooldown.get(item_name, -ORDER_SPAM_PREVENTION_DAYS - 1)
            if world.game_time.current_day - last_ordered_day < ORDER_SPAM_PREVENTION_DAYS: continue
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
        if not item_processed_this_tick: self.current_goal = "Idle"; self._mc_item_check_idx = 0

    # Renamed from _execute_manage_work_orders to _execute_manage_subordinates
    def _execute_manage_subordinates(self, world: 'World'):
        if not (self.job == "Manager" or self.rank in ["Noble Lord", "Baron"]) or not self.subordinates_names:
            self.current_goal = self.job_default_goal(); return # Not a manager or no one to manage

        # Prioritize managing work orders if also a Manager (dual role)
        if self.job == "Manager":
            self._execute_manage_work_orders_as_part_of_supervision(world) # A new helper for this
            # After potentially handling a WO, proceed to subordinate management unless an action was taken that changes goal

        if not world.game_time: return # Need game time for reviews

        # Iterate through subordinates for potential actions
        # Simple approach: one management action per 'Manage Subordinates' cycle to avoid spamming actions
        # More sophisticated: a priority queue of management tasks

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
        if not pending_orders: return # No orders to manage, main function will continue to subordinate mgmt

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
            inv=stockpile_obj.inventory.copy(); world.ledger.update_stockpile_record(stockpile_obj.name,inv,world.game_time.current_day)
            self.add_memory(f"Counted {stockpile_obj.name}"); print(f"{self.name} (Bookkeeper) counted {stockpile_obj.name}. Inv: {inv}. Day: {world.game_time.current_day}.")
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
        if not self.hauling_info: self.current_goal=self.job_default_goal() or "Idle"; return
        res=self.hauling_info.get("resource")
        if not res or self.inventory.get(res,0)==0:self.current_goal=self.job_default_goal() or "Idle";self.hauling_info=None;self.decide_action(world);return
        qty=self.inventory.get(res,0);sps=[s_obj for s_obj in world.get_stockpiles_for_resource(res)if s_obj.has_space_for(res,1)]
        if not sps:self.current_goal="Wander"; return
        sp_chosen=sps[0];self.hauling_info["target_stockpile_name"]=sp_chosen.name;self.hauling_info["quantity_to_haul"]=qty
        self.current_goal="Haul Resource to Stockpile";self.decide_action(world)
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

        # 2. Opportunistic Work Order Claiming
        # Check if character is available (idle, wandering, or their job allows picking up WOs) and has no active WO
        can_look_for_wo = self.current_goal in [None, "Idle", "Wander"] or \
                          (self.job in ["Master Craftsman", "Expedition Leader", "Manager"] and self.current_goal in ["Assess Production Needs", "Oversee Expedition", "Manage Work Orders", "Idle", None])

        if can_look_for_wo and not self.active_work_order_id:
            if self.skills:
                approved_orders = world.get_approved_craft_orders()
                if approved_orders:
                    for order in approved_orders:
                        if order.assigned_to is None:
                            item_name = order.details.get("item_name")
                            if item_name and item_name in BLUEPRINTS:
                                required_skill = BLUEPRINTS[item_name].get("job_skill_needed")
                                if required_skill and self.skills.get(required_skill, 0) > 0:
                                    order.status = "InProgress"; order.assigned_to = self.name
                                    self._reset_crafting_state(); self.active_work_order_id = order.order_id
                                    self.current_goal = "Execute Craft Order"; self.workshop_location = (self.x, self.y)
                                    self.add_memory(f"Claimed WO {order.order_id} for {item_name}.")
                                    print(f"{self.name} CLAIMED Work Order {order.order_id} ({item_name}) skill: {required_skill}.")
                                    self._execute_craft_order(world); return  # Start immediately

        # 3. Job-Specific Goal Setting if idle/wandering and no WO was claimed
        if self.current_goal in [None, "Idle", "Wander"]:
            self.current_goal = self.job_default_goal()

        # 4. Execute Current Goal
        if self.current_goal == "Assess Production Needs": self._execute_assess_production_needs(world); return
        elif self.current_goal == "Manage Subordinates": self._execute_manage_subordinates(world); return # New
        elif self.current_goal == "Manage Work Orders": self._execute_manage_work_orders_as_part_of_supervision(world); return # Retain for direct WO management if ever set
        elif self.current_goal == "Maintain Ledger": self._execute_maintain_ledger(world); return
        elif self.current_goal == "Count Stockpile": self._execute_count_stockpile(world); return
        elif self.current_goal == "Perform Woodcutter Duties": self._execute_perform_woodcutter_duties(world); return
        elif self.current_goal == "Perform Stonemason Duties": self._execute_perform_stonemason_duties(world); return
        elif self.current_goal == "Initiate Hauling": self._execute_initiate_hauling(world); return
        elif self.current_goal == "Haul Resource to Stockpile": self._execute_haul_resource(world); return
        elif self.current_goal == "Gather Wood": self._execute_gather_wood(world); return
        elif self.current_goal == "Gather Stone": self._execute_gather_stone(world); return
        elif self.current_goal == "Oversee Expedition": self._execute_oversee_expedition(world); return

        # 5. Fallback to Wander/Idle
        if self.current_goal is None or self.current_goal == "Idle":
            if random.random() < 0.05: self.current_goal = "Wander" # Low chance if truly has nothing else to do
            else: return # Remain Idle for this tick

        if self.current_goal == "Wander": self._execute_wander(world); return

        # Failsafe: If goal is somehow not covered, set to Idle to prevent loops
        # print(f"Warning: {self.name} has unhandled goal '{self.current_goal}'. Setting to Idle.")
        # self.current_goal = "Idle"
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