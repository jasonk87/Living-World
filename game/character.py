# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
import random
from .llm_integration import generate_dialogue
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS # Added STRUCTURE_BLUEPRINTS
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
        self.name = name; self.personality = personality; self.traits = traits;
        self.skills: Dict[str, Dict[str, Any]] = {} # Initialize as empty dict
        if skills: # Original skills is Dict[str, int] (level)
            for skill_name, level_val in skills.items():
                self.skills[skill_name] = {
                    "level": level_val,
                    "experience": 0.0,
                    "exp_to_next_level": self._calculate_exp_for_level(level_val)
                }

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

        # Health States
        self.is_sick: bool = False
        self.sickness_severity: int = 0 # 0: healthy, 1-3: mild, 4-6: moderate, 7-9: severe, 10: critical/dying
        self.is_injured: bool = False
        self.injury_severity: int = 0 # Similar scale to sickness
        self.appointed_by: Optional[str] = None # Tracks who appointed this character to their current key role

        # Social Attributes
        self.known_characters: List[str] = [] # List of names of characters met
        # self.relationships is already Dict[str, int] from before, suitable for relationship scores
        self.opinions: Dict[str, Dict[str, int]] = {} # e.g. {"Liam": {"greeting_style": 1, "small_talk_quality": -1}}
        self.dialogue_history: List[Dict[str, Any]] = [] # List of dialogue interaction dicts
        self.current_goal_details: Optional[Dict[str, Any]] = None # For goals needing specific targets, like greeting

        # Attributes for build orders (re-adding them here as they were missed)
        self.active_build_order_id: Optional[str] = None
        self.materials_gathered_for_build: bool = False
        self.building_site_target: Optional[Tuple[int, int]] = None
        self.current_building_project: Optional[str] = None
        # self.resource_to_fetch is already part of the minimal __init__

    def _calculate_exp_for_level(self, level: int) -> float:
        if level < 0: level = 0
        return float(int(config.BASE_EXP_TO_NEXT_LEVEL * ((level + 1) ** config.EXP_LEVEL_SCALING_FACTOR)))

    def _grant_skill_experience(self, skill_name: str, amount: float, world: 'World'):
        if skill_name not in self.skills:
            self.skills[skill_name] = {
                "level": 0,
                "experience": 0.0,
                "exp_to_next_level": self._calculate_exp_for_level(0)
            }

        # Add experience (consider learning rate modifiers later if re-adding status effects)
        self.skills[skill_name]["experience"] += amount
        self._check_skill_level_up(skill_name, world)

    def _check_skill_level_up(self, skill_name: str, world: 'World'):
        if skill_name not in self.skills:
            return

        skill_data = self.skills[skill_name]
        while skill_data["experience"] >= skill_data["exp_to_next_level"]:
            skill_data["level"] += 1
            skill_data["experience"] -= skill_data["exp_to_next_level"]
            skill_data["exp_to_next_level"] = self._calculate_exp_for_level(skill_data["level"])
            self.add_memory(f"{self.name}'s {skill_name} skill increased to level {skill_data['level']}!")
            # world.add_event_log_message(f"{self.name}'s {skill_name} skill increased to level {skill_data['level']}!") # If world events are re-added

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
            self.current_goal = self.job_default_goal() or "Idle"
            return

        order = world.get_work_order_by_id(self.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name:
            self._reset_building_state()
            self.current_goal = self.job_default_goal() or "Idle"
            return

        # Ensure needs are imported if used here, for now, assume energy is checked in decide_action
        # from .data import STRUCTURE_BLUEPRINTS # Moved to top-level import if not already there
        # For Phased Construction, STRUCTURE_BLUEPRINTS must be accessible. Assuming it is via top-level.
        # from .building import Building # For instantiation, assuming top-level.

        structure_blueprint_key = order.details["structure_type"]
        structure_bp_data = STRUCTURE_BLUEPRINTS.get(structure_blueprint_key) # Access directly after import
        if not structure_bp_data:
            order.status = "Denied"; order.denial_reason = f"Unknown blueprint {structure_blueprint_key}"
            self._reset_building_state(); self.current_goal = "Idle"; return

        # --- Material Gathering Phase ---
        if not self.materials_gathered_for_build:
            # Stage 1: If actively fetching a specific resource type AND inventory has space
            if self.resource_to_fetch and self.get_inventory_load() < self.max_inventory_items:
                self._execute_fetch_resource_for_build(world)
                # If _execute_fetch_resource_for_build still needs more ticks (e.g. moving, or stockpile empty)
                # and resource_to_fetch is still set, then return to continue.
                if self.resource_to_fetch:
                    return
            # If inventory is full, OR if resource_to_fetch was None to begin with,
            # OR if _execute_fetch_resource_for_build completed for the type (resource_to_fetch is now None),
            # then proceed to Stage 2.

            # Stage 2: Identify next resource type needed for the *entire project*.
            current_project_mats_fully_in_inventory = True
            next_resource_to_target_for_project = None
            for res_name, total_quantity_needed_for_project in structure_bp_data["required_resources"].items():
                if self.inventory.get(res_name, 0) < total_quantity_needed_for_project:
                    current_project_mats_fully_in_inventory = False
                    next_resource_to_target_for_project = res_name
                    break

            if current_project_mats_fully_in_inventory:
                self.materials_gathered_for_build = True
                self.resource_to_fetch = None # Should be already None if Stage 1 completed for last resource
                self.add_memory(f"All materials for {self.current_building_project} now in inventory.")
            elif next_resource_to_target_for_project:
                # We need more of 'next_resource_to_target_for_project'
                if self.get_inventory_load() >= self.max_inventory_items:
                    # Inventory is full, cannot pick up more. Decision: go to site.
                    if (self.x, self.y) != self.building_site_target:
                        self.add_memory(f"Inventory full. Have some materials for {self.current_building_project}, heading to site.")
                        self.move_towards(self.building_site_target[0], self.building_site_target[1], world)
                        return
                    else:
                        # At site, inventory full, but still missing some *other* types of materials for project.
                        # This is a tricky state. Builder might be stuck if they can't use what they have.
                        # For now, they will just wait at the site.

                        # At site, inventory full, but still missing materials for the project.
                        # The 'next_resource_to_target_for_project' variable must be valid here because
                        # 'current_project_mats_fully_in_inventory' was false.
                        self.add_memory(f"At site ({self.x},{self.y}) with full inventory. Still need {next_resource_to_target_for_project} for {self.current_building_project}. Heading to gather more.")

                        # Set up to fetch the next needed resource type.
                        needed_qty_of_this_type = structure_bp_data["required_resources"][next_resource_to_target_for_project] - self.inventory.get(next_resource_to_target_for_project, 0)
                        self.resource_to_fetch = {
                            "name": next_resource_to_target_for_project,
                            "quantity": needed_qty_of_this_type,
                            "target_stockpile_name": None # _execute_fetch_resource_for_build will find a stockpile
                        }
                        # Immediately attempt to fetch. Since character is at build site (not stockpile), this will trigger movement.
                        self._execute_fetch_resource_for_build(world)
                        return # End tick, fetching/moving is in progress.
                else:
                    # Inventory has space, so initiate fetching for the identified 'next_resource_to_target_for_project'.
                    needed_qty_of_this_type = structure_bp_data["required_resources"][next_resource_to_target_for_project] - self.inventory.get(next_resource_to_target_for_project, 0)
                    self.resource_to_fetch = {
                        "name": next_resource_to_target_for_project,
                        "quantity": needed_qty_of_this_type,
                        "target_stockpile_name": None # Fetch method will find a stockpile
                    }
                    self.add_memory(f"Targeting {needed_qty_of_this_type} {next_resource_to_target_for_project} for {self.current_building_project}.")
                    self._execute_fetch_resource_for_build(world) # This will try to fetch
                    return # End tick, fetching is in progress.
            # If no next_resource_to_target (should mean all gathered) but materials_gathered_for_build is still false,
            # it's an inconsistent state, let it re-evaluate next tick.
            # However, with the fix above, this path should be less likely for the described bug.
            return


        # --- Site Movement & Construction Phase (Reached if self.materials_gathered_for_build is True) ---
        if self.materials_gathered_for_build:
            if (self.x, self.y) != self.building_site_target:
                self.move_towards(self.building_site_target[0], self.building_site_target[1], world)
                return

            target_building = world.get_building_at(self.building_site_target[0], self.building_site_target[1])

            if not target_building: # First time at site with all materials to *start* construction
                # Consume ALL required resources from inventory - this assumes one-time deposit.
                committed_resources_display = {}
                for res_name, res_needed_total in structure_bp_data["required_resources"].items():
                    if self.inventory.get(res_name, 0) < res_needed_total:
                        self.add_memory(f"CRITICAL ERROR: materials_gathered_for_build is true, but missing {res_name} for {structure_blueprint_key}. Resetting gather flag.")
                        self.materials_gathered_for_build = False
                        self.resource_to_fetch = None # Force re-evaluation of what's needed
                        return

                    self.inventory[res_name] -= res_needed_total
                    if self.inventory[res_name] <= 0: del self.inventory[res_name]
                    committed_resources_display[res_name] = res_needed_total

                self.add_memory(f"Committed all materials {committed_resources_display} to start {self.current_building_project}.")

                from .building import Building # Local import
                target_building = Building(
                    structure_type=structure_blueprint_key, display_name=structure_bp_data["display_name"],
                    location=self.building_site_target, size=structure_bp_data["size"],
                    required_resources_for_blueprint=structure_bp_data["required_resources"].copy(), # For building's internal use
                    functionality=structure_bp_data.get("functionality"), required_skill=structure_bp_data.get("required_skill"),
                    construction_phases=structure_bp_data.get("construction_phases"),
                    map_char_initial=structure_bp_data.get("map_char_initial", "?"),
                    map_char_complete=structure_bp_data.get("map_char_complete", "B")
                )
                world.add_building(target_building)
                self.add_memory(f"Laid foundation for {target_building.display_name} at {self.building_site_target}.")

            # Work on the building
            if target_building and not target_building.is_operational:
                progress_this_tick = 1.0
                construction_skill_level = self.skills.get("Construction", {}).get("level", 0)
                progress_this_tick *= (1 + construction_skill_level * 0.1)

                prev_phase_idx = target_building.current_phase_index
                actual_progress = target_building.work_on(progress_this_tick)

                if actual_progress > 0:
                    self._grant_skill_experience("Construction", actual_progress * 0.5, world)

                self.add_memory(f"Worked on {target_building.display_name} (Phase: {target_building.get_current_phase_name()}, +{actual_progress:.1f} prog).")

                if target_building.current_phase_index != prev_phase_idx:
                    self.add_memory(f"{target_building.display_name} advanced to phase: {target_building.get_current_phase_name()}.")

                if target_building.is_operational:
                    order.status = "Completed"
                    self.add_memory(f"Completed Build WO {order.order_id} for {target_building.display_name}.")
                    self._reset_building_state()
                    self.current_goal = self.job_default_goal() or "Idle"
                    return
            elif target_building and target_building.is_operational: # Already completed
                order.status = "Completed"
                self._reset_building_state()
                self.current_goal = self.job_default_goal() or "Idle"
                return

        # Attributes for build orders
        self.active_build_order_id: Optional[str] = None
        self.materials_gathered_for_build: bool = False
        self.building_site_target: Optional[Tuple[int, int]] = None
        self.current_building_project: Optional[str] = None
        # self.resource_to_fetch is already defined

    def _reset_building_state(self):
        self.active_build_order_id = None
        self.materials_gathered_for_build = False
        self.building_site_target = None
        self.current_building_project = None
        self.resource_to_fetch = None # Ensure this is cleared too

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
        # print(f"DEBUG {self.name}: Attempting move from ({self.x},{self.y}) by ({dx},{dy}) to ({new_x},{new_y})")
        if not (0 <= new_x < world.grid_size[0] and 0 <= new_y < world.grid_size[1]):
            # print(f"DEBUG {self.name}: Move failed - out of bounds.")
            can_move = False
        if can_move:
            tile_type_at_new_loc = world.get_tile(new_x, new_y) # world.get_tile should give base tile like Grass, or building char
            # Check against non-traversable terrain types
            if tile_type_at_new_loc in ["Mountain", "Water"]: # Assuming these are map chars for non-traversable
                # print(f"DEBUG {self.name}: Move failed - tile type '{tile_type_at_new_loc}' is non-traversable.")
                can_move = False
            # Check for existing buildings or furniture at the destination that are not part of this character's current build order site
            # This needs more sophisticated check if buildings/furniture can be on "Grass"
            # For now, assume if get_tile returns something other than 'Grass' (or whatever is traversable), it might be an issue.
            # A better check would be:
            if world.get_building_at(new_x, new_y) is not None: # or world.get_furniture_at(new_x, new_y) is not None: # Temporarily commented for minimal test
                 # Allow moving to own build site even if building object exists there (e.g. foundation)
                if not (self.building_site_target and new_x == self.building_site_target[0] and new_y == self.building_site_target[1]):
                    # print(f"DEBUG {self.name}: Move failed - location ({new_x},{new_y}) occupied by building/furniture.")
                    can_move = False


            if can_move: # Re-check after tile type and building/furniture checks
                other_chars_at_new_loc = [char for char in world.get_characters_at_location(new_x, new_y) if char.name != self.name]
                if other_chars_at_new_loc:
                    # print(f"DEBUG {self.name}: Move failed - location ({new_x},{new_y}) occupied by another character.")
                    can_move = False

        if can_move:
            # print(f"DEBUG {self.name}: Move successful to ({new_x},{new_y}). Old pos: ({self.x},{self.y})")
            self.x = new_x; self.y = new_y;
            return True

        # print(f"DEBUG {self.name}: Move from ({self.x},{self.y}) to ({new_x},{new_y}) ultimately FAILED.")
        return False

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx = target_x - self.x; dy = target_y - self.y
        norm_dx, norm_dy = 0, 0
        if dx > 0: norm_dx = 1
        elif dx < 0: norm_dx = -1
        if dy > 0: norm_dy = 1
        elif dy < 0: norm_dy = -1
        if norm_dx == 0 and norm_dy == 0:
            # print(f"DEBUG {self.name}: move_towards target ({target_x},{target_y}) reached.")
            return

        # print(f"DEBUG {self.name}: move_towards ({target_x},{target_y}). Current: ({self.x},{self.y}). Trying ({norm_dx},{norm_dy}) first.")
        if self.move(norm_dx, norm_dy, world):
            # print(f"DEBUG {self.name}: move_towards success via diagonal/direct ({norm_dx},{norm_dy}). New pos: ({self.x},{self.y})")
            return

        if norm_dx != 0 and norm_dy != 0: # If diagonal failed, try cardinal
            # print(f"DEBUG {self.name}: move_towards diagonal failed. Trying cardinal x ({norm_dx},0).")
            if self.move(norm_dx, 0, world):
                # print(f"DEBUG {self.name}: move_towards success via cardinal x ({norm_dx},0). New pos: ({self.x},{self.y})")
                return
            # print(f"DEBUG {self.name}: move_towards cardinal x failed. Trying cardinal y (0,{norm_dy}).")
            if self.move(0, norm_dy, world):
                # print(f"DEBUG {self.name}: move_towards success via cardinal y (0,{norm_dy}). New pos: ({self.x},{self.y})")
                return
        elif norm_dx != 0 : # Only dx was non-zero, and self.move(norm_dx,0) must have failed if we are here
             pass # print(f"DEBUG {self.name}: move_towards cardinal x ({norm_dx},0) failed.")
        elif norm_dy != 0 : # Only dy was non-zero, and self.move(0,norm_dy) must have failed
             pass # print(f"DEBUG {self.name}: move_towards cardinal y (0,{norm_dy}) failed.")
        # print(f"DEBUG {self.name}: move_towards ({target_x},{target_y}) FAILED all attempts from ({self.x},{self.y}).")


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
        if self.job == "Mayor": return "Oversee Settlement"
        if self.job == "Chief Medical Officer": return "Oversee Medical Operations"
        if self.job == "Medic": return "Provide Medical Care"
        if self.job == "Sheriff": return "Maintain Peace in Settlement"
        if self.job == "Deputy": return "Patrol Area"
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
        current_progress_gain = 1.0 # Start with float for easier modification
        is_lazy_this_tick = False

        # Health Effects on Progress
        if self.is_sick:
            if self.sickness_severity > 7: # Severe sickness
                current_progress_gain *= 0.1 # Drastically reduced
                self.add_memory(f"Feeling too sick to work effectively on {task_name} (Severity: {self.sickness_severity}).")
            elif self.sickness_severity > 3: # Moderate sickness
                current_progress_gain *= 0.5 # Halved
                self.add_memory(f"Feeling sick, working slowly on {task_name} (Severity: {self.sickness_severity}).")
            else: # Mild sickness
                current_progress_gain *= 0.8 # Slightly reduced

        if self.is_injured:
            if self.injury_severity > 7: # Severe injury
                current_progress_gain *= 0.05 # Almost no progress
                self.add_memory(f"Too injured to work properly on {task_name} (Severity: {self.injury_severity}).")
            elif self.injury_severity > 3: # Moderate injury
                current_progress_gain *= 0.4 # Significantly reduced
                self.add_memory(f"Working with difficulty due to injury on {task_name} (Severity: {self.injury_severity}).")
            else: # Mild injury
                current_progress_gain *= 0.75 # Noticeably reduced

        if "Lazy" in self.traits and not "Focused" in self.traits:
            if random.random() < 0.25: # 25% chance to be lazy
                current_progress_gain = 0 # Overrides health effects if lazy for this tick
                is_lazy_this_tick = True
                self.add_memory(f"Felt lazy and decided to slack off for a bit while working on '{task_name}'.")

        if current_progress_gain > 0 and not is_lazy_this_tick: # Don't apply positive progress traits if slacked off or health brought to 0
            if "Diligent" in self.traits:
                if random.random() < 0.25: # 25% chance for bonus progress
                    current_progress_gain += 0.5 # Additive bonus, or could be multiplicative
                    self.add_memory(f"Worked with extra diligence on '{task_name}'.")
            elif "Focused" in self.traits: # Focused but not Diligent
                if random.random() < 0.10: # 10% chance for smaller bonus
                    current_progress_gain += 0.25
                    self.add_memory(f"Remained focused and made good progress on '{task_name}'.")

        current_progress_gain = max(0, current_progress_gain) # Ensure progress isn't negative

        self.task_work_progress += current_progress_gain

        if is_lazy_this_tick and current_progress_gain == 0: # If slacked, end tick here
            return True

        # --- Task Completion and Yield ---
        if self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            base_yield_amount = task_def.get("base_yield",1)

            # Trait Effect on Yield (e.g., Strong)
            final_yield_amount = base_yield_amount
            if "Strong" in self.traits and res_prod in ["Wood", "Stone", "Iron Ore"]: # Assuming Strong applies to these
                if random.random() < 0.20: # 20% chance for +1 bonus
                    final_yield_amount += 1
                    self.add_memory(f"Put my strength into '{task_name}' and got a bit extra {res_prod}.")

            can_add_to_inv = self.max_inventory_items - self.get_inventory_load()
            actual_yield_taken = min(final_yield_amount, can_add_to_inv)

            if actual_yield_taken > 0 and res_prod:
                self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield_taken
                tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
                self.add_memory(f"Task '{task_name}': got {actual_yield_taken} {res_prod} (base: {base_yield_amount}) with {tool_name_mem}.")
                print(f"{self.name} task '{task_name}' yielded {actual_yield_taken} {res_prod} (base: {base_yield_amount}).")
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

            # --- Trait Effects on Crafting Progress ---
            current_crafting_progress_gain = 1
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

    def _execute_gather_herbs(self, world: 'World'):
        # For now, assume herbs can be found in "Forest" tiles, similar to wood.
        # This would need adjustment if a specific "Meadow" tile or herb resource node is implemented.
        # The find_task_location would also need to be updated to support "Herbs" if it's tied to a specific tile.
        # For this initial pass, we'll directly use "Gather Herbs" task if a location can be found.

        # Temporary: find_task_location doesn't support "Herbs" yet.
        # We'll assume a generic "Forest" location for gathering if the task is "Gather Herbs".
        # This part needs refinement based on how herb locations are defined in the world.
        task_loc = self.find_task_location("Gather Herbs", world) # This will currently fail as "Gather Herbs" doesn't map to a known tile in find_task_location

        # Fallback: If find_task_location doesn't work for herbs yet, try finding any Forest tile.
        # This is a placeholder until find_task_location is updated or herb sources are better defined.
        if not task_loc:
            self.add_memory("No specific herb location found, trying generic Forest.")
            # Simplified search for any Forest tile for now
            found_forest_tile = None
            for r_idx in range(world.grid_size[0]):
                for c_idx in range(world.grid_size[1]):
                    if world.get_tile(r_idx, c_idx) == "Forest":
                        # Check if this forest tile actually has herbs - future enhancement
                        # For now, any forest tile is a potential spot.
                        found_forest_tile = (r_idx, c_idx)
                        break
                if found_forest_tile:
                    break
            task_loc = found_forest_tile

        if not task_loc:
            self.add_memory(f"Cannot find a location to gather herbs (e.g., Forest).")
            self.current_goal = "Idle" # Or back to a job default goal
            return

        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return

        # Execute the generic task for gathering
        if not self._execute_generic_task(world, "Gather Herbs"):
            # This could mean a tool is needed (if defined for "Gather Herbs" later)
            # or some other precondition failed.
            return

        # Check if inventory is full or if a personal quota is met (if any)
        # For now, just gather until inventory is full.
        if self.get_inventory_load() >= self.max_inventory_items:
            self.add_memory("Inventory full of herbs.")
            # Decide what to do next, e.g., haul herbs or return to duties.
            # For a Medic/CMO, this might be returning to the clinic or seeking patients.
            # For now, set to Idle, which will trigger job_default_goal.
            self.current_goal = self.job_default_goal() or "Idle"
            # If a specific "Haul Herbs" goal exists, it could be set here.

    def _execute_oversee_medical_operations(self, world: 'World'):
        if self.job != "Chief Medical Officer":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        self.add_memory(f"CMO {self.name} is overseeing medical operations.")

        # Scan for patients
        patient_found = False
        for char in world.characters:
            if char.is_sick or char.is_injured:
                patient_found = True
                self.add_memory(f"Patient detected: {char.name} (Sick: {char.is_sick}, Injured: {char.is_injured}, S_Sev: {char.sickness_severity}, I_Sev: {char.injury_severity})")
                # Future: Assign medic, prioritize, etc.
        if not patient_found:
            self.add_memory("No patients currently require attention.")

        # Check medical supplies
        medical_supplies_to_check = ["Herbs", "Bandages"]
        if world.ledger:
            for supply_name in medical_supplies_to_check:
                total_count = world.ledger.get_total_resource_count(supply_name)
                self.add_memory(f"Supply check: Current {supply_name} stock is {total_count}.")
                if total_count < getattr(config, "MEDICAL_SUPPLY_LOW_THRESHOLD", 5): # Using getattr for safety
                    self.add_memory(f"CMO {self.name} notes: {supply_name} levels are low ({total_count}). Should request more.")
                    # Future: Generate work order for crafting/gathering supplies.
        else:
            self.add_memory(f"CMO {self.name} cannot check medical supplies: Ledger not available.")

        # CMOs might also manage medic assignments, rest schedules for medical staff, etc.
        # For now, primarily observation and logging.
        if random.random() < 0.1:
             self.add_memory(f"CMO {self.name} reviews medical protocols and staff readiness.")
        return

    def _execute_provide_medical_care(self, world: 'World'):
        if self.job != "Medic":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        # Find a patient - simplistic: first sick/injured person found
        # Future: Could be assigned by CMO, or check a list of designated patients.
        target_patient: Optional['Character'] = None
        for char in world.characters:
            if char.name != self.name and (char.is_sick or char.is_injured):
                # Prioritize more severe cases if logic allows, or just take first one
                target_patient = char
                break

        if not target_patient:
            self.add_memory("No patients currently require medical care. Standing by.")
            # Medic might return to a clinic, or just idle here.
            self.current_goal = "Idle" # Reverts to job default next tick, which might be "Provide Medical Care" again.
            return

        self.add_memory(f"Medic {self.name} assigned to patient {target_patient.name} at ({target_patient.x},{target_patient.y}).")

        patient_loc = (target_patient.x, target_patient.y)
        if (self.x, self.y) != patient_loc:
            self.move_towards(patient_loc[0], patient_loc[1], world)
            self.add_memory(f"Moving towards patient {target_patient.name}.")
            return

        # At the patient, perform treatment (conceptual for now)
        self.add_memory(f"Medic {self.name} is treating {target_patient.name}.")

        # Attempt to use a bandage first, then herbs
        item_used_for_treatment = None
        if self.inventory.get("Bandages", 0) > 0:
            self.inventory["Bandages"] -= 1
            if self.inventory["Bandages"] <= 0:
                del self.inventory["Bandages"]
            item_used_for_treatment = "Bandages"
            self.add_memory(f"Used 1 Bandage on {target_patient.name}.")
        elif self.inventory.get("Herbs", 0) > 0:
            self.inventory["Herbs"] -= 1
            if self.inventory["Herbs"] <= 0:
                del self.inventory["Herbs"]
            item_used_for_treatment = "Herbs"
            self.add_memory(f"Used 1 Herb on {target_patient.name}.")
        else:
            self.add_memory(f"No medical supplies (Bandages/Herbs) to treat {target_patient.name}. Need to restock.")
            # Medic might change goal to "Gather Herbs" or request supplies.
            # For now, they are stuck this tick if no supplies.
            return

        # Apply treatment effect
        treatment_successful_this_tick = False
        if item_used_for_treatment == "Bandages" and target_patient.is_injured:
            reduction = random.randint(2, 3) # Bandages are quite effective for injuries
            # Skill influence - e.g. higher skill more likely to get higher end of reduction or small bonus
            if self.skills.get("Medicine", {}).get("level", 0) > 2: reduction += random.choice([0,1])

            target_patient.injury_severity -= reduction
            self.add_memory(f"Applied Bandages to {target_patient.name}'s injuries, severity reduced by {reduction} to {max(0, target_patient.injury_severity)}.")
            treatment_successful_this_tick = True
            if target_patient.injury_severity <= 0:
                target_patient.is_injured = False
                target_patient.injury_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their injuries!")
                world.add_event_log_message(f"{target_patient.name} recovered from injuries thanks to {self.name}.")

        elif item_used_for_treatment == "Herbs" and target_patient.is_sick:
            reduction = random.randint(1, 2) # Herbs are moderately effective for sickness
            if self.skills.get("Medicine", {}).get("level", 0) > 1: reduction += random.choice([0,1])

            target_patient.sickness_severity -= reduction
            self.add_memory(f"Administered Herbs to {target_patient.name} for sickness, severity reduced by {reduction} to {max(0, target_patient.sickness_severity)}.")
            treatment_successful_this_tick = True
            if target_patient.sickness_severity <= 0:
                target_patient.is_sick = False
                target_patient.sickness_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their sickness!")
                world.add_event_log_message(f"{target_patient.name} recovered from sickness thanks to {self.name}.")

        elif item_used_for_treatment: # Used an item but it wasn't the right type for the condition
            self.add_memory(f"Tried to use {item_used_for_treatment} on {target_patient.name}, but it wasn't effective for their current condition.")

        if treatment_successful_this_tick:
            self._grant_skill_experience("Medicine", 1.5, world) # More XP for successful application
        else:
            self._grant_skill_experience("Medicine", 0.2, world) # Minor XP for attempt

        # After treatment, Medic might look for another patient or return to standby.
        # For now, will re-evaluate from top next tick.
        self.current_goal = self.job_default_goal() or "Idle" # Re-evaluate next patient or task
        return


    def _execute_oversee_expedition(self, world: 'World'):
         if self.job != "Expedition Leader": self.current_goal = self.job_default_goal(); return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = "Idle"

    def _execute_oversee_settlement(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        self.add_memory(f"{self.name} the Mayor is assessing the overall resource status of the settlement.")

        key_resources = ["Wood", "Stone"] # Initial key resources to monitor. Add "Food" if it becomes a general resource.
        # Future: These could be dynamically determined or configured.

        if world.ledger:
            for resource_name in key_resources:
                total_count = world.ledger.get_total_resource_count(resource_name)
                self.add_memory(f"Ledger check: Current {resource_name} stock is {total_count}.")

                # Example thresholds for Mayor's concern or attention
                # These are arbitrary and can be refined or made dynamic.
                # For now, just logging. Future actions could be to issue directives or priorities.
                if total_count < config.MAYOR_RESOURCE_LOW_THRESHOLD: # Assuming a config value like 20
                    self.add_memory(f"Mayor {self.name} notes: {resource_name} levels are low ({total_count}). Action may be needed.")
                elif total_count > config.MAYOR_RESOURCE_HIGH_THRESHOLD: # Assuming a config value like 200
                    self.add_memory(f"Mayor {self.name} notes: {resource_name} levels are abundant ({total_count}).")
        else:
            self.add_memory(f"Mayor {self.name} cannot assess resource status: Ledger not available.")

        # Simulate Mayor's strategic thinking or planning
        if random.random() < 0.15: # Chance to log a more general thought
            self.add_memory(f"Mayor {self.name} spends time contemplating the settlement's long-term strategy and development.")

        # The Mayor's role is ongoing oversight. They don't typically "finish" this goal quickly.
        # They might stay in "Oversee Settlement" for many ticks, continuously monitoring.
        # Specific events or critical thresholds might trigger a change in their goal or actions later.
        # For this initial implementation, the Mayor doesn't change their own goal here.
        # They also do not move unless a future sub-task of overseeing requires it (e.g. "Inspect Project X")

        # Periodically review appointments
        if random.random() < 0.1: # 10% chance each time Mayor oversees settlement
            if self.job == "Mayor": # Ensure only mayor does this
                self._execute_manage_appointments(world)

        # Chance to give a speech
        if random.random() < 0.02: # 2% chance each time Mayor oversees settlement
            self.add_memory(f"Mayor {self.name} feels it's time to address the populace.")
            self.current_goal = "Give Speech"
            return # Goal changed, decide_action will pick it up next tick

        # Mayoral Project Initiation
        # Simplified: 5% chance each time the Mayor oversees settlement to initiate a project
        if random.random() < 0.05:
            # Determine a project. For now, let's assume it's always to build a 'wooden_hut'.
            # Future: Could be based on actual settlement needs (e.g., housing shortage).
            project_structure_type = "wooden_hut"
            structure_bp = STRUCTURE_BLUEPRINTS.get(project_structure_type)

            if structure_bp and world.game_time:
                # Find a suitable location - very simplified: find first available 2x2 grass area
                # This needs a much more robust placement system in the future.
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
                            build_location = (c, r) # Note: blueprint size is (width, height), location is (x,y) or (col,row)
                            break
                    if build_location: break

                if build_location:
                    project_name = f"Mayoral Project: Construct {structure_bp['display_name']}"
                    self.add_memory(f"Decreeing new project: {project_name} at {build_location}.")

                    order_details = {
                        "structure_type": project_structure_type,
                        "location": build_location,
                        "required_resources": structure_bp["required_resources"].copy(),
                        "initiated_by_mayor": True # Flag to differentiate from other build orders if needed
                    }
                    # Mayor gives high priority to their projects.
                    new_build_order = WorkOrder(order_type="BuildStructure", details=order_details,
                                                priority=3, creation_day=world.game_time.current_day)

                    world.add_work_order(new_build_order)
                    self.add_memory(f"Issued Work Order {new_build_order.order_id} for {project_name}. Expecting Managers to handle assignment.")
                else:
                    self.add_memory(f"Considered initiating a {project_structure_type} project, but could not find a suitable location.")
            elif not structure_bp:
                 self.add_memory(f"Wanted to initiate a {project_structure_type} project, but blueprint is missing.")


        return

    def _execute_manage_appointments(self, world: 'World'):
        if self.job != "Mayor": # Should only be called by Mayor
            return

        self.add_memory(f"Mayor {self.name} is reviewing key settlement appointments.")
        key_positions = ["Sheriff", "Chief Medical Officer", "Manager"] # Define key roles Mayor manages

        # Check for vacant positions and try to hire
        for position_job_title in key_positions:
            current_holder: Optional['Character'] = None
            for char in world.characters:
                if char.job == position_job_title:
                    current_holder = char
                    break

            if not current_holder:
                self.add_memory(f"Position of {position_job_title} is vacant. Seeking candidate.")
                # Simplified hiring: find first available character without a critical job
                candidate: Optional['Character'] = None
                potential_candidates: List['Character'] = []
                for char_to_check in world.characters:
                    if char_to_check.job not in key_positions and char_to_check.job != "Mayor" and char_to_check.rank != "Noble Lord":
                        required_skill_for_job = {"Sheriff": "Security", "Chief Medical Officer": "Medicine", "Manager": "Leadership"}.get(position_job_title)
                        if required_skill_for_job and char_to_check.skills.get(required_skill_for_job, {}).get("level", 0) > 0:
                            potential_candidates.append(char_to_check)
                        elif not required_skill_for_job: # Should ideally not happen for key positions
                            potential_candidates.append(char_to_check)

                if potential_candidates:
                    # Prefer candidate with highest relevant skill
                    # Add trait preference here later (e.g. "Diligent")
                    relevant_skill = {"Sheriff": "Security", "Chief Medical Officer": "Medicine", "Manager": "Leadership"}.get(position_job_title)
                    if relevant_skill:
                        potential_candidates.sort(key=lambda c: c.skills.get(relevant_skill, {}).get("level", 0), reverse=True)
                    candidate = potential_candidates[0] # Pick the best one

                    self.add_memory(f"Appointing {candidate.name} (Skill: {candidate.skills.get(relevant_skill, {}).get('level', 0) if relevant_skill else 'N/A'}) as the new {position_job_title}.")
                    # Unassign from old role if necessary (more complex logic for supervisor, etc. later)
                    if candidate.supervisor_name:
                        supervisor = world.get_character_by_name(candidate.supervisor_name)
                        if supervisor: supervisor.remove_subordinate(candidate.name)

                    candidate.job = position_job_title
                    candidate.supervisor_name = self.name # Mayor becomes their supervisor
                    candidate.appointed_by = self.name
                    # Potentially adjust rank, e.g., to "Skilled Worker" or similar if not already appropriate
                    if candidate.rank == "Worker": candidate.rank = "Skilled Worker"
                    self.add_subordinate(candidate.name)
                    candidate.add_memory(f"I have been appointed as {position_job_title} by Mayor {self.name}.")
                else:
                    self.add_memory(f"Could not find a suitable candidate for {position_job_title} at this time.")
            else:
                # Position is filled, consider firing (simplified: trait-influenced random chance)
                base_firing_consideration_chance = 0.02 # Base 2% chance to even consider it
                if "Strict" in self.traits: base_firing_consideration_chance *= 1.5
                if "Impatient" in self.traits: base_firing_consideration_chance *= 1.5
                if "Forgiving" in self.traits: base_firing_consideration_chance *= 0.5

                if random.random() < base_firing_consideration_chance:
                    self.add_memory(f"Considering the performance of {current_holder.name}, the current {position_job_title}.")

                    actual_firing_chance = 0.25 # Base 25% chance if considered
                    if "Ruthless" in self.traits: actual_firing_chance = 0.5
                    if "Forgiving" in self.traits and "Ruthless" not in self.traits: actual_firing_chance = 0.1

                    # Future: Add more sophisticated firing criteria based on performance metrics
                    # For now, trait-modified random chance.
                    if random.random() < actual_firing_chance:
                        self.add_memory(f"Decided to relieve {current_holder.name} of their duties as {position_job_title} due to perceived unsatisfactory performance.")
                        current_holder.add_memory(f"I have been fired from my position as {position_job_title} by Mayor {self.name}.")
                        current_holder.job = "Unemployed"
                        current_holder.appointed_by = None
                        if self.name in current_holder.supervisor_name : current_holder.supervisor_name = None # check if mayor is supervisor
                        if current_holder.name in self.subordinates_names: self.remove_subordinate(current_holder.name)
                        # Note: This doesn't automatically reassign their previous subordinates if they were a manager.
                    else:
                        self.add_memory(f"{current_holder.name}'s performance as {position_job_title} is deemed acceptable for now.")
        return

    def _execute_maintain_peace(self, world: 'World'): # For Sheriff
        if self.job != "Sheriff":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        self.add_memory(f"Sheriff {self.name} is maintaining peace in the settlement.")

        # Initial simple behavior: Log surveying and occasionally move to a central point or wander.
        if random.random() < 0.2:
            self.add_memory("Surveying the surroundings for any disturbances.")

        # Placeholder for patrolling movement: move towards a conceptual "town_center" or just wander slightly.
        # If world had defined key locations, Sheriff could move between them.
        # For now, a simple wander-like behavior if not actively doing something else.
        if random.random() < 0.1: # Low chance to decide to move to a different spot
            # Simple wander to simulate being present in different areas.
            # This could be replaced with movement to specific patrol points if defined.
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0:
                self.add_memory(f"Sheriff {self.name} moves to a new vantage point.")
                self.move(dx, dy, world) # move will handle collisions/boundaries

        # Future: Scan for incidents, characters with "Troublemaker" trait, etc.
        # For now, the Sheriff's presence is the primary function.
        # Goal remains "Maintain Peace in Settlement" unless an incident changes it.
        return

    def _execute_patrol_area(self, world: 'World'): # For Deputy
        if self.job != "Deputy":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        self.add_memory(f"Deputy {self.name} is patrolling their assigned area.")

        # Simple patrolling behavior: move randomly or towards predefined points.
        # For now, just a random move.
        if random.random() < 0.3: # Chance to move each tick while patrolling
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0: # Ensure there's an actual move attempt
                if self.move(dx, dy, world):
                    self.add_memory(f"Patrolling... moved to ({self.x},{self.y}).")
                else:
                    self.add_memory(f"Patrolling... tried to move but was blocked.")
            else:
                self.add_memory("Patrolling... surveying current location.")
        else:
            self.add_memory("Patrolling... observing the area.")

        # Goal remains "Patrol Area". Deputies would continuously patrol.
        # Could add logic to return to a "Guardhouse" or report to Sheriff periodically.
        return

    def _execute_seek_medical_attention(self, world: 'World'):
        self.add_memory("Feeling unwell, seeking medical attention.")

        # Find the nearest Medic or CMO
        # For simplicity, find any character with job "Medic" or "Chief Medical Officer"
        # Future: Could search for a "Clinic" building first.
        medical_personnel: List['Character'] = []
        for char in world.characters:
            if char.job in ["Medic", "Chief Medical Officer"] and char.name != self.name:
                medical_personnel.append(char)

        if not medical_personnel:
            self.add_memory("Cannot find any medical personnel. Resting and hoping for the best.")
            # Potentially change goal to "Rest" if such a goal exists, or just Idle.
            # For now, if no medic, they might just stop seeking.
            self.current_goal = "Idle"
            return

        # Find the closest one (simple distance)
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
                # Now the medic should ideally take over. The sick person might just idle here,
                # or a new "BeingTreated" state/goal could be introduced.
                # For now, setting to Idle. The Medic's `_execute_provide_medical_care`
                # should find this character as a patient.
                self.current_goal = "Idle"
            else:
                self.add_memory(f"Moving towards {closest_medic.name} at ({closest_medic.x},{closest_medic.y}) for help.")
                self.move_towards(closest_medic.x, closest_medic.y, world)
        else: # Should not happen if medical_personnel list was populated
            self.add_memory("Could not determine closest medic. Resting.")
            self.current_goal = "Idle"
        return

    def _execute_give_speech(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.job_default_goal() or "Idle"
            return

        speech_topic = "the general state of the settlement and future prospects"
        # Basic LLM integration placeholder
        generated_speech_snippet = ""
        if config.USE_LLM:
            # Simple prompt, can be greatly expanded
            prompt = (f"You are {self.name}, the Mayor of a small, developing settlement. "
                      f"Your personality is {self.personality} and you have traits: {', '.join(self.traits)}. "
                      f"Briefly generate a snippet of a speech you are giving to your populace about {speech_topic}. "
                      f"Keep it under 50 words.")
            generated_speech_snippet = generate_dialogue(prompt, self.name) # Assuming generate_dialogue can be used for this

        if generated_speech_snippet:
            self.add_memory(f"Gave a speech: \"{generated_speech_snippet}\"")
            world.add_event_log_message(f"Mayor {self.name} addresses the populace: \"{generated_speech_snippet}\"")
        else:
            self.add_memory(f"Practiced a speech about {speech_topic}.")
            world.add_event_log_message(f"Mayor {self.name} clears their throat, preparing a speech about {speech_topic}.")

        # Future: This action could affect world morale, NPC opinions of the Mayor, etc.
        # For now, it's just a logged action.

        self.current_goal = self.job_default_goal() # Return to overseeing or default state
        return

    def _execute_wander(self, world: 'World'):
        moves=[];
        for dx,dy in[(0,1),(0,-1),(1,0),(-1,0)]:
            tx,ty=self.x+dx,self.y+dy
            if 0<=tx<world.grid_size[0] and 0<=ty<world.grid_size[1] and \
                world.get_tile(tx,ty)not in["Water","Mountain","Forest","Rocks","SP_Mai","SP_Woo","SP_Sto"] and \
                not world.get_characters_at_location(tx,ty):moves.append((dx,dy))
        if moves:choice=random.choice(moves);self.move(choice[0],choice[1],world)

    def job_default_goal(self) -> str: # Ensure this exists for the minimal decide_action
        if self.job == "Builder":
            return "Perform Builder Duties"
        # Add other job defaults here if necessary for other tests, but builder is key now
        return "Idle"

    def decide_action(self, world: 'World'):
        if not world.game_time:
            self.current_goal = "Idle"
            return

        # Health check: If severely sick or injured, character may change goal
        # Thresholds for "severe" can be defined in config later
        # For now, let's use severity > 5 as a trigger to seek help.
        if self.current_goal != "Seek Medical Attention": # Avoid interrupting if already seeking help
            if self.is_sick and self.sickness_severity > 5:
                self.add_memory(f"Feeling very sick (Severity: {self.sickness_severity}). Need medical attention.")
                self.current_goal = "Seek Medical Attention"
                # No return here, let the goal execution happen below if this is the first time it's set.
            elif self.is_injured and self.injury_severity > 5:
                self.add_memory(f"Badly injured (Severity: {self.injury_severity}). Need medical attention.")
                self.current_goal = "Seek Medical Attention"

        # If goal changed to Seek Medical Attention, execute that immediately this tick.
        if self.current_goal == "Seek Medical Attention":
            # _execute_seek_medical_attention will be added later. For now, just log and idle.
            # self._execute_seek_medical_attention(world)
            # For now, if they need medical attention but can't execute the goal yet, they might just idle.
            # This ensures they don't attempt other work while severely ill/injured if the seek goal isn't fully implemented.
            # To prevent them from doing normal work, we can return here if the goal was just set.
            # Or, _execute_generic_task will handle reduced efficiency.
            # For now, let's assume _execute_generic_task will handle reduced work.
            # If _execute_seek_medical_attention is implemented, it would be called here.
            pass # Let it fall through to goal execution or _execute_generic_task check

        # Minimal Needs Check (Energy for Builder) - can be expanded later
        # For this test, assume energy is not a blocker or handled by _execute_build_order
        # if self.job == "Builder" and self.needs.get("Energy", 100) < 10:
        #     self.current_goal = "Seek Rest"; # Needs _execute_rest
        #     return


        # Builder Logic: Focus on Build Orders
        if self.job == "Builder":
            if self.active_build_order_id:
                if self.current_goal != "Execute Build Order":
                    self.current_goal = "Execute Build Order"
                self._execute_build_order(world)
                return
            else: # No active build order, try to claim one
                # This part is also covered if current_goal is "Perform Builder Duties"
                approved_build_orders = world.get_approved_build_orders()
                if approved_build_orders:
                    order_to_take = approved_build_orders[0] # Simplistic: take the first one

                    order_to_take.status = "InProgress"
                    order_to_take.assigned_to = self.name

                    self._reset_building_state() # Clear any old state
                    self.active_build_order_id = order_to_take.order_id
                    self.current_building_project = order_to_take.details.get("structure_type")
                    self.building_site_target = order_to_take.details.get("location")
                    self.materials_gathered_for_build = False # Reset for new order

                    self.current_goal = "Execute Build Order"
                    self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {self.current_building_project}.")
                    self._execute_build_order(world) # Start processing immediately
                    return
                else: # No approved build orders
                    if self.current_goal == "Perform Builder Duties":
                        self.add_memory("No build orders available.")
                        self.current_goal = "Idle" # No WOs to perform duties on
                    # If current_goal was already Idle or Wander, it remains so.

        # If current goal was set to Execute Build Order by claiming
        if self.current_goal == "Execute Build Order":
             if self.active_build_order_id: # Ensure there's still an active order
                self._execute_build_order(world)
                return
             else: # No active order, but goal is to execute one. Reset.
                self._reset_building_state()
                self.current_goal = self.job_default_goal()


        # Fallback to job default goal if idle or current goal completed/invalidated
        if self.current_goal in [None, "Idle", "Wander"]:
            self.current_goal = self.job_default_goal()

        # Execute current goal if it's a "Perform..." duty
        if self.current_goal == "Perform Builder Duties":
            # This will loop back to the Builder Logic section above if not already handled
            # or set to Idle if no WOs found.
            # To prevent immediate re-loop if no WOs, ensure builder logic sets to Idle.
             pass # Let the top builder logic handle it or set to Idle.

        # Other "Perform..." duties would go here if this was a full decide_action
        # elif self.current_goal == "Perform Woodcutter Duties": self._execute_perform_woodcutter_duties(world); return
        elif self.current_goal == "Oversee Settlement":
            self._execute_oversee_settlement(world)
            return
        elif self.current_goal == "Oversee Medical Operations": # Added for CMO
            self._execute_oversee_medical_operations(world)
            return
        elif self.current_goal == "Provide Medical Care": # Added for Medic
            self._execute_provide_medical_care(world)
            return
        elif self.current_goal == "Gather Herbs":
            self._execute_gather_herbs(world)
            return
        elif self.current_goal == "Maintain Peace in Settlement": # Added for Sheriff
            self._execute_maintain_peace(world)
            return
        elif self.current_goal == "Patrol Area": # Added for Deputy
            self._execute_patrol_area(world)
            return
        elif self.current_goal == "Give Speech": # Added for Mayor
            self._execute_give_speech(world)
            return
        elif self.current_goal == "Seek Medical Attention": # Added for sick/injured
            self._execute_seek_medical_attention(world)
            return
        elif self.current_goal == "Greet Character":
            self._execute_greet_character(world)
            return
        elif self.current_goal == "Introduce Self to Stranger":
            self._execute_introduce_self(world)
            return
        elif self.current_goal == "Small Talk":
            self._execute_small_talk(world)
            return
        elif self.current_goal == "Share Positive News":
            self._execute_share_positive_news(world)
            return
        elif self.current_goal == "Offer Comfort":
            self._execute_offer_comfort(world)
            return


        # If truly nothing else to do
        if self.current_goal == "Idle" or self.current_goal is None:
            # print(f"{self.name} is Idle.")
            return

        if self.current_goal == "Wander":
            self._execute_wander(world)
            return

        # If a goal is set but not handled above (e.g. a generic task name directly set as goal)
        # This minimal version doesn't use generic tasks directly for builder.
        # print(f"Warning: {self.name} has unhandled goal '{self.current_goal}'. Idling.")
        # self.current_goal = "Idle" # Fallback
        return

        # --- Social Interaction Initiation (Basic) ---
        # If idle or wandering, consider social interaction.
        # This block is for proactive social interactions (greeting, small talk, news).
        # Reactive interactions like "Offer Comfort" will be handled by a separate check.

        # Proactive Social Interaction Check
        if self.current_goal in ["Idle", "Wander"] and random.random() < config.SOCIAL_INTERACTION_CHANCE:
            potential_strangers: List[Character] = []
            potential_known_to_greet: List[Character] = []
            potential_known_for_smalltalk: List[Character] = []
            potential_known_for_news: List[Character] = []

            for other_char in world.characters:
                if other_char.name == self.name:
                    continue

                distance = abs(self.x - other_char.x) + abs(self.y - other_char.y)
                max_initiation_distance = 5

                if distance <= max_initiation_distance:
                    recently_interacted_today = False
                    if self.dialogue_history:
                        for entry in reversed(self.dialogue_history[-3:]): # Check last few interactions
                            if (entry.get("target") == other_char.name or entry.get("initiator") == other_char.name) and \
                               world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1:
                                recently_interacted_today = True
                                break

                    if not recently_interacted_today:
                        if other_char.name not in self.known_characters:
                            potential_strangers.append(other_char)
                        else: # Character is known
                            potential_known_for_smalltalk.append(other_char)
                            potential_known_for_news.append(other_char)
                            potential_known_to_greet.append(other_char) # Greeting is always an option if others aren't chosen

            target_char_for_interaction: Optional[Character] = None
            interaction_type = None

            # Determine interaction based on priority and chance
            # Trait influence for choosing to share news (e.g., "Chatty")
            chatty_bonus_for_news = 0.2 if "Chatty" in self.traits else 0.0

            if potential_strangers:
                target_char_for_interaction = random.choice(potential_strangers)
                interaction_type = "Introduce Self to Stranger"
            elif potential_known_for_news and random.random() < (0.3 + chatty_bonus_for_news): # 30-50% chance to share news
                target_char_for_interaction = random.choice(potential_known_for_news)
                interaction_type = "Share Positive News"
            elif potential_known_for_smalltalk and random.random() < 0.6: # 60% chance for small talk over just greeting
                target_char_for_interaction = random.choice(potential_known_for_smalltalk)
                interaction_type = "Small Talk"
            elif potential_known_to_greet:
                target_char_for_interaction = random.choice(potential_known_to_greet)
                interaction_type = "Greet Character"

            if target_char_for_interaction and interaction_type:
                self.current_goal = interaction_type
                self.current_goal_details = {"target_char_name": target_char_for_interaction.name}
                self.add_memory(f"Decided to '{interaction_type}' with {target_char_for_interaction.name}.")

                # Execute the chosen interaction (the actual execution happens via the main goal dispatcher in decide_action)
                # No need to call _execute_* here, as the goal will be picked up by the elif chain.
                return # Goal has been set, action for this tick is to initiate this.

        # Reactive Social Interaction Check (e.g., Offer Comfort)
        # This check happens even if not strictly Idle/Wandering, but not if already in a social goal.
        # Higher priority than general idling if conditions are met.
        social_goals = ["Greet Character", "Introduce Self to Stranger", "Small Talk", "Share Positive News", "Offer Comfort"]
        if self.current_goal not in social_goals : # Avoid interrupting an ongoing social interaction
            # Consider offering comfort if someone nearby is distressed
            # Trait influence: "Kind", "Compassionate" characters are more likely to offer comfort.
            comfort_chance_modifier = 0.0
            if "Kind" in self.traits: comfort_chance_modifier += 0.3
            if "Compassionate" in self.traits: comfort_chance_modifier += 0.4 # Stronger pull for compassionate

            if random.random() < (0.1 + comfort_chance_modifier): # Base 10% + trait bonus
                target_for_comfort: Optional[Character] = None
                for char_in_need in world.characters:
                    if char_in_need.name == self.name or char_in_need.name not in self.known_characters:
                        continue # Don't comfort self or strangers (yet)

                    distance = abs(self.x - char_in_need.x) + abs(self.y - char_in_need.y)
                    max_comfort_distance = 4 # Can notice someone in distress from a bit further

                    if distance <= max_comfort_distance:
                        is_distressed = (char_in_need.is_sick and char_in_need.sickness_severity > 3) or \
                                        (char_in_need.is_injured and char_in_need.injury_severity > 3)
                        # Future: could also check for very low mood, recent negative memory etc.

                        if is_distressed:
                            # Check if already comforted this person recently for this specific issue (simplistic check)
                            recently_comforted_for_this = False
                            if self.dialogue_history:
                                for entry in reversed(self.dialogue_history[-3:]): # Check last few interactions
                                    if entry.get("type") == "offer_comfort" and entry.get("target") == char_in_need.name and \
                                       world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1 : # Same day
                                        recently_comforted_for_this = True
                                        break
                            if not recently_comforted_for_this:
                                target_for_comfort = char_in_need
                                break # Found someone to comfort

                if target_for_comfort:
                    self.current_goal = "Offer Comfort"
                    self.current_goal_details = {"target_char_name": target_for_comfort.name}
                    self.add_memory(f"Noticed {target_for_comfort.name} seems distressed. Decided to offer comfort.")
                    # Execution will happen in the main goal dispatch elif chain.
                    return # Goal set.

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

    def _execute_greet_character(self, world: 'World'):
        if not self.current_goal_details or "target_char_name" not in self.current_goal_details:
            self.add_memory("Wanted to greet someone, but no target specified.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        target_name = self.current_goal_details["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to greet {target_name}, but they could not be found.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        # Check distance - characters should be close to greet
        # Using Manhattan distance for simplicity
        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_greeting_distance = 2 # Can be adjusted

        if distance > max_greeting_distance:
            self.add_memory(f"Trying to greet {target_name}, but they are too far away. Moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return # Still moving, try again next tick

        # --- At Greeting Distance ---
        self.add_memory(f"Approached {target_name} to greet them.")

        # Simple initial greeting effect:
        # 1. Both characters become aware of each other.
        if target_name not in self.known_characters:
            self.known_characters.append(target_name)
        if self.name not in target_char.known_characters:
            target_char.known_characters.append(self.name)

        # 2. Determine Relationship Impact based on traits
        initiator_friendly = "Friendly" in self.traits
        initiator_grumpy = "Grumpy" in self.traits
        target_friendly = "Friendly" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        # Base relationship change for meeting
        base_rel_change_initiator_to_target = 0
        base_rel_change_target_to_initiator = 0

        if target_name not in self.relationships: # First time initiator forms opinion of target
            if initiator_friendly and target_friendly: base_rel_change_initiator_to_target = 3
            elif initiator_friendly and not target_grumpy: base_rel_change_initiator_to_target = 2 # Friendly to Neutral
            elif initiator_friendly and target_grumpy: base_rel_change_initiator_to_target = 1 # Friendly optimistic
            elif initiator_grumpy and target_friendly: base_rel_change_initiator_to_target = 0 # Grumpy unimpressed by friendliness
            elif initiator_grumpy and target_grumpy: base_rel_change_initiator_to_target = 1 # Grumpy respects grumpy
            elif initiator_grumpy and not target_friendly: base_rel_change_initiator_to_target = 0 # Grumpy to Neutral
            else: base_rel_change_initiator_to_target = 1 # Neutral to anyone
            self.modify_relationship(target_name, base_rel_change_initiator_to_target, world, reason=f"First impression of {target_name}.")

        if self.name not in target_char.relationships: # First time target forms opinion of initiator
            if target_friendly and initiator_friendly: base_rel_change_target_to_initiator = 3
            elif target_friendly and not initiator_grumpy: base_rel_change_target_to_initiator = 2 # Friendly to Neutral
            elif target_friendly and initiator_grumpy: base_rel_change_target_to_initiator = 1 # Friendly to Grumpy (still tries)
            elif target_grumpy and initiator_friendly: base_rel_change_target_to_initiator = 0 # Grumpy unimpressed
            elif target_grumpy and initiator_grumpy: base_rel_change_target_to_initiator = 1 # Mutual grumpiness
            elif target_grumpy and not initiator_friendly: base_rel_change_target_to_initiator = 0 # Grumpy to Neutral
            else: base_rel_change_target_to_initiator = 1 # Neutral to anyone
            target_char.modify_relationship(self.name, base_rel_change_target_to_initiator, world, reason=f"First impression of {self.name}.")

        # For subsequent greetings (if they happen), could add a smaller, consistent positive modifier, or none.
        # For now, only first impressions are significantly impacted by this initial greeting.

        # 3. Generate Dialogue Snippets based on traits
        # Initiator's line
        if initiator_friendly:
            dialogue_line_self = random.choice([
                f"Well hello there, {target_name}! A pleasure to meet you.",
                f"Greetings, {target_name}! Hope you're having a good day.",
                f"Hi {target_name}! Always nice to see a new face." if target_name not in self.known_characters else f"Hi {target_name}! Good to see you again."
            ])
        elif initiator_grumpy:
            dialogue_line_self = random.choice([
                f"{target_name}.",
                f"Hmph. {target_name} is it?",
                "Yeah?"
            ])
        else: # Neutral initiator
            dialogue_line_self = random.choice([
                f"Hello, {target_name}.",
                f"Greetings, {target_name}.",
                f"Good day, {target_name}."
            ])

        # Target's reply
        if target_friendly:
            dialogue_line_target = random.choice([
                f"And a good day to you too, {self.name}!",
                f"Hello {self.name}! Nice to meet you as well.",
                f"Hi there, {self.name}!"
            ])
        elif target_grumpy:
            dialogue_line_target = random.choice([
                "Hmph.",
                "What do you want?",
                f"Seen you around, {self.name}."
            ])
        else: # Neutral target
            dialogue_line_target = random.choice([
                f"Hello, {self.name}.",
                f"Greetings.",
                f"Good day."
            ])

        # Store dialogue
        dialogue_entry = {
            "type": "greeting", # Or "introduction" if it's a first meeting
            "initiator": self.name,
            "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [ # Changed from "dialogue" to "dialogue_exchanges" to be clearer
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry) # Both characters record the interaction

        # 4. Form/Update Opinions based on the greeting
        # Initiator (self) forms an opinion about the target's response style
        if target_name not in self.opinions: self.opinions[target_name] = {}
        if target_friendly: self.opinions[target_name]["greeting_response"] = self.opinions[target_name].get("greeting_response", 0) + 1
        elif target_grumpy: self.opinions[target_name]["greeting_response"] = self.opinions[target_name].get("greeting_response", 0) - 1
        else: self.opinions[target_name]["greeting_response"] = self.opinions[target_name].get("greeting_response", 0) + 0 # Neutral

        # Target forms an opinion about the initiator's greeting style
        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        if initiator_friendly: target_char.opinions[self.name]["greeting_style"] = target_char.opinions[self.name].get("greeting_style", 0) + 1
        elif initiator_grumpy: target_char.opinions[self.name]["greeting_style"] = target_char.opinions[self.name].get("greeting_style", 0) - 1
        else: target_char.opinions[self.name]["greeting_style"] = target_char.opinions[self.name].get("greeting_style", 0) + 0 # Neutral

        # Clamp opinion scores (e.g., between -5 and 5 for this simple tag)
        self.opinions[target_name]["greeting_response"] = max(-5, min(5, self.opinions[target_name].get("greeting_response",0)))
        target_char.opinions[self.name]["greeting_style"] = max(-5, min(5, target_char.opinions[self.name].get("greeting_style",0)))


        self.add_memory(f"Greeted {target_name}. Said: '{dialogue_line_self}'. My opinion of their response style: {self.opinions[target_name]['greeting_response']}")
        target_char.add_memory(f"Was greeted by {self.name}. They said: '{dialogue_line_self}'. My opinion of their style: {target_char.opinions[self.name]['greeting_style']}. I replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.name} greeted {target_name}.")

        # 5. Target character's reaction:
        if target_char.current_goal != "Greet Character":
            target_char.add_memory(f"Acknowledged greeting from {self.name} while I was {target_char.current_goal}.")

        # 6. Greeting complete. Reset goal.
        self.current_goal = self.job_default_goal() or "Idle"
        self.current_goal_details = None
        return

    def _execute_offer_comfort(self, world: 'World'):
        if not self.current_goal_details or "target_char_name" not in self.current_goal_details:
            self.add_memory("Wanted to offer comfort, but no target specified.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        target_name = self.current_goal_details["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to offer comfort to {target_name}, but they could not be found.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        # Comfort is typically for known characters in a negative state
        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to offer comfort to {target_name}, but I don't know them.")
            self.current_goal = self.job_default_goal()
            self.current_goal_details = None
            return

        # Check if target is actually in a state deserving comfort (e.g. sick/injured)
        # This condition should ideally be part of the decision to initiate "Offer Comfort"
        if not (target_char.is_sick and target_char.sickness_severity > 3) and \
           not (target_char.is_injured and target_char.injury_severity > 3):
            self.add_memory(f"Considered offering comfort to {target_name}, but they seem fine now.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2
        if distance > max_interaction_distance:
            self.add_memory(f"Trying to offer comfort to {target_name}, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        self.add_memory(f"Offering comfort to {target_name}.")

        initiator_kind = "Kind" in self.traits or "Compassionate" in self.traits # Assuming Compassionate implies Kind
        initiator_grumpy = "Grumpy" in self.traits
        target_grumpy = "Grumpy" in target_char.traits

        # 1. Relationship Impact
        rel_change = 2 # Base positive impact for offering comfort
        if initiator_kind: rel_change += 2
        if initiator_grumpy: rel_change -= 1 # Grumpy comfort might be awkward but still counts

        # Target's state might influence how they perceive comfort
        if target_char.sickness_severity > 6 or target_char.injury_severity > 6 : # Very severe state
            rel_change +=1 # Extra appreciation if very unwell
        if target_grumpy:
            rel_change = max(0, rel_change -1) # Grumpy target might be less receptive

        rel_change = max(0, min(5, rel_change)) # Clamp between 0 and 5

        self.modify_relationship(target_name, rel_change, world, reason=f"Offered comfort to {target_name}.")
        target_char.modify_relationship(self.name, rel_change, world, reason=f"{self.name} offered comfort.")


        # 2. Dialogue
        comforting_lines_self = [
            f"I heard you weren't feeling too well, {target_name}. Hope you get better soon.",
            f"Sorry to see you're having a tough time, {target_name}. Let me know if there's anything I can do.",
            f"Hang in there, {target_name}. These things pass."
        ]
        if initiator_kind:
             comforting_lines_self.append(f"You're strong, {target_name}, you'll get through this. My thoughts are with you.")
        if initiator_grumpy: # Grumpy comfort is... different
            comforting_lines_self = [f"Heard you were down. Well, try not to be.", f"Tough luck, {target_name}. Get over it."]


        replies_target = ["Thank you, I appreciate that.", "Thanks for your concern.", "I'm trying my best."]
        if target_grumpy: replies_target = ["Hmph. Fine.", "I'll manage.", "Whatever."]
        elif target_char.sickness_severity > 6 or target_char.injury_severity > 6: # Very unwell
            replies_target.append("It means a lot... thank you.")


        dialogue_line_self = random.choice(comforting_lines_self)
        dialogue_line_target = random.choice(replies_target)

        dialogue_entry = {
            "type": "offer_comfort",
            "initiator": self.name,
            "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        # 3. Opinion Impact
        if target_name not in self.opinions: self.opinions[target_name] = {}
        opinion_tag_target = "grace_in_hardship" # How target handles being comforted
        current_opinion_target = self.opinions[target_name].get(opinion_tag_target, 0)
        if not target_grumpy : current_opinion_target +=1 # Non-grumpy people seen as more graceful
        self.opinions[target_name][opinion_tag_target] = max(-5, min(5, current_opinion_target))

        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        opinion_tag_initiator = "empathy_level"
        current_opinion_initiator = target_char.opinions[self.name].get(opinion_tag_initiator, 0)
        if initiator_kind: current_opinion_initiator +=2
        elif not initiator_grumpy: current_opinion_initiator +=1 # Neutral is still empathetic
        # Grumpy initiator offering comfort might still be seen as having some empathy, just awkwardly expressed
        target_char.opinions[self.name][opinion_tag_initiator] = max(-5, min(5, current_opinion_initiator))

        self.add_memory(f"Offered comfort to {target_name}. Said: '{dialogue_line_self}'. Their grace: {self.opinions[target_name].get(opinion_tag_target, 'N/A')}")
        target_char.add_memory(f"{self.name} offered comfort. Their empathy: {target_char.opinions[self.name].get(opinion_tag_initiator, 'N/A')}. I replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.name} offered comfort to {target_name}.")

        if target_char.current_goal not in ["Offer Comfort", "Seek Medical Attention"]:
            target_char.add_memory(f"{self.name} comforted me while I was {target_char.current_goal}.")

        self.current_goal = self.job_default_goal() or "Idle"
        self.current_goal_details = None
        return

    def _execute_share_positive_news(self, world: 'World'):
        if not self.current_goal_details or "target_char_name" not in self.current_goal_details:
            self.add_memory("Wanted to share news, but no target specified.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        target_name = self.current_goal_details["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to share news with {target_name}, but they could not be found.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to share news with {target_name}, but I don't know them well enough.")
            self.current_goal = self.job_default_goal() or "Idle" # Or try to introduce first
            self.current_goal_details = None
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2

        if distance > max_interaction_distance:
            self.add_memory(f"Trying to share news with {target_name}, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        self.add_memory(f"Sharing some positive news/gossip with {target_name}.")

        initiator_friendly = "Friendly" in self.traits
        initiator_grumpy = "Grumpy" in self.traits
        initiator_chatty = "Chatty" in self.traits
        target_friendly = "Friendly" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        # 1. Relationship Impact
        rel_change = 0
        if initiator_chatty or initiator_friendly: rel_change += 1
        if target_friendly: rel_change +=1
        elif target_grumpy: rel_change -=1

        # Cap positive impact, make negative impact less likely unless initiator is also grumpy
        if rel_change > 1: rel_change = 1
        if rel_change < 0 and not initiator_grumpy: rel_change = 0

        if rel_change != 0:
            self.modify_relationship(target_name, rel_change, world, reason=f"Shared some news with {target_name}.")
            target_char.modify_relationship(self.name, rel_change, world, reason=f"{self.name} shared some news.")

        # 2. Dialogue
        available_chars_for_gossip = [c.name for c in world.characters if c.name != self.name and c.name != target_name]
        gossip_subject_name = random.choice(available_chars_for_gossip) if available_chars_for_gossip else "someone"

        news_items_templates = [
            "Heard the hunters had a good catch today!",
            f"I saw {gossip_subject_name} looking particularly cheerful earlier.",
            "They say the weather's going to be perfect for the next few days.",
            "Someone mentioned finding an unusually large berry patch nearby.",
            "Word is the builders are making great progress on that new structure."
        ]
        if initiator_grumpy: # Grumpy "positive" news is more like a grudging admission
            news_items_templates = [
                "Suppose the harvest wasn't a total disaster.",
                "That new building isn't as bad as I expected.",
                "At least it's not raining for once.",
                f"Heard {gossip_subject_name} actually did something useful. Surprising."
            ]

        dialogue_line_self = random.choice(news_items_templates)

        replies_target = ["Oh, that's good to hear!", "Is that so? Interesting.", "Thanks for letting me know."]
        if target_friendly: replies_target.extend(["Wonderful news!", "That's fantastic!"])
        elif target_grumpy: replies_target = ["Hmph. Alright.", "And?", "Noted."]
        dialogue_line_target = random.choice(replies_target)

        dialogue_entry = {
            "type": "share_positive_news",
            "initiator": self.name,
            "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        # 3. Opinion Impact
        if target_name not in self.opinions: self.opinions[target_name] = {}
        opinion_tag_target = "receptiveness_to_news"
        current_opinion_target = self.opinions[target_name].get(opinion_tag_target, 0)
        if target_friendly: current_opinion_target +=1
        elif target_grumpy: current_opinion_target -=1
        self.opinions[target_name][opinion_tag_target] = max(-5, min(5, current_opinion_target))

        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        opinion_tag_initiator = "news_sharing_style" # e.g. informative, amusing, trivial
        current_opinion_initiator = target_char.opinions[self.name].get(opinion_tag_initiator, 0)
        if initiator_chatty: current_opinion_initiator +=1 # Chatty people might be seen as good news sharers
        if initiator_friendly: current_opinion_initiator +=1
        elif initiator_grumpy: current_opinion_initiator -=1 # Grumpy news might not be well received
        target_char.opinions[self.name][opinion_tag_initiator] = max(-5, min(5, current_opinion_initiator))

        self.add_memory(f"Shared news with {target_name}: '{dialogue_line_self}'. Their receptiveness: {self.opinions[target_name][opinion_tag_target]}")
        target_char.add_memory(f"{self.name} shared news: '{dialogue_line_self}'. Their style: {target_char.opinions[self.name][opinion_tag_initiator]}. I replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.name} shared some news with {target_name}.")

        if target_char.current_goal not in ["Share Positive News", "Small Talk", "Greet Character", "Introduce Self to Stranger"]:
            target_char.add_memory(f"Heard some news from {self.name} while I was {target_char.current_goal}.")

        self.current_goal = self.job_default_goal() or "Idle"
        self.current_goal_details = None
        return

    def _execute_small_talk(self, world: 'World'):
        if not self.current_goal_details or "target_char_name" not in self.current_goal_details:
            self.add_memory("Wanted to make small talk, but no target specified.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        target_name = self.current_goal_details["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to make small talk with {target_name}, but they could not be found.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        # Small talk should only be with known characters
        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to make small talk with {target_name}, but I don't know them. Maybe I should introduce myself first.")
            self.current_goal = "Introduce Self to Stranger" # Or just Idle
            # current_goal_details remains the same
            self._execute_introduce_self(world) # Attempt introduction
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2

        if distance > max_interaction_distance:
            self.add_memory(f"Trying to make small talk with {target_name}, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        # --- At Interaction Distance with a Known Character ---
        self.add_memory(f"Starting small talk with {target_name}.")

        # 1. Relationship Impact (minor, can be neutral or slightly positive/negative)
        initiator_friendly = "Friendly" in self.traits
        initiator_grumpy = "Grumpy" in self.traits
        initiator_chatty = "Chatty" in self.traits # New trait to consider
        target_friendly = "Friendly" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        rel_change = 0
        if initiator_chatty: rel_change +=1 # Chatty people enjoy small talk more
        if initiator_friendly: rel_change +=1

        if target_friendly: rel_change +=1
        elif target_grumpy: rel_change -=1 # Grumpy people might dislike small talk

        # Normalize change to be small
        if rel_change > 1: rel_change = 1
        if rel_change < 0 and not (initiator_grumpy and target_grumpy) : rel_change = 0 # Avoid negative impact unless both are grumpy
        if initiator_grumpy and target_grumpy: rel_change = 0 # Grumpy people might not bond over small talk

        if rel_change != 0:
            self.modify_relationship(target_name, rel_change, world, reason=f"Had some small talk with {target_name}.")
            target_char.modify_relationship(self.name, rel_change, world, reason=f"Had some small talk with {self.name}.")

        # 2. Dialogue Snippets for Small Talk
        # Initiator's line (topics: weather, work, general observation)
        small_talk_topics_initiator = [
            f"The weather's been something else lately, hasn't it, {target_name}?",
            "Keeping busy with work, I imagine?",
            "Anything interesting happen around here lately?",
            "Just taking a moment. How are things with you?"
        ]
        if initiator_friendly:
            small_talk_topics_initiator.extend([
                f"Lovely day, {target_name}!",
                f"Hope you're doing well, {target_name}."
            ])
        elif initiator_grumpy:
            small_talk_topics_initiator = [ # Grumpy small talk is more like a statement
                "Weather's terrible.",
                "Work never ends.",
                "Quiet around here... too quiet."
            ]
        dialogue_line_self = random.choice(small_talk_topics_initiator)

        # Target's reply
        small_talk_replies_target = [
            "Indeed it has.", "Same old, same old.", "Not much to report.", "Doing alright, thanks."
        ]
        if target_friendly:
            small_talk_replies_target.extend([
                "Yes, quite lovely!", "Oh, you know, the usual hustle and bustle!", "Can't complain!"
            ])
        elif target_grumpy:
            small_talk_replies_target = [
                "Hmph.", "Suppose so.", "Busy enough.", "Fine."
            ]
        dialogue_line_target = random.choice(small_talk_replies_target)

        dialogue_entry = {
            "type": "small_talk",
            "initiator": self.name,
            "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        # 3. Form/Update Opinions based on small talk
        # Opinion of target's engagement in small talk
        if target_name not in self.opinions: self.opinions[target_name] = {}
        opinion_tag_target = "small_talk_engagement"
        current_opinion_target = self.opinions[target_name].get(opinion_tag_target, 0)
        if target_friendly: current_opinion_target +=1
        elif target_grumpy: current_opinion_target -=1
        self.opinions[target_name][opinion_tag_target] = max(-5, min(5, current_opinion_target))

        # Opinion of initiator's small talk quality (from target's perspective)
        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        opinion_tag_initiator = "small_talk_quality"
        current_opinion_initiator = target_char.opinions[self.name].get(opinion_tag_initiator, 0)
        if initiator_chatty: current_opinion_initiator +=1
        if initiator_friendly: current_opinion_initiator +=1
        elif initiator_grumpy: current_opinion_initiator -=1 # Grumpy small talk might be seen as poor quality
        target_char.opinions[self.name][opinion_tag_initiator] = max(-5, min(5, current_opinion_initiator))

        self.add_memory(f"Made small talk with {target_name}. Topic: '{dialogue_line_self}'. My opinion of their engagement: {self.opinions[target_name][opinion_tag_target]}")
        target_char.add_memory(f"Had small talk with {self.name}. My opinion of their quality: {target_char.opinions[self.name][opinion_tag_initiator]}. Replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.name} and {target_name} made small talk.")

        if target_char.current_goal not in ["Small Talk", "Greet Character", "Introduce Self to Stranger"]:
             target_char.add_memory(f"Chatted briefly with {self.name} while I was {target_char.current_goal}.")

        self.current_goal = self.job_default_goal() or "Idle"
        self.current_goal_details = None
        return

    def _execute_introduce_self(self, world: 'World'):
        if not self.current_goal_details or "target_char_name" not in self.current_goal_details:
            self.add_memory("Wanted to introduce myself, but no target specified.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        target_name = self.current_goal_details["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to introduce myself to {target_name}, but they could not be found.")
            self.current_goal = self.job_default_goal() or "Idle"
            self.current_goal_details = None
            return

        # Ensure it's actually a stranger. If already known, switch to a generic greet or idle.
        if target_name in self.known_characters:
            self.add_memory(f"Wanted to introduce to {target_name}, but I already know them. Switching to greet.")
            self.current_goal = "Greet Character"
            # current_goal_details remains the same for the greet
            self._execute_greet_character(world) # Execute greet immediately
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2

        if distance > max_interaction_distance:
            self.add_memory(f"Trying to introduce myself to {target_name}, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        # --- At Interaction Distance with a Stranger ---
        self.add_memory(f"Approached {target_name} to introduce myself.")

        # 1. Become known to each other
        self.known_characters.append(target_name)
        if self.name not in target_char.known_characters: # Should usually be true if target_name wasn't in self.known_characters
            target_char.known_characters.append(self.name)

        # 2. Relationship Impact (similar to first greeting in _execute_greet_character)
        initiator_friendly = "Friendly" in self.traits
        initiator_grumpy = "Grumpy" in self.traits
        target_friendly = "Friendly" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        rel_change_initiator_to_target = 1 # Base for neutral intro
        if initiator_friendly and target_friendly: rel_change_initiator_to_target = 3
        elif initiator_friendly and not target_grumpy: rel_change_initiator_to_target = 2
        elif initiator_friendly and target_grumpy: rel_change_initiator_to_target = 1
        elif initiator_grumpy and target_friendly: rel_change_initiator_to_target = 0
        elif initiator_grumpy and target_grumpy: rel_change_initiator_to_target = 1
        elif initiator_grumpy: rel_change_initiator_to_target = 0
        self.modify_relationship(target_name, rel_change_initiator_to_target, world, reason=f"Introduced myself to {target_name}.")

        rel_change_target_to_initiator = 1 # Base for neutral intro
        if target_friendly and initiator_friendly: rel_change_target_to_initiator = 3
        elif target_friendly and not initiator_grumpy: rel_change_target_to_initiator = 2
        elif target_friendly and initiator_grumpy: rel_change_target_to_initiator = 1
        elif target_grumpy and initiator_friendly: rel_change_target_to_initiator = 0
        elif target_grumpy and initiator_grumpy: rel_change_target_to_initiator = 1
        elif target_grumpy: rel_change_target_to_initiator = 0
        target_char.modify_relationship(self.name, rel_change_target_to_initiator, world, reason=f"{self.name} introduced themselves.")

        # 3. Dialogue Snippets for Introduction
        # Initiator's line
        if initiator_friendly:
            dialogue_line_self = random.choice([
                f"Hello there! I don't think we've met, I'm {self.name}.",
                f"Hi! I'm {self.name}, a pleasure to make your acquaintance, {target_name}.",
                f"Greetings! You must be {target_name}. I'm {self.name}."
            ])
        elif initiator_grumpy:
            dialogue_line_self = random.choice([
                f"I'm {self.name}. You're {target_name}, right?",
                f"{self.name}. That's me. And you are?",
                f"Name's {self.name}."
            ])
        else: # Neutral initiator
            dialogue_line_self = random.choice([
                f"Hello, I'm {self.name}.",
                f"Greetings. My name is {self.name}. And you are {target_name}?",
                f"I am {self.name}."
            ])

        # Target's reply
        if target_friendly:
            dialogue_line_target = random.choice([
                f"A pleasure to meet you, {self.name}! I'm {target_name}.",
                f"Hello {self.name}! I'm {target_name}. Nice to meet you!",
                f"Hi {self.name}! I'm {target_name}."
            ])
        elif target_grumpy:
            dialogue_line_target = random.choice([
                f"{target_name}. And you are?",
                f"I'm {target_name}. What of it, {self.name}?",
                f"Yeah, I'm {target_name}."
            ])
        else: # Neutral target
            dialogue_line_target = random.choice([
                f"Hello, {self.name}. I am {target_name}.",
                f"Greetings. I'm {target_name}.",
                f"I am {target_name}. You are {self.name}."
            ])

        dialogue_entry = {
            "type": "introduction",
            "initiator": self.name,
            "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        # 4. Form/Update Opinions based on the introduction
        if target_name not in self.opinions: self.opinions[target_name] = {}
        if target_friendly: self.opinions[target_name]["introduction_response"] = self.opinions[target_name].get("introduction_response", 0) + 1
        elif target_grumpy: self.opinions[target_name]["introduction_response"] = self.opinions[target_name].get("introduction_response", 0) - 1
        else: self.opinions[target_name]["introduction_response"] = self.opinions[target_name].get("introduction_response", 0) + 0
        self.opinions[target_name]["introduction_response"] = max(-5, min(5, self.opinions[target_name].get("introduction_response",0)))

        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        if initiator_friendly: target_char.opinions[self.name]["introduction_style"] = target_char.opinions[self.name].get("introduction_style", 0) + 1
        elif initiator_grumpy: target_char.opinions[self.name]["introduction_style"] = target_char.opinions[self.name].get("introduction_style", 0) - 1
        else: target_char.opinions[self.name]["introduction_style"] = target_char.opinions[self.name].get("introduction_style", 0) + 0
        target_char.opinions[self.name]["introduction_style"] = max(-5, min(5, target_char.opinions[self.name].get("introduction_style",0)))

        self.add_memory(f"Introduced myself to {target_name}. Said: '{dialogue_line_self}'. My opinion of their response: {self.opinions[target_name]['introduction_response']}")
        target_char.add_memory(f"{self.name} introduced themselves. They said: '{dialogue_line_self}'. My opinion of their style: {target_char.opinions[self.name]['introduction_style']}. I replied: '{dialogue_line_target}'")
        world.add_event_log_message(f"{self.name} introduced themselves to {target_name}.")

        if target_char.current_goal != "Introduce Self to Stranger":
            target_char.add_memory(f"Met {self.name} while I was {target_char.current_goal}.")

        self.current_goal = self.job_default_goal() or "Idle"
        self.current_goal_details = None
        return