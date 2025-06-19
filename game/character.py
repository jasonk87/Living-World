# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder

if TYPE_CHECKING:
    from .world import World
    from .character import Character as OtherCharacter

STALE_THRESHOLD_DAYS = 2 # Data is stale if not updated in this many days

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: dict[str, int], x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10):
        self.name = name
        self.personality = personality
        self.traits = traits
        self.skills = skills
        self.x = x
        self.y = y
        self.inventory: Dict[str, int] = {}
        self.memory: List[str] = []
        self.needs: Dict[str, int] = needs if needs is not None else {}
        self.current_goal: Optional[str] = current_goal
        self.relationships: Dict[str, str] = {}
        self.job: Optional[str] = job
        self.max_inventory_items: int = max_inventory_items

        self.hauling_info: Optional[Dict] = None
        self.counting_target_stockpile_name: Optional[str] = None

        self.supervisor_name: Optional[str] = None
        self.subordinates_names: List[str] = []

    def set_supervisor(self, supervisor_name: Optional[str]): self.supervisor_name = supervisor_name
    def add_subordinate(self, subordinate_name: str):
        if subordinate_name not in self.subordinates_names: self.subordinates_names.append(subordinate_name)
    def remove_subordinate(self, subordinate_name: str):
        if subordinate_name in self.subordinates_names: self.subordinates_names.remove(subordinate_name)

    def __str__(self):
        base_info = (f"Character(Name: {self.name}, Job: {self.job}, Pos: ({self.x},{self.y}), "
                     f"Goal: {self.current_goal}, InvLoad: {self.get_inventory_load()}/{self.max_inventory_items})")
        supervisor_info = f"  Supervisor: {self.supervisor_name if self.supervisor_name else 'None'}"
        subordinates_info = f"  Subordinates: {len(self.subordinates_names)} ({', '.join(self.subordinates_names) if self.subordinates_names else 'None'})"
        return f"{base_info}\n{supervisor_info}\n{subordinates_info}"

    def get_inventory_load(self) -> int: return sum(self.inventory.values())

    def add_memory(self, event: str):
        self.memory.append(event)
        if len(self.memory) > 20: self.memory.pop(0)

    def interact(self, other_character: 'OtherCharacter', world: 'World'):
        if other_character.name == self.name: return
        context_key = "seeing again"
        if other_character.name not in self.relationships:
            self.relationships[other_character.name] = "Met"; other_character.relationships[self.name] = "Met"
            self.add_memory(f"Met {other_character.name} at ({self.x},{self.y})."); other_character.add_memory(f"Met {self.name} at ({other_character.x},{other_character.y}).")
            context_key = "first meeting"
        if context_key == "first meeting": print(f"{self.name} and {other_character.name} met for the first time.")
        pass

    def move(self, dx: int, dy: int, world: 'World'):
        new_x, new_y = self.x + dx, self.y + dy
        if 0 <= new_x < world.grid_size[0] and 0 <= new_y < world.grid_size[1]:
            occupying_chars = [c for c in world.get_characters_at_location(new_x, new_y) if c.name != self.name]
            if occupying_chars: return
            self.x = new_x; self.y = new_y
        pass

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx = target_x - self.x; dy = target_y - self.y
        if dx > 0: dx = 1
        elif dx < 0: dx = -1
        if dy > 0: dy = 1
        elif dy < 0: dy = -1
        if dx != 0 or dy != 0: self.move(dx, dy, world)
        pass

    def find_nearest_resource(self, resource_name: str, world: 'World') -> Optional[Tuple[int, int]]:
        locations = world.get_resources(resource_name)
        if not locations: return None
        if (self.x, self.y) in locations:
             tile_type = world.get_tile(self.x, self.y)
             if (resource_name == "Wood" and tile_type == "Forest") or \
                (resource_name == "Stone" and tile_type == "Rocks") or \
                tile_type == resource_name: return (self.x, self.y)
        for loc in locations:
            tile_type = world.get_tile(loc[0], loc[1])
            if (resource_name == "Wood" and tile_type == "Forest") or \
               (resource_name == "Stone" and tile_type == "Rocks") or \
               tile_type == resource_name: return loc
        return None

    def gather_resource(self, resource_name: str, world: 'World'):
        current_pos=(self.x,self.y); current_tile_type=world.get_tile(self.x,self.y)
        tile_is_source=(resource_name=="Wood" and current_tile_type=="Forest") or \
                       (resource_name=="Stone" and current_tile_type=="Rocks") or \
                       current_tile_type==resource_name
        if tile_is_source and resource_name in world.resources and current_pos in world.resources.get(resource_name,[]):
            self.inventory[resource_name]=self.inventory.get(resource_name,0)+1
            world.resources[resource_name].remove(current_pos)
            self.add_memory(f"Gathered {resource_name} at {current_pos}")
            resource_list_for_loc = [loc for loc in world.resources.get(resource_name, []) if loc == current_pos]
            if not resource_list_for_loc:
                if (resource_name=="Wood" and current_tile_type=="Forest") or \
                   (resource_name=="Stone" and current_tile_type=="Rocks"):
                    world.set_tile(self.x,self.y,"Grass")
                    print(f"{self.name} depleted {resource_name} at {current_pos}, tile changed to Grass.")
        pass

    def build(self, structure_type: str, world: 'World') -> bool:
        tile_type = world.get_tile(self.x, self.y)
        if tile_type != "Grass": return False
        if any(c.name != self.name for c in world.get_characters_at_location(self.x,self.y)): return False
        required = {"Shelter": {"Wood": 5}}.get(structure_type)
        if not required: return False
        if all(self.inventory.get(k,0) >= v for k,v in required.items()):
            for k,v in required.items(): self.inventory[k] -= v
            world.set_tile(self.x,self.y, structure_type)
            self.add_memory(f"Built {structure_type}"); return True
        return False

    def decide_action(self, world: 'World'):
        if not world.game_time: self.current_goal = "Idle"; return

        other_chars_here = [c for c in world.get_characters_at_location(self.x, self.y) if c.name != self.name]
        if other_chars_here and self.current_goal in ["Wander", "Idle", None]:
            self.interact(other_chars_here[0], world); return

        # --- Job-specific goal setting (ensure this is first) ---
        if self.job == "Expedition Leader":
             if self.current_goal not in ["Oversee Expedition"] or self.current_goal in ["Wander", None, "Idle"]:
                self.current_goal = "Oversee Expedition"
        elif self.job == "Manager":
            if self.current_goal not in ["Manage Work Orders"] or self.current_goal in ["Wander", None, "Idle"]:
                self.current_goal = "Manage Work Orders"
        elif self.job == "Bookkeeper":
            if self.current_goal not in ["Maintain Ledger", "Count Stockpile"] or self.current_goal in ["Wander", None, "Idle"]:
                self.current_goal = "Maintain Ledger"
        elif self.job == "Woodcutter":
            if self.current_goal not in ["Perform Woodcutter Duties", "Gather Wood", "Initiate Hauling", "Haul Resource to Stockpile"] or \
               self.current_goal in ["Wander", None, "Idle"]:
                self.current_goal = "Perform Woodcutter Duties"
        elif self.job == "Stonemason":
             if self.current_goal not in ["Perform Stonemason Duties", "Gather Stone", "Initiate Hauling", "Haul Resource to Stockpile"] or \
                self.current_goal in ["Wander", None, "Idle"]:
                self.current_goal = "Perform Stonemason Duties"

        # --- Execute Current Goal ---
        if self.current_goal == "Oversee Expedition":
            if self.job != "Expedition Leader": self.current_goal = None; self.decide_action(world); return # Should not happen if job check is correct
            if random.random() < 0.1: self.add_memory("Surveyed expedition progress.") # print(f"{self.name} (Expedition Leader) is overseeing.")
            self.current_goal = "Idle"
            return

        elif self.current_goal == "Manage Work Orders":
            if self.job != "Manager": self.current_goal = None; self.decide_action(world); return
            pending_orders = world.get_pending_work_orders()
            if not pending_orders: self.current_goal = "Idle"; return
            order_to_process = pending_orders[0]
            can_approve = True; missing_resources_notes = []; data_freshness_concerns = False
            required_resources = order_to_process.details.get("required_resources", {})
            if required_resources:
                for resource, req_qty in required_resources.items():
                    available_qty = world.ledger.get_total_resource_count(resource)
                    stockpiles_holding_resource = world.ledger.records.get(resource, {})
                    if not stockpiles_holding_resource and req_qty > 0: pass
                    else:
                        for sp_name in stockpiles_holding_resource.keys():
                            last_update_day = world.ledger.get_stockpile_last_update_day(sp_name)
                            if last_update_day is not None:
                                if world.game_time.current_day - last_update_day > STALE_THRESHOLD_DAYS:
                                    data_freshness_concerns = True
                                    stale_note = f"Ledger data for {sp_name} (has {resource}) is stale (Updated Day {last_update_day}, Current Day {world.game_time.current_day})."
                                    if stale_note not in self.memory: self.add_memory(stale_note); print(f"{self.name} (Manager) thinks: {stale_note}")
                    if available_qty < req_qty:
                        can_approve = False
                        missing_resources_notes.append(f"{resource} (need {req_qty}, ledger shows {available_qty})")
            if data_freshness_concerns: print(f"{self.name} (Manager) is concerned about data freshness for order {order_to_process.order_id}.")
            if can_approve:
                order_to_process.status = "Approved"; order_to_process.approved_by = self.name; order_to_process.approval_day = world.game_time.current_day
                self.add_memory(f"Approved WO {order_to_process.order_id}"); print(f"{self.name} (Manager) APPROVED order {order_to_process.order_id} for '{order_to_process.details.get('item_name') or order_to_process.details.get('structure_type')}'.")
            else:
                order_to_process.status = "Denied"; order_to_process.denied_by = self.name; order_to_process.denial_reason = f"Insufficient resources: {', '.join(missing_resources_notes)}"
                self.add_memory(f"Denied WO {order_to_process.order_id}. Reason: {order_to_process.denial_reason}"); print(f"{self.name} (Manager) DENIED order {order_to_process.order_id}. Reason: {order_to_process.denial_reason if missing_resources_notes else 'data freshness concerns or other reasons'}")
            return

        elif self.current_goal == "Maintain Ledger":
            if self.job != "Bookkeeper": self.current_goal = None; self.decide_action(world); return
            stockpiles_to_check = world.stockpiles
            if not stockpiles_to_check: self.current_goal = "Idle"; return
            target_sp = None; min_last_counted_day = float('inf')
            for sp_obj in stockpiles_to_check:
                last_day = world.ledger.get_stockpile_last_update_day(sp_obj.name)
                if last_day is None: target_sp = sp_obj; break
                if last_day < world.game_time.current_day:
                    if last_day < min_last_counted_day: min_last_counted_day = last_day; target_sp = sp_obj
            if target_sp is None: self.current_goal = "Idle"; return # All counted today
            self.counting_target_stockpile_name = target_sp.name; self.current_goal = "Count Stockpile"; self.decide_action(world); return

        elif self.current_goal == "Count Stockpile":
            if self.job != "Bookkeeper" or not self.counting_target_stockpile_name: self.current_goal = "Maintain Ledger"; self.counting_target_stockpile_name = None; self.decide_action(world); return
            stockpile_obj = world.get_stockpile_by_name(self.counting_target_stockpile_name)
            if not stockpile_obj: self.current_goal = "Maintain Ledger"; self.counting_target_stockpile_name = None; self.decide_action(world); return
            interaction_spot = stockpile_obj.deposit_tiles[0] if stockpile_obj.deposit_tiles else (stockpile_obj.rect[0], stockpile_obj.rect[1])
            if (self.x, self.y) == interaction_spot:
                actual_inventory = stockpile_obj.inventory.copy()
                world.ledger.update_stockpile_record(stockpile_obj.name, actual_inventory, world.game_time.current_day)
                self.add_memory(f"Counted {stockpile_obj.name} (Inv: {actual_inventory}) on day {world.game_time.current_day}.")
                print(f"{self.name} (Bookkeeper) counted {stockpile_obj.name}. Inv: {actual_inventory}. Day: {world.game_time.current_day}.")
                self.counting_target_stockpile_name = None; self.current_goal = "Maintain Ledger"; self.decide_action(world); return
            else: self.move_towards(interaction_spot[0], interaction_spot[1], world); return

        elif self.current_goal == "Perform Woodcutter Duties":
            if self.job != "Woodcutter": self.current_goal = None; self.decide_action(world); return
            wood_quota = self.needs.get("Wood", 5); current_wood_in_inv = self.inventory.get("Wood", 0)
            if self.get_inventory_load() >= self.max_inventory_items and current_wood_in_inv > 0 : self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Wood"}
            elif current_wood_in_inv < wood_quota: self.current_goal = "Gather Wood"
            else: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Wood"}
            self.decide_action(world); return

        elif self.current_goal == "Perform Stonemason Duties":
            if self.job != "Stonemason": self.current_goal = None; self.decide_action(world); return
            stone_quota = self.needs.get("Stone", 5); current_stone_in_inv = self.inventory.get("Stone", 0)
            if self.get_inventory_load() >= self.max_inventory_items and current_stone_in_inv > 0: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
            elif current_stone_in_inv < stone_quota: self.current_goal = "Gather Stone"
            else: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}
            self.decide_action(world); return

        elif self.current_goal == "Initiate Hauling":
            resource_to_haul = self.hauling_info.get("resource") if self.hauling_info else None
            if not resource_to_haul or self.inventory.get(resource_to_haul, 0) == 0: self.current_goal = None; self.hauling_info = None; self.decide_action(world); return
            qty_in_inventory = self.inventory.get(resource_to_haul,0)
            suitable_stockpiles = [sp_obj for sp_obj in world.get_stockpiles_for_resource(resource_to_haul) if sp_obj.has_space_for(resource_to_haul, 1)]
            if not suitable_stockpiles: self.current_goal = "Wander"; return
            chosen_stockpile = suitable_stockpiles[0]
            self.hauling_info["target_stockpile_name"] = chosen_stockpile.name; self.hauling_info["quantity_to_haul"] = qty_in_inventory
            self.current_goal = "Haul Resource to Stockpile"; self.decide_action(world); return

        elif self.current_goal == "Haul Resource to Stockpile" and self.hauling_info:
            target_sp_name = self.hauling_info.get("target_stockpile_name"); resource_to_haul = self.hauling_info.get("resource")
            if not resource_to_haul or self.inventory.get(resource_to_haul, 0) == 0: self.current_goal = None; self.hauling_info = None; self.decide_action(world); return
            stockpile_obj = world.get_stockpile_by_name(target_sp_name)
            if not stockpile_obj: self.current_goal = "Wander"; self.hauling_info = None; return
            interaction_spot = stockpile_obj.deposit_tiles[0] if stockpile_obj.deposit_tiles else None
            if not interaction_spot : self.current_goal = "Wander"; self.hauling_info = None; return
            if (self.x, self.y) == interaction_spot:
                qty_to_deposit = self.inventory.get(resource_to_haul, 0)
                success, qty_added = stockpile_obj.add_item(resource_to_haul, qty_to_deposit)
                if success and qty_added > 0:
                    self.inventory[resource_to_haul] -= qty_added
                    if self.inventory[resource_to_haul] <= 0: del self.inventory[resource_to_haul]
                    self.add_memory(f"Hauled {qty_added} {resource_to_haul} to {stockpile_obj.name}.")
                    print(f"{self.name} deposited {qty_added} {resource_to_haul} at {stockpile_obj.name}. Inv: {self.inventory}")
                self.current_goal = None; self.hauling_info = None
            else: self.move_towards(interaction_spot[0], interaction_spot[1], world)
            return

        elif self.current_goal == "Gather Wood":
            if self.get_inventory_load() >= self.max_inventory_items: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Wood"}; self.decide_action(world); return
            needed_wood_total = self.needs.get("Wood", 1)
            if self.job == "Woodcutter": needed_wood_total = self.needs.get("Wood",5)
            if self.inventory.get("Wood", 0) >= needed_wood_total:
                if self.job == "Woodcutter": self.current_goal = "Perform Woodcutter Duties"
                else: self.current_goal = "Wander"
                self.decide_action(world); return
            wood_loc = self.find_nearest_resource("Wood", world)
            if wood_loc:
                if (self.x, self.y) == wood_loc: self.gather_resource("Wood", world)
                else: self.move_towards(wood_loc[0], wood_loc[1], world)
            else: self.current_goal = "Wander"
            return

        elif self.current_goal == "Gather Stone":
            if self.get_inventory_load() >= self.max_inventory_items: self.current_goal = "Initiate Hauling"; self.hauling_info = {"resource": "Stone"}; self.decide_action(world); return
            needed_stone_total = self.needs.get("Stone", 1)
            if self.job == "Stonemason": needed_stone_total = self.needs.get("Stone", 5)
            if self.inventory.get("Stone",0) >= needed_stone_total:
                if self.job == "Stonemason": self.current_goal = "Perform Stonemason Duties"
                else: self.current_goal = "Wander"
                self.decide_action(world); return
            stone_loc = self.find_nearest_resource("Stone", world)
            if stone_loc:
                if(self.x, self.y) == stone_loc: self.gather_resource("Stone", world)
                else: self.move_towards(stone_loc[0], stone_loc[1], world)
            else: self.current_goal = "Wander"
            return

        elif self.current_goal == "Wander":
            possible_moves = []
            for dx_try, dy_try in [(0,1), (0,-1), (1,0), (-1,0)]:
                target_x, target_y = self.x + dx_try, self.y + dy_try
                if 0 <= target_x < world.grid_size[0] and 0 <= target_y < world.grid_size[1] and \
                   world.get_tile(target_x, target_y) not in ["Water", "Mountain", "Forest", "Rocks", "SP_Mai", "SP_Woo", "SP_Sto"] and \
                   not world.get_characters_at_location(target_x, target_y):
                    possible_moves.append((dx_try, dy_try))
            if possible_moves: move_choice = random.choice(possible_moves); self.move(move_choice[0], move_choice[1], world)
            return

        else: # Idle or unknown goal
            # If has a job, default to job's primary task. Otherwise, consider wandering.
            if self.job == "Expedition Leader": self.current_goal = "Oversee Expedition"
            elif self.job == "Manager": self.current_goal = "Manage Work Orders"
            elif self.job == "Bookkeeper": self.current_goal = "Maintain Ledger"
            elif self.job == "Woodcutter": self.current_goal = "Perform Woodcutter Duties"
            elif self.job == "Stonemason": self.current_goal = "Perform Stonemason Duties"
            elif self.current_goal is None or self.current_goal == "Idle": # No job, truly idle
                if random.random() < 0.05: self.current_goal = "Wander"
            else: # Unknown goal, no job to fall back on
                 self.current_goal = "Wander"
            # No recursive call here, let next tick pick up the new default/idle goal
            return
        pass # Should be unreachable.
