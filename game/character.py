# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS

if TYPE_CHECKING:
    from .world import World
    from .character import Character as OtherCharacter

STALE_THRESHOLD_DAYS = 2
ORDER_SPAM_PREVENTION_DAYS = 3

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: dict[str, int], x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10):
        self.name = name; self.personality = personality; self.traits = traits; self.skills = skills
        self.x = x; self.y = y; self.inventory = {}; self.memory = [];
        self.needs = needs if needs else {}; self.current_goal = current_goal
        self.relationships = {}; self.job = job; self.max_inventory_items = max_inventory_items
        self.hauling_info: Optional[Dict] = None
        self.counting_target_stockpile_name: Optional[str] = None
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}

        self.active_work_order_id: Optional[str] = None
        self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False
        self.items_crafted_for_wo: bool = False # Tracks if all units for the WO are crafted
        self.resource_to_fetch: Optional[Dict] = None
        self.workshop_location: Optional[Tuple[int,int]] = None

    def _reset_crafting_state(self):
        self.active_work_order_id = None
        self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False
        self.resource_to_fetch = None
        self.crafting_progress = 0
        self.hauling_info = None
        self.workshop_location = None

    def __str__(self):
        base_info = (f"Character(Name: {self.name}, Job: {self.job}, Pos: ({self.x},{self.y}), "
                     f"Goal: {self.current_goal}, WO: {self.active_work_order_id}, Load: {self.get_inventory_load()}/{self.max_inventory_items})")
        supervisor_info = f"  Supervisor: {self.supervisor_name if self.supervisor_name else 'None'}"
        subordinates_info = f"  Subordinates: {len(self.subordinates_names)}"
        return f"{base_info}\n{supervisor_info}; {subordinates_info}"
    def set_supervisor(self, supervisor_name: Optional[str]): self.supervisor_name = supervisor_name
    def add_subordinate(self, subordinate_name: str):
        if subordinate_name not in self.subordinates_names: self.subordinates_names.append(subordinate_name)
    def remove_subordinate(self, subordinate_name: str):
        if subordinate_name in self.subordinates_names: self.subordinates_names.remove(subordinate_name)
    def get_inventory_load(self) -> int: return sum(self.inventory.values())
    def add_memory(self, event: str): self.memory.append(event); self.memory = self.memory[-20:]
    def interact(self, other_character: 'OtherCharacter', world: 'World'): pass
    def move(self, dx: int, dy: int, world: 'World'):
        new_x,new_y=self.x+dx,self.y+dy
        if 0<=new_x<world.grid_size[0] and 0<=new_y<world.grid_size[1]:
            if not [c for c in world.get_characters_at_location(new_x,new_y) if c.name!=self.name]:
                self.x=new_x;self.y=new_y
    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx=target_x-self.x; dy=target_y-self.y
        if dx > 0: dx = 1
        elif dx < 0: dx = -1
        if dy > 0: dy = 1
        elif dy < 0: dy = -1
        if dx != 0 or dy != 0: self.move(dx, dy, world)
    def find_nearest_resource(self, resource_name: str, world: 'World') -> Optional[Tuple[int, int]]:
        locations=world.get_resources(resource_name)
        if not locations:return None
        tile_type_current = world.get_tile(self.x, self.y)
        if (resource_name == "Wood" and tile_type_current == "Forest") or \
           (resource_name == "Stone" and tile_type_current == "Rocks") or \
           tile_type_current == resource_name:
            if (self.x, self.y) in locations: return (self.x, self.y)
        for loc in locations:
            tile_type = world.get_tile(loc[0], loc[1])
            if(resource_name=="Wood" and tile_type=="Forest")or(resource_name=="Stone"and tile_type=="Rocks")or tile_type==resource_name:return loc
        return None
    def gather_resource(self, resource_name: str, world: 'World'):
        current_pos=(self.x,self.y);current_tile_type=world.get_tile(self.x,self.y)
        tile_is_source=(resource_name=="Wood" and current_tile_type=="Forest")or\
                       (resource_name=="Stone" and current_tile_type=="Rocks")or\
                       current_tile_type==resource_name
        if tile_is_source and resource_name in world.resources and current_pos in world.resources.get(resource_name,[]):
            self.inventory[resource_name]=self.inventory.get(resource_name,0)+1
            world.resources[resource_name].remove(current_pos)
            self.add_memory(f"Gathered {resource_name} at {current_pos}")
            if not [loc for loc in world.resources.get(resource_name,[])if loc==current_pos]:
                if(resource_name=="Wood" and current_tile_type=="Forest")or\
                  (resource_name=="Stone" and current_tile_type=="Rocks"):
                    world.set_tile(self.x,self.y,"Grass");
    def build(self, structure_type: str, world: 'World') -> bool: return False

    def decide_action(self, world: 'World'):
        if not world.game_time: self.current_goal = "Idle"; return

        # 1. Active Craft Order Execution takes top priority
        if self.current_goal == "Execute Craft Order" and self.active_work_order_id:
            self._execute_craft_order(world)
            return

        # 2. Interaction check (if not busy with an active craft order)
        other_chars_here = [c for c in world.get_characters_at_location(self.x, self.y) if c.name != self.name]
        if other_chars_here and self.current_goal in ["Wander", "Idle", None] and not self.active_work_order_id :
            self.interact(other_chars_here[0], world); return

        # 3. Opportunistic Work Order Claiming (if idle/wandering and has skills)
        # This runs BEFORE defaulting to primary job goal if idle.
        if self.current_goal in [None, "Idle", "Wander"] and not self.active_work_order_id:
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
                                    self._execute_craft_order(world) # Start immediately
                                    return  # Action taken: claimed and started order

        # 4. Job-Specific Goal Setting (Primary Duties) if no WO was claimed and character is idle/wandering
        if self.current_goal in [None, "Idle", "Wander"]: # Check again, as WO claiming might have set a goal
            if self.job == "Master Craftsman": self.current_goal = "Assess Production Needs"
            elif self.job == "Manager": self.current_goal = "Manage Work Orders"
            elif self.job == "Bookkeeper": self.current_goal = "Maintain Ledger"
            elif self.job == "Woodcutter": self.current_goal = "Perform Woodcutter Duties"
            elif self.job == "Stonemason": self.current_goal = "Perform Stonemason Duties"
            elif self.job == "Expedition Leader": self.current_goal = "Oversee Expedition"

        # 5. Execute Current Goal (Primary Job tasks or previously set goals)
        if self.current_goal == "Assess Production Needs": self._execute_assess_production_needs(world); return
        elif self.current_goal == "Manage Work Orders": self._execute_manage_work_orders(world); return
        elif self.current_goal == "Maintain Ledger": self._execute_maintain_ledger(world); return
        elif self.current_goal == "Count Stockpile": self._execute_count_stockpile(world); return
        elif self.current_goal == "Perform Woodcutter Duties": self._execute_perform_woodcutter_duties(world); return
        elif self.current_goal == "Perform Stonemason Duties": self._execute_perform_stonemason_duties(world); return
        elif self.current_goal == "Initiate Hauling": self._execute_initiate_hauling(world); return
        elif self.current_goal == "Haul Resource to Stockpile": self._execute_haul_resource(world); return
        elif self.current_goal == "Gather Wood": self._execute_gather_wood(world); return
        elif self.current_goal == "Gather Stone": self._execute_gather_stone(world); return
        elif self.current_goal == "Oversee Expedition": self._execute_oversee_expedition(world); return

        # 6. Fallback to Wander/Idle
        if self.current_goal is None or self.current_goal == "Idle":
            if random.random() < 0.05: self.current_goal = "Wander"
            else: return

        if self.current_goal == "Wander":
            moves=[];
            for dx,dy in[(0,1),(0,-1),(1,0),(-1,0)]:
                tx,ty=self.x+dx,self.y+dy
                if 0<=tx<world.grid_size[0] and 0<=ty<world.grid_size[1] and \
                   world.get_tile(tx,ty)not in["Water","Mountain","Forest","Rocks","SP_Mai","SP_Woo","SP_Sto"] and \
                   not world.get_characters_at_location(tx,ty):moves.append((dx,dy))
            if moves:choice=random.choice(moves);self.move(choice[0],choice[1],world)
            return
        return

    def _execute_craft_order(self, world: 'World'):
        order = world.get_work_order_by_id(self.active_work_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name :
            self._reset_crafting_state(); self.current_goal="Idle"; return # WO no longer valid

        item_name = order.details["item_name"]; item_qty_to_craft_total = order.details["quantity"]
        blueprint = BLUEPRINTS.get(item_name)
        # No need to re-check blueprint, already checked when claiming

        # Phase 1: Ensure all materials for ONE unit are gathered
        if not self.materials_gathered_for_wo:
            all_materials_for_one_unit_present = True
            for res, req_qty_per_unit in blueprint["required_resources"].items():
                if self.inventory.get(res, 0) < req_qty_per_unit:
                    all_materials_for_one_unit_present = False
                    # Update resource_to_fetch with the quantity still needed for THIS unit.
                    self.resource_to_fetch = {"name": res, "quantity": req_qty_per_unit - self.inventory.get(res, 0), "for_wo_id": order.order_id}
                    self.current_goal = "Fetch Resource for WO"; # Keep "Execute Craft Order" as main, this is sub-state
                    # print(f"{self.name} needs {self.resource_to_fetch['quantity']} {res} for one {item_name}. SubGoal: Fetch.")
                    # No recursive call, let Fetch Resource logic run below
                    break # Found a missing resource, break to go to fetching logic
            if all_materials_for_one_unit_present:
                self.materials_gathered_for_wo = True; self.resource_to_fetch = None
                # print(f"{self.name} has materials for one {item_name}.")

        # Phase 1.5: Fetch Resource for WO (if needed)
        if self.resource_to_fetch: # If fetching is needed for the current unit
            # print(f"{self.name} is in Fetch Resource state for {self.resource_to_fetch['name']}")
            res_name = self.resource_to_fetch["name"]
            # Check if we now have enough of this specific resource for ONE unit
            if self.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]:
                 self.resource_to_fetch = None # Done with this specific resource
                 # current_goal remains "Execute Craft Order" to re-evaluate overall material needs for the unit
                 # print(f"{self.name} fetched enough {res_name}. Re-evaluating material needs for {item_name}.")
                 return # Let next tick re-evaluate materials_gathered_for_wo

            target_sp_name = self.resource_to_fetch.get("target_stockpile_name")
            stockpile_to_fetch_from = world.get_stockpile_by_name(target_sp_name) if target_sp_name else None
            if not stockpile_to_fetch_from or stockpile_to_fetch_from.inventory.get(res_name, 0) == 0:
                suitable_stockpiles = [sp for sp in world.get_stockpiles_for_resource(res_name) if sp.inventory.get(res_name, 0) > 0]
                if not suitable_stockpiles: print(f"{self.name} needs {res_name} for WO {order.order_id}, but none in stockpiles. Waiting."); return
                stockpile_to_fetch_from = suitable_stockpiles[0]; self.resource_to_fetch["target_stockpile_name"] = stockpile_to_fetch_from.name

            interaction_spot = (stockpile_to_fetch_from.rect[0], stockpile_to_fetch_from.rect[1])
            if (self.x, self.y) == interaction_spot:
                max_can_carry = self.max_inventory_items - self.get_inventory_load()
                # Amount still needed for this specific resource for one unit of the blueprint
                needed_for_one_blueprint_unit = blueprint["required_resources"][res_name] - self.inventory.get(res_name, 0)

                qty_to_take = min(needed_for_one_blueprint_unit, stockpile_to_fetch_from.inventory.get(res_name,0), max_can_carry )

                if qty_to_take <= 0: # Can't carry more, or SP empty, or already have enough for this specific fetch.
                    self.resource_to_fetch = None # Stop fetching this specific item
                    # current_goal remains "Execute Craft Order", next tick will re-evaluate materials_gathered_for_wo
                    # print(f"{self.name} cannot take more {res_name} now (inv full or SP empty or enough gathered). Re-evaluating.")
                    return

                success, qty_taken = stockpile_to_fetch_from.remove_item(res_name, qty_to_take)
                if success and qty_taken > 0:
                    self.inventory[res_name] = self.inventory.get(res_name, 0) + qty_taken
                    self.add_memory(f"Fetched {qty_taken} {res_name} from {stockpile_to_fetch_from.name} for WO {order.order_id}.")
                    # print(f"{self.name} fetched {qty_taken} {res_name}. Inv: {self.inventory.get(res_name,0)}")
                    if self.inventory.get(res_name, 0) >= blueprint["required_resources"][res_name]:
                        self.resource_to_fetch = None # Done fetching this specific resource
                        # Goal stays Execute Craft Order to check if ALL materials for the unit are now present
            else: self.move_towards(interaction_spot[0], interaction_spot[1], world)
            return # Fetching takes time

        # Phase 2: Craft Item (if materials for one unit are present)
        if self.materials_gathered_for_wo and not self.items_crafted_for_wo:
            if not self.workshop_location: self.workshop_location = (self.x, self.y)
            if (self.x, self.y) != self.workshop_location: self.move_towards(self.workshop_location[0], self.workshop_location[1], world); return

            craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)
            self.crafting_progress += 1
            # print(f"{self.name} crafting {item_name} ({self.crafting_progress}/{craft_time_per_unit} for current unit)")
            if self.crafting_progress >= craft_time_per_unit:
                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    self.inventory[res] = self.inventory.get(res, 0) - req_qty_per_unit
                    if self.inventory[res] <= 0: del self.inventory[res]
                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1
                self.add_memory(f"Crafted 1 {item_name} for WO {order.order_id}. Total: {self.inventory.get(item_name,0)}/{item_qty_to_craft_total}")
                print(f"{self.name} CRAFTED 1 {item_name}. Inv has: {self.inventory.get(item_name,0)}/{item_qty_to_craft_total} for WO {order.order_id}.")
                self.crafting_progress = 0; self.materials_gathered_for_wo = False # Reset for next potential unit
                if self.inventory.get(item_name, 0) >= item_qty_to_craft_total: self.items_crafted_for_wo = True
            return

        # Phase 3: Deposit Crafted Item(s)
        if self.items_crafted_for_wo: # All units for the WO are crafted and in inventory
            if not self.hauling_info:
                if self.inventory.get(item_name, 0) > 0:
                    self.hauling_info = {"resource": item_name, "quantity": self.inventory.get(item_name,0), "for_wo_id": order.order_id, "is_crafted_item": True}
                    # current_goal is already "Execute Craft Order", but Initiate Hauling will be called by main loop
                    # NO, we need to change current_goal to Initiate Hauling for the hauling logic to run
                    self.current_goal = "Initiate Hauling"
                    # Call decide_action() again to let Initiate Hauling logic run immediately
                    # This might be problematic if it causes recursion.
                    # Alternative: let the main loop pick up Initiate Hauling next tick.
                    # For now, let's assume Initiate Hauling will be picked by the _execute_initiate_hauling call
                    # from the main decide_action structure if we simply return here.
                    # This means we need to ensure that if current_goal is InitiateHauling, it runs.
                    # The structure already handles this: Execute Craft Order is top, then other _execute methods.
                    # So, setting current_goal here is enough if we return.
                    return
                else:
                    order.status = "Completed"; self.add_memory(f"WO {order.order_id} ({item_name}) items gone?"); print(f"{self.name} COMPLETED WO {order.order_id} ({item_name})."); self._reset_crafting_state(); self.current_goal = "Idle"; return
            # If hauling_info becomes None and item is gone, it means hauling was completed by _execute_haul_resource
            elif self.hauling_info is None and self.inventory.get(item_name, 0) == 0:
                 order.status = "Completed"; self.add_memory(f"Completed/Stocked WO {order.order_id} ({item_name})."); print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name})."); self._reset_crafting_state(); self.current_goal = "Idle"; return
        return

    def _execute_assess_production_needs(self, world: 'World'):
        if self.job != "Master Craftsman": self.current_goal = None; self.decide_action(world); return
        item_processed_this_tick = False
        if not self.managed_item_targets: self.current_goal = "Idle"; return
        for item_name, target_qty in self.managed_item_targets.items():
            last_ordered_day = self.order_cooldown.get(item_name, -ORDER_SPAM_PREVENTION_DAYS - 1)
            if world.game_time.current_day - last_ordered_day < ORDER_SPAM_PREVENTION_DAYS: continue
            pending_or_approved_count = 0
            for wo in world.work_orders:
                if wo.details.get("item_name") == item_name and wo.status in ["Pending", "Approved", "InProgress"]:
                    pending_or_approved_count += wo.details.get("quantity", 1)
            if pending_or_approved_count < target_qty:
                blueprint = BLUEPRINTS.get(item_name)
                if not blueprint: print(f"Error: MC {self.name} - No blueprint for {item_name}."); continue
                qty_to_order = target_qty - pending_or_approved_count
                blueprint_req_res_per_item = blueprint["required_resources"]
                total_req_res_for_order = {res: qty * qty_to_order for res, qty in blueprint_req_res_per_item.items()}
                order_details = {"item_name": item_name, "quantity": qty_to_order, "required_resources": total_req_res_for_order}
                new_order = WorkOrder(order_type="CraftItem", details=order_details, creation_day=world.game_time.current_day, priority=2)
                world.add_work_order(new_order); self.order_cooldown[item_name] = world.game_time.current_day
                self.add_memory(f"Generated WO for {qty_to_order} {item_name}.")
                print(f"{self.name} (MC) generated WO for {qty_to_order} {item_name}(s).")
                item_processed_this_tick = True; break
        if not item_processed_this_tick: self.current_goal = "Idle"
    def _execute_manage_work_orders(self, world: 'World'):
        if self.job != "Manager": self.current_goal = None; self.decide_action(world); return
        pending_orders = world.get_pending_work_orders()
        if not pending_orders: self.current_goal = "Idle"; return
        order_to_process = pending_orders[0]; can_approve = True; missing_notes = []; stale_concerns = False
        req_res = order_to_process.details.get("required_resources", {})
        if req_res:
            for resource, req_qty in req_res.items():
                avail = world.ledger.get_total_resource_count(resource)
                for sp_name_key in world.ledger.records.get(resource, {}).keys():
                    last_update = world.ledger.get_stockpile_last_update_day(sp_name_key)
                    if last_update is not None and world.game_time.current_day - last_update > STALE_THRESHOLD_DAYS: stale_concerns = True; break
                if stale_concerns: self.add_memory(f"Stale data for WO {order_to_process.order_id}, res {resource}");
                if avail < req_qty: can_approve = False; missing_notes.append(f"{resource} (need {req_qty}, has {avail})")
        if stale_concerns and not can_approve: print(f"{self.name} (Manager) notes stale data for {order_to_process.order_id}, and resources confirmed insufficient.")
        elif stale_concerns: print(f"{self.name} (Manager) notes stale data for {order_to_process.order_id}, proceeding with caution.")
        if can_approve: order_to_process.status = "Approved"; order_to_process.approved_by = self.name; order_to_process.approval_day = world.game_time.current_day; self.add_memory(f"Approved WO {order_to_process.order_id}"); print(f"{self.name} (Manager) APPROVED {order_to_process.order_id[:8]}.")
        else: order_to_process.status = "Denied"; order_to_process.denied_by = self.name; order_to_process.denial_reason = f"Insuff: {', '.join(missing_notes) or 'stale data'}"; self.add_memory(f"Denied WO {order_to_process.order_id}"); print(f"{self.name} (Manager) DENIED {order_to_process.order_id[:8]}. Reason: {order_to_process.denial_reason}")
    def _execute_maintain_ledger(self, world: 'World'):
        if self.job != "Bookkeeper": self.current_goal = None; self.decide_action(world); return
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
        if self.job!="Woodcutter":self.current_goal=None;self.decide_action(world);return
        quota=self.needs.get("Wood",5);inv_val=self.inventory.get("Wood",0)
        if self.get_inventory_load()>=self.max_inventory_items and inv_val>0:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        elif inv_val<quota:self.current_goal="Gather Wood"
        else:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"}
        self.decide_action(world)
    def _execute_perform_stonemason_duties(self, world: 'World'):
        if self.job != "Stonemason": self.current_goal = None; self.decide_action(world); return
        quota = self.needs.get("Stone", 5); inv_val = self.inventory.get("Stone", 0)
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        elif inv_val < quota: self.current_goal = "Gather Stone"
        else: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
        self.decide_action(world)
    def _execute_initiate_hauling(self, world: 'World'):
        res=self.hauling_info.get("resource")if self.hauling_info else None
        if not res or self.inventory.get(res,0)==0:self.current_goal=None;self.hauling_info=None;self.decide_action(world);return
        qty=self.inventory.get(res,0);sps=[s_obj for s_obj in world.get_stockpiles_for_resource(res)if s_obj.has_space_for(res,1)]
        if not sps:self.current_goal="Wander"; return
        sp_chosen=sps[0];self.hauling_info["target_stockpile_name"]=sp_chosen.name;self.hauling_info["quantity_to_haul"]=qty
        self.current_goal="Haul Resource to Stockpile";self.decide_action(world)
    def _execute_haul_resource(self, world: 'World'):
        sp_name=self.hauling_info.get("target_stockpile_name");res=self.hauling_info.get("resource")
        if not res or self.inventory.get(res,0)==0:self.current_goal=None;self.hauling_info=None;self.decide_action(world);return
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
                    order.status = "Completed"
                    print(f"{self.name} COMPLETED and STOCKED Work Order {order.order_id} ({res}).")
                    self.add_memory(f"Completed and Stocked WO {order.order_id} ({res}).")
                self._reset_crafting_state(); self.current_goal=None
            else: self.current_goal=None;self.hauling_info=None
        else:self.move_towards(spot[0],spot[1],world)
    def _execute_gather_wood(self, world: 'World'):
        if self.get_inventory_load()>=self.max_inventory_items:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Wood"};self.decide_action(world);return
        needed=self.needs.get("Wood",1);job_need=self.needs.get("Wood",5)
        if self.job=="Woodcutter": needed = job_need
        if self.inventory.get("Wood",0)>=needed:
            if self.job=="Woodcutter":self.current_goal="Perform Woodcutter Duties"
            else:self.current_goal="Wander"
            self.decide_action(world);return
        loc=self.find_nearest_resource("Wood",world)
        if loc:
            if(self.x,self.y)==loc:self.gather_resource("Wood",world)
            else:self.move_towards(loc[0],loc[1],world)
        else:self.current_goal="Wander"
    def _execute_gather_stone(self, world: 'World'):
        if self.get_inventory_load()>=self.max_inventory_items:self.current_goal="Initiate Hauling";self.hauling_info={"resource":"Stone"};self.decide_action(world);return
        needed=self.needs.get("Stone",1);job_need=self.needs.get("Stone",5)
        if self.job=="Stonemason": needed = job_need
        if self.inventory.get("Stone",0)>=needed:
            if self.job=="Stonemason":self.current_goal="Perform Stonemason Duties"
            else:self.current_goal="Wander"
            self.decide_action(world);return
        loc=self.find_nearest_resource("Stone",world)
        if loc:
            if(self.x,self.y)==loc:self.gather_resource("Stone",world)
            else:self.move_towards(loc[0],loc[1],world)
        else:self.current_goal="Wander"
    def _execute_oversee_expedition(self, world: 'World'):
         if self.job != "Expedition Leader": self.current_goal = None; self.decide_action(world); return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = "Idle"
    # --- END OF HELPER _execute_ METHODS ---
