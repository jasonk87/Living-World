# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any, Set
import random
from .llm_integration import generate_dialogue # Kept as it's used
# from .stockpile import Stockpile # Not directly used by Character methods
# from .work_order import WorkOrder # Not directly used by Character methods
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS, JOB_SALARIES
from . import config
from .goal import Goal, GoalType, GoalStatus, DEFAULT_IDLE_GOAL, create_goal_from_job
from .rumor import Rumor # Added for rumor generation

if TYPE_CHECKING:
    from .world import World
    # Character can self-reference with 'Character' string hint if needed later

ORDER_SPAM_PREVENTION_DAYS = 3

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: dict[str, int], x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal_obj: Optional[Goal] = None,
                 job: Optional[str] = None,
                 max_inventory_items: int = 10,
                 rank: str = "Worker",
                 money: int = 10,
                 family_members: Optional[List[str]] = None,
                 liege: Optional[str] = None,
                 vassals: Optional[List[str]] = None):
        self.name = name; self.personality = personality; self.traits = traits;
        self.money: int = money
        self.family_members: List[str] = family_members if family_members else []
        self.skills: Dict[str, Dict[str, Any]] = {}
        if skills:
            for skill_name, level_val in skills.items():
                self.skills[skill_name] = {
                    "level": level_val,
                    "experience": 0.0,
                    "exp_to_next_level": self._calculate_exp_for_level(level_val)
                }

        self.x = x; self.y = y; self.inventory = {}; self.memory = [];
        self.needs = needs if needs else {};
        self.job = job

        self.relationships = {} # Initialize relationships first
        if self.family_members: # Then set family scores
            for member_name in self.family_members:
                if member_name != self.name:
                    self.relationships[member_name] = config.RELATIONSHIP_SCORE_FAMILY_BASE

        # Initialize current_goal with a Goal object
        if current_goal_obj:
            self.current_goal: Goal = current_goal_obj
        else:
            # Try to create a job-specific goal
            job_goal = create_goal_from_job(self.job or "Unemployed", self.name)
            if job_goal:
                self.current_goal: Goal = job_goal
            else:
                # Fallback to a default idle goal if job goal creation fails or job is "Unemployed" and has no default
                self.current_goal: Goal = Goal(GoalType.IDLE, assignee_id=self.name, originator_id="SystemInit")

        # Ensure assignee_id is always set on the initial goal
        if self.current_goal.assignee_id is None:
            self.current_goal.assignee_id = self.name
        if not self.current_goal.originator_id: # Ensure originator is set if not already
            self.current_goal.originator_id = self.name if self.current_goal.type != GoalType.IDLE else "SystemInit"

        self.max_inventory_items = max_inventory_items
        # self.hauling_info attribute is fully removed. Logic relies on current_goal.parameters.
        # self.counting_target_stockpile_name: Optional[str] = None # Attribute removed.
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False

        self.rank: str = rank
        self.liege: Optional[str] = liege
        self.vassals: List[str] = vassals if vassals is not None else []
        self.assigned_tasks: List[Dict] = [] # TODO: Re-evaluate if this is needed with Goal objects
        self.performance_rating: str = "Not Evaluated"
        self.last_performance_review_day: Optional[int] = None
        self.warning_count: int = 0
        self.resource_to_fetch: Optional[Dict] = None # Params for Fetch Resource goals
        self.workshop_location: Optional[Tuple[int,int]] = None # Params for Craft Order goal
        self.equipped_tool: Optional[Dict] = None
        self.task_work_progress: int = 0 # Progress for generic tasks
        self.tool_to_fetch_type: Optional[str] = None # Parameter for FETCH_TOOL goal
        self.fetching_tool_info: Optional[Dict] = None # Intermediate state for FETCH_TOOL
        self.goal_before_fetching_tool: Optional[Goal] = None # Store previous Goal object
        self.current_task_def_name: Optional[str] = None # For _execute_generic_task, could be part of GATHER_RESOURCE params
        self._mc_item_check_idx: int = 0

        self.is_sick: bool = False
        self.sickness_severity: int = 0
        self.is_injured: bool = False
        self.injury_severity: int = 0
        self.appointed_by: Optional[str] = None

        self.known_characters: List[str] = []
        self.opinions: Dict[str, Dict[str, int]] = {}
        self.dialogue_history: List[Dict[str, Any]] = []
        self.known_events: List[str] = []

        if 'Social' not in self.needs: self.needs['Social'] = 70 # Will be reframed as Belonging later or coexist
        if 'Energy' not in self.needs: self.needs['Energy'] = 100
        # Initialize new complex needs if not provided
        if 'Safety' not in self.needs: self.needs['Safety'] = config.NEED_SAFETY_DEFAULT
        if 'Belonging' not in self.needs: self.needs['Belonging'] = config.NEED_BELONGING_DEFAULT
        if 'Esteem' not in self.needs: self.needs['Esteem'] = config.NEED_ESTEEM_DEFAULT


        self.active_build_order_id: Optional[str] = None # ID of the WorkOrder
        self.materials_gathered_for_build: bool = False
        self.building_site_target: Optional[Tuple[int, int]] = None # Parameter for EXECUTE_BUILD_ORDER
        self.current_building_project: Optional[str] = None # Blueprint key, parameter for EXECUTE_BUILD_ORDER

        # Mood related attributes
        self.mood_score: int = config.MOOD_SCORE_NEUTRAL_START
        self.mood: str = "Neutral" # Initial descriptive mood, will be updated by _determine_mood_level
        # self.mood_tendency: Optional[str] = None # Example: "Optimistic", "Pessimistic" - for future enhancement
        self._determine_mood_level() # Set initial mood string based on score

        # Reputation attribute
        self.reputation_score: int = 0 # Initialize reputation
        self.known_rumor_ids: Set[str] = set() # For tracking rumors known by this character

    def update_reputation(self, change: int, reason: Optional[str] = None, world: Optional['World'] = None):
        """Updates reputation score, clamps it, and logs the change."""
        old_score = self.reputation_score
        self.reputation_score += change
        self.reputation_score = max(config.REPUTATION_SCORE_MIN, min(config.REPUTATION_SCORE_MAX, self.reputation_score))

        if reason and old_score != self.reputation_score:
            log_message = f"Reputation score changed by {change} to {self.reputation_score}. Reason: {reason}"
            self.add_memory(log_message)
            print(f"LOG: {self.name}'s {log_message}")
            if world and abs(change) >= config.REPUTATION_FOR_RUMOR_THRESHOLD:
                self._try_generate_rumor_from_reputation(change, reason, world)


    def _try_generate_rumor_from_reputation(self, rep_change: int, reason: str, world: 'World'):
        if not world.game_time:
            return

        normalized_reason = reason.lower().replace(" ", "_")
        normalized_reason = normalized_reason.split("(")[0].strip()
        if not normalized_reason:
            normalized_reason = "reputation_shift"

        is_positive = rep_change > 0
        sentiment_suffix = "positive" if is_positive else "negative"
        content_key = f"{normalized_reason}_{sentiment_suffix}"

        initial_strength = config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT
        if abs(rep_change) >= config.REPUTATION_FOR_RUMOR_THRESHOLD * 2:
            initial_strength = config.RUMOR_INITIAL_STRENGTH_SIGNIFICANT_EVENT

        rumor = Rumor(
            subject_char_id=self.name,
            content_key=content_key,
            initial_strength=initial_strength,
            creation_day=world.game_time.current_day,
            is_positive=is_positive,
            original_source_char_id=self.name,
        )
        world.add_rumor(rumor)
        self.known_rumor_ids.add(rumor.rumor_id)
        world.add_notable_event(
            "ReputationRumor",
            {
                "summary": f"Rumor about {self.name}'s reputation change ({sentiment_suffix}).",
                "subject": self.name,
                "sentiment": sentiment_suffix,
            },
        )
        self.add_memory(f"Word may spread ({rumor.rumor_id[:4]}) about me: {content_key}.")


    def _determine_mood_level(self) -> str:
        """Determines descriptive mood based on mood_score."""
        # Iterate MOOD_LEVELS (sorted by score descending) to find the first match
        sorted_mood_levels = sorted(config.MOOD_LEVELS.items(), key=lambda item: item[1], reverse=True)

        current_mood_name = "Neutral" # Default if no thresholds met (should not happen with Neutral at -20)
        for mood_name, threshold in sorted_mood_levels:
            if self.mood_score >= threshold:
                current_mood_name = mood_name
                break
        # Special case for Neutral, as its threshold is a lower bound of a band
        if self.mood_score < config.MOOD_LEVELS["Neutral"] and self.mood_score > config.MOOD_LEVELS.get("Displeased", -50): # Check if it's above Displeased but below Neutral's lower bound
             # This logic ensures that scores between Displeased's threshold and Neutral's threshold are correctly Neutral if not caught by other positive moods.
             # E.g. if Neutral is -20, Content is 20. A score of 5 should be Content. A score of -10 should be Neutral.
             # A score of -30 should be Displeased.
             # The sort order handles positive moods. For negative, we need to ensure Neutral band.
             if self.mood_score >= config.MOOD_LEVELS["Neutral"]: # Scores from -20 up to Content's threshold (20)
                 pass # Already correctly assigned by sorted list or will be Neutral if nothing else matches above it
             elif self.mood_score > config.MOOD_LEVELS.get("Displeased", -50): # e.g. -20 < score < -50
                 # This means it fell through all positive moods and Content, so it should be Neutral if above Displeased.
                 # However, the sorted list from highest to lowest should correctly assign "Neutral" for scores like -10.
                 # Let's re-verify the logic for MOOD_LEVELS["Neutral"] = -20
                 # If score is 10, "Neutral" is chosen (correct, as it's < 20 for Content)
                 # If score is -10, "Neutral" is chosen (correct)
                 # If score is -30, "Displeased" is chosen (correct, as it's < -20 for Neutral and >= -50 for Displeased)
                 # The initial sort and break should handle this correctly.
                 pass


        if self.mood != current_mood_name:
            self.add_memory(f"My mood changed to {current_mood_name} (Score: {self.mood_score}).")
            self.mood = current_mood_name
        return self.mood

    def update_mood_score(self, change: int, reason: Optional[str] = None):
        """Updates mood score, clamps it, and updates descriptive mood."""
        old_score = self.mood_score
        self.mood_score += change
        self.mood_score = max(config.MOOD_SCORE_MIN, min(config.MOOD_SCORE_MAX, self.mood_score))

        if reason and old_score != self.mood_score:
            self.add_memory(f"Mood score changed by {change} to {self.mood_score}. Reason: {reason}")

        self._determine_mood_level() # Update descriptive mood

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
            self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5) # Skill increase boosts esteem
            self.add_memory(f"Leveling up my {skill_name} skill to {skill_data['level']} boosted my esteem. Esteem: {self.needs['Esteem']}")
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
            self.current_goal = self.get_default_goal()
            return

        order = world.get_work_order_by_id(self.active_build_order_id)
        if not order or order.status != "InProgress" or order.assigned_to != self.name:
            self._reset_building_state()
            self.current_goal = self.get_default_goal()
            return

        # Ensure needs are imported if used here, for now, assume energy is checked in decide_action
        # from .data import STRUCTURE_BLUEPRINTS # Moved to top-level import if not already there
        # For Phased Construction, STRUCTURE_BLUEPRINTS must be accessible. Assuming it is via top-level.
        # from .building import Building # For instantiation, assuming top-level.

        structure_blueprint_key = order.details["structure_type"]
        structure_bp_data = STRUCTURE_BLUEPRINTS.get(structure_blueprint_key) # Access directly after import
        if not structure_bp_data:
            order.status = "Denied"; order.denial_reason = f"Unknown blueprint {structure_blueprint_key}"
            self._reset_building_state(); self.current_goal = DEFAULT_IDLE_GOAL(self.name); return

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
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Laid foundation for {target_building.display_name}")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 4) # Laying foundation is a good step
                self.add_memory(f"Laying foundation for {target_building.display_name} boosted my esteem. Esteem: {self.needs['Esteem']}")


            # Work on the building
            if target_building and not target_building.is_operational:
                base_build_progress = 1.0 # Base progress per tick for construction
                mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
                progress_this_tick = base_build_progress * mood_productivity_modifier
                if mood_productivity_modifier != 1.0:
                    self.add_memory(f"My mood ({self.mood}) is affecting my work on {target_building.display_name} (Modifier: {mood_productivity_modifier:.2f}).")

                construction_skill_level = self.skills.get("Construction", {}).get("level", 0)
                progress_this_tick *= (1 + construction_skill_level * 0.1) # Skill modifier

                # Could add trait effects (Diligent, Lazy) here similar to generic_task if desired
                # For now, primarily mood and skill.

                prev_phase_idx = target_building.current_phase_index
                actual_progress = target_building.work_on(max(0, progress_this_tick)) # Ensure progress isn't negative

                if actual_progress > 0:
                    self._grant_skill_experience("Construction", actual_progress * 0.5, world)

                self.add_memory(f"Worked on {target_building.display_name} (Phase: {target_building.get_current_phase_name()}, +{actual_progress:.1f} prog).")

                if target_building.current_phase_index != prev_phase_idx:
                    self.add_memory(f"{target_building.display_name} advanced to phase: {target_building.get_current_phase_name()}.")

                if target_building.is_operational:
                    order.status = "Completed"
                    self.add_memory(f"Completed Build WO {order.order_id} for {target_building.display_name}.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR, f"Completed building {target_building.display_name}")
                    self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 10) # Completing a whole building is a major esteem boost
                    self.add_memory(f"Completing the building {target_building.display_name} greatly boosted my esteem. Esteem: {self.needs['Esteem']}")
                    self._receive_payment(JOB_SALARIES.get("Execute Build Order", 25), f"completing {target_building.display_name}", world)
                    self._reset_building_state()
                    self.current_goal = self.get_default_goal() # Changed from create_goal_from_job
                    return
            elif target_building and target_building.is_operational: # Already completed (e.g. found it already done)
                if order.status != "Completed": # Only give mood boost if we are the one marking it complete
                    order.status = "Completed"
                    self.add_memory(f"Found Build WO {order.order_id} for {target_building.display_name} was already completed.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR / 2, f"Found building {target_building.display_name} already complete") # Half points for finding it done
                self._reset_building_state()
                self.current_goal = self.get_default_goal() # Changed from create_goal_from_job
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
        self.crafting_progress = 0; self.workshop_location = None
        # self.hauling_info = None # Attribute removed

    def to_dict(self):
        """Converts the character object to a dictionary for serialization."""
        return {
            "name": self.name,
            "personality": self.personality,
            "traits": self.traits,
            "skills": self.skills,
            "x": self.x,
            "y": self.y,
            "inventory": self.inventory,
            "memory": self.memory,
            "needs": self.needs,
            "job": self.job,
            "money": self.money,
            "current_goal": self.current_goal.to_dict() if self.current_goal else None,
            "rank": self.rank,
            "liege": self.liege,
            "vassals": self.vassals,
            "is_sick": self.is_sick,
            "sickness_severity": self.sickness_severity,
            "is_injured": self.is_injured,
            "injury_severity": self.injury_severity,
            "supervisor_name": self.supervisor_name,
            "subordinates_names": self.subordinates_names,
            "performance_rating": self.performance_rating,
            "warning_count": self.warning_count,
            "known_characters": self.known_characters,
            "relationships": self.relationships,
            "opinions": self.opinions,
            "dialogue_history": self.dialogue_history[-10:] # Return last 10 for brevity
        }

    def __str__(self):
        goal_str = str(self.current_goal) if self.current_goal else "None"
        base_info = (f"Character(Name: {self.name}, Rank: {self.rank}, Job: {self.job}, Pos: ({self.x},{self.y}), Goal: {goal_str}, WO: {self.active_work_order_id}, Load: {self.get_inventory_load()}/{self.max_inventory_items})")
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

    def _receive_payment(self, amount: int, reason: str, world: Optional['World'] = None):
        """Handles wages, routing through the world's treasury when available."""
        if amount <= 0:
            return

        paid_amount, owed_amount = amount, 0
        if world:
            paid_amount, owed_amount = world.process_payment(self, amount, reason)
        else:
            self.money += amount

        if paid_amount > 0:
            self.add_memory(f"Received {paid_amount} coins for {reason}.")
            self.update_mood_score(config.MOOD_CHANGE_GOT_PAID, f"Got paid for {reason}")
        if owed_amount > 0:
            self.add_memory(f"Still owed {owed_amount} coins for {reason}.")
            self.update_mood_score(getattr(config, "MOOD_CHANGE_PAYMENT_DELAY", -5), "Wages delayed")

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

        speed_modifier = 1.0
        if hasattr(world, "get_travel_speed_modifier"):
            speed_modifier = world.get_travel_speed_modifier()

        if speed_modifier < 1.0 and random.random() > speed_modifier:
            if random.random() < 0.15:
                weather_desc = getattr(world, "weather", "difficult").lower()
                self.add_memory(f"Travel slowed by {weather_desc} conditions.")
            return

        # print(f"DEBUG {self.name}: move_towards ({target_x},{target_y}). Current: ({self.x},{self.y}). Trying ({norm_dx},{norm_dy}) first.")
        if self.move(norm_dx, norm_dy, world):
            # print(f"DEBUG {self.name}: move_towards success via diagonal/direct ({norm_dx},{norm_dy}). New pos: ({self.x},{self.y})")
            if speed_modifier > 1.0:
                bonus_chance = min(speed_modifier - 1.0, 1.0)
                if random.random() < bonus_chance:
                    bonus_dx = target_x - self.x
                    bonus_dy = target_y - self.y
                    bonus_norm_dx = 0
                    bonus_norm_dy = 0
                    if bonus_dx > 0: bonus_norm_dx = 1
                    elif bonus_dx < 0: bonus_norm_dx = -1
                    if bonus_dy > 0: bonus_norm_dy = 1
                    elif bonus_dy < 0: bonus_norm_dy = -1
                    if bonus_norm_dx != 0 or bonus_norm_dy != 0:
                        self.move(bonus_norm_dx, bonus_norm_dy, world)
            return

        if norm_dx != 0 and norm_dy != 0: # If diagonal failed, try cardinal
            # print(f"DEBUG {self.name}: move_towards diagonal failed. Trying cardinal x ({norm_dx},0).")
            if self.move(norm_dx, 0, world):
                if speed_modifier > 1.0 and random.random() < min(speed_modifier - 1.0, 1.0):
                    bonus_dx = target_x - self.x
                    if bonus_dx != 0:
                        bonus_norm_dx = 1 if bonus_dx > 0 else -1
                        self.move(bonus_norm_dx, 0, world)
                # print(f"DEBUG {self.name}: move_towards success via cardinal x ({norm_dx},0). New pos: ({self.x},{self.y})")
                return
            # print(f"DEBUG {self.name}: move_towards cardinal x failed. Trying cardinal y (0,{norm_dy}).")
            if self.move(0, norm_dy, world):
                if speed_modifier > 1.0 and random.random() < min(speed_modifier - 1.0, 1.0):
                    bonus_dy = target_y - self.y
                    if bonus_dy != 0:
                        bonus_norm_dy = 1 if bonus_dy > 0 else -1
                        self.move(0, bonus_norm_dy, world)
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

    def job_default_goal_type_str(self) -> str: # Returns a string representing the goal type or job title
        if self.job == "Woodcutter": return "Perform Woodcutter Duties"
        if self.job == "Stonemason": return "Perform Stonemason Duties"
        if self.job == "Master Craftsman": return "Assess Production Needs"
        if self.job == "Manager": return "Manage Subordinates"
        if self.job == "Bookkeeper": return "Maintain Ledger"
        if self.job == "Expedition Leader": return "Oversee Expedition"
        if self.job == "Mayor": return "Oversee Settlement"
        if self.job == "Chief Medical Officer": return "Oversee Medical Operations"
        if self.job == "Medic": return "Provide Medical Care"
        if self.job == "Sheriff": return "Maintain Peace in Settlement"
        if self.job == "Deputy": return "Patrol Area"
        if self.job == "Reeve": return "Manage Estate"
        if self.job == "Bailiff": return "Assist Reeve"
        if self.rank in ["Noble Lord", "Baron"] and not self.subordinates_names:
            return "Oversee Domain"
        elif self.rank in ["Noble Lord", "Baron"]:
            return "Manage Subordinates"
        return "Idle" # Corresponds to GoalType.IDLE

    def get_default_goal(self) -> Goal:
        job_goal_str = self.job_default_goal_type_str()
        goal = create_goal_from_job(job_goal_str, self.name)
        return goal if goal else Goal(GoalType.IDLE, assignee_id=self.name, originator_id="SystemDefault")

    def _execute_fetch_tool(self, world: 'World') -> bool: # True if still fetching, False if done/failed
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
            # NEW: Check market if no tool is available
            # Find a tool of the required type from the market prices
            tool_to_buy = None
            market_items = getattr(world, "market_prices", {})
            for item_name in market_items.keys():
                price = world.get_market_price(item_name) if hasattr(world, "get_market_price") else market_items.get(item_name)
                if item_name in BLUEPRINTS and BLUEPRINTS[item_name].get("tool_type") == self.tool_to_fetch_type:
                    if price is not None and self.money >= price:
                        tool_to_buy = item_name
                        break

            if tool_to_buy:
                self.add_memory(f"No {self.tool_to_fetch_type} in stockpiles. Decided to buy one.")
                self.current_goal = Goal(GoalType.SEEK_TO_BUY_ITEM, assignee_id=self.name, originator_id=self.name, parameters={"item_name": tool_to_buy})
                return False # Let the dispatcher handle the new goal

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
                else: # Failed to equip for some reason
                    self.current_goal = self.goal_before_fetching_tool or DEFAULT_IDLE_GOAL(self.name)
                    self.tool_to_fetch_type = None; self.fetching_tool_info = None; self.goal_before_fetching_tool = None
                    return False
            else: # Failed to remove from stockpile (e.g. suddenly empty)
                self.fetching_tool_info = None # Force re-scan for tool
                return True # Still trying to fetch
        else:
            self.move_towards(spot[0], spot[1], world)
            return True

    def _execute_generic_task(self, world: 'World', task_name: str) -> bool: # True if task action taken, False if tool fetch needed
        if task_name not in JOB_TASK_DEFINITIONS:
            self.current_goal = self.get_default_goal()
            return False
        task_def = JOB_TASK_DEFINITIONS[task_name]; tool_type = task_def.get("required_tool_type")
        # self.current_task_def_name = task_name # This is already set by the calling gather function
        if tool_type and (not self.equipped_tool or self.equipped_tool.get("tool_type") != tool_type):
            if not self.goal_before_fetching_tool : self.goal_before_fetching_tool = self.current_goal
            # self.current_goal = "Fetch Tool"
            self.current_goal = Goal(GoalType.FETCH_TOOL, assignee_id=self.name, originator_id=self.name, parameters={"tool_type": tool_type})
            self.tool_to_fetch_type = tool_type # Still needed by _execute_fetch_tool internal logic
            self.task_work_progress = 0
            return False

        # --- Mood, Trait & Health Effects on Progress ---
        base_progress_per_tick = 1.0

        # Mood Effect
        mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
        current_progress_gain = base_progress_per_tick * mood_productivity_modifier
        if mood_productivity_modifier != 1.0:
            self.add_memory(f"My mood ({self.mood}) is affecting my work on {task_name} (Modifier: {mood_productivity_modifier:.2f}).")

        is_lazy_this_tick = False

        # Health Effects on Progress (Applied multiplicatively to mood-adjusted progress)
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

        # Trait Effects on Progress
        # Lazy trait can override everything if triggered
        if "Lazy" in self.traits and not "Focused" in self.traits: # Focused can counteract Lazy's slacking
            if random.random() < 0.25: # 25% chance to be lazy
                current_progress_gain = 0
                is_lazy_this_tick = True
                self.add_memory(f"Felt lazy and decided to slack off for a bit while working on '{task_name}'.")

        if current_progress_gain > 0 and not is_lazy_this_tick: # Positive traits only apply if not slacking and some progress is possible
            if "Diligent" in self.traits:
                if random.random() < 0.25:
                    current_progress_gain += 0.5 * base_progress_per_tick # Diligent bonus based on base, not already modified
                    self.add_memory(f"Worked with extra diligence on '{task_name}'.")
            elif "Focused" in self.traits:
                if random.random() < 0.10:
                    current_progress_gain += 0.25 * base_progress_per_tick
                    self.add_memory(f"Remained focused and made good progress on '{task_name}'.")

        current_progress_gain = max(0, current_progress_gain)
        self.task_work_progress += current_progress_gain

        if is_lazy_this_tick and current_progress_gain == 0: # If slacked, end tick here
            return True

        # --- Task Completion and Yield ---
        while self.task_work_progress >= task_def.get("base_time_per_yield", 1):
            res_prod = task_def.get("resource_produced")
            base_yield_amount = task_def.get("base_yield",1)

            # Trait Effect on Yield (e.g., Strong)
            final_yield_amount = base_yield_amount
            if "Strong" in self.traits and res_prod in ["Wood", "Stone", "Iron Ore"]: # Assuming Strong applies to these
                if random.random() < 0.20: # 20% chance for +1 bonus
                    final_yield_amount += 1
                    self.add_memory(f"Put my strength into '{task_name}' and got a bit extra {res_prod}.")

            if res_prod:
                env_multiplier = 1.0
                if hasattr(world, "get_resource_yield_multiplier"):
                    env_multiplier = world.get_resource_yield_multiplier(res_prod)
                if env_multiplier != 1.0:
                    adjusted_amount = int(round(final_yield_amount * env_multiplier))
                    if final_yield_amount > 0 and adjusted_amount == 0 and env_multiplier > 0:
                        adjusted_amount = 1
                    final_yield_amount = max(0, adjusted_amount)
                    weather_desc = getattr(world, "weather", "steady")
                    self.add_memory(
                        f"Environmental conditions ({weather_desc}, {world.season}) adjusted {res_prod} yield x{env_multiplier:.2f}."
                    )

            can_add_to_inv = self.max_inventory_items - self.get_inventory_load()
            actual_yield_taken = min(final_yield_amount, can_add_to_inv)

            if actual_yield_taken <= 0:
                if final_yield_amount > 0: # Tried to yield something but inventory was full
                    print(f"{self.name} inventory full for {task_name} (tried to yield {final_yield_amount} {res_prod}).")
                break # Exit the while loop if inventory is full

            self.inventory[res_prod] = self.inventory.get(res_prod,0) + actual_yield_taken
            tool_name_mem = self.equipped_tool['name'] if self.equipped_tool else 'hands'
            self.add_memory(f"Task '{task_name}': got {actual_yield_taken} {res_prod} (base: {base_yield_amount}) with {tool_name_mem}.")
            print(f"{self.name} task '{task_name}' yielded {actual_yield_taken} {res_prod} (base: {base_yield_amount}).")

            self.task_work_progress -= task_def.get("base_time_per_yield", 1) # Subtract cost of one yield

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
                    self.update_mood_score(config.MOOD_CHANGE_TOOL_BROKE, f"My {self.equipped_tool['name']} broke during task '{task_name}'")
                    self.needs['Safety'] = max(config.NEED_SCORE_MIN, self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 10) # Tool breaking is startling/unsafe
                    self.add_memory(f"Tool breaking made me feel less safe. Safety: {self.needs['Safety']}")
                    self.unequip_tool() # unequip_tool sets self.equipped_tool to None
                    break # Stop working if tool broke

            # Mood and Esteem boost for successful yield
            if actual_yield_taken > 0 and res_prod: # Ensure something was actually yielded
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Successfully gathered {res_prod} from task '{task_name}'")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 2) # Small esteem boost
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

            # --- Mood, Trait, Skill Effects on Crafting Progress ---
            base_craft_progress = 1.0
            mood_productivity_modifier = config.MOOD_EFFECT_PRODUCTIVITY.get(self.mood, 1.0)
            current_crafting_progress_gain = base_craft_progress * mood_productivity_modifier
            if mood_productivity_modifier != 1.0:
                 self.add_memory(f"My mood ({self.mood}) is affecting my crafting of {item_name} (Modifier: {mood_productivity_modifier:.2f}).")

            crafting_skill_level = self.skills.get("Crafting", {}).get("level", 0)
            skill_modifier = 1 + (crafting_skill_level * 0.05) # 5% progress boost per skill level
            current_crafting_progress_gain *= skill_modifier

            is_slacking_craft = False

            if "Lazy" in self.traits and not "Focused" in self.traits:
                if random.random() < 0.25:
                    current_crafting_progress_gain = 0
                    is_slacking_craft = True
                    self.add_memory(f"Felt lazy and slacked off while crafting {item_name} for WO {order.order_id}.")

            if current_crafting_progress_gain > 0 and not is_slacking_craft:
                if "Diligent" in self.traits:
                    if random.random() < 0.25:
                        current_crafting_progress_gain += 0.5 * base_craft_progress # Bonus based on base
                        self.add_memory(f"Worked with extra diligence crafting {item_name}.")
                elif "Focused" in self.traits:
                    if random.random() < 0.10:
                        current_crafting_progress_gain += 0.25 * base_craft_progress
                        self.add_memory(f"Remained focused while crafting {item_name}.")

            current_crafting_progress_gain = max(0, current_crafting_progress_gain)
            self.crafting_progress += current_crafting_progress_gain

            if is_slacking_craft and current_crafting_progress_gain == 0:
                return # End tick here if slacked off

            while self.crafting_progress >= craft_time_per_unit:
                # Check if there are enough materials for another unit
                can_craft_another = True
                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    if self.inventory.get(res, 0) < req_qty_per_unit:
                        can_craft_another = False
                        self.add_memory(f"Ran out of {res} to craft another {item_name}.")
                        break

                if not can_craft_another:
                    self.materials_gathered_for_wo = False # Set flag to re-gather
                    break # Exit the while loop

                for res, req_qty_per_unit in blueprint["required_resources"].items():
                    self.inventory[res] -= req_qty_per_unit
                    if self.inventory[res] <= 0: self.inventory.pop(res,None)

                self.inventory[item_name] = self.inventory.get(item_name, 0) + 1
                self.add_memory(f"Crafted 1 {item_name} for WO {order.order_id}.")
                print(f"{self.name} CRAFTED 1 {item_name}. Inv has: {self.inventory.get(item_name,0)}/{item_qty_total} for WO {order.order_id}.")
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, f"Crafted a {item_name}")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 3)
                self.add_memory(f"Crafting {item_name} boosted my esteem. Esteem: {self.needs['Esteem']}")
                self._grant_skill_experience("Crafting", 1.2, world)

                # --- Trigger Praise from Witnesses ---
                for witness in world.get_nearby_characters(self, radius=3):
                    if witness.current_goal.type in [GoalType.GREET_CHARACTER, GoalType.SMALL_TALK, GoalType.ARGUE, GoalType.PRAISE_CHARACTER]:
                        continue
                    if random.random() < 0.2:
                        witness.add_memory(f"Was impressed by {self.name} crafting a {item_name}.")
                        witness.current_goal = Goal(GoalType.PRAISE_CHARACTER, assignee_id=witness.name, originator_id=witness.name, parameters={"target_char_name": self.name})
                        break

                self.crafting_progress -= craft_time_per_unit # Subtract cost of one unit

                if self.inventory.get(item_name,0) >= item_qty_total:
                    self.items_crafted_for_wo = True
                    self.add_memory(f"All {item_qty_total} {item_name}(s) for WO {order.order_id} crafted.")
                    self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR / 2, f"Finished crafting all items for WO {order.order_id}")
                    self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5)
                    self.add_memory(f"Completing all crafting for WO {order.order_id} greatly boosted my esteem. Esteem: {self.needs['Esteem']}")
                    break # Exit while loop after finishing order
            return
        if self.items_crafted_for_wo: # This block means all items are crafted and now handles hauling/completion
            # Check if items are still in inventory (i.e., not yet hauled)
            items_to_haul_qty = self.inventory.get(item_name, 0)

            if items_to_haul_qty > 0: # Still items to haul
                # The old self.hauling_info is now directly passed as parameters.
                haul_params = {"resource":item_name, "quantity":items_to_haul_qty, "for_wo_id":order.order_id, "is_crafted_item":True}
                self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters=haul_params)
                return
            else: # All items crafted AND all items hauled (inventory of this item is 0)
                order.status = "Completed"
                self.add_memory(f"Completed and Stocked all items for WO {order.order_id} ({item_name}).")
                print(f"{self.name} COMPLETED/STOCKED WO {order.order_id} ({item_name}).")
                self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR, f"Fully completed WO {order.order_id}")
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 8) # Fully completing a WO is a major esteem boost
                self.add_memory(f"Fully completing and stocking WO {order.order_id} gave a major boost to my esteem. Esteem: {self.needs['Esteem']}")
                self._receive_payment(JOB_SALARIES.get("Execute Craft Order", 10), f"completing WO for {item_name}", world)
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
            self.current_goal = self.get_default_goal()
            return
        target_item_names = list(self.managed_item_targets.keys())
        if not target_item_names:
            self.current_goal = self.get_default_goal()
            return
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
                self._receive_payment(JOB_SALARIES.get("Assess Production Needs", 10), f"creating WO for {item_name}", world)
                item_processed_this_tick = True; self._mc_item_check_idx = (current_idx + 1) % len(target_item_names); break
        if not item_processed_this_tick:
            self.current_goal = self.get_default_goal()
            self._mc_item_check_idx = 0

    # Renamed from _execute_manage_work_orders to _execute_manage_subordinates
    def _execute_manage_subordinates(self, world: 'World'):
        if not (self.job == "Manager" or self.rank in ["Noble Lord", "Baron"]) or not self.subordinates_names:
            self.current_goal = self.get_default_goal()
            return # Not a manager or no one to manage

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
                self.current_goal = self.get_default_goal() # Re-evaluate next tick
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

                # Relationship influence (scaled)
                # A score of -100 adds +0.25 to chance, a score of 100 subtracts -0.25
                relationship_modifier = (relationship_to_sub / 100.0) * -0.25
                warning_chance += relationship_modifier

                warning_chance = max(0.05, min(0.95, warning_chance)) # Clamp chance

                if random.random() < warning_chance:
                    self.add_memory(f"Considering issuing warning to {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {warning_chance:.2f}).")
                    if subordinate.job == "Bookkeeper" and any(world.ledger.get_stockpile_last_update_day(sp.name) is None or (world.game_time.current_day - world.ledger.get_stockpile_last_update_day(sp.name) > config.STALE_THRESHOLD_DAYS + 2) for sp in world.stockpiles):
                        reason_for_warning = "Ledger maintenance remains unsatisfactory."

                    self.issue_warning(subordinate.name, world, reason_for_warning)
                    # Issuing a warning affects relationships
                    self.modify_relationship(subordinate.name, -10, world, reason=f"Issued warning to them for {reason_for_warning}")
                    subordinate.modify_relationship(self.name, -15, world, reason=f"Received warning from them about {reason_for_warning}")
                    self.current_goal = self.get_default_goal() # Action taken
                    return

            # --- Firing Logic ---
            # Condition for considering firing: performance is "Poor" AND at/above warning threshold.
            if subordinate.performance_rating == "Poor" and \
               subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD and \
               subordinate.performance_rating != "Fired":

                firing_chance = 0.5 # Base chance
                if "Ruthless" in self.traits or self.personality == "Stern": firing_chance += 0.25
                if "Compassionate" in self.traits or self.personality == "Kind": firing_chance -= 0.25

                # Relationship influence (scaled)
                # A score of -100 adds +0.3 to chance, a score of 100 subtracts -0.4
                if relationship_to_sub < 0:
                    relationship_modifier = (relationship_to_sub / 100.0) * -0.30 # e.g. -100 score -> +0.3 chance
                else:
                    relationship_modifier = (relationship_to_sub / 100.0) * -0.40 # e.g. +100 score -> -0.4 chance
                firing_chance += relationship_modifier

                firing_chance = max(0.01, min(0.99, firing_chance)) # Clamp chance

                self.add_memory(f"Considering firing {subordinate.name} (Perf: {subordinate.performance_rating}, Warns: {subordinate.warning_count}, Rel: {relationship_to_sub}, Chance: {firing_chance:.2f}).")
                if random.random() < firing_chance:
                    self.fire_subordinate(subordinate.name, world)
                    # Firing drastically affects relationship (mostly for the record now)
                    self.modify_relationship(subordinate.name, -100, world, reason="Fired them.")
                    # No need for subordinate to update relationship, they are 'gone' in terms of this dynamic with this supervisor
                    self.current_goal = self.get_default_goal() # Action taken
                    return

        # If no specific management action taken for any subordinate, manager might do other things or idle.
        # Or, if they just managed work orders, they might still want to check subordinates in the same tick if logic allows.
        # For now, one significant management action (review, warn, fire) or WO approval per "Manage Subordinates" cycle.
        # For now, just idle and wait for next cycle.
        self.current_goal = self.get_default_goal()


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
        if can_approve:
            order_to_process.status = "Approved"; order_to_process.approved_by = self.name; order_to_process.approval_day = world.game_time.current_day; self.add_memory(f"Approved WO {order_to_process.order_id}"); print(f"{self.name} (Manager) APPROVED {order_to_process.order_id[:8]}.")
            self._receive_payment(JOB_SALARIES.get("Manage Subordinates", 3), f"reviewing WO {order_to_process.order_id[:4]}", world)
        else:
            order_to_process.status = "Denied"; order_to_process.denied_by = self.name; order_to_process.denial_reason = f"Insuff: {', '.join(missing_notes) or 'stale data'}"; self.add_memory(f"Denied WO {order_to_process.order_id}"); print(f"{self.name} (Manager) DENIED {order_to_process.order_id[:8]}. Reason: {order_to_process.denial_reason}")
            self._receive_payment(JOB_SALARIES.get("Manage Subordinates", 3), f"reviewing WO {order_to_process.order_id[:4]}", world)
    def _execute_maintain_ledger(self, world: 'World'):
        if self.job != "Bookkeeper":
            self.current_goal = self.get_default_goal()
            return
        stockpiles_to_check=world.stockpiles; target_sp=None; min_day=float('inf')
        if not stockpiles_to_check:
            self.current_goal = self.get_default_goal()
            return
        for sp_obj in stockpiles_to_check:
            day=world.ledger.get_stockpile_last_update_day(sp_obj.name)
            if day is None:target_sp=sp_obj;break
            if day<world.game_time.current_day and day<min_day:min_day=day;target_sp=sp_obj
        if target_sp is None :
            self.current_goal = self.get_default_goal()
            return
        # self.counting_target_stockpile_name=target_sp.name # Removed
        self.current_goal = Goal(GoalType.COUNT_STOCKPILE, assignee_id=self.name, originator_id=self.name, parameters={"stockpile_name": target_sp.name})
        self.decide_action(world) # To immediately process the new goal if possible

    def _execute_count_stockpile(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or not self.current_goal.parameters.get("stockpile_name"): # Ensure goal and params exist
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or self.get_default_goal()
            self.decide_action(world)
            return

        target_stockpile_name = self.current_goal.parameters.get("stockpile_name")
        if self.job != "Bookkeeper" or not target_stockpile_name : # Check job and if name is actually there
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or self.get_default_goal()
            self.decide_action(world)
            return

        stockpile_obj=world.get_stockpile_by_name(target_stockpile_name)

        if not stockpile_obj:
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or self.get_default_goal()
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
                    # print(f"{self.name} (Bookkeeper, Careless) may have miscounted {target_stockpile_name}. Actual: {actual_inventory}, Recorded for Ledger: {recorded_inventory}")

            world.ledger.update_stockpile_record(target_stockpile_name, recorded_inventory, world.game_time.current_day)
            self.add_memory(f"Counted {target_stockpile_name}"); print(f"{self.name} (Bookkeeper) finished counting {target_stockpile_name}. Ledger updated with: {recorded_inventory}. Day: {world.game_time.current_day}.")
            self._receive_payment(JOB_SALARIES.get("Maintain Ledger", 4), f"counting {target_stockpile_name}", world)
            self.current_goal = create_goal_from_job("Maintain Ledger", self.name) or self.get_default_goal()
            self.decide_action(world)
            return
        else:self.move_towards(spot[0],spot[1],world)

    def _execute_perform_woodcutter_duties(self, world: 'World'):
        if self.job!="Woodcutter":
            self.current_goal = self.get_default_goal()
            return
        quota=self.needs.get("Wood",5);inv_val=self.inventory.get("Wood",0) # Default quota, can be overridden by Goal params
        # Check current_goal parameters for specific quota if set by a manager, etc.
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
            self.decide_action(world) # Process new goal
        # If no next_goal_type, means current logic is fine, or it's already Idle/Wander
    def _execute_perform_stonemason_duties(self, world: 'World'):
        if self.job != "Stonemason":
            self.current_goal = self.get_default_goal()
            return
        quota = self.current_goal.parameters.get("quota", self.needs.get("Stone",5)) # Corrected: Use current_goal.parameters
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
            # self.current_goal = self.get_default_goal() # This line was an error and removed
            self.decide_action(world) # Process new goal
        # If no next_goal_type, means current logic is fine, or it's already Idle/Wander - or if the above didn't set a new goal, it implies current one continues or becomes default via decide_action

    def _execute_initiate_hauling(self, world: 'World'):
        # Parameters should be in self.current_goal.parameters
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

            # Pay for hauling if it's a primary job duty
            if self.job == "Woodcutter" and res == "Wood":
                self._receive_payment(JOB_SALARIES.get("Perform Woodcutter Duties", 5), f"hauling {res}", world)
            elif self.job == "Stonemason" and res == "Stone":
                self._receive_payment(JOB_SALARIES.get("Perform Stonemason Duties", 5), f"hauling {res}", world)

            self.current_goal = self.get_default_goal()
        else:
            self.move_towards(spot[0],spot[1],world)

    def _execute_gather_wood(self, world: 'World'): # Assumes current_goal is GATHER_RESOURCE for Wood
        task_loc = self.find_task_location("Chop Wood", world)
        if not task_loc :
            print(f"{self.name} can't find Forest for Chop Wood.")
            self.current_goal = self.get_default_goal()
            return
        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return
        if not self._execute_generic_task(world, "Chop Wood"): # Handles tool fetching if needed
            return # _execute_generic_task would have changed goal to Fetch Tool

        inv_wood = self.inventory.get("Wood",0)
        # Default job quota, could be overridden by goal parameters if a specific amount is requested
        job_quota = self.current_goal.parameters.get("quota", self.needs.get("Wood",5) if self.job == "Woodcutter" else float('inf'))

        directive = world.get_resource_directive("Wood") if hasattr(world, "get_resource_directive") else None
        if directive:
            job_quota = max(job_quota, directive.get("per_trip_quota", job_quota))
            if world.game_time and directive.get("last_reminded_day") != world.game_time.current_day:
                directive["last_reminded_day"] = world.game_time.current_day
                self.add_memory(
                    f"Following directive to bring back at least {directive['per_trip_quota']} Wood (set by {directive.get('originator', 'leadership')})."
                )

        if self.get_inventory_load()>=self.max_inventory_items or inv_wood >= job_quota :
            # self.current_goal = "Perform Woodcutter Duties" # old
            self.current_goal = create_goal_from_job("Perform Woodcutter Duties", self.name) or self.get_default_goal()


    def _execute_gather_stone(self, world: 'World'): # Assumes current_goal is GATHER_RESOURCE for Stone
        task_loc = self.find_task_location("Mine Stone", world)
        if not task_loc :
            print(f"{self.name} can't find Rocks for Mine Stone.")
            self.current_goal = self.get_default_goal()
            return
        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return
        if not self._execute_generic_task(world, "Mine Stone"): # Handles tool fetching
            return

        inv_stone = self.inventory.get("Stone",0)
        job_quota = self.current_goal.parameters.get("quota", self.needs.get("Stone",5) if self.job == "Stonemason" else float('inf'))

        directive = world.get_resource_directive("Stone") if hasattr(world, "get_resource_directive") else None
        if directive:
            job_quota = max(job_quota, directive.get("per_trip_quota", job_quota))
            if world.game_time and directive.get("last_reminded_day") != world.game_time.current_day:
                directive["last_reminded_day"] = world.game_time.current_day
                self.add_memory(
                    f"Settlement directive urges gathering {directive['per_trip_quota']} Stone before returning."
                )

        if self.get_inventory_load()>=self.max_inventory_items or inv_stone >= job_quota:
            # self.current_goal = "Perform Stonemason Duties" # old
            self.current_goal = create_goal_from_job("Perform Stonemason Duties", self.name) or self.get_default_goal()


    def _execute_gather_herbs(self, world: 'World'): # Assumes current_goal is GATHER_RESOURCE for Herbs
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
            self.current_goal = self.get_default_goal() # Or back to a job default goal
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
        directive = world.get_resource_directive("Herbs") if hasattr(world, "get_resource_directive") else None
        per_trip_quota = directive.get("per_trip_quota") if directive else None
        if directive and world.game_time and directive.get("last_reminded_day") != world.game_time.current_day:
            directive["last_reminded_day"] = world.game_time.current_day
            self.add_memory(
                f"Clinic request: return with at least {per_trip_quota} Herbs to support medicine."
            )

        if self.get_inventory_load() >= self.max_inventory_items or (
            per_trip_quota is not None and self.inventory.get("Herbs", 0) >= per_trip_quota
        ):
            self.add_memory("Inventory full of herbs.")
            # Decide what to do next, e.g., haul herbs or return to duties.
            # For a Medic/CMO, this might be returning to the clinic or seeking patients.
            # For now, set to Idle, which will trigger get_default_goal.
            self.current_goal = self.get_default_goal()
            # If a specific "Haul Herbs" goal exists, it could be set here.
            # e.g. self.current_goal = Goal(GoalType.INITIATE_HAULING, ..., {"resource": "Herbs"})

    def _execute_oversee_medical_operations(self, world: 'World'):
        if self.job != "Chief Medical Officer":
            self.current_goal = self.get_default_goal()
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
            self.current_goal = self.get_default_goal()
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
            self.current_goal = self.get_default_goal() # Reverts to job default next tick
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
            self._receive_payment(JOB_SALARIES.get("Provide Medical Care", 8), f"treating {target_patient.name}", world)
        else:
            self._grant_skill_experience("Medicine", 0.2, world) # Minor XP for attempt

        # After treatment, Medic might look for another patient or return to standby.
        # For now, will re-evaluate from top next tick.
        self.current_goal = self.get_default_goal() # Re-evaluate next patient or task
        return


    def _execute_oversee_expedition(self, world: 'World'):
         if self.job != "Expedition Leader":
            self.current_goal = self.get_default_goal()
            return
         if random.random() < 0.1: self.add_memory("Surveyed expedition progress.")
         self.current_goal = self.get_default_goal() # Expedition leaders might idle if nothing specific to do

    def _execute_oversee_settlement(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
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
            self.current_goal = Goal(GoalType.GIVE_SPEECH, assignee_id=self.name, originator_id=self.name)
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
                        current_holder.job = "Unemployed" # This will make their default goal Idle or similar
                        current_holder.current_goal = Goal(GoalType.IDLE, assignee_id=current_holder.name) # Explicitly set to Idle
                        current_holder.appointed_by = None
                        if current_holder.supervisor_name == self.name : current_holder.supervisor_name = None
                        if current_holder.name in self.subordinates_names: self.remove_subordinate(current_holder.name)
                        # Note: This doesn't automatically reassign their previous subordinates if they were a manager.
                    else:
                        self.add_memory(f"{current_holder.name}'s performance as {position_job_title} is deemed acceptable for now.")
        return

    def _execute_maintain_peace(self, world: 'World'): # For Sheriff
        if self.job != "Sheriff":
            self.current_goal = self.get_default_goal()
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
            self.current_goal = self.get_default_goal()
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
            self.current_goal = self.get_default_goal()
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
                self.current_goal = self.get_default_goal()
            else:
                self.add_memory(f"Moving towards {closest_medic.name} at ({closest_medic.x},{closest_medic.y}) for help.")
                self.move_towards(closest_medic.x, closest_medic.y, world)
        else: # Should not happen if medical_personnel list was populated
            self.add_memory("Could not determine closest medic. Resting.")
            self.current_goal = self.get_default_goal()
        return

    def _execute_report_to_liege(self, world: 'World'):
        if not self.liege:
            self.current_goal.set_failed(reason="Character has no liege.")
            self.current_goal = self.get_default_goal()
            return

        liege_char = world.get_character_by_name(self.liege)
        if not liege_char:
            self.add_memory(f"Could not find my liege, {self.liege}, to report to.")
            self.current_goal.set_failed(reason=f"Liege '{self.liege}' not found in world.")
            self.current_goal = self.get_default_goal()
            return

        distance = abs(self.x - liege_char.x) + abs(self.y - liege_char.y)
        if distance > 2:
            self.add_memory(f"Traveling to report to my liege, {self.liege}.")
            self.move_towards(liege_char.x, liege_char.y, world)
            return

        # At liege's location, deliver the report
        self.add_memory(f"I have arrived and reported to my liege, {self.liege}.")
        liege_char.add_memory(f"My vassal, {self.name}, has reported to me.")

        # Simple relationship boost for fulfilling duty
        self.modify_relationship(self.liege, 2, world, reason="Reported to them as a loyal vassal.")
        liege_char.modify_relationship(self.name, 1, world, reason="They fulfilled their duty and reported to me.")

        self.current_goal.set_completed()
        self.current_goal = self.get_default_goal()

    def _execute_manage_estate(self, world: 'World'):
        self.add_memory("Managing the estate. (Placeholder)")
        self.current_goal = self.get_default_goal()

    def _execute_assist_reeve(self, world: 'World'):
        self.add_memory("Assisting the reeve. (Placeholder)")
        self.current_goal = self.get_default_goal()

    def _execute_hold_high_court(self, world: 'World'):
        if not self.vassals:
            self.add_memory("I wish to hold high court, but I have no vassals to summon.")
            self.current_goal.set_failed(reason="No vassals to summon.")
            self.current_goal = self.get_default_goal()
            return

        # Check if court is already in session (i.e., vassals are on their way or present)
        if "vassals_summoned" not in self.current_goal.parameters:
            self.add_memory("I am holding high court. I will summon my vassals.")
            self.current_goal.parameters["vassals_summoned"] = []
            for vassal_name in self.vassals:
                vassal = world.get_character_by_name(vassal_name)
                if vassal:
                    # Assign a high-priority goal to attend court
                    vassal.current_goal = Goal(GoalType.ATTEND_HIGH_COURT,
                                              assignee_id=vassal.name,
                                              originator_id=self.name,
                                              priority=2, # High priority to override other tasks
                                              parameters={"liege_name": self.name})
                    self.current_goal.parameters["vassals_summoned"].append(vassal_name)
            # After summoning, the liege waits.
            self.add_memory("My vassals have been summoned. I shall await their arrival.")
            return

        # If vassals have been summoned, check if they have all arrived.
        all_vassals_present = True
        for vassal_name in self.current_goal.parameters["vassals_summoned"]:
            vassal = world.get_character_by_name(vassal_name)
            if not vassal:
                continue # Vassal might have been removed from the world

            distance = abs(self.x - vassal.x) + abs(self.y - vassal.y)
            if distance > 2: # 2 is the interaction distance
                all_vassals_present = False
                break

        if all_vassals_present:
            self.add_memory("All my vassals are present. The high court is now in session.")
            # The "court" itself is a placeholder action for now.
            world.add_event_log_message(f"{self.name} holds high court with their vassals.")
            # Relationship boosts for all involved.
            for vassal_name in self.vassals:
                vassal = world.get_character_by_name(vassal_name)
                if vassal:
                    self.modify_relationship(vassal_name, 3, world, reason="They attended my high court.")
                    vassal.modify_relationship(self.name, 2, world, reason="I attended their high court as a loyal vassal.")

            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
        else:
            self.add_memory("Waiting for all my vassals to arrive for high court.")
            # The liege just waits, doing nothing else this tick.

    def _execute_attend_high_court(self, world: 'World'):
        liege_name = self.current_goal.parameters.get("liege_name")
        if not liege_name:
            self.current_goal.set_failed(reason="No liege specified to attend court.")
            self.current_goal = self.get_default_goal()
            return

        liege_char = world.get_character_by_name(liege_name)
        if not liege_char:
            self.add_memory(f"I was summoned to court by {liege_name}, but I cannot find them.")
            self.current_goal.set_failed(reason=f"Liege '{liege_name}' not found.")
            self.current_goal = self.get_default_goal()
            return

        distance = abs(self.x - liege_char.x) + abs(self.y - liege_char.y)
        if distance > 2:
            self.add_memory(f"Traveling to attend the high court of my liege, {liege_name}.")
            self.move_towards(liege_char.x, liege_char.y, world)
            return

        # Arrived at court
        self.add_memory(f"I have arrived at the high court of my liege, {liege_name}.")
        # The vassal's goal is complete upon arrival. They will wait here (by going idle)
        # until the liege's goal completes.
        self.current_goal.set_completed()
        self.current_goal = self.get_default_goal() # Will likely idle here

    def _execute_give_speech(self, world: 'World'):
        if self.job != "Mayor": # Should be GoalType.GIVE_SPEECH
            self.current_goal = self.get_default_goal()
            return

        speech_topic = "the general state of the settlement and future prospects"
        campaign_promises = getattr(world, "campaign_promises", {}).get(self.name, [])
        if campaign_promises:
            relevant_promises = [p for p in campaign_promises if p.get("status") in ("pledged", "enacted")]
            if relevant_promises:
                chosen_promise = random.choice(relevant_promises)
                resource_focus = chosen_promise.get("resource")
                if resource_focus:
                    if chosen_promise.get("status") == "pledged":
                        speech_topic = f"my pledge to strengthen our {resource_focus} supplies"
                    else:
                        speech_topic = f"progress delivering stronger {resource_focus} stores"
                elif chosen_promise.get("type") == "community_event":
                    speech_topic = "keeping community spirit high"
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

        self.current_goal = self.get_default_goal() # Return to overseeing or default state
        return

    def _execute_wander(self, world: 'World'): # Assumes current_goal is WANDER
        moves = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            tx, ty = self.x + dx, self.y + dy
            if 0 <= tx < world.grid_size[0] and 0 <= ty < world.grid_size[1] and \
                    world.get_tile(tx, ty) not in ["Water", "Mountain", "Forest", "Rocks", "SP_Mai", "SP_Woo", "SP_Sto"] and \
                    not world.get_characters_at_location(tx, ty):
                moves.append((dx, dy))

        if moves:
            choice = random.choice(moves)
            self.move(choice[0], choice[1], world)

    # This is the redundant job_default_goal. The primary one is around line 480.
    # def job_default_goal(self) -> str: # Ensure this exists for the minimal decide_action
    #     if self.job == "Builder":
    #         return "Perform Builder Duties"
    #     # Add other job defaults here if necessary for other tests, but builder is key now
    #     return "Idle"

    def decide_action(self, world: 'World'):
        if not world.game_time:
            # self.current_goal = "Idle" # Will be refactored to Goal object
            self.current_goal = self.get_default_goal()
            return

        # Update mood based on critical complex needs
        self._update_mood_from_critical_needs()

        # Health check: If severely sick or injured, character may change goal
        # Thresholds for "severe" can be defined in config later
        # For now, let's use severity > 5 as a trigger to seek help.
        if self.current_goal.type != GoalType.SEEK_MEDICAL_ATTENTION: # Avoid interrupting if already seeking help
            if self.is_sick and self.sickness_severity > 5:
                self.add_memory(f"Feeling very sick (Severity: {self.sickness_severity}). Need medical attention.")
                self.update_mood_score(config.MOOD_CHANGE_NEED_CRITICAL * 2, f"Severely sick (severity: {self.sickness_severity})") # Larger mood hit for severe sickness
                self.current_goal = Goal(GoalType.SEEK_MEDICAL_ATTENTION, assignee_id=self.name, originator_id=self.name)
            elif self.is_injured and self.injury_severity > 5:
                self.add_memory(f"Badly injured (Severity: {self.injury_severity}). Need medical attention.")
                self.update_mood_score(config.MOOD_CHANGE_NEED_CRITICAL * 2, f"Severely injured (severity: {self.injury_severity})") # Larger mood hit
                self.current_goal = Goal(GoalType.SEEK_MEDICAL_ATTENTION, assignee_id=self.name, originator_id=self.name)

        # Hunger check: If hungry, character will prioritize eating or getting food.
        if self.needs.get('Hunger', 100) < config.HUNGER_THRESHOLD_EAT and self.current_goal.type not in [GoalType.EAT_FOOD, GoalType.SEEK_TO_BUY_ITEM]:
            if self.inventory.get("Food", 0) > 0:
                self.add_memory(f"I am hungry (Hunger: {self.needs.get('Hunger', 100)}). I will eat the food I have.")
                self.current_goal = Goal(GoalType.EAT_FOOD, assignee_id=self.name, originator_id=self.name, priority=2)
            else:
                self.add_memory(f"I am hungry (Hunger: {self.needs.get('Hunger', 100)}) and have no food. I must go to the market.")
                self.current_goal = Goal(GoalType.SEEK_TO_BUY_ITEM, assignee_id=self.name, originator_id=self.name, parameters={"item_name": "Food"}, priority=2)

        # Mood-driven goal check (simple example: seek solitude if very sad/stressed)
        # This should ideally be before job-default goals but after critical needs like medical attention.
        if self.current_goal.type not in [GoalType.SEEK_MEDICAL_ATTENTION, GoalType.ASK_FOR_HELP]: # Don't override critical states
            if self.mood in ["Sad", "Stressed", "Furious"] and random.random() < config.MOOD_DRIVEN_GOAL_CHANCE:
                # For now, SEEK_SOLITUDE will just make them Wander.
                # A more complex implementation could make them avoid others or go to a quiet spot.
                self.add_memory(f"Feeling {self.mood}, I need some time alone.")
                self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name, details="Seeking solitude due to mood.") # Wander is a simple proxy for solitude

        # If goal changed to Seek Medical Attention, execute that immediately this tick.
        if self.current_goal.type == GoalType.SEEK_MEDICAL_ATTENTION:
            pass # Let it fall through to goal execution or _execute_generic_task check

        # --- Complex Need-Driven Goal/Action Biases ---
        # These are checked if not already in a critical goal state like SEEK_MEDICAL_ATTENTION or ASK_FOR_HELP

        # Safety Need Bias
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD and \
           self.current_goal.type not in [GoalType.SEEK_MEDICAL_ATTENTION, GoalType.ASK_FOR_HELP, GoalType.WANDER]: # Avoid overriding if already wandering for mood
            # If safety is critical, character might prioritize less risky actions or seek "safer" spots (proxied by Wander)
            if random.random() < 0.3: # 30% chance to override current non-critical goal to Wander for safety
                self.add_memory(f"Feeling very unsafe (Safety: {self.needs['Safety']:.0f}). Decided to wander to find a safer spot.")
                self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name, parameters={"reason": "critical_safety"})
                # No return here, let the main dispatcher pick up the Wander goal later in the tick if nothing else overrides.

        # Passive Safety Regeneration (if not in immediate danger)
        if not self.is_sick and not self.is_injured : # Basic check for "not in danger"
            # More checks could be added: e.g. not in combat, in a "safe" tagged location
            if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SCORE_MAX:
                 # Very slow passive regeneration, e.g., +0.1 per tick, or +1 every 10 ticks
                 # For simplicity, let's do a small chance for +1 per tick
                 if random.random() < 0.05 : # 5% chance to gain 1 safety per tick if safe
                    self.needs['Safety'] = min(config.NEED_SCORE_MAX, self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) + 1)
                    # self.add_memory(f"Feeling a bit safer. Safety: {self.needs['Safety']}") # Potentially too spammy for memory

        # --- Reactive "Ask for Help" for Critical Needs ---
        # Check before proactive social interactions or job defaults if not already handling a critical state.
        # social_goals_for_ask_check = ["Ask for Help", "Seek Medical Attention"] # Goals that address critical states
        critical_goal_types_for_ask_check = [GoalType.ASK_FOR_HELP, GoalType.SEEK_MEDICAL_ATTENTION]
        if self.current_goal.type not in critical_goal_types_for_ask_check:
            # Example: Ask for food if critically hungry and has no food
            if self.needs.get("Hunger", 100) < config.CRITICAL_NEED_THRESHOLD_FOR_HELP and self.inventory.get("Food", 0) == 0: # Assuming "Food" is an item type
                if random.random() < config.ASK_FOR_HELP_CHANCE:
                    potential_helpers: List[Character] = []
                    for other_char in world.characters:
                        if other_char.name == self.name or other_char.name not in self.known_characters:
                            continue
                        distance = abs(self.x - other_char.x) + abs(self.y - other_char.y)
                        if distance <= 3 and other_char.inventory.get("Food", 0) > 0: # Nearby and has food
                            potential_helpers.append(other_char)

                    if potential_helpers:
                        # Prefer helpers with higher relationship or "Generous" trait
                        potential_helpers.sort(key=lambda h: (("Generous" in h.traits), self.get_relationship_score(h.name)), reverse=True)
                        target_helper = potential_helpers[0]
                        # self.current_goal = "Ask for Help"
                        # self.current_goal_details = {
                        goal_params = {
                            "target_char_name": target_helper.name,
                            "help_type": "resource",
                            "item_name": "Food", # Assuming "Food" is the item name for generic food
                            "quantity": 1
                        }
                        self.current_goal = Goal(GoalType.ASK_FOR_HELP, assignee_id=self.name, originator_id=self.name, parameters=goal_params)
                        self.add_memory(f"Critically hungry, decided to ask {target_helper.name} for food.")
                        self.update_mood_score(config.MOOD_CHANGE_NEED_CRITICAL, "Critically hungry")
                        return # Goal set, will be executed by main dispatcher

        # Minimal Needs Check (Energy for Builder) - can be expanded later
        # For this test, assume energy is not a blocker or handled by _execute_build_order
        # if self.job == "Builder" and self.needs.get("Energy", 100) < 10:
        #     self.current_goal = "Seek Rest"; # Needs _execute_rest
        #     return


        # Builder Logic: Focus on Build Orders
        if self.job == "Builder":
            if self.active_build_order_id: # Already has an active build order
                if self.current_goal.type != GoalType.EXECUTE_BUILD_ORDER:
                    # self.current_goal = "Execute Build Order"
                    self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                             parameters={"order_id": self.active_build_order_id,
                                                         "structure_type": self.current_building_project,
                                                         "location": self.building_site_target})
                self._execute_build_order(world) # This function will manage its own state and completion
                return
            else: # No active build order, try to claim one if duty is to perform builder tasks
                if self.current_goal.type == GoalType.PERFORM_BUILDER_DUTIES:
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

                        # self.current_goal = "Execute Build Order"
                        self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                                 parameters={"order_id": self.active_build_order_id,
                                                             "structure_type": self.current_building_project,
                                                             "location": self.building_site_target})
                        self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {self.current_building_project}.")
                        self._execute_build_order(world) # Start processing immediately
                        return
                    else: # No approved build orders
                        self.add_memory("No build orders available for Builder Duties.")
                        self.current_goal = self.get_default_goal() # No WOs to perform duties on
                        # _execute_wander will be called if idle

        # If current goal was set to Execute Build Order by claiming or was already that
        if self.current_goal.type == GoalType.EXECUTE_BUILD_ORDER:
             if self.active_build_order_id: # Ensure there's still an active order
                self._execute_build_order(world)
                return
             else: # No active order, but goal is to execute one. This is an inconsistent state. Reset.
                self._reset_building_state()
                self.current_goal = self.get_default_goal() # Revert to job default

        # Fallback to job default goal if current goal is None or explicitly Idle/Wander (string check for now, will be GoalType)
        if self.current_goal is None or self.current_goal.type in [GoalType.IDLE, GoalType.WANDER]:
             new_default_goal = self.get_default_goal()
             if self.current_goal is None or self.current_goal.type != new_default_goal.type:
                self.current_goal = new_default_goal

        # --- Goal Execution Dispatcher ---
        # Note: Order matters. More specific/interrupting goals should be checked before generic ones.
        # Example: SEEK_MEDICAL_ATTENTION already handled above.

        goal_executed_this_tick = True # Assume a goal will be handled unless specified otherwise
        # Perform <Job> Duties goals often break down into other goals.
        if self.current_goal.type == GoalType.PERFORM_BUILDER_DUTIES: # Already handled by builder logic above or will become IDLE
            pass # Builder logic sets to EXECUTE_BUILD_ORDER or IDLE
        elif self.current_goal.type == GoalType.PERFORM_WOODCUTTER_DUTIES: self._execute_perform_woodcutter_duties(world)
        elif self.current_goal.type == GoalType.PERFORM_STONEMASON_DUTIES: self._execute_perform_stonemason_duties(world)
        # Add other "Perform <Job> Duties" here, they typically set a more specific goal and call decide_action or return

        # Specific Action Goals
        elif self.current_goal.type == GoalType.EXECUTE_BUILD_ORDER: self._execute_build_order(world) # Already handled above too
        elif self.current_goal.type == GoalType.EXECUTE_CRAFT_ORDER: self._execute_craft_order(world)
        elif self.current_goal.type == GoalType.FETCH_TOOL: self._execute_fetch_tool(world)
        elif self.current_goal.type == GoalType.GATHER_RESOURCE:
            resource_name = self.current_goal.parameters.get("resource_name")
            if resource_name == "Wood": self._execute_gather_wood(world)
            elif resource_name == "Stone": self._execute_gather_stone(world)
            elif resource_name == "Herbs": self._execute_gather_herbs(world)
            else: self.current_goal = self.get_default_goal() # Unknown resource
        elif self.current_goal.type == GoalType.INITIATE_HAULING: self._execute_initiate_hauling(world)
        elif self.current_goal.type == GoalType.HAUL_RESOURCE_TO_STOCKPILE: self._execute_haul_resource(world)
        elif self.current_goal.type == GoalType.COUNT_STOCKPILE: self._execute_count_stockpile(world)

        # Management/Oversight Goals
        elif self.current_goal.type == GoalType.ASSESS_PRODUCTION_NEEDS: self._execute_assess_production_needs(world)
        elif self.current_goal.type == GoalType.MANAGE_SUBORDINATES: self._execute_manage_subordinates(world)
        elif self.current_goal.type == GoalType.MAINTAIN_LEDGER: self._execute_maintain_ledger(world)
        elif self.current_goal.type == GoalType.OVERSEE_SETTLEMENT: self._execute_oversee_settlement(world)
        elif self.current_goal.type == GoalType.OVERSEE_MEDICAL_OPERATIONS: self._execute_oversee_medical_operations(world)
        elif self.current_goal.type == GoalType.PROVIDE_MEDICAL_CARE: self._execute_provide_medical_care(world)
        elif self.current_goal.type == GoalType.MAINTAIN_PEACE_IN_SETTLEMENT: self._execute_maintain_peace(world)
        elif self.current_goal.type == GoalType.PATROL_AREA: self._execute_patrol_area(world)
        elif self.current_goal.type == GoalType.GIVE_SPEECH: self._execute_give_speech(world)
        elif self.current_goal.type == GoalType.SEEK_MEDICAL_ATTENTION: self._execute_seek_medical_attention(world)
        elif self.current_goal.type == GoalType.REPORT_TO_LIEGE: self._execute_report_to_liege(world)
        elif self.current_goal.type == GoalType.MANAGE_ESTATE: self._execute_manage_estate(world)
        elif self.current_goal.type == GoalType.ASSIST_REEVE: self._execute_assist_reeve(world)
        elif self.current_goal.type == GoalType.HOLD_HIGH_COURT: self._execute_hold_high_court(world)
        elif self.current_goal.type == GoalType.ATTEND_HIGH_COURT: self._execute_attend_high_court(world)

        # Social Goals
        elif self.current_goal.type == GoalType.GREET_CHARACTER: self._execute_greet_character(world)
        elif self.current_goal.type == GoalType.INTRODUCE_SELF_TO_STRANGER: self._execute_introduce_self(world)
        elif self.current_goal.type == GoalType.SMALL_TALK: self._execute_small_talk(world)
        elif self.current_goal.type == GoalType.SHARE_POSITIVE_NEWS: self._execute_share_positive_news(world)
        elif self.current_goal.type == GoalType.OFFER_COMFORT: self._execute_offer_comfort(world)
        elif self.current_goal.type == GoalType.ARGUE: self._execute_argue(world)
        elif self.current_goal.type == GoalType.ASK_FOR_HELP: self._execute_ask_for_help(world)
        elif self.current_goal.type == GoalType.SHARE_SECRET: self._execute_share_secret(world)
        elif self.current_goal.type == GoalType.FORMAL_APOLOGY: self._execute_formal_apology(world)
        elif self.current_goal.type == GoalType.PRAISE_CHARACTER: self._execute_praise_character(world)
        elif self.current_goal.type == GoalType.SHARE_RUMOR: self._execute_share_rumor(world)
        elif self.current_goal.type == GoalType.SEEK_TO_BUY_ITEM: self._execute_buy_item(world)

        # Need-Driven Goals
        elif self.current_goal.type == GoalType.EAT_FOOD: self._execute_eat_food(world)
        elif self.current_goal.type == GoalType.SEEK_RECOGNITION: self._execute_seek_recognition(world)
        elif self.current_goal.type == GoalType.MAKE_NEW_FRIEND: self._execute_make_new_friend(world)
        elif self.current_goal.type == GoalType.IMPROVE_DWELLING: self._execute_improve_dwelling(world)

        # Default/Fallback Behaviors
        elif self.current_goal.type == GoalType.IDLE:
            self._execute_wander(world) # Idle characters wander
            goal_executed_this_tick = True # Wander is an action
        elif self.current_goal.type == GoalType.WANDER: # Explicit Wander goal
            self._execute_wander(world)
            goal_executed_this_tick = True
        else:
            # This case means a GoalType exists but has no corresponding _execute method in the dispatcher
            print(f"Warning: {self.name} has unhandled GoalType '{self.current_goal.type}'. Setting to Idle.")
            self.current_goal = self.get_default_goal()
            self._execute_wander(world) # Wander if unhandled goal
            goal_executed_this_tick = True


        # --- Need-Driven Goal Generation ---
        # If idle, consider if any critical needs should spawn a new long-term goal.
        if self.current_goal.type in [GoalType.IDLE, GoalType.WANDER]:
            if self._consider_need_driven_goals(world):
                return # A new need-driven goal was set, so end this turn's decision making.

        # --- Social Interaction Initiation (if previous goal didn't consume the tick or led to Idle/Wander) ---
        # This block is for proactive social interactions (greeting, small talk, news).
        # Reactive interactions like "Offer Comfort" will be handled by a separate check.
        # Only attempt new social interaction if current goal is now IDLE or WANDER as a result of previous logic.
        if self.current_goal.type in [GoalType.IDLE, GoalType.WANDER]:
            current_social_interaction_chance = config.SOCIAL_INTERACTION_CHANCE
            # Original Social need check
            if self.needs.get('Social', 70) < config.LOW_SOCIAL_NEED_THRESHOLD:
                current_social_interaction_chance += config.SOCIAL_INTERACTION_CHANCE_LOW_NEED_BONUS

            # Belonging need bias: Increases desire for social interaction
            if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
                current_social_interaction_chance += 0.15 # Significant boost if belonging is critical
                self.add_memory(f"Feeling a strong need for connection (Belonging: {self.needs['Belonging']:.0f}), more likely to socialize.")
            elif self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < (config.NEED_BELONGING_CRITICAL_THRESHOLD + 20): # Moderately low
                current_social_interaction_chance += 0.05

            # Mood influence on general social interaction chance
            mood_social_mod = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(self.mood, 0.0)
            current_social_interaction_chance += mood_social_mod # Additive, can be negative
            current_social_interaction_chance = max(0.01, min(0.95, current_social_interaction_chance)) # Clamp

            if random.random() < current_social_interaction_chance:
                potential_strangers: List[Character] = []
                potential_known_to_greet: List[Character] = []
                potential_known_for_smalltalk: List[Character] = []
                potential_known_for_news: List[Character] = []

                target_weights: Dict[str, float] = {}
                min_opinion_to_avoid = -3
                min_opinion_to_prefer = 3

                for other_char in world.characters:
                    if other_char.name == self.name: continue
                    distance = abs(self.x - other_char.x) + abs(self.y - other_char.y)
                    max_initiation_distance = 5
                    if distance <= max_initiation_distance:
                        recently_interacted_today = False
                        if self.dialogue_history:
                            for entry in reversed(self.dialogue_history[-3:]):
                                if (entry.get("target") == other_char.name or entry.get("initiator") == other_char.name) and \
                                   world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1:
                                    recently_interacted_today = True; break
                        if not recently_interacted_today:
                            if other_char.name not in self.known_characters:
                                potential_strangers.append(other_char)
                            else: # Character is known
                                tier = self.get_relationship_tier(other_char.name)
                                current_impression_score = sum(self.opinions.get(other_char.name, {}).values())
                                relationship_score = self.get_relationship_score(other_char.name)

                                weight = 1.0 # Base weight
                                # Tier-based adjustment
                                if tier == config.RELATIONSHIP_TIER_FAMILY: weight *= 3.0
                                elif tier == "Close Friend": weight *= 2.5
                                elif tier == "Friend": weight *= 2.0
                                elif tier == "Friendly Acquaintance": weight *= 1.5
                                elif tier == "Disliked": weight *= 0.5
                                elif tier == "Rival": weight *= 0.2
                                elif tier == "Archenemy": weight *= 0.05

                                # Opinion-based adjustment (more fine-grained)
                                if current_impression_score > 5: weight *= 1.5
                                elif current_impression_score < -5: weight *= 0.5

                                # Direct relationship score influence (can be strong)
                                if relationship_score > 75 : weight *= 1.5 # Very high relationship
                                elif relationship_score < -75 : weight *= 0.1 # Very low relationship

                                # Belonging need bias: Prefer positive relationships more strongly if Belonging is low
                                if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
                                    if relationship_score > 10: # Friends, family, etc.
                                        weight *= 1.5 # Further boost interaction with positive connections
                                    elif relationship_score < -10: # Disliked, rivals
                                        weight *= 0.5 # Further penalize interaction with negative connections

                                target_weights[other_char.name] = max(0.01, weight) # Ensure a minimal chance

                                potential_known_for_smalltalk.append(other_char)
                                potential_known_for_news.append(other_char)
                                potential_known_to_greet.append(other_char)

                target_char_for_interaction: Optional[Character] = None
                interaction_goal_type: Optional[GoalType] = None
                # interaction_type_str was used before, now map to GoalType

                def weighted_random_choice(choices: List[Character], weights: Dict[str, float]) -> Optional[Character]:
                    if not choices: return None
                    weighted_choices = []
                    for choice_char in choices:
                        weight = weights.get(choice_char.name, 1.0)
                        weighted_choices.extend([choice_char] * int(weight * 10))
                    return random.choice(weighted_choices) if weighted_choices else None

                chatty_bonus_for_news = 0.2 if "Chatty" in self.traits else 0.0

                if potential_strangers:
                    target_char_for_interaction = random.choice(potential_strangers)
                    interaction_goal_type = GoalType.INTRODUCE_SELF_TO_STRANGER
                elif potential_known_for_news and random.random() < (0.3 + chatty_bonus_for_news):
                    target_char_for_interaction = weighted_random_choice(potential_known_for_news, target_weights)
                    if target_char_for_interaction: interaction_goal_type = GoalType.SHARE_POSITIVE_NEWS
                elif potential_known_for_smalltalk and random.random() < 0.6:
                    target_char_for_interaction = weighted_random_choice(potential_known_for_smalltalk, target_weights)
                    if target_char_for_interaction: interaction_goal_type = GoalType.SMALL_TALK
                elif potential_known_to_greet:
                    target_char_for_interaction = weighted_random_choice(potential_known_to_greet, target_weights)
                    if target_char_for_interaction: interaction_goal_type = GoalType.GREET_CHARACTER

                if target_char_for_interaction and interaction_goal_type:
                    goal_params = {"target_char_name": target_char_for_interaction.name}
                    self.current_goal = Goal(interaction_goal_type, assignee_id=self.name, originator_id=self.name, parameters=goal_params)
                    self.add_memory(f"Decided to '{interaction_goal_type.name}' with {target_char_for_interaction.name}.") # Changed .value to .name
                    # Goal set, dispatcher will handle it.
                else: # If no other social interaction chosen, consider sharing a rumor
                    share_rumor_chance = config.RUMOR_SPREAD_CHANCE_BASE
                    if "Chatty" in self.traits:
                        share_rumor_chance += config.RUMOR_SPREAD_CHATTY_BONUS

                    if random.random() < share_rumor_chance and self.known_rumor_ids:
                        # Find a rumor to share and a target who doesn't know it
                        target_for_rumor: Optional['Character'] = None
                        rumor_to_share: Optional[Rumor] = None

                        # Find best rumor (strongest) that self knows
                        known_rumors = [world.get_rumor_by_id(rid) for rid in self.known_rumor_ids if world.get_rumor_by_id(rid)]
                        if known_rumors:
                            known_rumors.sort(key=lambda r: r.current_strength, reverse=True)

                            # Find a nearby character who doesn't know the best rumors
                            for r in known_rumors:
                                potential_listeners = [
                                    char for char in world.get_nearby_characters(self, radius=4)
                                    if char.name in self.known_characters and r.rumor_id not in char.known_rumor_ids
                                ]
                                if potential_listeners:
                                    # Prefer listeners with higher relationship
                                    potential_listeners.sort(key=lambda l: self.get_relationship_score(l.name), reverse=True)
                                    target_for_rumor = potential_listeners[0]
                                    rumor_to_share = r
                                    break # Found a rumor and a target

                        if target_for_rumor and rumor_to_share:
                            goal_params = {"target_char_name": target_for_rumor.name, "rumor_id": rumor_to_share.rumor_id}
                            self.current_goal = Goal(GoalType.SHARE_RUMOR, assignee_id=self.name, originator_id=self.name, parameters=goal_params)
                            self.add_memory(f"Feeling gossipy, decided to share a rumor about {rumor_to_share.subject_char_id} with {target_for_rumor.name}.")


        # --- Reactive Social Interaction Checks (Offer Comfort, Argue, Formal Apology) ---
        # These checks happen even if not strictly Idle/Wandering, but not if already in a social goal
        # that isn't also a reactive one (e.g. don't interrupt an apology to start an argument).
        non_interruptible_social_goals = [
            GoalType.OFFER_COMFORT, GoalType.ARGUE, GoalType.ASK_FOR_HELP, GoalType.FORMAL_APOLOGY, GoalType.SHARE_SECRET
        ]
        if self.current_goal.type not in non_interruptible_social_goals :
            # --- Offer Comfort Check ---
            comfort_chance_modifier = 0.0
            if "Kind" in self.traits: comfort_chance_modifier += 0.3
            if "Compassionate" in self.traits: comfort_chance_modifier += 0.4

            if random.random() < (config.REACTIVE_SOCIAL_BASE_CHANCE + comfort_chance_modifier):
                target_for_comfort: Optional[Character] = None
                # Similar logic to find distressed character...
                # (Assuming logic from the original block for finding char_in_need)
                # Simplified for brevity:
                for char_in_need in world.characters: # Placeholder for actual distress check logic
                    if char_in_need.name != self.name and char_in_need.name in self.known_characters and \
                       (char_in_need.mood in ["Sad", "Stressed"] or char_in_need.is_sick or char_in_need.is_injured) and \
                       abs(self.x - char_in_need.x) + abs(self.y - char_in_need.y) <= 4:
                        # Check if already comforted recently
                        recently_interacted = False
                        for entry in reversed(self.dialogue_history[-3:]):
                             if entry.get("target") == char_in_need.name and entry.get("type") == "offer_comfort" and \
                                world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1:
                                 recently_interacted = True; break
                        if not recently_interacted:
                            target_for_comfort = char_in_need; break

                if target_for_comfort:
                    self.current_goal = Goal(GoalType.OFFER_COMFORT, assignee_id=self.name, originator_id=self.name, parameters={"target_char_name": target_for_comfort.name})
                    self.add_memory(f"Noticed {target_for_comfort.name} seems distressed. Decided to offer comfort.")
                    # Goal set, dispatcher will handle.

            # --- Potential for Argument Check ---
            if self.current_goal.type not in non_interruptible_social_goals: # Re-check, Offer Comfort might have set goal
                argue_chance_modifier = 0.0
                if "Hot-headed" in self.traits: argue_chance_modifier += 0.15
                # Similar logic to find target to argue with...
                # Simplified for brevity:
                for other_char in world.characters: # Placeholder for actual argument trigger logic
                    if other_char.name != self.name and other_char.name in self.known_characters and \
                       (self.get_relationship_score(other_char.name) < -40 or ("Hot-headed" in self.traits and "Hot-headed" in other_char.traits)) and \
                       abs(self.x - other_char.x) + abs(self.y - other_char.y) <= 2:
                        recently_interacted = False
                        for entry in reversed(self.dialogue_history[-2:]):
                             if entry.get("target") == other_char.name and entry.get("type") == "argue" and \
                                world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1:
                                 recently_interacted = True; break
                        if not recently_interacted:
                            self.current_goal = Goal(GoalType.ARGUE, assignee_id=self.name, originator_id=self.name, parameters={"target_char_name": other_char.name})
                            self.add_memory(f"Feeling confrontational towards {other_char.name}. Decided to argue.")
                            break # Found someone to argue with

            # --- Potential for Formal Apology ---
            if self.current_goal.type not in non_interruptible_social_goals: # Re-check again
                apology_chance = 0.05 # Base chance
                if "Kind" in self.traits or "Diplomatic" in self.traits: apology_chance += 0.15
                if "Proud" in self.traits or "Stubborn" in self.traits: apology_chance -= 0.1
                if self.mood in ["Guilty", "Sad"]: apology_chance += 0.1 # Mood can influence

                if random.random() < max(0.01, apology_chance):
                    target_for_apology: Optional[Character] = None
                    for char_name_in_history, rel_score in self.relationships.items():
                        if rel_score < -10: # Relationship is poor
                            # Check recent dialogue for arguments
                            had_recent_argument = False
                            for entry in reversed(self.dialogue_history[-5:]): # Check recent history
                                if entry.get("type") == "argue" and \
                                   (entry.get("initiator") == self.name and entry.get("target") == char_name_in_history or \
                                    entry.get("initiator") == char_name_in_history and entry.get("target") == self.name) and \
                                   world.game_time and (world.game_time.current_day - entry.get("day", -100)) <= 3: # Argued within last 3 days
                                    had_recent_argument = True; break

                            if had_recent_argument:
                                # Avoid apologizing too often for the same thing
                                already_apologized_recently = False
                                for entry in reversed(self.dialogue_history[-5:]):
                                    if entry.get("type") == "formal_apology" and entry.get("target") == char_name_in_history and \
                                       world.game_time and (world.game_time.current_day - entry.get("day", -100)) <= 5:
                                        already_apologized_recently = True; break
                                if not already_apologized_recently:
                                    target_char_obj = world.get_character_by_name(char_name_in_history)
                                    if target_char_obj and abs(self.x - target_char_obj.x) + abs(self.y - target_char_obj.y) <= 5: # Reasonably nearby
                                        target_for_apology = target_char_obj
                                        break
                    if target_for_apology:
                        self.current_goal = Goal(GoalType.FORMAL_APOLOGY, assignee_id=self.name, originator_id=self.name, parameters={"target_char_name": target_for_apology.name})
                        self.add_memory(f"Feeling remorseful about past conflict with {target_for_apology.name}. Decided to offer a formal apology.")

        return # End of decide_action

    def _execute_craft_order_simple(self, world: 'World', blueprint, item_name, item_qty_total):
        # Simplified version for debugging
        craft_time_per_unit = blueprint.get("craft_time_per_unit", 5)
        base_craft_progress = 1.0
        crafting_skill_level = self.skills.get("Crafting", {}).get("level", 0)
        skill_modifier = 1 + (crafting_skill_level * 0.05)
        current_crafting_progress_gain = base_craft_progress * skill_modifier
        self.crafting_progress += current_crafting_progress_gain
        if self.crafting_progress >= craft_time_per_unit:
            self.inventory[item_name] = self.inventory.get(item_name, 0) + 1
            if self.inventory.get(item_name, 0) >= item_qty_total:
                self.items_crafted_for_wo = True

    def _consider_need_driven_goals(self, world: 'World') -> bool:
        """
        Checks for critical needs and has a chance to generate a long-term goal to address them.
        Returns True if a new goal was set, False otherwise.
        """
        # Do not override existing high-priority goals
        if self.current_goal and self.current_goal.priority < 7: # 1-6 are high prio
            return False

        # Check Esteem
        if self.needs.get('Esteem', 50) < config.NEED_ESTEEM_CRITICAL_THRESHOLD:
            if random.random() < 0.1: # 10% chance per tick when esteem is critical
                self.add_memory("Feeling a deep need for recognition. I should do something to prove my worth.")
                self.current_goal = Goal(GoalType.SEEK_RECOGNITION, assignee_id=self.name, originator_id=self.name, priority=8)
                return True

        # Check Belonging
        if self.needs.get('Belonging', 60) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            if random.random() < 0.1:
                self.add_memory("I feel so alone. I need to make a connection.")
                self.current_goal = Goal(GoalType.MAKE_NEW_FRIEND, assignee_id=self.name, originator_id=self.name, priority=8)
                return True

        # Check Safety
        if self.needs.get('Safety', 70) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
            if random.random() < 0.1:
                self.add_memory("This place doesn't feel safe. I must do something to protect myself.")
                self.current_goal = Goal(GoalType.IMPROVE_DWELLING, assignee_id=self.name, originator_id=self.name, priority=7)
                return True

        return False

    def _execute_seek_recognition(self, world: 'World'):
        """
        Executes the goal of seeking recognition. Involves moving to a public place
        and performing an action to demonstrate skill.
        """
        # Define a public square (e.g., center of the map)
        public_square_loc = (world.grid_size[0] // 2, world.grid_size[1] // 2)

        # State machine for the goal, stored in goal parameters
        sub_state = self.current_goal.parameters.get("sub_state", "moving_to_public_square")

        if sub_state == "moving_to_public_square":
            self.add_memory("I need to get noticed. I'll go to the public square.")
            if (self.x, self.y) == public_square_loc:
                self.current_goal.parameters["sub_state"] = "performing_action"
                self.add_memory("I'm at the public square. Time to do something impressive.")
                # Fall through to the next state in the same tick
            else:
                self.move_towards(public_square_loc[0], public_square_loc[1], world)
                return # Still moving

        # After moving, or if already there, perform the action
        if self.current_goal.parameters.get("sub_state") == "performing_action":
            # Determine highest skill
            highest_skill = "None"
            highest_level = -1
            if self.skills:
                 # Filter out non-actionable skills if necessary
                actionable_skills = {k: v for k, v in self.skills.items() if k in ["Crafting", "Construction", "Woodcutting", "Stonemasonry", "Medicine"]}
                if actionable_skills:
                    highest_skill, skill_data = max(actionable_skills.items(), key=lambda item: item[1]['level'])
                    highest_level = skill_data['level']

            self.add_memory(f"My best skill is {highest_skill} (Lvl {highest_level}). I will demonstrate it.")

            # Simple demonstration: just log it and check for witnesses
            # Future: Could trigger a sub-goal like CRAFT_MASTERPIECE
            action_description = f"demonstrating my {highest_skill} skill"
            if highest_skill == "None":
                action_description = "trying to look important"

            witnesses = world.get_nearby_characters(self, radius=4)
            if witnesses:
                witness_names = [w.name for w in witnesses]
                self.add_memory(f"I am {action_description} in front of {', '.join(witness_names)}.")
                world.add_event_log_message(f"{self.name} is {action_description} in the public square, witnessed by {', '.join(witness_names)}.")

                # Esteem boost for being witnessed
                esteem_boost = 10 + len(witnesses) * 2
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', 50) + esteem_boost)
                self.add_memory(f"Being watched gave my esteem a boost of {esteem_boost}! Esteem: {self.needs['Esteem']:.0f}")

                # Relationship boost with witnesses
                for witness in witnesses:
                    witness.modify_relationship(self.name, 2, world, reason=f"Was impressed by their public display of skill.")
                    witness.add_memory(f"Was impressed by {self.name}'s demonstration of {highest_skill}.")
            else:
                self.add_memory(f"I am {action_description}, but no one is around to see.")
                # Smaller esteem boost for the attempt
                self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', 50) + 3)
                self.add_memory(f"Even though no one saw, I feel a bit better for trying. Esteem: {self.needs['Esteem']:.0f}")


            # Goal is completed after one demonstration action
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()

    def _execute_make_new_friend(self, world: 'World'):
        """
        Executes the goal of making a new friend. Involves finding a stranger
        and initiating an introduction.
        """
        # State machine for the goal
        sub_state = self.current_goal.parameters.get("sub_state", "finding_stranger")
        target_stranger_name = self.current_goal.parameters.get("target_stranger_name")

        if sub_state == "finding_stranger":
            self.add_memory("I feel lonely. I'm going to find someone new to talk to.")
            potential_strangers = [
                char for char in world.characters
                if char.name != self.name and char.name not in self.known_characters
            ]

            if not potential_strangers:
                self.add_memory("I couldn't find anyone new to meet right now.")
                self.current_goal.set_failed(reason="No strangers available")
                self.current_goal = self.get_default_goal()
                return

            # Choose the closest stranger
            closest_stranger = min(
                potential_strangers,
                key=lambda s: abs(self.x - s.x) + abs(self.y - s.y)
            )

            self.current_goal.parameters["sub_state"] = "moving_to_stranger"
            self.current_goal.parameters["target_stranger_name"] = closest_stranger.name
            self.add_memory(f"I see someone I don't know, {closest_stranger.name}. I'll go say hello.")
            # Fall through to next state
            target_stranger_name = closest_stranger.name

        if self.current_goal.parameters.get("sub_state") == "moving_to_stranger":
            if not target_stranger_name:
                self.add_memory("I lost track of who I was going to meet.")
                self.current_goal.set_failed(reason="Target stranger name was lost")
                self.current_goal = self.get_default_goal()
                return

            stranger = world.get_character_by_name(target_stranger_name)
            if not stranger or stranger.name in self.known_characters:
                self.add_memory(f"My target {target_stranger_name} is gone or I already met them.")
                self.current_goal.set_failed(reason="Target stranger no longer valid")
                self.current_goal = self.get_default_goal()
                return

            distance = abs(self.x - stranger.x) + abs(self.y - stranger.y)
            if distance <= 2:
                # Close enough, switch to introduction goal
                self.add_memory(f"I'm close enough to {stranger.name}. Time to introduce myself.")
                self.current_goal = Goal(
                    GoalType.INTRODUCE_SELF_TO_STRANGER,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"target_char_name": stranger.name}
                )
                # The 'decide_action' loop will now execute the introduction.
                # The belonging need will be fulfilled within _execute_introduce_self.
            else:
                self.move_towards(stranger.x, stranger.y, world)

    def _execute_improve_dwelling(self, world: 'World'):
        """
        Executes the goal of improving one's dwelling for safety.
        Phase 1: Gather basic materials for a shelter.
        """
        self.add_memory("I need to improve my dwelling to feel safer. I'll start by gathering wood.")

        # Define the amount of wood needed for this phase
        wood_needed = self.current_goal.parameters.get("wood_needed", 10)

        # Check if we already have enough wood
        if self.inventory.get("Wood", 0) >= wood_needed:
            self.add_memory(f"I have gathered enough wood ({self.inventory.get('Wood', 0)}/{wood_needed}) to improve my dwelling for now.")
            # Fulfill the Safety need
            safety_boost = 25
            self.needs['Safety'] = min(config.NEED_SCORE_MAX, self.needs.get('Safety', 50) + safety_boost)
            self.add_memory(f"Feeling safer after gathering materials. Safety increased by {safety_boost} to {self.needs['Safety']:.0f}.")

            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
            return

        # If we don't have enough wood, switch to a gathering goal
        self.add_memory(f"I need more wood for my dwelling (have {self.inventory.get('Wood', 0)}/{wood_needed}).")

        # This goal now becomes a GATHER_RESOURCE goal.
        # The `decide_action` loop will then pick up this new goal and execute it.
        # When the character is idle again, and the Safety need is still low,
        # they might re-trigger IMPROVE_DWELLING, and the check for wood will pass.
        self.current_goal = Goal(
            GoalType.GATHER_RESOURCE,
            assignee_id=self.name,
            originator_id=self.name,
            parameters={"resource_name": "Wood", "task_name": "Chop Wood", "quota": wood_needed}
        )

    def _execute_praise_character(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to praise {target_name}, but they are gone.")
            self.current_goal = self.get_default_goal()
            return

        if abs(self.x - target_char.x) + abs(self.y - target_char.y) > 2:
            self.add_memory(f"Moving closer to praise {target_name}.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        # At praising distance
        self.add_memory(f"I praised {target_name} for their excellent work.")
        target_char.add_memory(f"I was praised by {self.name}! It feels good to be recognized.")

        # Boost target's esteem significantly
        target_char.needs['Esteem'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Esteem', 50) + 20)
        target_char.add_memory(f"The praise from {self.name} boosted my esteem to {target_char.needs['Esteem']:.0f}.")
        target_char.update_mood_score(15, f"Was praised by {self.name}")

        # Relationship boost
        self.modify_relationship(target_name, 5, world, reason="Praised their work.")
        target_char.modify_relationship(self.name, 10, world, reason="They praised my work.")
        self._apply_family_splash_effect(target_char, 10, world, reason="praised")

        # Mood boost for praiser
        self.update_mood_score(5, f"Praised {target_name}")

        self.current_goal = self.get_default_goal()


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
        rating_modifier_score = 0.0 # -2 to +2 scale for simplicity, now float

        # Personality/Traits based modifier
        if "Strict" in self.traits or self.personality == "Demanding": rating_modifier_score -= 1.0
        if "Kind" in self.traits or self.personality == "Forgiving": rating_modifier_score += 1.0
        if "Lazy" in self.traits and random.random() < 0.3: rating_modifier_score += 1.0 # Lazy supervisor might inflate rating

        # Relationship based modifier (more granular)
        relationship_to_sub = self.get_relationship_score(subordinate.name)
        # Scale relationship score from -100..100 to a modifier of -1.5..1.5
        relationship_modifier = (relationship_to_sub / 100.0) * 1.5
        rating_modifier_score += relationship_modifier

        # Apply modifier score to objective rating
        # Define rating scale: Poor (-2), Needs Improvement (-1), Satisfactory (0), Good (1), Excellent (2)
        rating_scale = {"Poor": -2, "Needs Improvement": -1, "Satisfactory": 0, "Good": 1, "Excellent": 2, "Not Evaluated": 0}
        objective_score = rating_scale.get(objective_rating, 0)

        final_score_float = max(-2.0, min(2.0, objective_score + rating_modifier_score)) # Clamp final score as float
        final_score = int(round(final_score_float)) # Round to nearest integer for rating lookup

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
            self.modify_relationship(subordinate.name, relationship_change_value // 2, world, reason=f"Performance review outcome: {final_rating}")
            subordinate.modify_relationship(self.name, relationship_change_value, world, reason=f"Performance review outcome from {self.name}: {final_rating}")

        # Manager's mood from conducting review
        manager_mood_change = 0
        if final_rating in ["Excellent", "Good"]: manager_mood_change = 3
        elif final_rating in ["Poor"]: manager_mood_change = -3
        if "Strict" in self.traits and final_rating == "Poor": manager_mood_change -=2
        if "Compassionate" in self.traits and final_rating == "Poor": manager_mood_change +=1
        self.update_mood_score(manager_mood_change, f"Conducted review for {subordinate.name} (Rated: {final_rating})")

        # Subordinate's mood
        sub_mood_change = {"Excellent": config.MOOD_CHANGE_PROMOTED, "Good": 10, "Satisfactory": 2, "Needs Improvement": -8, "Poor": config.MOOD_CHANGE_RECEIVED_WARNING}.get(final_rating,0)
        subordinate.update_mood_score(sub_mood_change, f"Performance review: {final_rating}")

        # Subordinate's Esteem
        esteem_change = 0
        if final_rating == "Excellent": esteem_change = 15
        elif final_rating == "Good": esteem_change = 10
        elif final_rating == "Satisfactory": esteem_change = 2
        elif final_rating == "Needs Improvement": esteem_change = -5
        elif final_rating == "Poor": esteem_change = -10

        if esteem_change != 0:
            subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, min(config.NEED_SCORE_MAX, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + esteem_change))
            subordinate.add_memory(f"My performance review ({final_rating}) changed my esteem by {esteem_change}. Esteem: {subordinate.needs['Esteem']}")

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
        subordinate.update_mood_score(config.MOOD_CHANGE_RECEIVED_WARNING, f"Received warning: {reason_message}")
        subordinate.needs['Belonging'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 8) # Warnings can make one feel less part of the group
        subordinate.add_memory(f"Receiving a warning made me feel less accepted. Belonging: {subordinate.needs['Belonging']}")
        subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 7) # Warnings damage esteem
        subordinate.add_memory(f"Receiving a warning also damaged my esteem. Esteem: {subordinate.needs['Esteem']}")

        # Manager's mood
        manager_mood_hit = -5
        if "Strict" in self.traits: manager_mood_hit -=2
        elif "Forgiving" in self.traits: manager_mood_hit +=2
        self.update_mood_score(manager_mood_hit, f"Issued warning to {subordinate.name}")

        # Splash effect on family
        self._apply_family_splash_effect(subordinate, -15, world, reason=f"issued a warning to")

        if subordinate.warning_count >= config.FIRING_WARNING_THRESHOLD: # Threshold for automatic performance degradation
            if subordinate.performance_rating != "Poor":
                subordinate.performance_rating = "Poor"
                self.add_memory(f"{subordinate.name}'s performance set to Poor due to {subordinate.warning_count} warnings (Threshold: {config.FIRING_WARNING_THRESHOLD}).")
                subordinate.add_memory(f"Performance automatically set to Poor due to reaching {subordinate.warning_count} warnings.")
                print(f"{subordinate.name}'s performance automatically set to Poor due to {subordinate.warning_count} warnings.")
                subordinate.update_mood_score(-10, "Performance set to Poor due to warnings")
                subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 10) # Further esteem hit
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

        # Manager's mood for firing someone
        manager_mood_change = -10 # Base stress/unpleasantness
        if "Ruthless" in self.traits: manager_mood_change += 8 # Ruthless managers might feel less bad or even good
        elif "Compassionate" in self.traits: manager_mood_change -= 5 # Compassionate managers feel worse
        self.update_mood_score(manager_mood_change, f"Fired {subordinate.name}")

        # Remove from supervisor's list
        if subordinate.name in self.subordinates_names:
            self.remove_subordinate(subordinate.name) # Uses existing method

        # Update subordinate's status
        original_job = subordinate.job
        subordinate.supervisor_name = None
        subordinate.job = "Unemployed"
        subordinate.rank = "Commoner" # Or some other default non-noble/non-worker rank
        subordinate.current_goal = Goal(GoalType.IDLE, assignee_id=subordinate.name)
        subordinate.assigned_tasks = []
        subordinate.performance_rating = "Fired"
        subordinate.update_mood_score(config.MOOD_CHANGE_FIRED, f"Fired from job as {original_job}")
        subordinate.needs['Belonging'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 25) # Major hit to belonging
        subordinate.add_memory(f"Being fired made me lose my sense of belonging with my work group. Belonging: {subordinate.needs['Belonging']}")
        subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 30) # Huge esteem hit
        subordinate.add_memory(f"Being fired crushed my esteem. Esteem: {subordinate.needs['Esteem']}")

        rep_change_reason = f"Was fired from job as {original_job} by {self.name}"
        subordinate.update_reputation(config.REPUTATION_CHANGE_FIRED, rep_change_reason, world=world)
        if abs(config.REPUTATION_CHANGE_FIRED) >= config.REPUTATION_FOR_RUMOR_THRESHOLD and world.game_time:
            rumor_content_key = "was_fired_negative"
            # Firing is often a more significant event
            rumor_strength = config.RUMOR_INITIAL_STRENGTH_SIGNIFICANT_EVENT
            new_rumor = Rumor(
                subject_char_id=subordinate.name, # Fired person is the subject
                content_key=rumor_content_key,
                initial_strength=rumor_strength,
                creation_day=world.game_time.current_day,
                is_positive=False,
                original_source_char_id=self.name # Manager firing is the source
            )
            world.add_rumor(new_rumor)
            # Subject (subordinate) and source (self, the manager) know the rumor
            subordinate.known_rumor_ids.add(new_rumor.rumor_id)
            self.known_rumor_ids.add(new_rumor.rumor_id)
            subordinate.add_memory(f"Being fired by {self.name} will likely start negative rumors ({new_rumor.rumor_id[:4]}) about me.")
            self.add_memory(f"Firing {subordinate.name} might cause rumors ({new_rumor.rumor_id[:4]}).")

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
        self._apply_family_splash_effect(subordinate, -50, world, reason=f"fired") # Use a large, but not extreme, base for splash

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

    def _apply_family_splash_effect(self, target_char: 'Character', original_change: int, world: 'World', reason: str):
        """
        Applies a smaller, 'splashed' relationship change to the target's family members
        from the perspective of the character initiating the action.
        """
        if not target_char.family_members:
            return

        splash_change = int(round(original_change * config.FAMILY_RELATIONSHIP_SPLASH_FACTOR))

        # Ensure a very significant event still has some splash, even if the factor is low
        if splash_change == 0:
            if original_change > 5: splash_change = 1
            elif original_change < -5: splash_change = -1

        if splash_change == 0:
            return # No splash effect to apply

        for family_member_name in target_char.family_members:
            if family_member_name == self.name or family_member_name == target_char.name:
                continue

            # The initiator's (self) relationship towards the family member changes.
            # This represents the initiator thinking "I like/dislike this family now"
            splash_reason_self = f"Family association: {reason} {target_char.name}"
            self.modify_relationship(family_member_name, splash_change, world, reason=splash_reason_self)

            # The family member's relationship towards the initiator also changes.
            family_member = world.get_character_by_name(family_member_name)
            if family_member:
                # Family member must know the initiator to have their opinion changed.
                if self.name not in family_member.known_characters:
                    continue

                splash_reason_family = f"Family splash: {self.name} {reason} {target_char.name}"
                family_member.modify_relationship(self.name, splash_change, world, reason=splash_reason_family)
                family_member.add_memory(f"I heard {self.name} {reason} my family member {target_char.name}. It affects how I see them.")

    def get_relationship_tier(self, target_char_name: str) -> str:
        """Determines the descriptive relationship tier with another character."""
        if target_char_name == self.name:
            return "Self"
        if target_char_name in self.family_members:
            # Family can also have scores, but "Family" tier might override or add nuance
            # For now, if explicitly family, return that. Score still matters for non-family interactions.
            return config.RELATIONSHIP_TIER_FAMILY

        score = self.relationships.get(target_char_name)
        if score is None:
            return config.RELATIONSHIP_TIER_STRANGER

        # RELATIONSHIP_TIERS in config should be sorted from highest score requirement to lowest
        for tier_name, threshold in config.RELATIONSHIP_TIERS:
            if score >= threshold:
                return tier_name

        # If score is below all defined positive/neutral thresholds, it's likely the lowest tier
        # (e.g., Archenemy if its threshold is very low like -90)
        # This assumes the last entry in RELATIONSHIP_TIERS is the lowest possible score-based tier.
        if config.RELATIONSHIP_TIERS:
             # Check if score is even lower than the lowest defined threshold
            lowest_tier_name, lowest_threshold = config.RELATIONSHIP_TIERS[-1]
            if score < lowest_threshold: # Should ideally match the lowest if list is comprehensive
                return lowest_tier_name

        return config.RELATIONSHIP_TIERS[-1][0] if config.RELATIONSHIP_TIERS else "Neutral" # Fallback

    def _execute_greet_character(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to greet someone, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to greet {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
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

        # 6. Fulfill Social Need
        fulfillment = config.SOCIAL_FULFILLMENT_GREET_INTRODUCE
        self.needs['Social'] = min(100, self.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)
        self.add_memory(f"Social need increased by {fulfillment} to {self.needs['Social']} after greeting {target_name}.")
        target_char.add_memory(f"Social need increased by {fulfillment} to {target_char.needs['Social']} after being greeted by {self.name}.")

        # Update relationships based on overall opinions
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Mood change from greeting
        mood_change_initiator = config.MOOD_CHANGE_POSITIVE_SOCIAL
        mood_change_target = config.MOOD_CHANGE_POSITIVE_SOCIAL
        if initiator_grumpy: mood_change_initiator -= 2 # Grumpy people might not enjoy initiating as much
        if target_grumpy: mood_change_target -= 2    # Grumpy people might not enjoy being greeted as much
        if "Friendly" in self.traits and "Friendly" in target_char.traits: # Extra bonus for mutual friendliness
            mood_change_initiator += 2
            mood_change_target += 2

        self.update_mood_score(mood_change_initiator, f"Greeted {target_name}")
        target_char.update_mood_score(mood_change_target, f"Was greeted by {self.name}")

        # Belonging Need Fulfillment
        belonging_increase = 3 # Base for a simple greeting
        self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        self.add_memory(f"Greeting {target_name} made me feel a bit more connected. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Being greeted by {self.name} made me feel a bit more connected. Belonging: {target_char.needs['Belonging']}")

        # Process listeners
        self._process_nearby_listeners(world, target_char, "greeting", self.traits, target_char.traits)

        # 7. Greeting complete. Reset goal.
        self.current_goal = self.get_default_goal()
        return

    def _execute_formal_apology(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to apologize, but no target specified."); self.current_goal = self.get_default_goal(); return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Apology target {target_name} not found."); self.current_goal = self.get_default_goal(); return

        if abs(self.x - target_char.x) + abs(self.y - target_char.y) > 2: # Need to be relatively close
            self.add_memory(f"Moving closer to {target_name} to apologize.")
            self.move_towards(target_char.x, target_char.y, world); return

        self.add_memory(f"Attempting a formal apology to {target_name}.")

        # Success of apology depends on target's personality, mood, and relationship
        base_acceptance_chance = 0.4 # Base chance of apology being accepted
        if "Forgiving" in target_char.traits: base_acceptance_chance += 0.25
        if "Grumpy" in target_char.traits or "Stern" in target_char.personality: base_acceptance_chance -= 0.2

        target_relationship_tier = target_char.get_relationship_tier(self.name)
        if target_relationship_tier in ["Friend", "Close Friend", "Family", "Soulmate"]: base_acceptance_chance += 0.2
        elif target_relationship_tier in ["Rival", "Archenemy"]: base_acceptance_chance -= 0.3

        target_mood_effect = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(target_char.mood, 0.0)
        # Positive mood makes target more receptive, negative makes them less so (inverted for acceptance)
        final_acceptance_chance = base_acceptance_chance - target_mood_effect
        final_acceptance_chance = max(0.05, min(0.95, final_acceptance_chance))

        dialogue_line_self = f"I've been thinking, {target_name}, and I wanted to sincerely apologize for my behavior earlier."
        dialogue_line_target = ""
        relationship_change = 0

        if random.random() < final_acceptance_chance:
            self.add_memory(f"My apology to {target_name} was accepted.")
            target_char.add_memory(f"{self.name} apologized, and I've accepted it.")
            dialogue_line_target = random.choice([f"Thank you, {self.name}. I appreciate that.", "It takes courage to apologize. Accepted.", "Alright. Let's move past it."])
            relationship_change = 10 + (5 if "Forgiving" in target_char.traits else 0) # Significant repair
            # Mood boost for both
            self.update_mood_score(8, f"Apology accepted by {target_name}")
            target_char.update_mood_score(5, f"Accepted apology from {self.name}")

            # Esteem boost for initiator for doing the right thing
            self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5)
            self.add_memory(f"Apologizing and being accepted made me feel better about myself. Esteem: {self.needs['Esteem']}")

            # Belonging Need Fulfillment (mending bridges)
            belonging_increase_initiator = 7
            belonging_increase_target = 5
            self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase_initiator)
            target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase_target)
            self.add_memory(f"My accepted apology to {target_name} helped mend our connection. Belonging: {self.needs['Belonging']}")
            target_char.add_memory(f"Accepting {self.name}'s apology made me feel more connected. Belonging: {target_char.needs['Belonging']}")

            rep_change_reason = f"Successfully apologized to {target_name}"
            self.update_reputation(config.REPUTATION_CHANGE_APOLOGY_ACCEPTED, rep_change_reason, world=world)
            if abs(config.REPUTATION_CHANGE_APOLOGY_ACCEPTED) >= config.REPUTATION_FOR_RUMOR_THRESHOLD and world.game_time:
                rumor_content_key = "apology_accepted_positive"
                rumor_strength = config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT
                new_rumor = Rumor(
                    subject_char_id=self.name, # Apologizer is the subject
                    content_key=rumor_content_key,
                    initial_strength=rumor_strength,
                    creation_day=world.game_time.current_day,
                    is_positive=True,
                    original_source_char_id=target_name # Target of apology is a key witness/source
                )
                world.add_rumor(new_rumor)
                # Subject (self) and source (target_char) know the rumor
                self.known_rumor_ids.add(new_rumor.rumor_id)
                target_char.known_rumor_ids.add(new_rumor.rumor_id)
                self.add_memory(f"My accepted apology to {target_name} might start a positive rumor ({new_rumor.rumor_id[:4]}) about me.")
                target_char.add_memory(f"{self.name}'s apology to me was sincere; people might hear about it (rumor {new_rumor.rumor_id[:4]}).")

            # Clear negative opinion tags related to arguments
            if target_name in self.opinions:
                self.opinions[target_name].pop("argumentative", None); self.opinions[target_name].pop("disagreeable", None)
            if self.name in target_char.opinions:
                target_char.opinions[self.name].pop("argumentative", None); target_char.opinions[self.name].pop("disagreeable", None)
        else:
            self.add_memory(f"My apology to {target_name} was not fully accepted.")
            target_char.add_memory(f"{self.name} apologized, but I'm still not sure.")
            dialogue_line_target = random.choice([f"I hear you, {self.name}, but I need some more time.", "Words are easy. Let's see if your actions change.", "Hmph. We'll see."])
            relationship_change = 2 # Minor improvement for the attempt
            self.update_mood_score(-2, f"Apology to {target_name} was met with skepticism.")
            # Target's mood might not change or slightly improve for the gesture
            target_char.update_mood_score(1, f"{self.name} apologized, I'm considering it.")

            # Belonging Need Reduction (failed attempt to mend)
            belonging_decrease_initiator = 3
            self.needs['Belonging'] = max(config.NEED_SCORE_MIN, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - belonging_decrease_initiator)
            self.add_memory(f"My apology to {target_name} being met with skepticism made me feel a bit more isolated. Belonging: {self.needs['Belonging']}")
            # Target's belonging might not change much or slightly decrease if the interaction remains tense. For now, no change for target on rejected apology.

        self.modify_relationship(target_name, relationship_change, world, reason="Formal apology offered.")
        target_char.modify_relationship(self.name, relationship_change // 2, world, reason=f"{self.name} offered an apology.") # Target also slightly mollified by attempt

        # Apply splash effect if apology was accepted and had a positive impact
        if relationship_change > 5: # Threshold for a "successful" apology
            self._apply_family_splash_effect(target_char, relationship_change, world, reason="successfully apologized to")

        dialogue_entry = { "type": "formal_apology", "initiator": self.name, "target": target_name,
                           "day": world.game_time.current_day if world.game_time else -1,
                           "dialogue_exchanges": [{"speaker": self.name, "line": dialogue_line_self}, {"speaker": target_name, "line": dialogue_line_target}] }
        self.dialogue_history.append(dialogue_entry); target_char.dialogue_history.append(dialogue_entry)
        world.add_event_log_message(f"{self.name} formally apologized to {target_name}.")

        self.current_goal = self.get_default_goal()
        return

    def _execute_share_secret(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to share a secret, but no target specified."); self.current_goal = self.get_default_goal(); return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Secret target {target_name} not found."); self.current_goal = self.get_default_goal(); return

        relationship_tier = self.get_relationship_tier(target_name)
        allowed_tiers = [config.RELATIONSHIP_TIER_FAMILY, "Close Friend", "Soulmate"] # From config or defined list

        if relationship_tier not in allowed_tiers:
            self.add_memory(f"Tried to share a secret with {target_name}, but we're not close enough ({relationship_tier}).")
            self.current_goal = self.get_default_goal(); return

        if abs(self.x - target_char.x) + abs(self.y - target_char.y) > 1: # Secrets require close proximity
            self.add_memory(f"Moving closer to {target_name} to share a secret.")
            self.move_towards(target_char.x, target_char.y, world); return

        # Simple secret sharing
        secret_content = random.choice(["a hidden stash of berries", "a funny dream I had", "that I'm not a fan of the Mayor's new hat", "my plan to build the biggest turnip ever"])
        self.add_memory(f"Shared a secret with {target_name}: '{secret_content}'. They seemed to appreciate it.")
        target_char.add_memory(f"{self.name} shared a secret with me: '{secret_content}'. I'll keep it safe.")

        # Significant relationship boost
        self.modify_relationship(target_name, 15, world, reason="Shared a secret, building trust.")
        target_char.modify_relationship(self.name, 15, world, reason="Was trusted with a secret.")

        # Mood boost for both
        self.update_mood_score(10, f"Shared a secret with {target_name}")
        target_char.update_mood_score(10, f"Was trusted with a secret by {self.name}")

        # Belonging Need Fulfillment (very significant for both)
        belonging_increase = 15
        self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        self.add_memory(f"Sharing a secret with {target_name} created a strong bond. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Being trusted with a secret by {self.name} made me feel very connected. Belonging: {target_char.needs['Belonging']}")

        # Log dialogue (simplified)
        dialogue_entry = { "type": "share_secret", "initiator": self.name, "target": target_name,
                           "day": world.game_time.current_day if world.game_time else -1,
                           "dialogue_exchanges": [{"speaker": self.name, "line": f"(Whispering) Psst, {target_name}, can I tell you something?"},
                                                  {"speaker": target_name, "line": "(Leans in) Of course, what is it?"},
                                                  {"speaker": self.name, "line": f"(Whispers) {secret_content}."},
                                                  {"speaker": target_name, "line": "(Gasps softly) Your secret is safe with me!"}] }
        self.dialogue_history.append(dialogue_entry); target_char.dialogue_history.append(dialogue_entry)
        world.add_event_log_message(f"{self.name} shared a secret with {target_name}.")

        self.current_goal = self.get_default_goal()
        return

    def _execute_share_rumor(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters or "rumor_id" not in self.current_goal.parameters:
            self.add_memory("Wanted to share a rumor, but goal parameters were incomplete.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        rumor_id = self.current_goal.parameters["rumor_id"]
        target_char = world.get_character_by_name(target_name)
        rumor = world.get_rumor_by_id(rumor_id)

        if not target_char or not rumor:
            self.add_memory("Wanted to share a rumor, but the target or rumor is gone.")
            self.current_goal = self.get_default_goal()
            return

        if abs(self.x - target_char.x) + abs(self.y - target_char.y) > 2:
            self.add_memory(f"Moving closer to {target_name} to share a juicy rumor.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        # At location, share the rumor
        self.add_memory(f"Sharing a rumor about {rumor.subject_char_id} with {target_name}.")

        # Target learns the rumor, which also affects their opinion of the subject
        # The rumor object itself tracks who knows it
        was_new_rumor_for_target = rumor.is_known_by(target_char.name)
        rumor.add_knower(target_char.name)
        target_char.known_rumor_ids.add(rumor.rumor_id)
        if not was_new_rumor_for_target:
            target_char._process_learned_rumor(rumor, world)

        # Rumor dynamics: strength increases, decay is reset for the day
        rumor.current_strength += config.RUMOR_SPREAD_STRENGTH_INCREASE
        if world.game_time:
            rumor.last_spread_day = world.game_time.current_day

        # Social consequences for the sharer and target
        rel_change = 1
        if "Chatty" in self.traits: rel_change += 1
        if rumor.is_positive: rel_change += 1
        else: rel_change -= 1 # Sharing negative rumors is a bit less bonding

        self.modify_relationship(target_name, rel_change, world, reason="Shared a rumor.")
        target_char.modify_relationship(self.name, rel_change, world, reason="They shared a rumor with me.")

        # Target forms an opinion about the sharer's gossipy nature
        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        opinion_tag = "gossipy"
        gossip_opinion_change = 1
        if not rumor.is_positive: gossip_opinion_change += 1 # Sharing negative rumors is more gossipy
        target_char.opinions[self.name][opinion_tag] = target_char.opinions[self.name].get(opinion_tag, 0) + gossip_opinion_change
        target_char.opinions[self.name][opinion_tag] = max(-5, min(5, target_char.opinions[self.name].get(opinion_tag,0)))


        # Dialogue generation
        dialogue_line_self = f"Psst, {target_name}, did you hear about {rumor.subject_char_id}?"
        if "Chatty" in self.traits:
            dialogue_line_self = f"Oh my goodness, {target_name}, you will not BELIEVE what I heard about {rumor.subject_char_id}!"

        dialogue_line_target = "Oh? Do tell."
        if "Grumpy" in target_char.traits:
            dialogue_line_target = "I don't care for gossip."
        elif "Friendly" in target_char.traits:
            dialogue_line_target = "No! What happened?"

        dialogue_entry = {
            "type": "share_rumor", "initiator": self.name, "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [
                {"speaker": self.name, "line": dialogue_line_self},
                {"speaker": target_name, "line": dialogue_line_target},
                {"speaker": self.name, "line": f"(Whispering) They say... {rumor.content_key}!"}
            ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        world.add_event_log_message(f"{self.name} shared a rumor with {target_name} about {rumor.subject_char_id}.")

        # Finalize
        self.current_goal = self.get_default_goal()
        return

    def _execute_buy_item(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "item_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to buy an item, but no item was specified.")
            self.current_goal = self.get_default_goal()
            return

        item_name = self.current_goal.parameters["item_name"]
        price = world.get_market_price(item_name) if hasattr(world, "get_market_price") else world.market_prices.get(item_name)

        if price is None:
            self.add_memory(f"Wanted to buy {item_name}, but it's not sold at the market.")
            self.current_goal = self.get_default_goal()
            return

        if self.money < price:
            self.add_memory(f"Wanted to buy {item_name}, but I can't afford it.")
            # Maybe generate a "need money" goal in the future
            self.current_goal = self.get_default_goal()
            return

        # Move to the market
        if (self.x, self.y) != world.market_location:
            self.add_memory(f"Moving to the market to buy {item_name}.")
            self.move_towards(world.market_location[0], world.market_location[1], world)
            return

        # At the market, perform the transaction
        self.money -= price
        self.inventory[item_name] = self.inventory.get(item_name, 0) + 1
        self.add_memory(f"Bought 1 {item_name} for {price} coins. I have {self.money} coins left.")

        # If it was a tool, equip it immediately and go back to what we were doing
        if BLUEPRINTS.get(item_name, {}).get("type") == "Tool":
            self.equip_tool(item_name)
            self.current_goal = self.goal_before_fetching_tool or self.get_default_goal()
            self.goal_before_fetching_tool = None
            self.tool_to_fetch_type = None
            self.fetching_tool_info = None
        else:
            # For other items, just go back to the default goal for now
            self.current_goal = self.get_default_goal()

    def _execute_eat_food(self, world: 'World'):
        if self.inventory.get("Food", 0) > 0:
            self.inventory["Food"] -= 1
            if self.inventory["Food"] <= 0:
                del self.inventory["Food"]

            hunger_satisfaction = BLUEPRINTS.get("Food", {}).get("hunger_satisfaction", 40)
            if 'Hunger' not in self.needs:
                self.needs['Hunger'] = 0
            self.needs['Hunger'] = min(100, self.needs['Hunger'] + hunger_satisfaction)

            self.add_memory(f"Ate some food. Hunger is now {self.needs['Hunger']}.")
            self.update_mood_score(config.MOOD_CHANGE_NEED_FULFILLED, "Ate some food")
            self.current_goal = self.get_default_goal()
        else:
            self.add_memory("Wanted to eat, but I have no food.")
            self.current_goal.set_failed(reason="No food in inventory")
            self.current_goal = self.get_default_goal()

    def _execute_argue(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to argue, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        # Reason for argument can be passed in goal parameters if needed, e.g. {"reason": "conflicting_traits"}
        # For now, the trigger logic is in decide_action.

        if not target_char:
            self.add_memory(f"Wanted to argue with {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2
        if distance > max_interaction_distance:
            self.add_memory(f"Trying to argue with {target_name}, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        self.add_memory(f"Having an argument with {target_name}.")

        initiator_hotheaded = "Hot-headed" in self.traits
        initiator_grumpy = "Grumpy" in self.traits
        target_hotheaded = "Hot-headed" in target_char.traits
        target_grumpy = "Grumpy" in target_char.traits

        # 1. Relationship Impact (Significant negative impact)
        rel_penalty = -10
        if initiator_hotheaded or target_hotheaded: rel_penalty -= 5 # Hot-headed arguments are worse
        if initiator_grumpy and target_grumpy: rel_penalty -=2 # Two grumps arguing is extra bad

        self.modify_relationship(target_name, rel_penalty, world, reason=f"Had an argument with {target_name}.")
        target_char.modify_relationship(self.name, rel_penalty, world, reason=f"Had an argument with {self.name}.")

        # 2. Dialogue (simple argumentative lines)
        arg_lines_initiator = [
            f"I completely disagree with your approach, {target_name}!",
            "That's just not right, and you know it!",
            "Are you even listening to yourself?"
        ]
        if initiator_hotheaded: arg_lines_initiator.append(f"This is outrageous, {target_name}!")
        elif initiator_grumpy: arg_lines_initiator.append(f"Whatever, {target_name}. You're wrong.")

        arg_lines_target = [
            f"Oh, here we go again, {self.name}...",
            "You're the one not making any sense!",
            "I don't have time for this nonsense."
        ]
        if target_hotheaded: arg_lines_target.append(f"How dare you say that to me, {self.name}?!")
        elif target_grumpy: arg_lines_target.append(f"Just leave me alone, {self.name}.")

        dialogue_line_self = random.choice(arg_lines_initiator)
        dialogue_line_target = random.choice(arg_lines_target)

        dialogue_entry = {
            "type": "argue", "initiator": self.name, "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "dialogue_exchanges": [ {"speaker": self.name, "line": dialogue_line_self}, {"speaker": target_name, "line": dialogue_line_target} ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        # 3. Opinion Impact
        if target_name not in self.opinions: self.opinions[target_name] = {}
        self.opinions[target_name]["argumentative"] = self.opinions[target_name].get("argumentative", 0) - 2
        self.opinions[target_name]["disagreeable"] = self.opinions[target_name].get("disagreeable", 0) -1
        self.opinions[target_name]["argumentative"] = max(-5, min(5, self.opinions[target_name].get("argumentative",0)))
        self.opinions[target_name]["disagreeable"] = max(-5, min(5, self.opinions[target_name].get("disagreeable",0)))


        if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
        target_char.opinions[self.name]["argumentative"] = target_char.opinions[self.name].get("argumentative", 0) - 2
        target_char.opinions[self.name]["disagreeable"] = target_char.opinions[self.name].get("disagreeable", 0) -1
        target_char.opinions[self.name]["argumentative"] = max(-5, min(5, target_char.opinions[self.name].get("argumentative",0)))
        target_char.opinions[self.name]["disagreeable"] = max(-5, min(5, target_char.opinions[self.name].get("disagreeable",0)))

        # 4. Social Need Impact (Arguments are draining)
        social_need_penalty = 15
        self.needs['Social'] = max(0, self.needs.get('Social', 0) - social_need_penalty)
        target_char.needs['Social'] = max(0, target_char.needs.get('Social', 0) - social_need_penalty)
        self.add_memory(f"Argument with {target_name} was draining. Social need -{social_need_penalty} to {self.needs['Social']}.")
        target_char.add_memory(f"Argument with {self.name} was draining. Social need -{social_need_penalty} to {target_char.needs['Social']}.")

        self.add_memory(f"Argued with {target_name}. I said: '{dialogue_line_self}'. They said: '{dialogue_line_target}'.")
        target_char.add_memory(f"Argued with {self.name}. They said: '{dialogue_line_self}'. I replied: '{dialogue_line_target}'.")
        world.add_event_log_message(f"{self.name} and {target_name} had an argument.")

        # Update relationships from opinions (even after an argument, general impression might shift)
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Mood change from argument (already applied in social need penalty, but can be more direct)
        argue_mood_penalty = config.MOOD_CHANGE_NEGATIVE_SOCIAL - 5 # Arguments are worse than just negative social
        if initiator_hotheaded: argue_mood_penalty -=5
        if target_hotheaded: # Target also gets more upset if they are hotheaded
             target_char.update_mood_score(argue_mood_penalty -5, f"Argued with hot-headed {self.name}")
        else:
             target_char.update_mood_score(argue_mood_penalty, f"Argued with {self.name}")
        self.update_mood_score(argue_mood_penalty, f"Argued with {target_name}")

        # Belonging Need Reduction (significant for both)
        belonging_penalty = 10
        self.needs['Belonging'] = max(config.NEED_SCORE_MIN, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - belonging_penalty)
        target_char.needs['Belonging'] = max(config.NEED_SCORE_MIN, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - belonging_penalty)
        self.add_memory(f"Arguing with {target_name} damaged my sense of connection. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Arguing with {self.name} made me feel more isolated. Belonging: {target_char.needs['Belonging']}")

        # Listeners might form strong negative opinions or gain negative social fulfillment
        self._process_nearby_listeners(world, target_char, "argue", self.traits, target_char.traits)
        self._apply_family_splash_effect(target_char, rel_penalty, world, reason="argued with")

        self.current_goal = self.get_default_goal()
        return

    def _execute_ask_for_help(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to ask for help, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        params = self.current_goal.parameters
        target_name = params["target_char_name"]
        target_char = world.get_character_by_name(target_name)
        help_type = params.get("help_type", "general")
        item_name_needed = params.get("item_name")
        quantity_needed = params.get("quantity", 1)

        if not target_char:
            self.add_memory(f"Wanted to ask {target_name} for help, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to ask {target_name} for help, but I don't know them.")
            self.current_goal = self.get_default_goal()
            return

        distance = abs(self.x - target_char.x) + abs(self.y - target_char.y)
        max_interaction_distance = 2
        if distance > max_interaction_distance:
            self.add_memory(f"Trying to ask {target_name} for help, moving closer.")
            self.move_towards(target_char.x, target_char.y, world)
            return

        self.add_memory(f"Approaching {target_name} to ask for {help_type} help" + (f" with {item_name_needed}" if item_name_needed else "") + ".")

        # Determine target's willingness and ability to help
        can_help = False
        willing_to_help = False

        # Willingness based on relationship, traits, and mood
        base_willingness_chance = 0.2

        # Trait influence (target)
        if "Generous" in target_char.traits or "Kind" in target_char.traits: base_willingness_chance = 0.7
        elif "Selfish" in target_char.traits or "Grumpy" in target_char.traits: base_willingness_chance = 0.05

        # Relationship Tier influence (target towards initiator)
        # Note: target_char.get_relationship_tier(self.name) would be target's view of initiator.
        # For simplicity, using initiator's view of target for now, or assume symmetric for this interaction.
        # A more advanced model would use target's actual tier towards initiator.
        target_relationship_tier_to_initiator = target_char.get_relationship_tier(self.name) # Target's tier towards me
        tier_modifier = config.RELATIONSHIP_ASK_FOR_HELP_MODIFIERS.get(target_relationship_tier_to_initiator, 0.0)
        base_willingness_chance += tier_modifier

        # Initiator's mood effect
        initiator_mood_social_modifier = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(self.mood, 0.0)
        final_willingness_chance = base_willingness_chance + initiator_mood_social_modifier

        # Initiator's reputation effect on target's willingness
        initiator_reputation_modifier = self.reputation_score * config.REPUTATION_EFFECT_ON_WILLINGNESS_TO_HELP
        final_willingness_chance += initiator_reputation_modifier
        if initiator_reputation_modifier != 0:
            target_char.add_memory(f"My willingness to help {self.name} is slightly affected by their reputation ({self.reputation_score:.0f} -> {initiator_reputation_modifier:+.2f} chance).")

        final_willingness_chance = max(0.0, min(1.0, final_willingness_chance))

        willing_to_help = random.random() < final_willingness_chance
        # Selfish trait override (stronger effect)
        if "Selfish" in target_char.traits and target_relationship_tier_to_initiator not in ["Family", "Soulmate", "Close Friend"]: # Selfish people might still help very close relations
            if random.random() > 0.05: # 95% chance selfish person will refuse unless very close
                 willing_to_help = False

        # Ability to help
        dialogue_line_self = f"Excuse me, {target_name}, I was wondering if you could help me?"
        if help_type == "resource" and item_name_needed:
            dialogue_line_self = f"{target_name}, I'm in a bit of a bind. Could you spare {quantity_needed} {item_name_needed}?"
            if target_char.inventory.get(item_name_needed, 0) >= quantity_needed:
                can_help = True
        elif help_type == "tool" and item_name_needed: # Simplistic: asking for a specific tool by name
            dialogue_line_self = f"{target_name}, I desperately need a {item_name_needed}. Do you have one I could borrow/have?"
            if target_char.inventory.get(item_name_needed, 0) > 0: # TODO: check if it's their equipped tool
                can_help = True
        elif help_type == "task_assistance": # Conceptual for now
            dialogue_line_self = f"{target_name}, I'm really struggling with this task. Any chance you could lend a hand?"
            # For task assistance, 'can_help' could depend on target's skills vs. task requirements.
            # For now, assume they can always conceptually offer some task assistance if willing.
            can_help = True # Simplified for now

        dialogue_line_target = ""
        outcome_message = ""

        if willing_to_help and can_help:
            # --- Help is given ---
            if help_type == "resource" and item_name_needed:
                target_char.inventory[item_name_needed] -= quantity_needed
                if target_char.inventory[item_name_needed] <= 0: del target_char.inventory[item_name_needed]
                self.inventory[item_name_needed] = self.inventory.get(item_name_needed, 0) + quantity_needed
                outcome_message = f"{target_name} gave {quantity_needed} {item_name_needed} to {self.name}."
                dialogue_line_target = f"Of course, {self.name}. Here you go."
            elif help_type == "tool" and item_name_needed:
                # TODO: More complex tool lending/giving logic, for now, simple transfer
                target_char.inventory[item_name_needed] -= 1
                if target_char.inventory[item_name_needed] <= 0: del target_char.inventory[item_name_needed]
                self.inventory[item_name_needed] = self.inventory.get(item_name_needed, 0) + 1
                outcome_message = f"{target_name} gave a {item_name_needed} to {self.name}."
                dialogue_line_target = f"Certainly, {self.name}, take this {item_name_needed}."
            elif help_type == "task_assistance":
                outcome_message = f"{target_name} agreed to help {self.name} with their task."
                dialogue_line_target = f"Sure, {self.name}, I can help with that for a bit."
                # Future: Target might get a temporary work order or their goal changes.

            self.modify_relationship(target_name, 5, world, reason="They helped me when I asked.") # Grateful
            target_char.modify_relationship(self.name, 3, world, reason="I helped them out.") # Feels good to help
            self.update_mood_score(config.MOOD_CHANGE_NEED_FULFILLED_FROM_CRITICAL, f"Received help from {target_name}")
            target_char.update_mood_score(config.MOOD_CHANGE_POSITIVE_SOCIAL, f"Helped {self.name}")

            rep_change_reason = f"Helped {self.name} with {item_name_needed or help_type}"
            target_char.update_reputation(config.REPUTATION_CHANGE_HELPED_OTHER, rep_change_reason, world=world)
            if abs(config.REPUTATION_CHANGE_HELPED_OTHER) >= config.REPUTATION_FOR_RUMOR_THRESHOLD and world.game_time:
                rumor_content_key = "helped_someone_positive" # Generic key
                rumor_strength = config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT
                new_rumor = Rumor(
                    subject_char_id=target_char.name,
                    content_key=rumor_content_key,
                    initial_strength=rumor_strength,
                    creation_day=world.game_time.current_day,
                    is_positive=True,
                    original_source_char_id=self.name # The one asking for help is a source/witness
                )
                world.add_rumor(new_rumor)
                # Subject (target_char) and source (self) know the rumor
                target_char.known_rumor_ids.add(new_rumor.rumor_id)
                self.known_rumor_ids.add(new_rumor.rumor_id)
                target_char.add_memory(f"A rumor ({new_rumor.rumor_id[:4]}) might be starting about me helping {self.name}.")
                self.add_memory(f"My asking for help from {target_char.name} might start a rumor ({new_rumor.rumor_id[:4]}) about their generosity.")


            if target_name not in self.opinions: self.opinions[target_name] = {}
            self.opinions[target_name]["helpful"] = self.opinions[target_name].get("helpful",0) + 2
            if self.name not in target_char.opinions: target_char.opinions[self.name] = {}
            target_char.opinions[self.name]["grateful"] = target_char.opinions[self.name].get("grateful",0) + 1

        elif willing_to_help and not can_help:
            outcome_message = f"{target_name} was willing but unable to help {self.name}."
            dialogue_line_target = f"I'd like to help, {self.name}, but I don't have any {item_name_needed} to spare right now." if item_name_needed else f"I wish I could help, {self.name}, but I'm not able to at the moment."
            self.modify_relationship(target_name, 1, world, reason="They were willing to help, even if they couldn't.")
            self.update_mood_score(config.MOOD_CHANGE_NEGATIVE_SOCIAL // 2, f"Was unable to get help from {target_name}, but they were willing.") # Lesser hit
            if target_name not in self.opinions: self.opinions[target_name] = {}
            self.opinions[target_name]["willing_but_unable"] = self.opinions[target_name].get("willing_but_unable",0) + 1
        else: # Unwilling to help (or unable and unwilling)
            outcome_message = f"{target_name} declined to help {self.name}."
            dialogue_line_target = f"Sorry, {self.name}, I can't help you with that right now."
            if "Grumpy" in target_char.traits: dialogue_line_target = f"Not my problem, {self.name}."
            elif "Selfish" in target_char.traits: dialogue_line_target = f"I need to look out for myself, {self.name}."

            self.modify_relationship(target_name, -3, world, reason="They wouldn't help when I asked.")
            self.update_mood_score(config.MOOD_CHANGE_NEGATIVE_SOCIAL, f"Denied help by {target_name}")

            target_mood_change_on_denial = -2 # Default small hit for being unhelpful
            if can_help and ("Kind" in target_char.traits or "Generous" in target_char.traits) and not ("Selfish" in target_char.traits):
                # If they *could* help, were unwilling, AND are generally kind/generous (and not selfish), they might feel some guilt.
                target_mood_change_on_denial -= 3 # Extra mood hit for guilt
                target_char.add_memory(f"Felt a bit bad for not helping {self.name} when I could have.")
            target_char.update_mood_score(target_mood_change_on_denial, f"Declined to help {self.name}")

            if target_name not in self.opinions: self.opinions[target_name] = {}
            self.opinions[target_name]["unhelpful"] = self.opinions[target_name].get("unhelpful",0) -1
            if can_help: # If they could have helped but chose not to
                 self.opinions[target_name]["unhelpful"] -=1 # Extra negative mark

        # Log dialogue and outcome
        dialogue_entry = {
            "type": "ask_for_help", "initiator": self.name, "target": target_name,
            "day": world.game_time.current_day if world.game_time else -1,
            "details_of_request": {"type": help_type, "item": item_name_needed, "qty": quantity_needed},
            "dialogue_exchanges": [ {"speaker": self.name, "line": dialogue_line_self}, {"speaker": target_name, "line": dialogue_line_target} ]
        }
        self.dialogue_history.append(dialogue_entry)
        target_char.dialogue_history.append(dialogue_entry)

        self.add_memory(f"Asked {target_name} for help. They said: '{dialogue_line_target}'. Outcome: {outcome_message}")
        target_char.add_memory(f"{self.name} asked me for help. I said: '{dialogue_line_target}'. Outcome: {outcome_message}")
        world.add_event_log_message(outcome_message)

        # Social Need Fulfillment (if help was positive or attempted earnestly)
        if willing_to_help: # Even if unable, the attempt can be socially bonding
            self.needs['Social'] = min(100, self.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_GREET_INTRODUCE) # Generic small boost
            target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_GREET_INTRODUCE)

        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)
        self._process_nearby_listeners(world, target_char, "ask_for_help", self.traits, target_char.traits)

        self.current_goal = self.get_default_goal()
        return

    def _execute_offer_comfort(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to offer comfort, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to offer comfort to {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        # Comfort is typically for known characters in a negative state
        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to offer comfort to {target_name}, but I don't know them.")
            self.current_goal = self.get_default_goal() # Changed from self.job_default_goal()
            return

        # Check if target is actually in a state deserving comfort (e.g. sick/injured)
        # This condition should ideally be part of the decision to initiate "Offer Comfort"
        if not (target_char.is_sick and target_char.sickness_severity > 3) and \
           not (target_char.is_injured and target_char.injury_severity > 3):
            self.add_memory(f"Considered offering comfort to {target_name}, but they seem fine now.")
            self.current_goal = self.get_default_goal()
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

        # 4. Fulfill Social Need
        # Initiator gets fulfillment for being kind, target for receiving comfort.
        self.needs['Social'] = min(100, self.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_OFFER_COMFORT_INITIATOR)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_OFFER_COMFORT_TARGET)
        self.add_memory(f"Social need increased by {config.SOCIAL_FULFILLMENT_OFFER_COMFORT_INITIATOR} to {self.needs['Social']} after comforting {target_name}.")
        target_char.add_memory(f"Social need increased by {config.SOCIAL_FULFILLMENT_OFFER_COMFORT_TARGET} to {target_char.needs['Social']} after being comforted by {self.name}.")

        # Update relationships based on overall opinions
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Mood change from offering/receiving comfort
        initiator_comfort_mood_boost = config.MOOD_CHANGE_POSITIVE_SOCIAL + (5 if initiator_kind else 0)
        target_comfort_mood_boost = config.MOOD_CHANGE_POSITIVE_SOCIAL + 10 # Receiving comfort is very positive
        if target_grumpy: target_comfort_mood_boost -=5 # Grumpy people are less cheered

        self.update_mood_score(initiator_comfort_mood_boost, f"Offered comfort to {target_name}")
        target_char.update_mood_score(target_comfort_mood_boost, f"Received comfort from {self.name}")

        # Belonging Need Fulfillment (significant for both)
        initiator_belonging_increase = 8
        target_belonging_increase = 10 # Receiving comfort is a strong belonging signal
        self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + initiator_belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + target_belonging_increase)
        self.add_memory(f"Offering comfort to {target_name} made me feel more connected. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Receiving comfort from {self.name} made me feel like I belong. Belonging: {target_char.needs['Belonging']}")

        # Process listeners
        self._process_nearby_listeners(world, target_char, "offer_comfort", self.traits, target_char.traits)

        self.current_goal = self.get_default_goal()
        return

    def _execute_share_positive_news(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to share news, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to share news with {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to share news with {target_name}, but I don't know them well enough.")
            self.current_goal = self.get_default_goal() # Or try to introduce first
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

        # 2. Dialogue (Potentially about a notable event)
        dialogue_line_self = ""
        dialogue_line_target = ""
        shared_event_id: Optional[str] = None

        # Attempt to share a notable event
        # Higher chance if "Chatty" or if the news queue isn't empty
        event_share_chance = 0.4 + (0.2 if initiator_chatty else 0.0)
        if world.recent_notable_events and random.random() < event_share_chance:
            unknown_events_to_target = [
                event for event in world.recent_notable_events
                if event["id"] not in target_char.known_events and event["id"] in self.known_events
            ]
            if not unknown_events_to_target and world.recent_notable_events: # If target knows all I know, or I know none, try to learn one myself to share
                 potential_new_event_for_me = [event for event in world.recent_notable_events if event["id"] not in self.known_events]
                 if potential_new_event_for_me:
                     event_to_learn = random.choice(potential_new_event_for_me)
                     self.known_events.append(event_to_learn["id"])
                     self.add_memory(f"Learned about event: {event_to_learn.get('details',{}).get('summary', event_to_learn['type'])}")
                     # Re-check if this newly learned event can be shared
                     if event_to_learn["id"] not in target_char.known_events:
                         unknown_events_to_target.append(event_to_learn)

            if unknown_events_to_target:
                event_to_share = random.choice(unknown_events_to_target)
                shared_event_id = event_to_share["id"]
                event_summary = event_to_share.get("details", {}).get("summary", f"something about {event_to_share['type']}")

                dialogue_line_self = f"Have you heard about {event_summary}?"
                if initiator_grumpy: dialogue_line_self = f"Guess you heard about {event_summary} already."
                elif initiator_friendly: dialogue_line_self = f"Oh, {target_name}, guess what! {event_summary}!"

                if target_friendly: dialogue_line_target = random.choice(["Oh, really? Tell me more!", "That's interesting news!", f"About {event_summary}? No, what happened?"])
                elif target_grumpy: dialogue_line_target = random.choice(["And?", "So?", "Old news probably."])
                else: dialogue_line_target = random.choice(["I hadn't heard.", "What about it?", "Okay."])

                target_char.known_events.append(shared_event_id) # Target now knows
                target_char.add_memory(f"Learned from {self.name} about: {event_summary}")


        if not dialogue_line_self: # Fallback to generic news/gossip if no event shared
            available_chars_for_gossip = [c.name for c in world.characters if c.name != self.name and c.name != target_name]
            gossip_subject_name = random.choice(available_chars_for_gossip) if available_chars_for_gossip else "someone"
            news_items_templates = [
                "Heard the hunters had a good catch today!",
                f"I saw {gossip_subject_name} looking particularly cheerful earlier.",
                "They say the weather's going to be perfect for the next few days.",
            ]
            if initiator_grumpy:
                news_items_templates = [ "Suppose the harvest wasn't a total disaster.", f"Heard {gossip_subject_name} actually did something useful. Surprising." ]
            dialogue_line_self = random.choice(news_items_templates)

            replies_target_generic = ["Oh, that's good to hear!", "Is that so? Interesting."]
            if target_friendly: replies_target_generic.extend(["Wonderful news!", "That's fantastic!"])
            elif target_grumpy: replies_target_generic = ["Hmph. Alright.", "Noted."]
            dialogue_line_target = random.choice(replies_target_generic)

        dialogue_entry = {
            "type": "share_positive_news", # Could be "share_event_news" if shared_event_id is not None
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

        # 4. Fulfill Social Need
        fulfillment = config.SOCIAL_FULFILLMENT_POSITIVE_NEWS
        self.needs['Social'] = min(100, self.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)
        self.add_memory(f"Social need increased by {fulfillment} to {self.needs['Social']} after sharing news with {target_name}.")
        target_char.add_memory(f"Social need increased by {fulfillment} to {target_char.needs['Social']} after hearing news from {self.name}.")

        # Update relationships based on overall opinions
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Mood change from sharing/receiving news
        news_mood_boost = config.MOOD_CHANGE_POSITIVE_SOCIAL
        if initiator_chatty: news_mood_boost += 3 # Chatty people enjoy sharing news more
        if target_grumpy: # Grumpy target might not care for news
            target_char.update_mood_score(news_mood_boost // 2, f"Heard news from {self.name}, but wasn't very interested.")
        else:
            target_char.update_mood_score(news_mood_boost, f"Heard news from {self.name}")
        self.update_mood_score(news_mood_boost + (3 if initiator_chatty else 0), f"Shared news with {target_name}")

        # Belonging Need Fulfillment
        belonging_increase = 6 # Sharing news is a good social connector
        self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        self.add_memory(f"Sharing news with {target_name} strengthened my sense of belonging. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Hearing news from {self.name} strengthened my sense of belonging. Belonging: {target_char.needs['Belonging']}")

        # Process listeners
        self._process_nearby_listeners(world, target_char, "share_positive_news", self.traits, target_char.traits)

        self.current_goal = self.get_default_goal()
        return

    def _process_nearby_listeners(self, world: 'World', target_char: 'Character', interaction_type: str, initiator_traits: List[str], target_traits: List[str]):
        """
        Processes characters who might be listening to an interaction.
        Listeners form opinions and might gain some social fulfillment.
        """
        listener_radius = 2 # How close a character needs to be to "overhear"
        social_goals = ["Greet Character", "Introduce Self to Stranger", "Small Talk", "Share Positive News", "Offer Comfort"]

        for listener in world.characters:
            if listener.name == self.name or listener.name == target_char.name:
                continue # Skip initiator and direct target

            # Listener must be idle or wandering, and not already in a social goal themselves
            if listener.current_goal not in ["Idle", "Wander"] or listener.current_goal in social_goals:
                continue

            distance_to_initiator = abs(listener.x - self.x) + abs(listener.y - self.y)
            distance_to_target = abs(listener.x - target_char.x) + abs(listener.y - target_char.y)

            if distance_to_initiator <= listener_radius or distance_to_target <= listener_radius:
                # Listener is close enough to one of the participants
                listener.add_memory(f"Overheard {self.name} and {target_char.name} interacting ({interaction_type}).")

                # Listener forms opinions about initiator's observed behavior
                if self.name not in listener.opinions: listener.opinions[self.name] = {}
                observed_tag_initiator = f"observed_{interaction_type}_style" # e.g., observed_greeting_style
                opinion_change_initiator = 0
                if "Friendly" in initiator_traits: opinion_change_initiator += 1
                if "Grumpy" in initiator_traits: opinion_change_initiator -=1
                listener.opinions[self.name][observed_tag_initiator] = max(-5, min(5, listener.opinions[self.name].get(observed_tag_initiator, 0) + opinion_change_initiator))

                # Listener forms opinions about target's observed behavior (response)
                if target_char.name not in listener.opinions: listener.opinions[target_char.name] = {}
                observed_tag_target = f"observed_{interaction_type}_response_style"
                opinion_change_target = 0
                if "Friendly" in target_traits: opinion_change_target += 1
                if "Grumpy" in target_traits: opinion_change_target -=1
                listener.opinions[target_char.name][observed_tag_target] = max(-5, min(5, listener.opinions[target_char.name].get(observed_tag_target, 0) + opinion_change_target))

                # Minor social fulfillment for listening to a neutral/positive interaction
                # (Excluding if the interaction itself was negative, e.g. an argument - future)
                if interaction_type not in ["Offer Comfort"]: # Comfort is specific, others are general
                    listener.needs['Social'] = min(100, listener.needs.get('Social', 0) + config.SOCIAL_FULFILLMENT_LISTEN_POSITIVE)
                    listener.add_memory(f"Social need slightly up from overhearing conversation.")

                # Optional: Listener Dialogue History (Step 4.C) - can be added here if desired
                # For now, just a memory.

    def _execute_small_talk(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to make small talk, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to make small talk with {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        # Small talk should only be with known characters
        if target_name not in self.known_characters:
            self.add_memory(f"Wanted to make small talk with {target_name}, but I don't know them. Maybe I should introduce myself first.")
            # self.current_goal = "Introduce Self to Stranger"
            self.current_goal = Goal(GoalType.INTRODUCE_SELF_TO_STRANGER, assignee_id=self.name, originator_id=self.name, parameters={"target_char_name": target_name})
            # self._execute_introduce_self(world) # Dispatcher will handle this new goal.
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

        # 4. Fulfill Social Need
        fulfillment = config.SOCIAL_FULFILLMENT_SMALL_TALK
        self.needs['Social'] = min(100, self.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)
        self.add_memory(f"Social need increased by {fulfillment} to {self.needs['Social']} after small talk with {target_name}.")
        target_char.add_memory(f"Social need increased by {fulfillment} to {target_char.needs['Social']} after small talk with {self.name}.")

        # Update relationships based on overall opinions
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Process listeners
        # Corrected interaction type for listeners of small talk
        self._process_nearby_listeners(world, target_char, "small_talk", self.traits, target_char.traits)

        # Mood change from small talk
        small_talk_mood_change = config.MOOD_CHANGE_POSITIVE_SOCIAL -2 # Small talk is less impactful
        if initiator_chatty: small_talk_mood_change += 2
        if target_grumpy: # Grumpy people dislike small talk
            target_char.update_mood_score(-3, f"Endured small talk with {self.name}")
            if initiator_grumpy: # If initiator also grumpy, less negative for target
                 target_char.update_mood_score(1, f"Grudgingly acknowledged {self.name}'s small talk") # net -2
        else:
            target_char.update_mood_score(small_talk_mood_change, f"Small talk with {self.name}")

        self.update_mood_score(small_talk_mood_change, f"Small talk with {target_name}")

        # Belonging Need Fulfillment
        belonging_increase = 5 # Small talk is a bit more engaging
        self.needs['Belonging'] = min(config.NEED_SCORE_MAX, self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        target_char.needs['Belonging'] = min(config.NEED_SCORE_MAX, target_char.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) + belonging_increase)
        self.add_memory(f"Small talk with {target_name} improved my sense of belonging. Belonging: {self.needs['Belonging']}")
        target_char.add_memory(f"Small talk with {self.name} improved my sense of belonging. Belonging: {target_char.needs['Belonging']}")

        self.current_goal = self.get_default_goal()
        return

    def _update_mood_from_critical_needs(self):
        """Checks critical complex needs and updates mood accordingly."""
        # Safety Need
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
            # Check if mood hasn't been recently hit for this specific need to avoid spamming penalties
            # This requires a more sophisticated tracking system (e.g., last time mood was hit for safety)
            # For now, apply it if mood is not already very low due to this.
            # A simpler check: only apply if current mood isn't already Furious/Stressed from safety.
            # This is still imperfect. A cooldown per need type would be better.
            # For this iteration, we'll just apply it, assuming it's checked once per decision cycle.
            self.update_mood_score(config.MOOD_CHANGE_SAFETY_CRITICAL, "Critically low safety")

        # Belonging Need
        if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            self.update_mood_score(config.MOOD_CHANGE_BELONGING_CRITICAL, "Critically low belonging")

        # Esteem Need
        if self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) < config.NEED_ESTEEM_CRITICAL_THRESHOLD:
            self.update_mood_score(config.MOOD_CHANGE_ESTEEM_CRITICAL, "Critically low esteem")

    def _process_learned_rumor(self, rumor: Rumor, world: 'World'):
        """Processes a newly learned rumor, potentially affecting opinions of the rumor's subject."""
        if rumor.subject_char_id == self.name:
            self.add_memory(f"Heard a rumor ({rumor.rumor_id[:4]}) about myself: '{rumor.content_key}'. No change in self-opinion from this.")
            return

        if rumor.current_strength < config.MIN_RUMOR_STRENGTH_FOR_OPINION_EFFECT:
            self.add_memory(f"Heard a faint rumor ({rumor.rumor_id[:4]}) about {rumor.subject_char_id} ('{rumor.content_key}'), but it's too weak to form a strong opinion.")
            return

        opinion_tag_key = "rumor_impression_positive" if rumor.is_positive else "rumor_impression_negative"

        # Ensure opinion dictionary exists for the subject
        if rumor.subject_char_id not in self.opinions:
            self.opinions[rumor.subject_char_id] = {}

        # Calculate opinion change based on rumor strength
        opinion_change_magnitude = rumor.current_strength * config.RUMOR_OPINION_EFFECT_STRENGTH_FACTOR
        opinion_change_magnitude = min(opinion_change_magnitude, config.MAX_OPINION_CHANGE_FROM_RUMOR) # Cap max change per rumor

        opinion_delta = int(round(opinion_change_magnitude))
        if not rumor.is_positive:
            opinion_delta *= -1

        current_opinion_score = self.opinions[rumor.subject_char_id].get(opinion_tag_key, 0)
        new_opinion_score = max(-10, min(10, current_opinion_score + opinion_delta)) # Clamp individual rumor tag

        if new_opinion_score != current_opinion_score:
            self.opinions[rumor.subject_char_id][opinion_tag_key] = new_opinion_score
            self.add_memory(f"Heard a rumor ({rumor.rumor_id[:4]}) about {rumor.subject_char_id}: '{rumor.content_key}' (Strength: {rumor.current_strength}). My '{opinion_tag_key}' opinion of them is now {new_opinion_score}.")

            # Allow this new opinion to influence overall relationship
            self._update_relationship_from_opinions(rumor.subject_char_id, world)
        else:
            self.add_memory(f"Heard a rumor ({rumor.rumor_id[:4]}) about {rumor.subject_char_id}: '{rumor.content_key}', but my opinion on that aspect didn't change significantly.")


    def _update_relationship_from_opinions(self, target_name: str, world: 'World'):
        if target_name not in self.opinions:
            return # No opinions formed yet

        opinion_tags = self.opinions.get(target_name, {})
        if not opinion_tags:
            return

        # Simple sum of opinion tag scores. More complex weighting could be added later.
        # Positive tags increase score, negative tags decrease it.
        overall_impression_score = sum(opinion_tags.values())

        # Determine a subtle adjustment factor.
        # Example: if overall_impression is +5, relationship might adjust by +0.5 or +1.
        # If -5, relationship might adjust by -0.5 or -1.
        # This should be a slow, gradual influence.
        adjustment_factor = 0.1 # How much 1 point of impression score translates to relationship points
        relationship_adjustment = int(round(overall_impression_score * adjustment_factor))

        # Max adjustment per call to prevent rapid swings based on single interactions,
        # especially if this is called frequently.
        max_adjustment_per_call = 1
        relationship_adjustment = max(-max_adjustment_per_call, min(max_adjustment_per_call, relationship_adjustment))


        if relationship_adjustment != 0:
            current_relationship = self.get_relationship_score(target_name)
            self.modify_relationship(target_name, relationship_adjustment, world,
                                     reason=f"General impression ({overall_impression_score}) led to adjustment.")
            # self.add_memory(f"My general impression of {target_name} ({overall_impression_score}) subtly changed our relationship from {current_relationship} by {relationship_adjustment}.")

        # Optional: Decay or normalization of opinion tags over time if they are meant to be more fluid.
        # For now, opinions are cumulative until directly changed by new interactions.

    def _execute_introduce_self(self, world: 'World'):
        if not self.current_goal or not self.current_goal.parameters or "target_char_name" not in self.current_goal.parameters:
            self.add_memory("Wanted to introduce myself, but no target specified in goal parameters.")
            self.current_goal = self.get_default_goal()
            return

        target_name = self.current_goal.parameters["target_char_name"]
        target_char = world.get_character_by_name(target_name)

        if not target_char:
            self.add_memory(f"Wanted to introduce myself to {target_name}, but they could not be found.")
            self.current_goal = self.get_default_goal()
            return

        # Ensure it's actually a stranger. If already known, switch to a generic greet or idle.
        if target_name in self.known_characters:
            self.add_memory(f"Wanted to introduce to {target_name}, but I already know them. Switching to greet.")
            # self.current_goal = "Greet Character"
            self.current_goal = Goal(GoalType.GREET_CHARACTER, assignee_id=self.name, originator_id=self.name, parameters={"target_char_name": target_name})
            # self._execute_greet_character(world) # Dispatcher will handle this
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

        # Reputation effect on initial relationship (initiator's view of target)
        target_reputation_effect = int(round(target_char.reputation_score * config.REPUTATION_EFFECT_ON_INITIAL_RELATIONSHIP))
        rel_change_initiator_to_target += target_reputation_effect
        reason_intro_self = f"Introduced myself to {target_name}"
        if target_reputation_effect != 0:
            reason_intro_self += f" (their reputation {target_char.reputation_score} influenced by {target_reputation_effect})"
        self.modify_relationship(target_name, rel_change_initiator_to_target, world, reason=reason_intro_self)

        rel_change_target_to_initiator = 1 # Base for neutral intro
        if target_friendly and initiator_friendly: rel_change_target_to_initiator = 3
        elif target_friendly and not initiator_grumpy: rel_change_target_to_initiator = 2
        elif target_friendly and initiator_grumpy: rel_change_target_to_initiator = 1
        elif target_grumpy and initiator_friendly: rel_change_target_to_initiator = 0
        elif target_grumpy and initiator_grumpy: rel_change_target_to_initiator = 1
        elif target_grumpy: rel_change_target_to_initiator = 0

        # Reputation effect on initial relationship (target's view of initiator)
        initiator_reputation_effect = int(round(self.reputation_score * config.REPUTATION_EFFECT_ON_INITIAL_RELATIONSHIP))
        rel_change_target_to_initiator += initiator_reputation_effect
        reason_intro_target = f"{self.name} introduced themselves"
        if initiator_reputation_effect != 0:
            reason_intro_target += f" (their reputation {self.reputation_score} influenced by {initiator_reputation_effect})"
        target_char.modify_relationship(self.name, rel_change_target_to_initiator, world, reason=reason_intro_target)

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

        # 5. Fulfill Social Need
        fulfillment = config.SOCIAL_FULFILLMENT_GREET_INTRODUCE # Same as greeting for now
        self.needs['Social'] = min(100, self.needs.get('Social', 0) + fulfillment)
        target_char.needs['Social'] = min(100, target_char.needs.get('Social', 0) + fulfillment)
        self.add_memory(f"Social need increased by {fulfillment} to {self.needs['Social']} after introducing to {target_name}.")
        target_char.add_memory(f"Social need increased by {fulfillment} to {target_char.needs['Social']} after {self.name} introduced themselves.")

        # Update relationships based on overall opinions
        self._update_relationship_from_opinions(target_name, world)
        target_char._update_relationship_from_opinions(self.name, world)

        # Mood change from introduction (generally positive)
        intro_mood_boost = config.MOOD_CHANGE_POSITIVE_SOCIAL + 1 # Slightly more than a generic greeting
        if "Friendly" in self.traits: intro_mood_boost +=2
        if "Friendly" in target_char.traits: intro_mood_boost +=2

        self.update_mood_score(intro_mood_boost, f"Introduced myself to {target_name}")
        target_char.update_mood_score(intro_mood_boost, f"Met {self.name}")

        # Process listeners
        self._process_nearby_listeners(world, target_char, "introduction", self.traits, target_char.traits)

        self.current_goal = self.get_default_goal()
        return