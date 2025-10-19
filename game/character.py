# game/character.py
from collections import deque
from copy import deepcopy
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any, Set, Deque, Union, Iterable
import random
from .llm_integration import generate_dialogue # Kept as it's used
# from .stockpile import Stockpile # Not directly used by Character methods
# from .work_order import WorkOrder # Not directly used by Character methods
from .data import (
    BLUEPRINTS,
    JOB_TASK_DEFINITIONS,
    STRUCTURE_BLUEPRINTS,
    JOB_SALARIES,
    NOBLE_RANKS_OR_JOBS,
)
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
                 vassals: Optional[List[str]] = None,
                 supervisor_name: Optional[str] = None,
                 age: Optional[int] = None,
                 origin: Optional[str] = None,
                 citizenship: str = "Resident",
                 arrival_day: Optional[int] = None):
        self.name = name; self.personality = personality; self.traits = traits;
        self.money: int = money
        self.net_worth: int = money
        self.wealth_status: str = "modest"
        self.wealth_history: Deque[Tuple[int, int]] = deque(maxlen=getattr(config, "WEALTH_HISTORY_MAX_ENTRIES", 30))
        self.businesses_owned: List[str] = []
        self.business_roles: Dict[str, str] = {}
        self.retired: bool = False
        self._last_business_check_day: Optional[int] = None
        self._last_wealth_evaluation_day: Optional[int] = None
        self._last_jealousy_day: Optional[int] = None
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
        self.family_roles: Dict[str, Set[str]] = {}
        self.romantic_partners: Set[str] = set()
        self.ex_partners: Set[str] = set()
        self.children_names: Set[str] = set()
        self.parent_names: Set[str] = set()
        self.active_romances: Dict[str, Dict[str, Any]] = {}
        self.marriage_history: List[Dict[str, Any]] = []
        self._last_family_daily_day: Optional[int] = None
        self._last_child_day: Optional[int] = None
        self._romance_cooldowns: Dict[str, int] = {}
        self._romance_attempt_window: Deque[Tuple[int, str]] = deque(maxlen=10)
        self._last_romance_eval_day: Optional[int] = None
        self._last_commitment_check: Optional[int] = None
        if self.family_members: # Then set family scores
            for member_name in self.family_members:
                if member_name != self.name:
                    self.relationships[member_name] = config.RELATIONSHIP_SCORE_FAMILY_BASE
                    kin_set = self.family_roles.setdefault("kin", set())
                    kin_set.add(member_name)

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
        self.supervisor_name: Optional[str] = supervisor_name; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False
        self.leadership_oversight_score: float = 0.0
        self._last_oversight_evaluation_day: Optional[int] = None
        self._last_oversight_summary: Optional[Dict[str, Any]] = None
        self._last_oversight_memory_day: Optional[int] = None
        self._last_management_day: Optional[int] = None
        self._management_actions_today: float = 0.0
        self._management_action_notes: List[str] = []
        self.supervisor_oversight: float = 0.0
        self.last_supervisor_oversight_day: Optional[int] = None
        self._neglect_slack_pressure: float = 0.0
        self._neglect_illegal_pressure: float = 0.0

        self.rank: str = rank
        self.liege: Optional[str] = liege
        self.vassals: List[str] = vassals if vassals is not None else []
        self.assigned_tasks: List[Dict] = [] # Historical record of manager-assigned tasks for performance reviews
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
        self.active_crime_assignment: Optional[str] = None
        self.crime_investigation_focus: Optional[Dict[str, Any]] = None
        self.active_interview_assignment: Optional[Dict[str, Any]] = None
        self.active_law_petition_id: Optional[str] = None
        self.active_law_draft_id: Optional[str] = None
        self.last_estate_review_day: Optional[int] = None
        self.active_estate_orders: List[Dict[str, Any]] = []
        self.last_high_court_day: Optional[int] = None
        self.last_campaign_speech_day: Optional[int] = None
        self._comfort_cooldowns: Dict[str, int] = {}
        self._argument_cooldowns: Dict[str, int] = {}

        self.is_sick: bool = False
        self.sickness_severity: int = 0
        self.is_injured: bool = False
        self.injury_severity: int = 0
        self.appointed_by: Optional[str] = None

        health_defaults = getattr(config, "HEALTH_PROFILE_DEFAULTS", {})
        base_vitality = float(health_defaults.get("base_vitality", 72))
        vitality_variance = float(health_defaults.get("vitality_variance", 6))
        base_immunity = float(health_defaults.get("base_immunity", 0.6))
        immunity_variance = float(health_defaults.get("immunity_variance", 0.1))
        base_stress = float(health_defaults.get("base_stress", 0.2))
        vitality = max(
            getattr(config, "HEALTH_VITALITY_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_VITALITY_CEILING", 100.0),
                base_vitality + random.uniform(-vitality_variance, vitality_variance),
            ),
        )
        immunity = max(
            getattr(config, "HEALTH_IMMUNITY_FLOOR", 0.05),
            min(
                getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                base_immunity + random.uniform(-immunity_variance, immunity_variance),
            ),
        )
        stress = max(
            getattr(config, "HEALTH_STRESS_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_STRESS_CEILING", 1.0),
                base_stress + random.uniform(-0.05, 0.05),
            ),
        )
        self.health_profile: Dict[str, Any] = {
            "vitality": vitality,
            "immune_resilience": immunity,
            "stress": stress,
            "chronic_conditions": [],
            "recent_events": deque(maxlen=getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10)),
            "condition_history": [],
            "last_checkup_day": None,
            "last_checkup_note_day": None,
        }
        self.health_profile["vitality_band"] = self._classify_vitality(vitality)
        self.health_profile["stress_band"] = self._classify_stress(stress)
        self.health_profile["immunity_band"] = self._classify_immunity(immunity)

        self.known_characters: List[str] = []
        self.opinions: Dict[str, Dict[str, int]] = {}
        self.dialogue_history: List[Dict[str, Any]] = []
        self.life_history: List[Dict[str, Any]] = []
        self._life_event_flags: Set[str] = set()
        self.known_events: List[str] = []

        self.personal_pursuits: List[Dict[str, Any]] = []
        self.personal_pursuit_log: Deque[Dict[str, Any]] = deque(
            maxlen=getattr(config, "PERSONAL_PURSUIT_LOG_MAX", 12)
        )
        self.active_personal_project: Optional[str] = None
        self._last_personal_pursuit_day: Optional[int] = None

        self.profession_history: List[Dict[str, Any]] = []
        self.career_stage: str = getattr(config, "CAREER_DEFAULT_STAGE", "Apprentice")
        self.job_satisfaction: float = getattr(config, "CAREER_SATISFACTION_BASELINE", 0.6)
        self.professional_focus: Optional[str] = None
        self.current_profession_tenure: int = 0
        self._current_profession_start_day: Optional[int] = None
        self._last_profession_review_day: Optional[int] = None
        self._last_career_stage_day: Optional[int] = None
        self._last_career_high_day: Optional[int] = None
        self._last_burnout_alert_day: Optional[int] = None
        self._last_recorded_job: Optional[str] = self.job
        self._triggered_tenure_milestones: Set[int] = set()

        self.age_years: int = age if age is not None else random.randint(18, 45)
        self.age_in_days: int = 0
        self.origin: str = origin or "Local"
        self.citizenship_status: str = citizenship
        self.arrival_day: Optional[int] = arrival_day
        self._last_phase_key: Optional[str] = None
        self._phase_social_bias: float = 0.0
        self._phase_rest_threshold_bonus: int = 0

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
        self.home_location: Optional[Tuple[int, int]] = None
        self.resting_at_home: bool = False
        self._rest_ticks: int = 0

        # Mood related attributes
        self.mood_score: int = config.MOOD_SCORE_NEUTRAL_START
        self.mood: str = "Neutral" # Initial descriptive mood, will be updated by _determine_mood_level
        # self.mood_tendency: Optional[str] = None # Example: "Optimistic", "Pessimistic" - for future enhancement
        self._determine_mood_level() # Set initial mood string based on score

        self._initialize_personal_pursuits()

        base_decision_weights = getattr(config, "DECISION_BASE_WEIGHTS", None)
        if base_decision_weights:
            self._decision_profile: Dict[str, Any] = deepcopy(base_decision_weights)
        else:
            self._decision_profile = {
                "work_focus": 1.0,
                "social_focus": 1.0,
                "rest_threshold_adjustment": 0.0,
                "ask_for_help_multiplier": 1.0,
                "risk_modifier": 1.0,
            }
        self._decision_profile_day: Optional[int] = None

        # Reputation attribute
        self.reputation_score: int = 0 # Initialize reputation
        self.known_rumor_ids: Set[str] = set() # For tracking rumors known by this character
        self._cached_path: Deque[Tuple[int, int]] = deque()
        self._cached_path_target: Optional[Tuple[int, int]] = None
        self._cached_path_revision: Optional[int] = None
        self.criminal_record: List[Dict[str, Any]] = []

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

        # Ensure scores that fall between Neutral and the first negative tier still read as Neutral
        neutral_floor = config.MOOD_LEVELS.get("Neutral", 0)
        displeased_floor = config.MOOD_LEVELS.get("Displeased", neutral_floor - 30)
        if (
            self.mood_score < neutral_floor
            and self.mood_score >= displeased_floor
            and current_mood_name not in {"Displeased", "Angry", "Furious"}
        ):
            current_mood_name = "Neutral"


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

    def participate_in_training(
        self,
        program_name: str,
        skill_name: str,
        experience_gain: float,
        world: 'World',
    ) -> Dict[str, Union[int, float]]:
        """Apply structured training progress and return before/after metrics."""

        skill_record = self.skills.get(skill_name)
        before_level = skill_record["level"] if skill_record else 0
        before_experience = skill_record["experience"] if skill_record else 0.0

        self._grant_skill_experience(skill_name, experience_gain, world)

        updated_record = self.skills.get(skill_name, {})
        after_level = updated_record.get("level", before_level)
        after_experience = updated_record.get("experience", before_experience)

        esteem_default = getattr(config, "NEED_ESTEEM_DEFAULT", 50)
        esteem_cap = getattr(config, "NEED_SCORE_MAX", 100)
        esteem_boost = getattr(config, "TRAINING_ESTEEM_BOOST", 0)
        if esteem_boost:
            current_esteem = self.needs.get("Esteem", esteem_default)
            self.needs["Esteem"] = min(esteem_cap, current_esteem + esteem_boost)

        self.add_memory(
            f"Attended {program_name} to hone {skill_name}. "
            f"Level {before_level}→{after_level}."
        )

        return {
            "level_before": before_level,
            "level_after": after_level,
            "experience_before": before_experience,
            "experience_after": after_experience,
        }

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

    def _process_builder_routine(self, world: 'World') -> bool:
        """Handle builder duty goals and active build orders."""
        if self.job != "Builder":
            return False

        if not self.current_goal:
            self.current_goal = self.get_default_goal()

        if self.active_build_order_id:
            if self.current_goal.type != GoalType.EXECUTE_BUILD_ORDER:
                self.current_goal = Goal(
                    GoalType.EXECUTE_BUILD_ORDER,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={
                        "order_id": self.active_build_order_id,
                        "structure_type": self.current_building_project,
                        "location": self.building_site_target,
                    },
                )
            self._execute_build_order(world)
            return True

        if self.current_goal.type != GoalType.PERFORM_BUILDER_DUTIES:
            return False

        approved_build_orders = world.get_approved_build_orders()
        if not approved_build_orders:
            self.add_memory("No build orders available for Builder Duties.")
            self.current_goal = self.get_default_goal()
            return True

        order_to_take = approved_build_orders[0]
        order_to_take.status = "InProgress"
        order_to_take.assigned_to = self.name

        self._reset_building_state()
        self.active_build_order_id = order_to_take.order_id
        details = order_to_take.details or {}
        self.current_building_project = details.get("structure_type")
        self.building_site_target = details.get("location")
        self.materials_gathered_for_build = False

        self.current_goal = Goal(
            GoalType.EXECUTE_BUILD_ORDER,
            assignee_id=self.name,
            originator_id=self.name,
            parameters={
                "order_id": self.active_build_order_id,
                "structure_type": self.current_building_project,
                "location": self.building_site_target,
            },
        )
        structure_label = self.current_building_project or "a structure"
        self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {structure_label}.")
        self._execute_build_order(world)
        return True

    def _reset_crafting_state(self):
        self.active_work_order_id = None; self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False; self.resource_to_fetch = None
        self.crafting_progress = 0; self.workshop_location = None
        # self.hauling_info = None # Attribute removed

    def get_status_and_emoji(self) -> Tuple[str, str]:
        if self.resting_at_home:
            return "Resting", "😴"
        if self.is_sick or self.is_injured:
            return "Unwell", "🤒"
        if self.current_goal:
            goal_type = self.current_goal.type
            # Mapping from goal types to status and emoji
            goal_to_status = {
                (GoalType.SMALL_TALK, GoalType.GREET_CHARACTER, GoalType.SHARE_POSITIVE_NEWS, GoalType.INTRODUCE_SELF_TO_STRANGER, GoalType.SHARE_RUMOR): ("Socializing", "💬"),
                (GoalType.EXECUTE_BUILD_ORDER, GoalType.EXECUTE_CRAFT_ORDER, GoalType.GATHER_RESOURCE, GoalType.PERFORM_WOODCUTTER_DUTIES, GoalType.PERFORM_STONEMASON_DUTIES): ("Working", "🛠️"),
                (GoalType.EAT_FOOD, GoalType.DRINK_WATER): ("Eating", "🍴"),
                (GoalType.WANDER,): ("Wandering", "🚶"),
            }
            for goals, (status, emoji) in goal_to_status.items():
                if goal_type in goals:
                    return status, emoji

            if self.job == 'Builder' and self.active_build_order_id:
                return "Building", "🏗️"

        if self.mood == "Happy":
             return "Idle", "😊"
        if self.mood == "Sad":
             return "Idle", "😢"

        return "Idle", "🙂"

    def get_current_task_label(self) -> str:
        if not self.current_goal:
            return "Thinking..."

        goal_type = self.current_goal.type
        params = self.current_goal.parameters or {}

        if goal_type == GoalType.IDLE:
            return "Idling"
        if goal_type == GoalType.WANDER:
            return "Wandering aimlessly"
        if goal_type == GoalType.EXECUTE_BUILD_ORDER and self.current_building_project:
            return f"Building a {STRUCTURE_BLUEPRINTS.get(self.current_building_project, {}).get('display_name', self.current_building_project)}"
        if goal_type == GoalType.GATHER_RESOURCE and 'resource_name' in params:
            return f"Gathering {params['resource_name']}"
        if goal_type in [GoalType.SMALL_TALK, GoalType.GREET_CHARACTER, GoalType.INTRODUCE_SELF_TO_STRANGER] and 'target_char_name' in params:
            return f"Chatting with {params['target_char_name']}"
        if goal_type == GoalType.REST_AT_HOME:
            return "Resting at home"

        # Generic fallback
        goal_name = goal_type.name.replace("_", " ").title()
        return goal_name

    def to_dict(self, world: Optional['World'] = None):
        """Converts the character object to a dictionary for serialization."""
        status, emoji = self.get_status_and_emoji()
        current_task = self.get_current_task_label()
        location_short = ""
        if world:
            building = world.get_building_at(self.x, self.y)
            if building:
                location_short = building.display_name
            else:
                tile = world.get_tile(self.x, self.y)
                if tile:
                    location_short = tile.replace("_", " ").title()
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
            "career_stage": self.career_stage,
            "job_satisfaction": self.job_satisfaction,
            "profession_focus": self.professional_focus,
            "profession_tenure": self.current_profession_tenure,
            "profession_history": self.export_profession_history(limit=8),
            "is_sick": self.is_sick,
            "sickness_severity": self.sickness_severity,
            "is_injured": self.is_injured,
            "injury_severity": self.injury_severity,
            "health_profile": self.get_health_snapshot(),
            "supervisor_name": self.supervisor_name,
            "subordinates_names": self.subordinates_names,
            "performance_rating": self.performance_rating,
            "warning_count": self.warning_count,
            "known_characters": self.known_characters,
            "relationships": self.relationships,
            "opinions": self.opinions,
            "dialogue_history": self.dialogue_history[-10:], # Return last 10 for brevity
            "decision_profile": deepcopy(self._decision_profile) if self._decision_profile else None,
            "personal_pursuits": self.export_personal_pursuits(),
            "personal_pursuit_log": self.export_personal_pursuit_log(limit=8),
            "active_personal_project": self.active_personal_project,
            "criminal_record": self.criminal_record,
            "reputation_score": self.reputation_score,
            "family_members": self.family_members,
            "family_roles": self.get_family_roles_snapshot(),
            "romantic_partners": self.get_romantic_partners(),
            "life_highlights": self.get_life_highlights(),
            # New fields for HUD
            "status": status,
            "emoji": emoji,
            "current_task": current_task,
            "location_short": location_short,
        }

    @staticmethod
    def _classify_vitality(value: float) -> str:
        if value >= 85:
            return "robust"
        if value >= 70:
            return "steady"
        if value >= 50:
            return "strained"
        if value >= 30:
            return "frail"
        return "critical"

    @staticmethod
    def _classify_stress(value: float) -> str:
        if value <= 0.18:
            return "calm"
        if value <= 0.32:
            return "steady"
        if value <= 0.55:
            return "tense"
        if value <= 0.75:
            return "strained"
        return "overwhelmed"

    @staticmethod
    def _classify_immunity(value: float) -> str:
        if value >= 0.78:
            return "resilient"
        if value >= 0.6:
            return "steady"
        if value >= 0.45:
            return "susceptible"
        return "fragile"

    def get_health_snapshot(self) -> Dict[str, Any]:
        profile = getattr(self, "health_profile", None)
        if not profile:
            return {}

        snapshot: Dict[str, Any] = {
            "vitality": round(float(profile.get("vitality", 0.0)), 1),
            "immune_resilience": round(float(profile.get("immune_resilience", 0.0)), 3),
            "stress": round(float(profile.get("stress", 0.0)), 3),
            "vitality_band": profile.get("vitality_band"),
            "stress_band": profile.get("stress_band"),
            "immunity_band": profile.get("immunity_band"),
            "last_checkup_day": profile.get("last_checkup_day"),
        }

        events = profile.get("recent_events", [])
        if isinstance(events, deque):
            events_iterable = list(events)
        else:
            events_iterable = list(events)
        snapshot["recent_events"] = [deepcopy(evt) for evt in events_iterable[-getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10):]]

        condition_history = profile.get("condition_history", [])
        snapshot["condition_history"] = [deepcopy(evt) for evt in condition_history[-12:]]
        snapshot["chronic_conditions"] = [deepcopy(entry) for entry in profile.get("chronic_conditions", [])]
        snapshot["active_conditions"] = [deepcopy(entry) for entry in profile.get("active_conditions", [])]

        return snapshot

    def record_health_event(
        self,
        world: Optional['World'],
        event_type: str,
        summary: str,
        *,
        severity: Optional[float] = None,
        delta: Optional[float] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        profile = getattr(self, "health_profile", None)
        if profile is None:
            return {}

        event_day = None
        if world and world.game_time:
            event_day = world.game_time.current_day

        record = {
            "day": event_day,
            "type": event_type,
            "summary": summary,
        }
        if severity is not None:
            record["severity"] = round(float(severity), 2)
        if delta is not None:
            record["delta"] = round(float(delta), 2)
        if tags:
            record["tags"] = [str(tag) for tag in tags if tag]

        significance = 1
        if event_type in {"fell_ill", "injured", "recovered"}:
            significance = 2

        self.add_memory(summary)

        life_event_logged = False
        life_event_error: Optional[str] = None
        try:
            self.record_life_event(
                world,
                f"health_{event_type}",
                summary,
                tags=["health"] + list(record.get("tags", [])),
                significance=significance,
            )
            life_event_logged = True
        except Exception as exc:  # noqa: BLE001
            life_event_error = f"{exc.__class__.__name__}: {exc}"
            if world and hasattr(world, "add_event_log_message"):
                world.add_event_log_message(
                    f"Failed to log health life event '{event_type}' for {self.name}: {life_event_error}"
                )

        record["life_event_logged"] = life_event_logged
        if life_event_error:
            record["life_event_error"] = life_event_error

        events_deque = profile.setdefault(
            "recent_events",
            deque(maxlen=getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10)),
        )
        events_deque.append(record)

        history = profile.setdefault("condition_history", [])
        history.append(dict(record))
        if len(history) > 48:
            del history[:-48]

        return dict(record)

    def evaluate_daily_health(self, world: Optional['World']) -> List[Dict[str, Any]]:
        profile = getattr(self, "health_profile", None)
        if profile is None:
            return []

        events: List[Dict[str, Any]] = []
        need_thresholds = getattr(config, "HEALTH_NEED_THRESHOLDS", {})
        need_margin = getattr(config, "HEALTH_NEED_RECOVERY_MARGIN", 15)
        vitality_weights = getattr(config, "HEALTH_VITALITY_NEED_WEIGHTS", {})
        stress_need_weight = getattr(config, "HEALTH_STRESS_NEED_WEIGHT", 0.1)
        stress_recovery = getattr(config, "HEALTH_STRESS_RECOVERY_RATE", 0.05)
        vitality_recovery_bonus = getattr(config, "HEALTH_VITALITY_RECOVERY_BONUS", 2.0)

        vitality = float(profile.get("vitality", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_vitality", 70)))
        stress = float(profile.get("stress", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_stress", 0.2)))
        immunity = float(profile.get("immune_resilience", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_immunity", 0.6)))

        vitality_delta = 0.0
        stress_delta = 0.0

        for need, threshold in need_thresholds.items():
            current_value = self.needs.get(need, threshold)
            if current_value < threshold:
                deficit = (threshold - current_value) / 100.0
                vitality_delta -= deficit * vitality_weights.get(need, 5.0)
                stress_delta += deficit * stress_need_weight
            elif current_value >= threshold + need_margin:
                recovery_factor = (current_value - threshold) / 100.0
                vitality_delta += recovery_factor * vitality_recovery_bonus
                stress_delta -= stress_recovery

        if self.is_sick and self.sickness_severity > 0:
            vitality_delta -= 1.0 + 0.18 * float(self.sickness_severity)
            stress_delta += 0.04 * float(self.sickness_severity)
        if self.is_injured and self.injury_severity > 0:
            vitality_delta -= 0.8 + 0.12 * float(self.injury_severity)
            stress_delta += 0.035 * float(self.injury_severity)

        vitality = max(
            getattr(config, "HEALTH_VITALITY_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_VITALITY_CEILING", 100.0),
                vitality + vitality_delta,
            ),
        )
        stress = max(
            getattr(config, "HEALTH_STRESS_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_STRESS_CEILING", 1.0),
                stress + stress_delta,
            ),
        )

        immunity += (vitality - getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_vitality", 70)) / 100.0 * getattr(config, "HEALTH_IMMUNITY_VITALITY_WEIGHT", 0.32)
        immunity -= stress * getattr(config, "HEALTH_IMMUNITY_STRESS_WEIGHT", 0.45)
        if not self.is_sick and not self.is_injured and vitality_delta > 0:
            immunity += 0.02
        immunity = max(
            getattr(config, "HEALTH_IMMUNITY_FLOOR", 0.05),
            min(
                getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                immunity,
            ),
        )

        profile["vitality"] = vitality
        profile["stress"] = stress
        profile["immune_resilience"] = immunity
        profile["immunity_band"] = self._classify_immunity(immunity)

        if world and world.game_time:
            profile["last_evaluated_day"] = world.game_time.current_day

        previous_band = profile.get("vitality_band")
        new_band = self._classify_vitality(vitality)
        if previous_band and new_band != previous_band:
            change = vitality - profile.get("previous_vitality", vitality)
            events.append(
                self.record_health_event(
                    world,
                    "vitality_shift",
                    f"Vitality is now {new_band} ({vitality:.0f}).",
                    delta=change,
                    tags=["vitality"],
                )
            )
        profile["vitality_band"] = new_band
        profile["previous_vitality"] = vitality

        previous_stress_band = profile.get("stress_band")
        new_stress_band = self._classify_stress(stress)
        if previous_stress_band and new_stress_band != previous_stress_band:
            events.append(
                self.record_health_event(
                    world,
                    "stress_shift",
                    f"Stress level is now {new_stress_band} ({stress:.2f}).",
                    severity=stress,
                    tags=["stress"],
                )
            )
        profile["stress_band"] = new_stress_band

        sickness_model = getattr(config, "HEALTH_SICKNESS_MODEL", {})
        injury_model = getattr(config, "HEALTH_INJURY_MODEL", {})

        # Sickness progression or onset
        if not self.is_sick:
            exposure_bonus = 0.0
            if world:
                for other in world.get_nearby_characters(self, radius=sickness_model.get("exposure_radius", 1)):
                    if getattr(other, "is_sick", False):
                        exposure_bonus += sickness_model.get("exposure_bonus", 0.05)
            vitality_factor = max(0.0, (sickness_model.get("worsen_threshold", 40) - vitality) / 100.0)
            immunity_factor = max(0.0, 1.0 - immunity)
            sickness_chance = (
                sickness_model.get("base_chance", 0.01)
                + vitality_factor * sickness_model.get("vitality_weight", 0.2)
                + immunity_factor * sickness_model.get("immunity_weight", 0.3)
                + exposure_bonus
            )
            sickness_chance = min(0.95, max(0.0, sickness_chance))
            if random.random() < sickness_chance:
                severity_range = sickness_model.get("severity_range", (1.0, 3.0))
                severity = max(0.5, random.uniform(*severity_range))
                self.is_sick = True
                self.sickness_severity = round(max(float(self.sickness_severity), severity), 1)
                event = self.record_health_event(
                    world,
                    "fell_ill",
                    f"Fell ill (severity {self.sickness_severity:.1f}).",
                    severity=self.sickness_severity,
                    tags=["illness"],
                )
                events.append(event)
                if world:
                    world.add_event_log_message(f"{self.name} has fallen ill (severity {self.sickness_severity:.1f}).")
                    world.add_notable_event(
                        "CharacterSickness",
                        {
                            "summary": f"{self.name} has fallen ill.",
                            "character": self.name,
                            "severity": self.sickness_severity,
                        },
                    )
                    if world.game_time:
                        new_rumor = Rumor(
                            subject_char_id=self.name,
                            content_key="has_fallen_ill_negative",
                            initial_strength=config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT,
                            creation_day=world.game_time.current_day,
                            is_positive=False,
                            original_source_char_id=self.name,
                        )
                        world.add_rumor(new_rumor)
                        self.known_rumor_ids.add(new_rumor.rumor_id)
        else:
            worsen_threshold = sickness_model.get("worsen_threshold", 40)
            worsen_chance = sickness_model.get("worsen_chance", 0.2)
            if vitality < worsen_threshold and random.random() < worsen_chance:
                increase = random.choice([0.5, 1.0])
                self.sickness_severity = round(min(10.0, self.sickness_severity + increase), 1)
                events.append(
                    self.record_health_event(
                        world,
                        "sickness_worsened",
                        f"Illness worsened to severity {self.sickness_severity:.1f}.",
                        severity=self.sickness_severity,
                        tags=["illness", "worsened"],
                    )
                )
            else:
                recovery = sickness_model.get("recovery_rate", 0.8)
                if vitality >= sickness_model.get("recovery_vitality", 70):
                    recovery += 0.6
                recovery += max(0.0, immunity - 0.55) * sickness_model.get("recovery_immunity_bonus", 0.05) * 5
                previous_severity = self.sickness_severity
                self.sickness_severity = round(max(0.0, self.sickness_severity - recovery), 1)
                if self.sickness_severity <= 0:
                    self.is_sick = False
                    self.sickness_severity = 0
                    events.append(
                        self.record_health_event(
                            world,
                            "recovered",
                            "Recovered from illness.",
                            tags=["illness", "recovery"],
                        )
                    )
                    immunity = min(
                        getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                        immunity + sickness_model.get("recovery_immunity_bonus", 0.05),
                    )
                    profile["immune_resilience"] = immunity
                    profile["immunity_band"] = self._classify_immunity(immunity)
                    if world:
                        world.add_event_log_message(f"{self.name} has recovered from illness.")
                elif previous_severity - self.sickness_severity >= 1.5:
                    events.append(
                        self.record_health_event(
                            world,
                            "sickness_improved",
                            f"Illness eased to severity {self.sickness_severity:.1f}.",
                            severity=self.sickness_severity,
                            tags=["illness", "improving"],
                        )
                    )

        # Injury progression or onset
        if not self.is_injured:
            job_modifier = injury_model.get("job_risk", {}).get(self.job, 0.0)
            vitality_penalty = max(0.0, (injury_model.get("worsen_threshold", 45) - vitality) / 100.0) * injury_model.get("vitality_weight", 0.01)
            injury_chance = min(0.9, max(0.0, injury_model.get("base_chance", 0.0015) + job_modifier + vitality_penalty))
            if random.random() < injury_chance:
                severity_range = injury_model.get("severity_range", (1.0, 4.0))
                injury_severity = max(0.5, random.uniform(*severity_range))
                self.is_injured = True
                self.injury_severity = round(max(float(self.injury_severity), injury_severity), 1)
                event = self.record_health_event(
                    world,
                    "injured",
                    f"Sustained an injury (severity {self.injury_severity:.1f}).",
                    severity=self.injury_severity,
                    tags=["injury"],
                )
                events.append(event)
                if world:
                    world.add_event_log_message(f"{self.name} has been injured (severity {self.injury_severity:.1f}).")
                    world.add_notable_event(
                        "CharacterInjury",
                        {
                            "summary": f"{self.name} has been injured.",
                            "character": self.name,
                            "severity": self.injury_severity,
                        },
                    )
                    if world.game_time:
                        new_rumor = Rumor(
                            subject_char_id=self.name,
                            content_key="has_been_injured_negative",
                            initial_strength=config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT,
                            creation_day=world.game_time.current_day,
                            is_positive=False,
                            original_source_char_id=self.name,
                        )
                        world.add_rumor(new_rumor)
                        self.known_rumor_ids.add(new_rumor.rumor_id)
        else:
            worsen_threshold = injury_model.get("worsen_threshold", 45)
            worsen_chance = injury_model.get("worsen_chance", 0.15)
            if vitality < worsen_threshold and random.random() < worsen_chance:
                increase = random.choice([0.5, 1.0])
                self.injury_severity = round(min(10.0, self.injury_severity + increase), 1)
                events.append(
                    self.record_health_event(
                        world,
                        "injury_worsened",
                        f"Injury worsened to severity {self.injury_severity:.1f}.",
                        severity=self.injury_severity,
                        tags=["injury", "worsened"],
                    )
                )
            else:
                recovery = injury_model.get("recovery_rate", 0.7)
                if vitality >= injury_model.get("recovery_vitality", 65):
                    recovery += 0.4
                previous_severity = self.injury_severity
                self.injury_severity = round(max(0.0, self.injury_severity - recovery), 1)
                if self.injury_severity <= 0:
                    self.is_injured = False
                    self.injury_severity = 0
                    events.append(
                        self.record_health_event(
                            world,
                            "injury_healed",
                            "Recovered from injury.",
                            tags=["injury", "recovery"],
                        )
                    )
                elif previous_severity - self.injury_severity >= 1.5:
                    events.append(
                        self.record_health_event(
                            world,
                            "injury_improved",
                            f"Injury eased to severity {self.injury_severity:.1f}.",
                            severity=self.injury_severity,
                            tags=["injury", "improving"],
                        )
                    )

        active_conditions: List[Dict[str, Any]] = []
        if self.is_sick and self.sickness_severity > 0:
            active_conditions.append({
                "type": "illness",
                "severity": self.sickness_severity,
                "status": "active",
            })
        if self.is_injured and self.injury_severity > 0:
            active_conditions.append({
                "type": "injury",
                "severity": self.injury_severity,
                "status": "active",
            })
        chronic_conditions = profile.get("chronic_conditions", [])
        profile["active_conditions"] = active_conditions + [deepcopy(cond) for cond in chronic_conditions]

        if (self.is_sick or self.is_injured) and world and world.game_time:
            note_day = profile.get("last_checkup_note_day")
            if note_day is None or world.game_time.current_day - note_day >= 3:
                events.append(
                    self.record_health_event(
                        world,
                        "checkup_due",
                        "Needs a clinic follow-up soon.",
                        tags=["medical"],
                    )
                )
                profile["last_checkup_note_day"] = world.game_time.current_day

        return [event for event in events if event]

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

    def _summarize_recent_memory(self) -> Dict[str, Any]:
        lookback = getattr(config, "DECISION_MEMORY_LOOKBACK", 20)
        keywords: Dict[str, Dict[str, float]] = getattr(config, "DECISION_MEMORY_KEYWORD_EFFECTS", {})
        summary: Dict[str, Any] = {"keyword_hits": {}, "entries_considered": 0}
        if not self.memory or not keywords:
            return summary

        recent_entries = self.memory[-lookback:]
        summary["entries_considered"] = len(recent_entries)
        keyword_hits: Dict[str, int] = {}
        for entry in recent_entries:
            entry_lower = entry.lower()
            for keyword in keywords.keys():
                if keyword in entry_lower:
                    keyword_hits[keyword] = keyword_hits.get(keyword, 0) + 1
        summary["keyword_hits"] = keyword_hits
        return summary

    def _build_decision_profile(self, world: 'World') -> Dict[str, Any]:
        base_weights = getattr(config, "DECISION_BASE_WEIGHTS", None)
        if base_weights:
            profile: Dict[str, Any] = deepcopy(base_weights)
        else:
            profile = {
                "work_focus": 1.0,
                "social_focus": 1.0,
                "rest_threshold_adjustment": 0.0,
                "ask_for_help_multiplier": 1.0,
                "risk_modifier": 1.0,
            }

        memory_summary = self._summarize_recent_memory()
        profile["memory_summary"] = memory_summary
        keyword_effects: Dict[str, Dict[str, float]] = getattr(config, "DECISION_MEMORY_KEYWORD_EFFECTS", {})
        for keyword, count in memory_summary.get("keyword_hits", {}).items():
            effects = keyword_effects.get(keyword)
            if not effects:
                continue
            for effect_key, modifier in effects.items():
                if effect_key == "rest_threshold_adjustment":
                    profile[effect_key] = profile.get(effect_key, 0.0) + (modifier * count)
                else:
                    profile[effect_key] = profile.get(effect_key, 1.0 if effect_key != "rest_threshold_adjustment" else 0.0) + (modifier * count)

        personality_biases: Dict[str, Dict[str, float]] = getattr(config, "DECISION_PERSONALITY_BIASES", {})
        for key, value in personality_biases.get(self.personality, {}).items():
            profile[key] = profile.get(key, 0.0 if key == "rest_threshold_adjustment" else 1.0) + value

        trait_biases: Dict[str, Dict[str, float]] = getattr(config, "DECISION_TRAIT_BIASES", {})
        for trait in self.traits:
            for key, value in trait_biases.get(trait, {}).items():
                profile[key] = profile.get(key, 0.0 if key == "rest_threshold_adjustment" else 1.0) + value

        if self.job:
            job_biases: Dict[str, Dict[str, float]] = getattr(config, "DECISION_JOB_FOCUS", {})
            for key, value in job_biases.get(self.job, {}).items():
                profile[key] = profile.get(key, 0.0 if key == "rest_threshold_adjustment" else 1.0) + value

        positive_threshold = getattr(config, "DECISION_RELATIONSHIP_POSITIVE_THRESHOLD", 60)
        negative_threshold = getattr(config, "DECISION_RELATIONSHIP_NEGATIVE_THRESHOLD", -25)
        positive_count = 0
        negative_count = 0
        for relation_score in self.relationships.values():
            if relation_score >= positive_threshold:
                positive_count += 1
            elif relation_score <= negative_threshold:
                negative_count += 1
        profile["relationship_summary"] = {
            "positive": positive_count,
            "negative": negative_count,
        }
        profile["social_focus"] = profile.get("social_focus", 1.0) + (
            positive_count * getattr(config, "DECISION_RELATIONSHIP_POSITIVE_BONUS", 0.0)
        )
        profile["social_focus"] = profile.get("social_focus", 1.0) + (
            negative_count * getattr(config, "DECISION_RELATIONSHIP_NEGATIVE_PENALTY", 0.0)
        )
        profile["rest_threshold_adjustment"] = profile.get("rest_threshold_adjustment", 0.0) + (
            negative_count * getattr(config, "DECISION_RELATIONSHIP_STRESS_REST", 0.0)
        )

        satisfaction_baseline = getattr(config, "CAREER_SATISFACTION_BASELINE", 0.6)
        satisfaction_offset = self.job_satisfaction - satisfaction_baseline
        profile["work_focus"] = profile.get("work_focus", 1.0) + (
            satisfaction_offset * getattr(config, "DECISION_JOB_SATISFACTION_WEIGHT", 0.0)
        )
        if satisfaction_offset < -0.25:
            profile["rest_threshold_adjustment"] = profile.get("rest_threshold_adjustment", 0.0) + getattr(
                config,
                "DECISION_BURNOUT_REST_BONUS",
                0.0,
            )

        profile["work_focus"] = max(0.35, min(1.85, profile.get("work_focus", 1.0)))
        profile["social_focus"] = max(0.2, min(2.0, profile.get("social_focus", 1.0)))
        profile["ask_for_help_multiplier"] = max(0.2, min(2.5, profile.get("ask_for_help_multiplier", 1.0)))
        profile["risk_modifier"] = max(0.3, min(1.8, profile.get("risk_modifier", 1.0)))
        profile["rest_threshold_adjustment"] = max(
            -10.0,
            min(15.0, profile.get("rest_threshold_adjustment", 0.0)),
        )

        if world.game_time:
            profile["evaluated_day"] = world.game_time.current_day
            self._decision_profile_day = world.game_time.current_day

        return profile

    def record_life_event(
        self,
        world: Optional['World'],
        event_type: str,
        summary: str,
        *,
        related: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        significance: int = 1,
        propagate_to_family: bool = False,
        details: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append a structured life event to the character's personal chronicle."""

        related_list: List[str] = []
        if related:
            if isinstance(related, (list, tuple, set)):
                related_list = [str(item) for item in related if item]
            else:
                related_list = [str(related)]

        tags_list: List[str] = []
        if tags:
            if isinstance(tags, (list, tuple, set)):
                tags_list = [str(tag) for tag in tags if tag]
            else:
                tags_list = [str(tags)]

        day = None
        if world and world.game_time:
            day = world.game_time.current_day
        elif self.arrival_day is not None:
            day = self.arrival_day
        else:
            day = len(self.life_history)

        significance = max(1, int(significance))

        event: Dict[str, Any] = {
            "day": day,
            "type": event_type,
            "summary": summary,
            "related": related_list,
            "tags": tags_list,
            "significance": significance,
            "source": self.name,
        }
        if details:
            event["details"] = deepcopy(details)

        if dedupe_key:
            for existing in reversed(self.life_history):
                if existing.get("dedupe_key") == dedupe_key:
                    return deepcopy(existing)
            event["dedupe_key"] = dedupe_key

        self.life_history.append(event)
        max_events = getattr(config, "LIFE_HISTORY_MAX_EVENTS", 120)
        if len(self.life_history) > max_events:
            self.life_history = self.life_history[-max_events:]

        if propagate_to_family and world and hasattr(world, "share_family_event"):
            world.share_family_event(self, event)

        return deepcopy(event)

    def _life_event_exists(self, candidate: Dict[str, Any]) -> bool:
        signature = (
            candidate.get("day"),
            candidate.get("type"),
            candidate.get("summary"),
            candidate.get("source"),
        )
        for existing in self.life_history:
            if existing.get("dedupe_key") and candidate.get("dedupe_key"):
                if existing.get("dedupe_key") == candidate.get("dedupe_key"):
                    return True
            existing_signature = (
                existing.get("day"),
                existing.get("type"),
                existing.get("summary"),
                existing.get("source"),
            )
            if existing_signature == signature:
                return True
        return False

    def register_family_role(self, relation_type: str, other_name: str) -> None:
        if not relation_type or not other_name or other_name == self.name:
            return

        bucket = self.family_roles.setdefault(relation_type, set())
        bucket.add(other_name)

        if relation_type == "partners":
            self.romantic_partners.add(other_name)
            self.ex_partners.discard(other_name)
            if other_name in self.active_romances:
                self.active_romances.pop(other_name, None)
        elif relation_type == "children":
            self.children_names.add(other_name)
        elif relation_type == "parents":
            self.parent_names.add(other_name)

        if relation_type != "kin" and "kin" in self.family_roles:
            kin_bucket = self.family_roles["kin"]
            if other_name in kin_bucket:
                kin_bucket.discard(other_name)
                if not kin_bucket:
                    self.family_roles.pop("kin")

    def get_family_roles_snapshot(self) -> Dict[str, List[str]]:
        snapshot: Dict[str, List[str]] = {}
        for role, members in self.family_roles.items():
            if members:
                snapshot[role] = sorted(members)
        return snapshot

    def deregister_family_role(self, relation_type: str, other_name: str) -> None:
        bucket = self.family_roles.get(relation_type)
        if bucket and other_name in bucket:
            bucket.discard(other_name)
            if not bucket:
                self.family_roles.pop(relation_type, None)

        if relation_type == "partners":
            if other_name in self.romantic_partners:
                self.romantic_partners.discard(other_name)
            self.ex_partners.add(other_name)
        elif relation_type == "children":
            self.children_names.discard(other_name)
        elif relation_type == "parents":
            self.parent_names.discard(other_name)

        if relation_type != "kin":
            kin_bucket = self.family_roles.setdefault("kin", set())
            if other_name in kin_bucket:
                return
            kin_bucket.add(other_name)

    def receive_family_event(
        self,
        world: Optional['World'],
        source_name: str,
        original_event: Dict[str, Any],
    ) -> None:
        """Record a family update echoed from another household member."""

        if not original_event:
            return

        day = original_event.get("day")
        if day is None and world and world.game_time:
            day = world.game_time.current_day

        base_summary = original_event.get("summary", "Family update.")
        summary = f"{source_name}: {base_summary}" if source_name else base_summary

        related = list(original_event.get("related", []) or [])
        if source_name and source_name not in related:
            related.append(source_name)

        tags = list(original_event.get("tags", []) or [])
        if "family_echo" not in tags:
            tags.append("family_echo")

        significance = max(1, int(original_event.get("significance", 1)))
        echo_event = {
            "day": day,
            "type": f"family_{original_event.get('type', 'update')}",
            "summary": summary,
            "related": related,
            "tags": tags,
            "significance": max(1, significance // 2),
            "source": source_name,
            "is_family_echo": True,
        }
        if "details" in original_event:
            echo_event["details"] = deepcopy(original_event["details"])

        if self._life_event_exists(echo_event):
            return

        self.life_history.append(echo_event)
        max_events = getattr(config, "LIFE_HISTORY_MAX_EVENTS", 120)
        if len(self.life_history) > max_events:
            self.life_history = self.life_history[-max_events:]

    def get_life_highlights(self, limit: int = 5) -> List[Dict[str, Any]]:
        threshold = getattr(config, "LIFE_HISTORY_HIGHLIGHT_THRESHOLD", 2)
        highlights = [evt for evt in self.life_history if evt.get("significance", 1) >= threshold]
        return [deepcopy(evt) for evt in highlights[-limit:]]

    def export_life_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit is None or limit >= len(self.life_history):
            events = self.life_history
        else:
            events = self.life_history[-limit:]
        return [deepcopy(evt) for evt in events]

    def export_profession_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = [deepcopy(entry) for entry in self.profession_history]
        current_entry: Dict[str, Any] = {
            "job": self.job or "Unassigned",
            "stage": self.career_stage,
            "tenure": self.current_profession_tenure,
            "status": "current",
        }
        if self._current_profession_start_day is not None:
            current_entry["start_day"] = self._current_profession_start_day
        if self.job_satisfaction is not None:
            current_entry["satisfaction"] = round(self.job_satisfaction, 3)
        if self.professional_focus:
            current_entry["focus"] = self.professional_focus
        history.append(current_entry)
        if limit is not None and limit > 0:
            history = history[-limit:]
        return history

    def _initialize_personal_pursuits(self) -> None:
        library: Dict[str, Dict[str, Any]] = getattr(config, "PERSONAL_PURSUITS_LIBRARY", {})
        if not library:
            self.personal_pursuits = []
            self.personal_pursuit_log.clear()
            self.active_personal_project = None
            return

        weighted: List[Tuple[str, float]] = []
        personality_weights: Dict[str, Dict[str, float]] = getattr(
            config, "PERSONAL_PURSUIT_PERSONALITY_WEIGHTS", {}
        )
        trait_weights: Dict[str, Dict[str, float]] = getattr(
            config, "PERSONAL_PURSUIT_TRAIT_WEIGHTS", {}
        )
        job_weights: Dict[str, Dict[str, float]] = getattr(
            config, "PERSONAL_PURSUIT_JOB_WEIGHTS", {}
        )

        for key, definition in library.items():
            base_weight = float(definition.get("base_weight", 1.0))
            if base_weight <= 0:
                continue
            weight = base_weight
            weight += personality_weights.get(self.personality, {}).get(key, 0.0)
            for trait in self.traits:
                weight += trait_weights.get(trait, {}).get(key, 0.0)
            if self.job:
                weight += job_weights.get(self.job, {}).get(key, 0.0)
            weight = max(0.0, weight)
            if weight > 0:
                weighted.append((key, weight))

        if not weighted:
            weighted = [
                (key, max(0.1, float(definition.get("base_weight", 1.0))))
                for key, definition in library.items()
            ]

        weighted.sort(key=lambda item: item[1], reverse=True)
        slots = max(1, int(getattr(config, "PERSONAL_PURSUIT_SLOTS", 2)))
        selected = weighted[:slots]

        pursuits: List[Dict[str, Any]] = []
        for key, weight in selected:
            definition = deepcopy(library.get(key, {}))
            entry: Dict[str, Any] = {
                "key": key,
                "name": definition.get("name", key.replace("_", " ").title()),
                "category": definition.get("category", "Personal"),
                "progress": 0.0,
                "level": 0,
                "streak": 0,
                "affinity": max(0.1, float(weight)),
                "need_focus": definition.get("need_focus"),
                "need_gain": int(
                    definition.get(
                        "need_gain",
                        getattr(config, "PERSONAL_PURSUIT_NEED_GAIN_DEFAULT", 5),
                    )
                ),
                "mood_bonus": int(
                    definition.get(
                        "mood_bonus",
                        getattr(config, "PERSONAL_PURSUIT_MOOD_BONUS_DEFAULT", 3),
                    )
                ),
                "progress_per_day": float(
                    definition.get(
                        "progress_per_day",
                        getattr(config, "PERSONAL_PURSUIT_PROGRESS_PER_DAY", 0.2),
                    )
                ),
                "skill_gain": dict(definition.get("skill_gain", {})),
                "memory_template": definition.get("memory_template"),
                "milestone_summary": definition.get("milestone_summary"),
                "tags": list(definition.get("tags", [])),
                "last_day": None,
            }
            pursuits.append(entry)

        self.personal_pursuits = pursuits
        self.personal_pursuit_log.clear()
        self.active_personal_project = None

    def _score_personal_pursuit(self, pursuit: Dict[str, Any]) -> float:
        score = float(pursuit.get("affinity", 1.0))
        energy = self.needs.get("Energy", 60)
        low_energy_threshold = getattr(config, "PERSONAL_PURSUIT_LOW_ENERGY_THRESHOLD", 40)
        if energy < low_energy_threshold:
            score -= getattr(config, "PERSONAL_PURSUIT_LOW_ENERGY_PENALTY", 0.4)

        need_focus = pursuit.get("need_focus")
        if need_focus:
            threshold = getattr(config, "PERSONAL_PURSUIT_NEED_DRIVE_THRESHOLD", 55)
            need_value = self.needs.get(need_focus, threshold)
            if need_value < threshold:
                deficit = threshold - need_value
                score += deficit * getattr(config, "PERSONAL_PURSUIT_NEED_WEIGHT", 0.01)

        if self.mood_score <= getattr(config, "PERSONAL_PURSUIT_LOW_MOOD_THRESHOLD", -20):
            score += getattr(config, "PERSONAL_PURSUIT_LOW_MOOD_BONUS", 0.3)

        streak = max(0, int(pursuit.get("streak", 0)))
        score += streak * getattr(config, "PERSONAL_PURSUIT_STREAK_BONUS", 0.1)
        return max(0.0, score)

    def evaluate_personal_pursuits_daily(self, world: 'World') -> List[Dict[str, Any]]:
        if not world or not world.game_time or not self.personal_pursuits:
            return []

        day = world.game_time.current_day
        if self._last_personal_pursuit_day == day:
            return []
        self._last_personal_pursuit_day = day

        forget_window = max(1, int(getattr(config, "PERSONAL_PURSUIT_STREAK_FORGET_DAYS", 3)))
        for pursuit in self.personal_pursuits:
            last_day = pursuit.get("last_day")
            if last_day is None:
                continue
            if day - int(last_day) > forget_window and pursuit.get("streak", 0) > 0:
                pursuit["streak"] = max(0, int(pursuit.get("streak", 0)) - 1)

        ranked = sorted(
            self.personal_pursuits,
            key=lambda entry: self._score_personal_pursuit(entry),
            reverse=True,
        )
        if not ranked:
            return []

        chosen = ranked[0]
        score = self._score_personal_pursuit(chosen)
        threshold = getattr(config, "PERSONAL_PURSUIT_ENGAGE_THRESHOLD", 0.6)
        events: List[Dict[str, Any]] = []

        if score < threshold:
            if chosen.get("streak", 0) > 0:
                chosen["streak"] = max(0, int(chosen.get("streak", 0)) - 1)
            self.active_personal_project = None
            log_entry = {
                "day": day,
                "type": "skip",
                "pursuit": chosen.get("name", chosen.get("key")),
                "score": round(score, 3),
                "reason": "low_energy"
                if self.needs.get("Energy", 0) < getattr(config, "PERSONAL_PURSUIT_LOW_ENERGY_THRESHOLD", 40)
                else "low_drive",
            }
            self.personal_pursuit_log.append(log_entry)
            events.append(
                {
                    "type": "pursuit_skipped",
                    "pursuit": chosen.get("key"),
                    "name": chosen.get("name"),
                    "score": round(score, 3),
                    "reason": log_entry["reason"],
                }
            )
            return events

        chosen.setdefault("level", 0)
        chosen.setdefault("progress", 0.0)
        chosen.setdefault("streak", 0)

        chosen["last_day"] = day
        chosen["streak"] = int(chosen.get("streak", 0)) + 1
        self.active_personal_project = chosen.get("key")

        base_progress = float(chosen.get("progress_per_day", 0.2))
        progress_gain = base_progress
        progress_gain += max(0.0, score - threshold) * getattr(
            config, "PERSONAL_PURSUIT_SCORE_PROGRESS_SCALE", 0.1
        )
        progress_gain *= 1 + (chosen["streak"] - 1) * getattr(
            config, "PERSONAL_PURSUIT_STREAK_PROGRESS_BONUS", 0.1
        )

        chosen["progress"] = float(chosen.get("progress", 0.0)) + max(0.0, progress_gain)

        mood_delta = int(chosen.get("mood_bonus", getattr(config, "PERSONAL_PURSUIT_MOOD_BONUS_DEFAULT", 3)))
        if mood_delta:
            self.update_mood_score(
                mood_delta,
                reason=f"Invested time in {chosen.get('name', 'a personal pursuit')}",
            )

        need_focus = chosen.get("need_focus")
        need_delta = 0
        if need_focus:
            gain_amount = int(
                chosen.get(
                    "need_gain",
                    getattr(config, "PERSONAL_PURSUIT_NEED_GAIN_DEFAULT", 5),
                )
            )
            if gain_amount:
                current_value = self.needs.get(need_focus, getattr(config, f"NEED_{need_focus.upper()}_DEFAULT", 50))
                self.needs[need_focus] = min(config.NEED_SCORE_MAX, current_value + gain_amount)
                need_delta = gain_amount

        skill_gain: Dict[str, Any] = chosen.get("skill_gain", {})
        for skill_name, experience in skill_gain.items():
            try:
                self._grant_skill_experience(skill_name, float(experience), world)
            except Exception:
                continue

        memory_note = chosen.get("memory_template")
        if memory_note:
            self.add_memory(memory_note)
        else:
            self.add_memory(f"Spent time pursuing {chosen.get('name', 'a passion')}.")

        progress_threshold = max(0.5, float(getattr(config, "PERSONAL_PURSUIT_LIFE_EVENT_PROGRESS", 1.0)))
        levels_gained = 0
        while chosen["progress"] >= progress_threshold:
            chosen["progress"] -= progress_threshold
            chosen["level"] = int(chosen.get("level", 0)) + 1
            levels_gained += 1

        log_entry = {
            "day": day,
            "type": "pursuit",
            "pursuit": chosen.get("name", chosen.get("key")),
            "stage": int(chosen.get("level", 0)),
            "progress": round(chosen.get("progress", 0.0), 3),
            "streak": chosen.get("streak", 0),
            "score": round(score, 3),
        }

        if levels_gained > 0:
            log_entry["milestone"] = int(chosen.get("level", 0))
        self.personal_pursuit_log.append(log_entry)

        events.append(
            {
                "type": "pursuit_engaged",
                "pursuit": chosen.get("key"),
                "name": chosen.get("name"),
                "category": chosen.get("category"),
                "stage": int(chosen.get("level", 0)),
                "progress": round(chosen.get("progress", 0.0), 3),
                "score": round(score, 3),
                "streak": chosen.get("streak", 0),
                "mood_delta": mood_delta,
                "need_focus": need_focus,
                "need_delta": need_delta,
            }
        )

        if levels_gained > 0:
            summary = chosen.get("milestone_summary") or f"Reached a new milestone in {chosen.get('name', 'a pursuit')}"
            life_event = self.record_life_event(
                world,
                "pursuit_milestone",
                summary,
                related=[chosen.get("name")],
                tags=["pursuit", chosen.get("category", "personal")],
                significance=2,
                details={
                    "pursuit": chosen.get("key"),
                    "category": chosen.get("category"),
                    "level": int(chosen.get("level", 0)),
                    "streak": chosen.get("streak", 0),
                },
            )
            milestone_event = {
                "type": "pursuit_milestone",
                "pursuit": chosen.get("key"),
                "name": chosen.get("name"),
                "category": chosen.get("category"),
                "stage": int(chosen.get("level", 0)),
                "streak": chosen.get("streak", 0),
            }
            if life_event:
                milestone_event["life_event"] = life_event
            self.personal_pursuit_log.append(
                {
                    "day": day,
                    "type": "milestone",
                    "pursuit": chosen.get("name", chosen.get("key")),
                    "stage": int(chosen.get("level", 0)),
                }
            )
            events.append(milestone_event)

        return events

    def export_personal_pursuits(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        pursuits = list(self.personal_pursuits)
        if limit is not None and limit > 0:
            pursuits = pursuits[:limit]
        exported: List[Dict[str, Any]] = []
        for entry in pursuits:
            exported.append(
                {
                    "key": entry.get("key"),
                    "name": entry.get("name"),
                    "category": entry.get("category"),
                    "progress": round(float(entry.get("progress", 0.0)), 3),
                    "level": int(entry.get("level", 0)),
                    "streak": int(entry.get("streak", 0)),
                    "affinity": round(float(entry.get("affinity", 0.0)), 3),
                    "need_focus": entry.get("need_focus"),
                    "tags": list(entry.get("tags", [])),
                    "last_day": entry.get("last_day"),
                    "progress_per_day": round(float(entry.get("progress_per_day", 0.0)), 3),
                }
            )
        return exported

    def export_personal_pursuit_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        entries = list(self.personal_pursuit_log)
        if limit is not None and limit > 0:
            entries = entries[-limit:]
        return [deepcopy(entry) for entry in entries]

    def get_romantic_partners(self) -> List[str]:
        return sorted(self.romantic_partners)

    def get_children(self) -> List[str]:
        return sorted(self.children_names)

    def get_parents(self) -> List[str]:
        return sorted(self.parent_names)

    def get_active_romances_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {name: deepcopy(data) for name, data in self.active_romances.items()}

    def is_single(self) -> bool:
        return not self.romantic_partners and not self.active_romances

    def note_romance_started(
        self,
        world: Optional['World'],
        partner_name: str,
        compatibility: float,
        impetus: str,
    ) -> None:
        record: Dict[str, Any] = {
            "status": "courting",
            "compatibility": round(max(0.0, min(1.0, compatibility)), 3),
            "impetus": impetus,
        }
        day = None
        if world and world.game_time:
            day = world.game_time.current_day
        if day is not None:
            record["since_day"] = day
        self.active_romances[partner_name] = record
        self._romance_cooldowns.pop(partner_name, None)
        if day is not None:
            self._romance_attempt_window.append((day, partner_name))
        if hasattr(self, "record_life_event"):
            summary = f"Began courting {partner_name}."
            self.record_life_event(
                world,
                "romance_started",
                summary,
                related=[partner_name],
                tags=["family", "relationship"],
                significance=2,
                propagate_to_family=True,
                details={"partner": partner_name, "compatibility": record["compatibility"], "impetus": impetus},
                dedupe_key=f"romance_started:{self.name}:{partner_name}:{day}",
            )

    def note_romance_ended(
        self,
        world: Optional['World'],
        partner_name: str,
        reason: str,
        *,
        committed: bool = False,
        divorce: bool = False,
    ) -> None:
        if partner_name in self.active_romances:
            self.active_romances.pop(partner_name, None)
        if committed:
            self.handle_union_dissolved(partner_name, world, reason, divorce=divorce)
            return

        cooldown_days = random.randint(4, 8)
        self._romance_cooldowns[partner_name] = cooldown_days
        self.ex_partners.add(partner_name)
        if hasattr(self, "record_life_event"):
            summary = f"Romance with {partner_name} ended ({reason})."
            self.record_life_event(
                world,
                "romance_ended",
                summary,
                related=[partner_name],
                tags=["family", "relationship", "breakup"],
                significance=2,
                propagate_to_family=True,
                details={"partner": partner_name, "reason": reason},
                dedupe_key=f"romance_ended:{self.name}:{partner_name}:{reason}",
            )

    def handle_union_formed(
        self,
        world: Optional['World'],
        partner_name: str,
        *,
        ceremony: Optional[str] = None,
    ) -> None:
        day = None
        if world and world.game_time:
            day = world.game_time.current_day
        self.romantic_partners.add(partner_name)
        self.ex_partners.discard(partner_name)
        if partner_name in self.active_romances:
            self.active_romances.pop(partner_name, None)
        self._romance_cooldowns.pop(partner_name, None)
        self._last_commitment_check = day
        active_entry: Optional[Dict[str, Any]] = None
        for entry in reversed(self.marriage_history):
            if entry.get("partner") == partner_name and entry.get("status") == "active":
                active_entry = entry
                break
        if active_entry:
            if day is not None and "day" not in active_entry:
                active_entry["day"] = day
            if ceremony:
                active_entry["ceremony"] = ceremony
        else:
            entry: Dict[str, Any] = {
                "partner": partner_name,
                "status": "active",
            }
            if day is not None:
                entry["day"] = day
            if ceremony:
                entry["ceremony"] = ceremony
            self.marriage_history.append(entry)
        max_entries = getattr(config, "MARRIAGE_HISTORY_MAX", 24)
        if len(self.marriage_history) > max_entries:
            self.marriage_history = self.marriage_history[-max_entries:]

    def handle_union_dissolved(
        self,
        partner_name: str,
        world: Optional['World'],
        reason: str,
        *,
        divorce: bool = False,
    ) -> None:
        if partner_name in self.romantic_partners:
            self.romantic_partners.discard(partner_name)
        self.ex_partners.add(partner_name)
        cooldown_days = random.randint(9, 16)
        self._romance_cooldowns[partner_name] = cooldown_days
        day = None
        if world and world.game_time:
            day = world.game_time.current_day
        for entry in reversed(self.marriage_history):
            if entry.get("partner") == partner_name and entry.get("status") == "active":
                entry["status"] = "ended"
                if day is not None:
                    entry["ended_day"] = day
                entry["reason"] = reason
                entry["divorce"] = divorce
                break
        if hasattr(self, "record_life_event"):
            event_type = "divorce" if divorce else "union_ended"
            summary = f"Divorced {partner_name} ({reason})." if divorce else f"Separated from {partner_name} ({reason})."
            self.record_life_event(
                world,
                event_type,
                summary,
                related=[partner_name],
                tags=["family", "relationship", "breakup"],
                significance=4 if divorce else 3,
                propagate_to_family=True,
                details={"partner": partner_name, "reason": reason, "divorce": divorce},
                dedupe_key=f"union_end:{self.name}:{partner_name}:{event_type}",
            )

    def note_child_added(self, world: Optional['World'], child_name: str) -> None:
        self.children_names.add(child_name)
        if world and world.game_time:
            self._last_child_day = world.game_time.current_day

    def _romance_interest_chance(self) -> float:
        base = getattr(config, "ROMANCE_DAILY_BASE_CHANCE", 0.08)
        modifier = 0.0
        modifier += getattr(config, "ROMANCE_PERSONALITY_INCLINATIONS", {}).get(self.personality, 0.0)
        for trait in self.traits:
            modifier += getattr(config, "ROMANCE_TRAIT_INFLUENCES", {}).get(trait, 0.0)
        belonging = self.needs.get("Belonging", 0)
        if belonging < 35:
            modifier += 0.12
        elif belonging > 80:
            modifier -= 0.05
        mood_score = getattr(self, "mood_score", 0)
        if mood_score < -20:
            modifier -= 0.05
        elif mood_score > 35:
            modifier += 0.03
        satisfaction = getattr(self, "job_satisfaction", 0.6)
        if satisfaction >= 0.8:
            modifier += 0.03
        elif satisfaction < 0.35:
            modifier -= 0.05
        if self.active_romances:
            modifier -= 0.08 * len(self.active_romances)
        return max(0.0, min(0.85, base + modifier))

    def _romantic_compatibility(self, other: Optional['Character']) -> float:
        if not other:
            return 0.0
        relationship_score = self.get_relationship_score(other.name)
        other_relationship = other.get_relationship_score(self.name)
        normalized = (relationship_score + other_relationship) / (2 * max(1, config.RELATIONSHIP_SCORE_MAX))
        normalized = max(-1.0, min(1.0, normalized))
        compatibility = 0.3 + (normalized * 0.4)
        if self.personality == other.personality:
            compatibility += 0.1
        personality_pair = {self.personality, other.personality}
        if personality_pair == {"Romantic", "Dreamer"}:
            compatibility += 0.08
        elif personality_pair == {"Stoic", "Cheerful"}:
            compatibility += 0.04
        elif personality_pair == {"Stoic", "Stoic"}:
            compatibility -= 0.05
        shared_traits = set(self.traits) & set(other.traits)
        compatibility += 0.05 * len(shared_traits & {"Affectionate", "Loyal", "Generous", "Patient"})
        compatibility += 0.02 * len(shared_traits)
        if "Jealous" in self.traits and "Charming" in other.traits:
            compatibility -= 0.05
        if "Cold" in self.traits or "Cold" in other.traits:
            compatibility -= 0.08
        wealth_gap = abs(getattr(self, "net_worth", 0) - getattr(other, "net_worth", 0))
        if wealth_gap > 400:
            compatibility -= 0.05
        elif wealth_gap < 75:
            compatibility += 0.03
        compatibility = max(0.0, min(1.0, compatibility))
        return compatibility

    def _child_desire_score(self, partner: 'Character') -> float:
        base = getattr(config, "FAMILY_CHILD_DESIRE_BASE", 0.12)
        personality_bonus = getattr(config, "FAMILY_CHILD_PERSONALITY_BONUS", {})
        trait_bonus = getattr(config, "FAMILY_CHILD_TRAIT_BONUS", {})
        base += personality_bonus.get(self.personality, 0.0)
        base += personality_bonus.get(getattr(partner, "personality", ""), 0.0)
        for trait in self.traits:
            base += trait_bonus.get(trait, 0.0)
        for trait in getattr(partner, "traits", []):
            base += trait_bonus.get(trait, 0.0)
        belonging = min(self.needs.get("Belonging", 0), partner.needs.get("Belonging", 0))
        threshold = getattr(config, "FAMILY_CHILD_MIN_BELONGING", 55)
        if belonging < threshold:
            base -= 0.3
        wealth_total = getattr(self, "net_worth", 0) + getattr(partner, "net_worth", 0)
        if wealth_total > 500:
            base += 0.05
        elif wealth_total < 60:
            base -= 0.05
        if getattr(self, "retired", False) or getattr(partner, "retired", False):
            base -= 0.05
        return max(0.0, min(0.9, base))

    def _can_plan_child_with(self, partner: 'Character', world: 'World', day: int) -> bool:
        min_age = getattr(config, "FAMILY_CHILD_MIN_AGE", 18)
        max_age = getattr(config, "FAMILY_CHILD_MAX_AGE", 45)
        my_age = getattr(self, "age_years", min_age)
        partner_age = getattr(partner, "age_years", min_age)
        if not (min_age <= my_age <= max_age):
            return False
        if not (min_age <= partner_age <= max_age):
            return False
        cooldown = getattr(config, "FAMILY_CHILD_COOLDOWN_DAYS", 18)
        if self._last_child_day is not None and day - self._last_child_day < cooldown:
            return False
        if getattr(partner, "_last_child_day", None) is not None and day - partner._last_child_day < cooldown:
            return False
        if getattr(self, "is_sick", False) or getattr(self, "is_injured", False):
            return False
        if getattr(partner, "is_sick", False) or getattr(partner, "is_injured", False):
            return False
        housing_requirement = getattr(config, "FAMILY_CHILD_HOUSING_REQUIREMENT", 0)
        if housing_requirement:
            has_home = bool(self.home_location or partner.home_location)
            if not has_home:
                return False
        if self.get_relationship_score(partner.name) < getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT", 55) // 2:
            return False
        if partner.get_relationship_score(self.name) < getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT", 55) // 2:
            return False
        return True

    def _should_plan_child(self, world: 'World', partner: 'Character', day: int) -> bool:
        if not self._can_plan_child_with(partner, world, day):
            return False
        desire = self._child_desire_score(partner)
        return random.random() < desire

    def _select_romance_candidate(self, world: 'World') -> Optional['Character']:
        candidates: List['Character'] = []
        threshold = getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_DATE", 25)
        for other in world.characters:
            if other is self:
                continue
            if other.name in self.romantic_partners or self.name in other.romantic_partners:
                continue
            if other.name in self.active_romances or self.name in other.active_romances:
                continue
            if other._romance_cooldowns.get(self.name):
                continue
            if self._romance_cooldowns.get(other.name):
                continue
            if other.romantic_partners:
                continue
            rel = self.get_relationship_score(other.name)
            other_rel = other.get_relationship_score(self.name)
            if rel < threshold or other_rel < threshold:
                continue
            candidates.append(other)
        if not candidates:
            return None
        sample = random.sample(candidates, min(len(candidates), 5))
        scored = sorted(sample, key=lambda candidate: self._romantic_compatibility(candidate), reverse=True)
        for candidate in scored:
            compatibility = self._romantic_compatibility(candidate)
            if compatibility >= 0.2:
                return candidate
        return None

    def evaluate_family_daily(self, world: 'World') -> List[Dict[str, Any]]:
        if not world or not world.game_time:
            return []
        day = world.game_time.current_day
        if self._last_family_daily_day == day:
            return []
        self._last_family_daily_day = day

        for name in list(self._romance_cooldowns.keys()):
            self._romance_cooldowns[name] -= 1
            if self._romance_cooldowns[name] <= 0:
                self._romance_cooldowns.pop(name, None)

        actions: List[Dict[str, Any]] = []

        for partner_name, romance in list(self.active_romances.items()):
            if partner_name < self.name:
                continue
            other = world.get_character_by_name(partner_name)
            if not other:
                actions.append({
                    "type": "end_romance",
                    "with": partner_name,
                    "reason": "lost contact",
                })
                continue
            if self.name not in other.active_romances:
                actions.append({
                    "type": "end_romance",
                    "with": partner_name,
                    "reason": "fell out of touch",
                })
                continue
            rel = self.get_relationship_score(partner_name)
            other_rel = other.get_relationship_score(self.name)
            if rel < getattr(config, "ROMANCE_BREAKUP_REL_THRESHOLD", -20) or other_rel < getattr(config, "ROMANCE_BREAKUP_REL_THRESHOLD", -20):
                actions.append({
                    "type": "end_romance",
                    "with": partner_name,
                    "reason": "growing distant",
                })
                continue
            compatibility = romance.get("compatibility")
            if compatibility is None:
                compatibility = self._romantic_compatibility(other)
            since_day = romance.get("since_day")
            days_together = day - since_day if since_day is not None else 0
            commit_threshold = getattr(config, "ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT", 55)
            if (
                rel >= commit_threshold
                and other_rel >= commit_threshold
                and days_together >= getattr(config, "ROMANCE_MIN_DAYS_BEFORE_UNION", 6)
            ):
                commit_chance = 0.15 + compatibility
                commit_chance += getattr(config, "ROMANCE_COMMITMENT_PERSONALITY_MODIFIERS", {}).get(self.personality, 0.0)
                commit_chance += getattr(config, "ROMANCE_COMMITMENT_PERSONALITY_MODIFIERS", {}).get(other.personality, 0.0)
                commit_chance = max(0.05, min(0.85, commit_chance))
                if random.random() < commit_chance:
                    actions.append({
                        "type": "propose_union",
                        "with": partner_name,
                        "compatibility": compatibility,
                    })
                    continue
            if compatibility < 0.22 and random.random() < 0.05:
                actions.append({
                    "type": "end_romance",
                    "with": partner_name,
                    "reason": "low spark",
                })

        for partner_name in sorted(self.romantic_partners):
            if partner_name < self.name:
                continue
            other = world.get_character_by_name(partner_name)
            if not other:
                actions.append({
                    "type": "dissolve_union",
                    "with": partner_name,
                    "reason": "bereavement",
                    "divorce": False,
                })
                continue
            rel = self.get_relationship_score(partner_name)
            other_rel = other.get_relationship_score(self.name)
            if (
                rel <= getattr(config, "ROMANCE_DIVORCE_REL_THRESHOLD", -45)
                or other_rel <= getattr(config, "ROMANCE_DIVORCE_REL_THRESHOLD", -45)
            ):
                chance = getattr(config, "ROMANCE_DIVORCE_BASE_CHANCE", 0.06)
                for trait in self.traits:
                    chance += getattr(config, "ROMANCE_DIVORCE_TRAIT_BONUS", {}).get(trait, 0.0)
                for trait in other.traits:
                    chance += getattr(config, "ROMANCE_DIVORCE_TRAIT_BONUS", {}).get(trait, 0.0)
                chance = max(0.02, min(0.9, chance))
                if random.random() < chance:
                    actions.append({
                        "type": "dissolve_union",
                        "with": partner_name,
                        "reason": "irreconcilable differences",
                        "divorce": True,
                    })
                    continue
            if rel < getattr(config, "ROMANCE_BREAKUP_REL_THRESHOLD", -20) and random.random() < getattr(config, "ROMANCE_BREAKUP_BASE_CHANCE", 0.04):
                actions.append({
                    "type": "dissolve_union",
                    "with": partner_name,
                    "reason": "grew apart",
                    "divorce": False,
                })
                continue
            if self.name < partner_name and self._should_plan_child(world, other, day):
                actions.append({
                    "type": "plan_child",
                    "with": partner_name,
                })

        if self.is_single():
            interest = self._romance_interest_chance()
            if random.random() < interest:
                candidate = self._select_romance_candidate(world)
                if candidate and self.name < candidate.name:
                    compatibility = self._romantic_compatibility(candidate)
                    actions.append({
                        "type": "start_romance",
                        "with": candidate.name,
                        "compatibility": compatibility,
                        "impetus": self.personality or "Chance",
                    })

        return actions

    def receive_cultural_event_boost(self, event_data: Dict[str, Any], world: 'World') -> None:
        """Apply morale and need adjustments when the settlement hosts a cultural event."""
        event_name = event_data.get("name", "community gathering")
        description = event_data.get("description")
        event_key = event_data.get("key", event_name.lower())

        belonging_bonus = int(event_data.get("belonging_bonus", 0))
        esteem_bonus = int(event_data.get("esteem_bonus", 0))
        social_bonus = int(event_data.get("social_bonus", 0))
        mood_bonus = int(event_data.get("mood_bonus", 0))

        if belonging_bonus:
            current_belonging = self.needs.get("Belonging", config.NEED_BELONGING_DEFAULT)
            self.needs["Belonging"] = min(
                config.NEED_SCORE_MAX,
                max(config.NEED_SCORE_MIN, current_belonging + belonging_bonus),
            )

        if esteem_bonus:
            current_esteem = self.needs.get("Esteem", config.NEED_ESTEEM_DEFAULT)
            self.needs["Esteem"] = min(
                config.NEED_SCORE_MAX,
                max(config.NEED_SCORE_MIN, current_esteem + esteem_bonus),
            )

        if social_bonus:
            current_social = self.needs.get("Social", config.NEED_SCORE_MAX // 2)
            self.needs["Social"] = min(
                config.NEED_SCORE_MAX,
                max(config.NEED_SCORE_MIN, current_social + social_bonus),
            )

        if mood_bonus:
            self.update_mood_score(mood_bonus, f"Enjoyed {event_name}")

        flavor_lines = event_data.get("flavor") or []
        flavor_snippet = random.choice(flavor_lines) if flavor_lines else ""
        fragments = [frag for frag in [description, flavor_snippet] if frag]
        memory_summary = f"Enjoyed {event_name}."
        if fragments:
            memory_summary += " " + " ".join(fragments)
        self.add_memory(memory_summary.strip())

        if hasattr(self, "known_events"):
            self.known_events.append(event_key)
            self.known_events = self.known_events[-20:]

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

    def receive_income(self, amount: int, source: str, mood_reason: Optional[str] = None) -> None:
        """Receive personal income that does not route through the public treasury."""
        if amount <= 0:
            return

        self.money += amount
        coins_text = "coin" if amount == 1 else "coins"
        self.add_memory(f"Earned {amount} {coins_text} from {source}.")
        mood_bonus = getattr(config, "BUSINESS_INCOME_MOOD_BONUS", 0)
        if mood_bonus:
            self.update_mood_score(mood_bonus, mood_reason or f"Income from {source}")

    def assign_business_role(self, business_id: str, role: str) -> None:
        """Track business ownership or employment for this character."""
        self.business_roles[business_id] = role
        if role == "owner":
            if business_id not in self.businesses_owned:
                self.businesses_owned.append(business_id)
        else:
            if business_id in self.businesses_owned:
                self.businesses_owned.remove(business_id)

    def leave_business_role(self, business_id: str, reason: Optional[str] = None) -> None:
        role = self.business_roles.pop(business_id, None)
        if role == "owner" and business_id in self.businesses_owned:
            self.businesses_owned.remove(business_id)
        if reason:
            self.add_memory(reason)

    def is_entrepreneurial(self) -> bool:
        personalities = set(getattr(config, "ENTREPRENEURIAL_PERSONALITIES", []))
        traits = set(getattr(config, "ENTREPRENEURIAL_TRAITS", []))
        return (self.personality in personalities) or bool(traits.intersection(self.traits))

    def _get_profession_track(self) -> Dict[str, Any]:
        tracks = getattr(config, "PROFESSION_TRACK_DEFINITIONS", {})
        if not isinstance(tracks, dict):
            return {}
        job_name = self.job or "Unassigned"
        track: Optional[Dict[str, Any]] = tracks.get(job_name)
        if track is None:
            lowered = job_name.lower()
            for key, candidate in tracks.items():
                if isinstance(candidate, dict) and key.lower() == lowered:
                    track = candidate
                    break
        if track is None:
            track = tracks.get("default", {})
        return deepcopy(track) if isinstance(track, dict) else {}

    def _reset_profession_for_new_job(
        self,
        world: Optional['World'],
        today: int,
    ) -> Optional[Dict[str, Any]]:
        previous_job = self._last_recorded_job
        tenure_before_reset = self.current_profession_tenure
        updates: Dict[str, Any] = {}

        if previous_job and previous_job not in {"Unemployed", "Retiree"} and tenure_before_reset > 0:
            history_entry: Dict[str, Any] = {
                "job": previous_job,
                "stage": self.career_stage,
                "tenure": tenure_before_reset,
                "end_day": today,
                "status": "archived",
            }
            if self._current_profession_start_day is not None:
                history_entry["start_day"] = self._current_profession_start_day
            self.profession_history.append(history_entry)
            max_history = getattr(config, "CAREER_MAX_HISTORY", 16)
            if len(self.profession_history) > max_history:
                self.profession_history = self.profession_history[-max_history:]
            summary = (
                f"Departed role as {previous_job} after {tenure_before_reset} "
                f"day{'s' if tenure_before_reset != 1 else ''}."
            )
            self.add_memory(summary)
            self.record_life_event(
                world,
                "career_transition",
                summary,
                tags=["career"],
                significance=2,
                details={"job": previous_job, "tenure": tenure_before_reset},
            )
            updates["job_change"] = {
                "from": previous_job,
                "to": self.job or "Unassigned",
                "tenure": tenure_before_reset,
            }

        new_job = self.job or "Unassigned"
        if new_job and new_job not in {"Unassigned", "Unemployed", "Retiree"}:
            join_summary = f"Began work as a {new_job}."
            self.add_memory(join_summary)
            self.record_life_event(
                world,
                "career_assignment",
                join_summary,
                tags=["career"],
                significance=2,
                details={"job": new_job},
            )
            if "job_change" not in updates:
                updates["job_change"] = {
                    "from": previous_job or "Unassigned",
                    "to": new_job,
                    "tenure": tenure_before_reset,
                }

        self.current_profession_tenure = 0
        self._current_profession_start_day = today
        self._last_recorded_job = self.job
        self._last_career_stage_day = today
        baseline = getattr(config, "CAREER_SATISFACTION_BASELINE", 0.6)
        personality_mods = getattr(config, "CAREER_PERSONALITY_MODIFIERS", {}).get(self.personality, {})
        trait_mods = getattr(config, "CAREER_TRAIT_MODIFIERS", {})
        stability_bonus = personality_mods.get("stability_bonus", 0.0) + personality_mods.get(
            "satisfaction_bonus", 0.0
        )
        trait_bonus = sum(trait_mods.get(trait, {}).get("satisfaction_bonus", 0.0) for trait in self.traits)
        self.job_satisfaction = max(0.0, min(1.0, baseline + stability_bonus + trait_bonus))
        self._triggered_tenure_milestones.clear()
        return updates or None

    def calculate_net_worth(self, world: Optional['World'] = None) -> int:
        """Estimate the character's total wealth, including business equity."""
        wealth_total = int(self.money)
        multiplier = getattr(config, "BUSINESS_NETWORTH_MULTIPLIER", 1.0)
        if world and hasattr(world, "businesses"):
            for business_id in self.businesses_owned:
                business = world.businesses.get(business_id) if business_id in world.businesses else None
                if not business or business.get("status") not in {"active", "paused"}:
                    continue
                capital_value = int(business.get("capital", 0))
                cash_reserve = int(business.get("cash_reserve", 0))
                wealth_total += int(capital_value * multiplier) + cash_reserve

        self.net_worth = max(0, wealth_total)

        thresholds = getattr(config, "WEALTH_STATUS_THRESHOLDS", {})
        previous_status = self.wealth_status
        if thresholds:
            sorted_thresholds = sorted(thresholds.items(), key=lambda item: item[1])
            chosen_status = previous_status
            for status_label, threshold in sorted_thresholds:
                if self.net_worth >= threshold:
                    chosen_status = status_label
            self.wealth_status = chosen_status
        else:
            self.wealth_status = "modest"

        return self.net_worth

    def evaluate_daily_wealth(self, world: 'World') -> Dict[str, Any]:
        """Daily wealth upkeep — consider promotions, business ventures, and retirement."""
        if not world or not world.game_time:
            return {}

        today = world.game_time.current_day
        if self._last_wealth_evaluation_day == today:
            return {}
        self._last_wealth_evaluation_day = today

        updates: Dict[str, Any] = {}

        previous_status = self.wealth_status
        previous_rank = self.rank
        previous_net = self.net_worth

        net = self.calculate_net_worth(world)
        self.wealth_history.append((today, net))

        if previous_status != self.wealth_status:
            summary = f"Wealth status shifted to {self.wealth_status} (net worth {net} coins)."
            self.add_memory(summary)
            self.record_life_event(
                world,
                "wealth_status_change",
                summary,
                tags=["wealth"],
                significance=2,
                details={"net_worth": net, "previous_status": previous_status},
            )
            updates["status_change"] = {"status": self.wealth_status, "net_worth": net}

        noble_threshold = getattr(config, "NOBILITY_WEALTH_THRESHOLD", 0)
        noble_title = getattr(config, "NOBILITY_TITLE", "Noble Lord")
        noble_ranks = set(getattr(config, "NOBLE_RANKS_OR_JOBS", []) or NOBLE_RANKS_OR_JOBS)
        if (
            noble_threshold
            and net >= noble_threshold
            and self.rank not in noble_ranks
            and self.rank != noble_title
            and f"nobility_{noble_title}" not in self._life_event_flags
        ):
            previous_rank = self.rank
            self.rank = noble_title
            self._life_event_flags.add(f"nobility_{noble_title}")
            self.add_memory(f"Elevated to the rank of {noble_title} thanks to amassed fortunes.")
            self.record_life_event(
                world,
                "nobility_elevation",
                f"Elevated to {noble_title} through wealth and influence.",
                tags=["nobility", "wealth"],
                significance=4,
                details={"net_worth": net, "previous_rank": previous_rank},
                propagate_to_family=True,
            )
            world.add_event_log_message(f"{self.name} is recognized as a {noble_title} after amassing considerable wealth.")
            updates["nobility"] = {"title": noble_title, "net_worth": net}

        if not self.retired and self.job not in {"Mayor", "Reeve"}:
            retirement_personalities = set(getattr(config, "RETIREMENT_PERSONALITIES", []))
            wealth_threshold = getattr(config, "RETIREMENT_WEALTH_THRESHOLD", 0)
            min_age = getattr(config, "RETIREMENT_MIN_AGE", 60)
            chance = getattr(config, "RETIREMENT_DAILY_CHANCE", 0.0)
            if (
                self.age_years >= min_age
                and net >= wealth_threshold
                and self.personality in retirement_personalities
                and random.random() < chance
            ):
                old_job = self.job
                self.job = "Retiree"
                self.retired = True
                self.add_memory(f"Retired from life as a {old_job} after securing {net} coins in wealth.")
                self.record_life_event(
                    world,
                    "retirement",
                    f"Retired from {old_job} with a nest egg of {net} coins.",
                    tags=["retirement", "wealth"],
                    significance=3,
                    details={"net_worth": net, "former_job": old_job},
                )
                world.add_event_log_message(f"{self.name} retires from the workforce with savings of {net} coins.")
                updates["retired"] = {"former_job": old_job, "net_worth": net}

        max_owned = getattr(config, "BUSINESS_MAX_OWNERSHIP", 1)
        startup_funds = getattr(config, "BUSINESS_START_MIN_FUNDS", 9999)
        if (
            not self.retired
            and len(self.businesses_owned) < max_owned
            and self.money >= startup_funds
            and net >= startup_funds
        ):
            if self._last_business_check_day != today:
                self._last_business_check_day = today
                if self.is_entrepreneurial() and hasattr(world, "launch_business"):
                    business = world.launch_business(self)
                    if business:
                        updates["business_started"] = {
                            "id": business.get("id"),
                            "name": business.get("name"),
                            "industry": business.get("industry"),
                        }

        updates["net_worth"] = net
        updates["previous_net_worth"] = previous_net
        return updates

    def evaluate_profession_daily(self, world: 'World') -> Dict[str, Any]:
        if not world or not world.game_time:
            return {}

        today = world.game_time.current_day
        if self._last_profession_review_day == today:
            return {}
        self._last_profession_review_day = today

        updates: Dict[str, Any] = {}
        job_name = self.job or "Unassigned"

        track = self._get_profession_track()
        if self._last_recorded_job != self.job:
            reset_updates = self._reset_profession_for_new_job(world, today)
            if reset_updates and "job_change" in reset_updates:
                updates["job_change"] = reset_updates["job_change"]

        if self._current_profession_start_day is None:
            self._current_profession_start_day = today - self.current_profession_tenure

        if job_name == "Retiree":
            self.professional_focus = None
            rest_gain = getattr(config, "CAREER_SATISFACTION_GAIN", 0.08) * 0.5
            self.job_satisfaction = max(0.0, min(1.0, self.job_satisfaction + rest_gain))
            return updates

        if job_name in {"Unassigned", "Unemployed"}:
            self.professional_focus = None
            idle_decay = getattr(config, "CAREER_IDLE_DECAY", 0.04)
            if idle_decay:
                self.job_satisfaction = max(0.0, self.job_satisfaction - idle_decay)
            if (
                self.job_satisfaction <= getattr(config, "CAREER_BURNOUT_THRESHOLD", 0.35)
                and self._last_burnout_alert_day != today
            ):
                self._last_burnout_alert_day = today
                self.update_mood_score(
                    getattr(config, "CAREER_SATISFACTION_MOOD_PENALTY", -8),
                    "Unsettled without a calling",
                )
                updates["burnout"] = {"satisfaction": round(self.job_satisfaction, 3), "reason": "unassigned"}
            return updates

        self.current_profession_tenure += 1

        primary_skill = track.get("skill") if isinstance(track, dict) else None
        self.professional_focus = primary_skill
        base_xp = float(track.get("daily_xp", 1.0)) if isinstance(track, dict) else 1.0

        personality_mods = getattr(config, "CAREER_PERSONALITY_MODIFIERS", {}).get(self.personality, {})
        trait_mods = getattr(config, "CAREER_TRAIT_MODIFIERS", {})
        xp_multiplier = 1.0 + personality_mods.get("learning_bonus", 0.0)
        for trait in self.traits:
            xp_multiplier += trait_mods.get(trait, {}).get("xp_bonus", 0.0)
        xp_total = max(0.0, base_xp * xp_multiplier)

        if xp_total and primary_skill:
            before_level = self.skills.get(primary_skill, {}).get("level", 0)
            self._grant_skill_experience(primary_skill, xp_total, world)
            after_level = self.skills.get(primary_skill, {}).get("level", before_level)
            if after_level > before_level:
                updates.setdefault("level_ups", []).append(
                    {"skill": primary_skill, "level": after_level}
                )

        decay = getattr(config, "CAREER_SATISFACTION_DECAY", 0.05)
        gain = getattr(config, "CAREER_SATISFACTION_GAIN", 0.08)
        satisfaction = self.job_satisfaction
        if decay:
            satisfaction -= decay
        satisfaction += gain * max(0.5, xp_multiplier)

        wealth_expectation = track.get("wealth_expectation") if isinstance(track, dict) else None
        thresholds = getattr(config, "WEALTH_STATUS_THRESHOLDS", {})
        if wealth_expectation and isinstance(thresholds, dict):
            expected_threshold = thresholds.get(wealth_expectation)
            if expected_threshold is not None:
                if getattr(self, "net_worth", self.money) >= expected_threshold:
                    satisfaction += getattr(config, "CAREER_WEALTH_SATISFACTION_BONUS", 0.08)
                    if personality_mods.get("wealth_bonus"):
                        satisfaction += personality_mods["wealth_bonus"]
                else:
                    satisfaction -= getattr(config, "CAREER_WEALTH_SATISFACTION_PENALTY", 0.1)

        focus = track.get("focus") if isinstance(track, dict) else None
        for trait in self.traits:
            trait_mod = trait_mods.get(trait, {})
            if focus == "service" and trait_mod.get("service_bonus"):
                satisfaction += trait_mod["service_bonus"]

        satisfaction_floors = [
            trait_mods.get(trait, {}).get("satisfaction_floor")
            for trait in self.traits
            if trait_mods.get(trait, {}).get("satisfaction_floor") is not None
        ]
        progress_pressure = personality_mods.get("promotion_pressure", 0.0)
        for trait in self.traits:
            progress_pressure += trait_mods.get(trait, {}).get("promotion_pressure", 0.0)

        patience = getattr(config, "CAREER_PROGRESS_PATIENCE_DAYS", 10)
        last_progress = self._last_career_stage_day or self._current_profession_start_day or today
        days_since_progress = max(0, today - last_progress)
        if progress_pressure > 0 and days_since_progress > patience:
            burnout_resistance = sum(
                trait_mods.get(trait, {}).get("burnout_resistance", 0.0) for trait in self.traits
            )
            penalty = progress_pressure * ((days_since_progress - patience + 1) / max(1, patience)) * 0.1
            penalty *= max(0.0, 1.0 - burnout_resistance)
            satisfaction -= penalty

        if satisfaction_floors:
            satisfaction = max(satisfaction, max(satisfaction_floors))

        satisfaction = max(0.0, min(1.0, satisfaction))
        previous_satisfaction = self.job_satisfaction
        self.job_satisfaction = satisfaction

        burnout_threshold = getattr(config, "CAREER_BURNOUT_THRESHOLD", 0.35)
        ambition_threshold = getattr(config, "CAREER_AMBITION_THRESHOLD", 0.85)

        if satisfaction <= burnout_threshold:
            if self._last_burnout_alert_day != today:
                self._last_burnout_alert_day = today
                self.update_mood_score(
                    getattr(config, "CAREER_SATISFACTION_MOOD_PENALTY", -8),
                    f"Dissatisfied with {job_name} duties",
                )
                updates["burnout"] = {"satisfaction": round(satisfaction, 3)}
        else:
            self._last_burnout_alert_day = None

        if satisfaction >= ambition_threshold:
            if self._last_career_high_day != today:
                self._last_career_high_day = today
                self.update_mood_score(
                    getattr(config, "CAREER_SATISFACTION_MOOD_BONUS", 6),
                    f"Thriving as a {job_name}",
                )
                focus_bonus = getattr(config, "CAREER_FOCUS_MOOD_BONUS", {}).get(focus)
                if focus_bonus:
                    self.update_mood_score(focus_bonus, f"Proud of {job_name} focus")
                updates["thriving"] = {"satisfaction": round(satisfaction, 3)}
        else:
            self._last_career_high_day = None

        stage_before = self.career_stage
        stage_after = stage_before
        stage_thresholds = getattr(config, "CAREER_STAGE_THRESHOLDS", {})
        if isinstance(stage_thresholds, dict) and primary_skill:
            skill_level = self.skills.get(primary_skill, {}).get("level", 0)
            ordered = sorted(stage_thresholds.items(), key=lambda item: item[1])
            for stage_name, threshold in ordered:
                if skill_level >= threshold:
                    stage_after = stage_name
        if stage_after != stage_before:
            self.career_stage = stage_after
            self._last_career_stage_day = today
            summary = f"Recognized as a {stage_after} {job_name}."
            self.add_memory(summary)
            self.record_life_event(
                world,
                "career_stage_change",
                summary,
                tags=["career", stage_after.lower()],
                significance=3,
                details={
                    "job": job_name,
                    "stage": stage_after,
                    "previous_stage": stage_before,
                    "skill": primary_skill,
                    "level": self.skills.get(primary_skill, {}).get("level", 0),
                },
            )
            rep_bonus = getattr(config, "CAREER_STAGE_REPUTATION_BONUS", {}).get(stage_after)
            if rep_bonus:
                self.update_reputation(rep_bonus, f"Advanced to {stage_after} {job_name}", world)
            updates["stage_change"] = {
                "from": stage_before,
                "to": stage_after,
                "skill": primary_skill,
                "level": self.skills.get(primary_skill, {}).get("level", 0),
            }

        milestones = getattr(config, "CAREER_TENURE_MILESTONES", [])
        reached: List[int] = []
        for milestone in milestones:
            if (
                isinstance(milestone, int)
                and milestone > 0
                and self.current_profession_tenure >= milestone
                and milestone not in self._triggered_tenure_milestones
            ):
                self._triggered_tenure_milestones.add(milestone)
                reached.append(milestone)
                note = f"Marked {milestone} days as a {job_name}."
                self.add_memory(note)
                self.record_life_event(
                    world,
                    "career_tenure",
                    note,
                    tags=["career"],
                    significance=2,
                    details={"job": job_name, "milestone": milestone},
                )
        if reached:
            updates["tenure_milestones"] = reached

        if updates and "satisfaction" not in updates:
            updates["satisfaction"] = {
                "previous": round(previous_satisfaction, 3),
                "current": round(self.job_satisfaction, 3),
            }

        return updates

    def evaluate_leadership_oversight_daily(self, world: 'World') -> Optional[Dict[str, Any]]:
        if not world or not world.game_time:
            return None
        if not self.holds_leadership_role():
            self.leadership_oversight_score = 0.0
            self._last_oversight_summary = None
            return None

        today = world.game_time.current_day
        if self._last_management_day != today:
            self._management_actions_today = 0.0
            self._management_action_notes = []
            self._last_management_day = today

        baseline = getattr(config, "LEADERSHIP_OVERSIGHT_BASELINE", 0.35)
        oversight_score = baseline

        leadership_skill = self.skills.get("Leadership", {}).get("level", 0)
        oversight_score += leadership_skill * getattr(config, "LEADERSHIP_OVERSIGHT_SKILL_WEIGHT", 0.06)

        oversight_score += min(
            1.0,
            self._management_actions_today * getattr(config, "LEADERSHIP_OVERSIGHT_ACTION_WEIGHT", 0.2),
        )

        if self.subordinates_names:
            relationship_scores = [self.get_relationship_score(name) for name in self.subordinates_names]
            average_relationship = sum(relationship_scores) / max(1, len(relationship_scores))
            normalized_relationship = (average_relationship + 100) / 200
        else:
            normalized_relationship = 0.5

        oversight_score += normalized_relationship * getattr(
            config, "LEADERSHIP_OVERSIGHT_RELATIONSHIP_WEIGHT", 0.2
        )

        oversight_score += getattr(config, "LEADERSHIP_OVERSIGHT_PERSONALITY_BONUS", {}).get(self.personality, 0.0)
        for trait in self.traits:
            oversight_score += getattr(config, "LEADERSHIP_OVERSIGHT_TRAIT_BONUS", {}).get(trait, 0.0)

        oversight_score = max(0.0, min(1.0, oversight_score))
        self.leadership_oversight_score = oversight_score

        summary: Dict[str, Any] = {
            "leader": self.name,
            "role": self.job or self.rank or "Leader",
            "score": oversight_score,
            "actions": round(self._management_actions_today, 2),
            "skill": leadership_skill,
            "relationships": round(normalized_relationship, 2),
            "subordinates": len(self.subordinates_names),
            "flags": [],
        }
        if self._management_action_notes:
            summary["notes"] = list(self._management_action_notes[-4:])

        neglect_threshold = getattr(config, "LEADERSHIP_NEGLECT_THRESHOLD", 0.45)
        commendable_threshold = getattr(config, "LEADERSHIP_HIGH_WATERMARK", 0.78)

        memory_logged = False
        if self.subordinates_names and self._management_actions_today <= 0:
            summary["flags"].append("no_actions")
            if self._last_oversight_memory_day != today:
                self.add_memory("Realized I haven't checked on my crew today—I need to make rounds soon.")
                memory_logged = True

        if oversight_score >= commendable_threshold:
            summary["flags"].append("commendable")
            if not memory_logged and self._last_oversight_memory_day != today:
                self.add_memory("Feeling confident about how closely I'm guiding everyone today.")
                memory_logged = True
        elif oversight_score < neglect_threshold:
            summary["flags"].append("neglect")
            if not memory_logged and self._last_oversight_memory_day != today:
                self.add_memory("Too many distractions—I barely checked on my team today.")
                memory_logged = True

        if memory_logged:
            self._last_oversight_memory_day = today

        self._last_oversight_evaluation_day = today
        self._last_oversight_summary = summary.copy()
        return summary.copy()

    def handle_business_closure(self, business_id: str, world: Optional['World'], reason: str) -> None:
        if business_id in self.business_roles:
            self.leave_business_role(business_id, reason)
            self.record_life_event(
                world,
                "business_closure",
                reason,
                tags=["business"],
                significance=2,
                details={"business_id": business_id},
            )

    def interact(self, other: 'Character', world: 'World') -> bool:
        """Trigger a lightweight social interaction with another character."""
        if other is None or world is None:
            return False
        if other.name == self.name:
            return False

        if not self.current_goal or self.current_goal.type not in {
            GoalType.IDLE,
            GoalType.WANDER,
            GoalType.SMALL_TALK,
            GoalType.INTRODUCE_SELF_TO_STRANGER,
        }:
            return False

        distance = abs(self.x - other.x) + abs(self.y - other.y)
        knows_other = other.name in self.known_characters

        if knows_other:
            new_goal = Goal(
                GoalType.SMALL_TALK,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"target_char_name": other.name},
            )
            interaction_desc = "small talk"
        else:
            new_goal = Goal(
                GoalType.INTRODUCE_SELF_TO_STRANGER,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"target_char_name": other.name},
            )
            interaction_desc = "an introduction"

        self.current_goal = new_goal

        if distance > 1:
            self.add_memory(f"Heading toward {other.name} for {interaction_desc}.")
            self.move_towards(other.x, other.y, world)
        else:
            self.add_memory(f"Initiating {interaction_desc} with {other.name}.")

        return True

    def move(self, dx: int, dy: int, world: 'World') -> bool:
        if dx == 0 and dy == 0:
            return True

        old_coords = (self.x, self.y)
        new_x, new_y = old_coords[0] + dx, old_coords[1] + dy
        if not world.is_walkable(new_x, new_y, ignore_characters={self.name}):
            return False

        if not world.reserve_tile(self.name, (new_x, new_y)):
            return False

        self.x, self.y = new_x, new_y
        world.update_character_position(self, old_coords, (new_x, new_y))
        world.release_tile(self.name)
        self._clear_cached_path()
        return True

    def _handle_failed_move_attempt(self, dx: int, dy: int, world: 'World') -> None:
        """Record why a step failed so characters can react to blocked paths."""
        target_x, target_y = self.x + dx, self.y + dy

        if not (0 <= target_x < world.grid_size[0] and 0 <= target_y < world.grid_size[1]):
            blocker_desc = "the edge of the map"
        else:
            blocking_building = world.get_building_at(target_x, target_y)
            blocking_chars = [char.name for char in world.get_characters_at_location(target_x, target_y)]
            if blocking_building:
                blocker_desc = blocking_building.display_name
            elif blocking_chars:
                joined_names = ", ".join(blocking_chars[:3])
                remainder = "" if len(blocking_chars) <= 3 else " and others"
                blocker_desc = f"{joined_names}{remainder}"
            else:
                blocker_desc = world.get_tile(target_x, target_y)

        memory_entry = f"Route to ({target_x}, {target_y}) blocked by {blocker_desc}."
        if not self.memory or self.memory[-1] != memory_entry:
            self.add_memory(memory_entry)

    def _clear_cached_path(self) -> None:
        self._cached_path.clear()
        self._cached_path_target = None
        self._cached_path_revision = None

    def _ensure_path_to(self, target: Tuple[int, int], world: 'World') -> bool:
        current_revision = getattr(world, "map_revision", None)
        needs_replan = (
            not self._cached_path and (self.x, self.y) != target
        ) or self._cached_path_target != target or self._cached_path_revision != current_revision

        if not needs_replan and self._cached_path:
            next_step = self._cached_path[0]
            if max(abs(next_step[0] - self.x), abs(next_step[1] - self.y)) > 1:
                needs_replan = True

        if not needs_replan:
            return True

        path = world.find_path((self.x, self.y), target, ignore_characters={self.name})
        if not path:
            self._clear_cached_path()
            return False

        if len(path) <= 1:
            self._cached_path = deque()
        else:
            self._cached_path = deque(path[1:])
        self._cached_path_target = target
        self._cached_path_revision = current_revision
        return bool(self._cached_path) or (self.x, self.y) == target

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        target = (target_x, target_y)
        if (self.x, self.y) == target:
            self._clear_cached_path()
            return True

        if not self._ensure_path_to(target, world):
            failure_dx = 1 if target_x > self.x else -1 if target_x < self.x else 0
            failure_dy = 1 if target_y > self.y else -1 if target_y < self.y else 0
            if failure_dx != 0 or failure_dy != 0:
                self._handle_failed_move_attempt(failure_dx, failure_dy, world)
            return False

        speed_modifier = 1.0
        if hasattr(world, "get_travel_speed_modifier"):
            speed_modifier = world.get_travel_speed_modifier()

        if speed_modifier < 1.0 and random.random() > speed_modifier:
            if random.random() < 0.15:
                weather_desc = getattr(world, "weather", "difficult").lower()
                self.add_memory(f"Travel slowed by {weather_desc} conditions.")
            return False

        steps_to_take = 1
        if speed_modifier > 1.0:
            bonus_chance = min(speed_modifier - 1.0, 1.0)
            if random.random() < bonus_chance:
                steps_to_take += 1

        moved = False
        for _ in range(steps_to_take):
            if not self._cached_path:
                break

            next_step = self._cached_path[0]
            if not world.is_walkable(next_step[0], next_step[1], ignore_characters={self.name}):
                self._clear_cached_path()
                failure_dx = 1 if target_x > self.x else -1 if target_x < self.x else 0
                failure_dy = 1 if target_y > self.y else -1 if target_y < self.y else 0
                if failure_dx != 0 or failure_dy != 0:
                    self._handle_failed_move_attempt(failure_dx, failure_dy, world)
                return moved and (self.x, self.y) == target

            if not world.reserve_tile(self.name, next_step):
                self._clear_cached_path()
                return moved and (self.x, self.y) == target

            self._cached_path.popleft()
            self.x, self.y = next_step
            world.release_tile(self.name)
            moved = True

            if (self.x, self.y) == target:
                self._clear_cached_path()
                return True

        return moved and (self.x, self.y) == target
        # print(f"DEBUG {self.name}: move_towards ({target_x},{target_y}) FAILED all attempts from ({self.x},{self.y}).")


    def advance_age(self, world: 'World') -> None:
        """Increment the character's age and celebrate yearly milestones."""
        days_per_season = getattr(config, "DAYS_PER_SEASON", 10)
        seasons_per_year = len(getattr(world, "SEASONS", ["Spring", "Summer", "Autumn", "Winter"])) or 4
        days_per_year = max(1, days_per_season * seasons_per_year)

        self.age_in_days += 1
        if self.age_in_days >= days_per_year:
            self.age_in_days -= days_per_year
            self.age_years += 1
            birthday_message = f"Celebrated a birthday—now {self.age_years} years old."
            self.add_memory(birthday_message)
            if hasattr(world, "add_event_log_message"):
                world.add_event_log_message(f"{self.name} celebrates a birthday (age {self.age_years}).")

    def _apply_phase_behavior(self, world: 'World', phase_info: Optional[Dict[str, Any]]):
        """Adjust daily behavior based on the active phase schedule."""
        self._phase_social_bias = 0.0
        self._phase_rest_threshold_bonus = 0
        if not phase_info:
            return

        phase_key = phase_info.get("key")
        if phase_key and phase_key != self._last_phase_key:
            phase_name = phase_info.get("name", phase_key.title())
            phase_desc = phase_info.get("description")
            description_suffix = f" — {phase_desc}" if phase_desc else ""
            self.add_memory(f"{phase_name} begins{description_suffix}.")
            self._last_phase_key = phase_key

        tweaks = getattr(config, "PHASE_BEHAVIOR_TWEAKS", {}).get(phase_key, {})
        self._phase_social_bias = tweaks.get("social_bonus", 0.0)

        if tweaks.get("job_focus") and self.current_goal.type in [GoalType.IDLE, GoalType.WANDER]:
            default_goal = self.get_default_goal()
            if default_goal and default_goal.type not in [GoalType.IDLE, GoalType.WANDER]:
                self.add_memory("Duty calls—I should focus on my work this phase.")
                self.current_goal = default_goal

        if tweaks.get("meal_focus") and self.current_goal.type not in [GoalType.EAT_FOOD, GoalType.SEEK_TO_BUY_ITEM]:
            if self.inventory.get("Food", 0) > 0 and self.needs.get("Hunger", 100) < config.NEED_SCORE_MAX:
                self.add_memory("It's the communal meal hour—time to take a break and eat.")
                self.current_goal = Goal(GoalType.EAT_FOOD, assignee_id=self.name, originator_id=self.name, priority=2)

        if tweaks.get("force_rest"):
            self._phase_rest_threshold_bonus = 15
            if self.current_goal.type not in [GoalType.REST_AT_HOME, GoalType.FIND_SHELTER, GoalType.SEEK_MEDICAL_ATTENTION]:
                if self.current_goal.priority >= 3:
                    home_building = self._ensure_home_assignment(world)
                    if home_building:
                        self.add_memory(f"Quiet hours descend—returning to {home_building.display_name} to rest.")
                        self.current_goal = Goal(
                            GoalType.REST_AT_HOME,
                            assignee_id=self.name,
                            originator_id=self.name,
                            parameters={"building_location": home_building.location},
                            priority=2,
                        )
                else:
                    self.add_memory("Quiet hours begin but duty keeps me occupied.")
        else:
            self._phase_rest_threshold_bonus = tweaks.get("rest_threshold_bonus", 0)

    def _should_seek_weather_shelter(self, weather_event: Dict[str, Any]) -> bool:
        severity = weather_event.get("severity", 1)
        requires_shelter = weather_event.get("requires_shelter", False)
        if requires_shelter and self.current_goal.priority >= 2:
            return True
        if severity >= 3 and self.current_goal.priority >= 3:
            return True
        return False

    def _seek_weather_shelter(self, world: 'World', weather_event: Dict[str, Any]):
        if self.current_goal.type in [GoalType.REST_AT_HOME, GoalType.FIND_SHELTER]:
            return
        home_building = self._ensure_home_assignment(world)
        event_name = weather_event.get("name", "severe weather")
        if home_building:
            self.add_memory(f"{event_name} forces me indoors at {home_building.display_name}.")
            self.current_goal = Goal(
                GoalType.REST_AT_HOME,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"building_location": home_building.location, "reason": event_name},
                priority=2,
            )
        else:
            self.add_memory(f"{event_name} rages—I must find shelter fast.")
            self.current_goal = Goal(GoalType.FIND_SHELTER, assignee_id=self.name, originator_id=self.name, priority=2)

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
        task_def = JOB_TASK_DEFINITIONS.get(task_name)
        if not task_def:
            return None

        resource_name = task_def.get("resource_produced")
        if resource_name:
            resource_nodes = world.get_resources(resource_name)
            if resource_nodes:
                def _node_location(entry: Any) -> Tuple[int, int]:
                    if isinstance(entry, dict):
                        loc = entry.get("location") or entry.get("coord")
                        if loc:
                            return tuple(loc)
                        return (0, 0)
                    return tuple(entry)

                sorted_nodes = sorted(
                    resource_nodes,
                    key=lambda node: abs(_node_location(node)[0] - self.x) + abs(_node_location(node)[1] - self.y),
                )
                for node in sorted_nodes:
                    node_loc = _node_location(node)
                    if world.get_tile(*node_loc) != "OutOfBounds" and world.is_resource_node(resource_name, node_loc):
                        return node_loc

        tile_preferences = {
            "Wood": ["Forest"],
            "Stone": ["Rocks", "Mountain"],
            "Iron Ore": ["Rocks", "Mountain"],
            "Herbs": ["Forest", "Meadow", "Grass"],
            "Food": ["Fields", "Meadow", "Grass"],
            "Water": ["Water", "River", "Stream", "Well"],
        }
        tiles_to_scan = tile_preferences.get(resource_name, [])
        if not tiles_to_scan:
            return None

        closest_match: Optional[Tuple[int, int]] = None
        closest_distance = float("inf")
        for r_idx in range(world.grid_size[0]):
            for c_idx in range(world.grid_size[1]):
                tile = world.get_tile(r_idx, c_idx)
                if tile not in tiles_to_scan:
                    continue
                distance = abs(r_idx - self.x) + abs(c_idx - self.y)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_match = (r_idx, c_idx)
        return closest_match

    def _deposit_resource_to_nearest_stockpile(
        self, resource_name: str, world: 'World', amount: Optional[int] = None
    ) -> bool:
        available = self.inventory.get(resource_name, 0)
        if available <= 0:
            return True

        stockpiles = world.get_stockpiles_for_resource(resource_name)
        if not stockpiles:
            self.add_memory(f"No stockpile is configured to accept {resource_name} right now.")
            return True

        def closest_distance(sp):
            return min(abs(pt[0] - self.x) + abs(pt[1] - self.y) for pt in sp.access_points)

        target_stockpile = min(stockpiles, key=closest_distance)
        access_point = min(
            target_stockpile.access_points,
            key=lambda loc: abs(loc[0] - self.x) + abs(loc[1] - self.y),
        )

        if (self.x, self.y) != access_point:
            self.move_towards(access_point[0], access_point[1], world)
            return False

        deposit_amount = available if amount is None else min(amount, available)
        success, added = target_stockpile.add_item(resource_name, deposit_amount)
        if not success or added <= 0:
            self.add_memory(f"{target_stockpile.name} has no space for additional {resource_name}.")
            return True

        remaining = available - added
        if remaining > 0:
            self.inventory[resource_name] = remaining
        else:
            self.inventory.pop(resource_name, None)

        world.add_event_log_message(
            f"{self.name} stores {added} {resource_name} in {target_stockpile.name}."
        )
        if world.game_time:
            world.ledger.update_stockpile_record(
                target_stockpile.name, target_stockpile.inventory, world.game_time.current_day
            )
        return True
    def gather_resource(self, resource_name: str, world: 'World') -> bool:
        """Generic resource gathering entry point used by dynamic goals."""
        specialized_handlers = {
            "Wood": self._execute_gather_wood,
            "Stone": self._execute_gather_stone,
            "Herbs": self._execute_gather_herbs,
        }

        handler = specialized_handlers.get(resource_name)
        if handler:
            handler(world)
            return True

        task_name = None
        for name, definition in JOB_TASK_DEFINITIONS.items():
            if definition.get("resource_produced") == resource_name:
                task_name = name
                break

        if not task_name:
            self.add_memory(f"I don't know how to gather {resource_name}.")
            self.current_goal = self.get_default_goal()
            return False

        target_location = self.find_task_location(task_name, world)
        if not target_location:
            self.add_memory(f"Couldn't locate any {resource_name} to gather.")
            self.current_goal = self.get_default_goal()
            return False

        if (self.x, self.y) != target_location:
            self.move_towards(target_location[0], target_location[1], world)
            return True

        if not self._execute_generic_task(world, task_name):
            return True # Tool fetching or prerequisite handling will adjust the goal

        quota = None
        if self.current_goal and self.current_goal.parameters:
            quota = self.current_goal.parameters.get("quota")

        if quota is not None and self.inventory.get(resource_name, 0) >= quota:
            self.add_memory(f"Gathered the requested {quota} {resource_name}.")
            self.current_goal = self.get_default_goal()

        return True
    def build(self, structure_type: str, world: 'World') -> bool: return False

    def job_default_goal_type_str(self) -> str: # Returns a string representing the goal type or job title
        if self.job == "Woodcutter": return "Perform Woodcutter Duties"
        if self.job == "Stonemason": return "Perform Stonemason Duties"
        if self.job == "Farmer": return "Perform Farmer Duties"
        if self.job == "Hunter": return "Perform Hunter Duties"
        if self.job == "Fletcher": return "Perform Fletcher Duties"
        if self.job == "Master Craftsman": return "Assess Production Needs"
        if self.job == "Manager": return "Manage Subordinates"
        if self.job == "Chancellor": return "Oversee Settlement"
        if self.job == "Bookkeeper": return "Maintain Ledger"
        if self.job == "Expedition Leader": return "Oversee Expedition"
        if self.job == "Mayor": return "Oversee Settlement"
        if self.job == "Chief Medical Officer": return "Oversee Medical Operations"
        if self.job == "Medic": return "Provide Medical Care"
        if self.job == "Sheriff": return "Maintain Peace in Settlement"
        if self.job == "Marshal": return "Maintain Defenses"
        if self.job == "Spymaster": return "Maintain Peace in Settlement"
        if self.job == "Deputy": return "Patrol Area"
        if self.job == "Scout": return "Patrol Area"
        if self.job == "Militia Soldier": return "Patrol Area"
        if self.job == "Reeve": return "Manage Estate"
        if self.job == "Steward": return "Manage Estate"
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

    def holds_leadership_role(self) -> bool:
        if self.subordinates_names:
            return True
        leadership_titles = set(getattr(config, "LEADERSHIP_ROLE_TITLES", []))
        if self.job and self.job in leadership_titles:
            return True
        if self.rank and self.rank in leadership_titles:
            return True
        noble_titles = set(getattr(config, "NOBLE_RANKS_OR_JOBS", []) or [])
        if self.rank and self.rank in noble_titles:
            return True
        return False

    def _record_management_activity(self, world: Optional['World'], label: Optional[str], weight: float = 1.0) -> None:
        if not self.holds_leadership_role() or not world or not getattr(world, "game_time", None):
            return
        day = world.game_time.current_day
        if self._last_management_day != day:
            self._management_actions_today = 0.0
            self._management_action_notes = []
            self._last_management_day = day
        self._management_actions_today += max(0.0, weight)
        if label:
            if len(self._management_action_notes) >= 6:
                self._management_action_notes.pop(0)
            self._management_action_notes.append(label)

    def _compute_supervision_slack_probability(self, base_chance: float, world: Optional['World']) -> Tuple[float, bool]:
        chance = max(0.0, base_chance)
        oversight_bonus_applied = False
        if not self.supervisor_name:
            return min(1.0, chance), False

        threshold = getattr(config, "LEADERSHIP_NEGLECT_THRESHOLD", 0.45)
        oversight = self.supervisor_oversight
        if world and world.game_time:
            if (
                self.last_supervisor_oversight_day is None
                or self.last_supervisor_oversight_day != world.game_time.current_day
            ):
                oversight *= 0.8

        slack_pressure = self._neglect_slack_pressure
        if threshold > 0:
            gap_ratio = max(0.0, threshold - oversight) / threshold
            slack_pressure = max(slack_pressure, gap_ratio)

        if slack_pressure > 0:
            bonus = slack_pressure * getattr(config, "LEADERSHIP_SLACKING_BASE_CHANCE", 0.12)
            if "Lazy" in self.traits:
                bonus *= 1.15
            if "Diligent" in self.traits or "Focused" in self.traits:
                bonus *= 0.6
            chance += bonus
            oversight_bonus_applied = bonus > 1e-6

        chance = min(1.0, max(0.0, chance))
        return chance, oversight_bonus_applied

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

        # Trait and supervision effects on progress
        base_lazy_chance = 0.0
        if "Lazy" in self.traits and "Focused" not in self.traits:
            base_lazy_chance = 0.25
        slack_chance, oversight_slack = self._compute_supervision_slack_probability(base_lazy_chance, world)
        if slack_chance > 0 and random.random() < slack_chance:
            current_progress_gain = 0
            is_lazy_this_tick = True
            if oversight_slack and base_lazy_chance <= 0:
                watcher = self.supervisor_name or "leadership"
                self.add_memory(f"With {watcher} absent I drifted off during '{task_name}'.")
            elif oversight_slack and base_lazy_chance > 0:
                watcher = self.supervisor_name or "no one"
                self.add_memory(f"Felt lazy and noticed {watcher} wasn't watching, so I coasted on '{task_name}'.")
            else:
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

            if hasattr(world, "record_resource_harvest") and world.is_resource_node(res_prod, (self.x, self.y)):
                world.record_resource_harvest(res_prod, (self.x, self.y), actual_yield_taken)

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

            base_lazy_chance = 0.0
            if "Lazy" in self.traits and "Focused" not in self.traits:
                base_lazy_chance = 0.25
            slack_chance, oversight_slack = self._compute_supervision_slack_probability(base_lazy_chance, world)
            if slack_chance > 0 and random.random() < slack_chance:
                current_crafting_progress_gain = 0
                is_slacking_craft = True
                if oversight_slack and base_lazy_chance <= 0:
                    watcher = self.supervisor_name or "leadership"
                    self.add_memory(f"Took advantage of lax oversight to slack on WO {order.order_id}.")
                elif oversight_slack and base_lazy_chance > 0:
                    watcher = self.supervisor_name or "no one"
                    self.add_memory(f"Felt lazy and noticed {watcher} absent, so I coasted on WO {order.order_id}.")
                else:
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
            order_to_process.status = "Approved"
            order_to_process.approved_by = self.name
            order_to_process.approval_day = world.game_time.current_day
            self.add_memory(f"Approved WO {order_to_process.order_id}")
            print(f"{self.name} (Manager) APPROVED {order_to_process.order_id[:8]}.")
            self._receive_payment(JOB_SALARIES.get("Manage Subordinates", 3), f"reviewing WO {order_to_process.order_id[:4]}", world)
            self._record_management_activity(world, f"order_approve:{order_to_process.order_id[:4]}", weight=0.5)
        else:
            order_to_process.status = "Denied"
            order_to_process.denied_by = self.name
            order_to_process.denial_reason = f"Insuff: {', '.join(missing_notes) or 'stale data'}"
            self.add_memory(f"Denied WO {order_to_process.order_id}")
            print(f"{self.name} (Manager) DENIED {order_to_process.order_id[:8]}. Reason: {order_to_process.denial_reason}")
            self._receive_payment(JOB_SALARIES.get("Manage Subordinates", 3), f"reviewing WO {order_to_process.order_id[:4]}", world)
            self._record_management_activity(world, f"order_deny:{order_to_process.order_id[:4]}", weight=0.5)
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

    def _execute_perform_farmer_duties(self, world: 'World'):
        if self.job != "Farmer":
            self.current_goal = self.get_default_goal()
            return

        params = self.current_goal.parameters
        params.setdefault("phase", "gather")
        deliver_threshold = max(3, min(self.max_inventory_items, 6))

        if params.get("phase") == "deliver" or self.inventory.get("Food", 0) >= deliver_threshold:
            params["phase"] = "deliver"
            if self._deposit_resource_to_nearest_stockpile("Food", world):
                params["phase"] = "gather"
                self.current_goal = self.get_default_goal()
            return

        field_location = self.find_task_location("Tend Fields", world)
        if not field_location:
            self.add_memory("No open fields to tend today; shifting to other duties.")
            self.current_goal = self.get_default_goal()
            return

        if (self.x, self.y) != field_location:
            self.move_towards(field_location[0], field_location[1], world)
            return

        if not self._execute_generic_task(world, "Tend Fields"):
            return

        if self.inventory.get("Food", 0) >= deliver_threshold:
            params["phase"] = "deliver"

    def _execute_perform_hunter_duties(self, world: 'World'):
        if self.job != "Hunter":
            self.current_goal = self.get_default_goal()
            return

        params = self.current_goal.parameters
        params.setdefault("phase", "stalk")
        deliver_threshold = max(2, min(self.max_inventory_items, 5))

        if params.get("phase") == "deliver" or self.inventory.get("Food", 0) >= deliver_threshold:
            params["phase"] = "deliver"
            if self._deposit_resource_to_nearest_stockpile("Food", world):
                params["phase"] = "stalk"
                self.current_goal = self.get_default_goal()
            return

        hunt_location = self.find_task_location("Hunt Game", world)
        if not hunt_location:
            self.add_memory("Couldn't find promising hunting grounds today.")
            self.current_goal = self.get_default_goal()
            return

        if (self.x, self.y) != hunt_location:
            self.move_towards(hunt_location[0], hunt_location[1], world)
            return

        if not self._execute_generic_task(world, "Hunt Game"):
            return

        if self.inventory.get("Food", 0) >= deliver_threshold:
            params["phase"] = "deliver"

    def _execute_perform_fletcher_duties(self, world: 'World'):
        if self.job != "Fletcher":
            self.current_goal = self.get_default_goal()
            return

        params = self.current_goal.parameters
        params.setdefault("phase", "craft")
        bundle_threshold = max(2, min(self.max_inventory_items, 4))

        if params.get("phase") == "deliver" or self.inventory.get("Arrow Bundle", 0) >= bundle_threshold:
            params["phase"] = "deliver"
            if self._deposit_resource_to_nearest_stockpile("Arrow Bundle", world):
                params["phase"] = "craft"
                self.current_goal = self.get_default_goal()
            return

        if self.inventory.get("Wood", 0) < 2:
            stockpiles = world.get_stockpiles_for_resource("Wood")
            if not stockpiles:
                self.add_memory("No wood available for fletching.")
                self.current_goal = self.get_default_goal()
                return
            target_stockpile = min(
                stockpiles,
                key=lambda sp: min(abs(pt[0] - self.x) + abs(pt[1] - self.y) for pt in sp.access_points),
            )
            access_point = min(
                target_stockpile.access_points,
                key=lambda loc: abs(loc[0] - self.x) + abs(loc[1] - self.y),
            )
            if (self.x, self.y) != access_point:
                self.move_towards(access_point[0], access_point[1], world)
                return
            success, removed = target_stockpile.remove_item("Wood", 3)
            if not success or removed <= 0:
                self.add_memory(f"{target_stockpile.name} had no wood for fletching today.")
                return
            self.inventory["Wood"] = self.inventory.get("Wood", 0) + removed
            if world.game_time:
                world.ledger.update_stockpile_record(
                    target_stockpile.name, target_stockpile.inventory, world.game_time.current_day
                )
            world.add_event_log_message(
                f"{self.name} withdrew {removed} Wood from {target_stockpile.name} for arrow crafting."
            )
            return

        starting_arrows = self.inventory.get("Arrow Bundle", 0)
        if not self._execute_generic_task(world, "Fletch Arrows"):
            return
        produced = self.inventory.get("Arrow Bundle", 0) - starting_arrows
        if produced > 0:
            wood_used = produced * 2
            current_wood = self.inventory.get("Wood", 0)
            if current_wood >= wood_used:
                current_wood -= wood_used
                if current_wood > 0:
                    self.inventory["Wood"] = current_wood
                else:
                    self.inventory.pop("Wood", None)
            else:
                self.inventory.pop("Wood", None)
            self.add_memory(f"Crafted {produced} arrow bundles for the militia.")
            self.update_mood_score(config.MOOD_CHANGE_SUCCESSFUL_TASK_MINOR, "Finished an arrow batch")

        if self.inventory.get("Arrow Bundle", 0) >= bundle_threshold:
            params["phase"] = "deliver"

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
        task_loc = self.find_task_location("Gather Herbs", world)

        if not task_loc:
            self.add_memory("I couldn't find any herb patches in the surrounding woods.")
            self.current_goal = self.get_default_goal()
            return

        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return

        if not self._execute_generic_task(world, "Gather Herbs"):
            return

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

        if hasattr(world, "get_medical_queue_snapshot"):
            queue_snapshot = world.get_medical_queue_snapshot()
            if queue_snapshot:
                top_case = queue_snapshot[0]
                summary = (
                    f"Triage review: {top_case.get('patient')} needs care for {top_case.get('condition')} "
                    f"(severity {top_case.get('severity')})."
                )
                self.add_memory(summary)
                if len(queue_snapshot) > 1:
                    self.add_memory(
                        f"{len(queue_snapshot) - 1} additional case(s) awaiting treatment."
                    )
            else:
                self.add_memory("Medical triage queue is currently clear.")

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

        if hasattr(world, "get_clinic_supply_requests"):
            open_requests = [
                req
                for req in world.get_clinic_supply_requests()
                if req.get("status") == "open"
            ]
            for request in open_requests[:2]:
                self.add_memory(
                    f"Clinic request logged: {request.get('resource')} at {request.get('current')}/"
                    f"{request.get('threshold')} units."
                )
            if open_requests:
                self.add_memory("Coordinating restock plans with gatherers and apothecaries.")

        # CMOs might also manage medic assignments, rest schedules for medical staff, etc.
        # For now, primarily observation and logging.
        if random.random() < 0.1:
             self.add_memory(f"CMO {self.name} reviews medical protocols and staff readiness.")
        return

    def _execute_provide_medical_care(self, world: 'World'):
        if self.job != "Medic":
            self.current_goal = self.get_default_goal()
            return

        goal_params = self.current_goal.parameters
        case: Optional[Dict[str, Any]] = None
        case_id = goal_params.get("case_id")

        if case_id and hasattr(world, "get_medical_case_by_id"):
            case = world.get_medical_case_by_id(case_id)
            if not case:
                goal_params.pop("case_id", None)

        if not case and hasattr(world, "claim_medical_case"):
            claimed = world.claim_medical_case(self.name)
            if claimed:
                case = claimed
                goal_params["case_id"] = case.get("case_id")

        target_patient: Optional['Character'] = None
        condition_focus: Optional[str] = None

        if case:
            patient_name = case.get("patient")
            target_patient = world.get_character_by_name(patient_name)
            condition_focus = case.get("condition")
            if not target_patient or (not target_patient.is_sick and not target_patient.is_injured):
                if hasattr(world, "resolve_medical_case"):
                    world.resolve_medical_case(
                        case.get("case_id"),
                        "cancelled",
                        notes="Patient no longer requires treatment.",
                    )
                goal_params.pop("case_id", None)
                target_patient = None
                condition_focus = None

        if not target_patient:
            highest_need = -1.0
            for char in world.characters:
                if char.name == self.name:
                    continue
                if char.is_injured and char.injury_severity > highest_need:
                    target_patient = char
                    condition_focus = "injury"
                    highest_need = char.injury_severity
                if char.is_sick and char.sickness_severity > highest_need:
                    target_patient = char
                    condition_focus = "sickness"
                    highest_need = char.sickness_severity

            if target_patient and hasattr(world, "register_medical_case"):
                severity_value = (
                    target_patient.injury_severity
                    if condition_focus == "injury"
                    else target_patient.sickness_severity
                )
                case, _ = world.register_medical_case(
                    target_patient.name,
                    condition_focus or "sickness",
                    severity_value,
                    reporter=self.name,
                    cause="Medic triage assignment",
                    location=(target_patient.x, target_patient.y),
                )
                if case:
                    goal_params["case_id"] = case.get("case_id")
                    condition_focus = case.get("condition")

        if not target_patient:
            self.add_memory("No patients currently require medical care. Standing by.")
            self.current_goal = self.get_default_goal()
            return

        self.add_memory(
            f"Medic {self.name} assigned to patient {target_patient.name} at ({target_patient.x},{target_patient.y})."
        )

        patient_loc = (target_patient.x, target_patient.y)
        if (self.x, self.y) != patient_loc:
            self.move_towards(patient_loc[0], patient_loc[1], world)
            self.add_memory(f"Moving towards patient {target_patient.name}.")
            return

        self.add_memory(f"Medic {self.name} is treating {target_patient.name}.")

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
            self.add_memory(
                f"No medical supplies (Bandages/Herbs) to treat {target_patient.name}. Need to restock."
            )
            if case and hasattr(world, "record_medical_treatment"):
                severity_after = (
                    target_patient.injury_severity
                    if condition_focus == "injury"
                    else target_patient.sickness_severity
                )
                world.record_medical_treatment(
                    case.get("case_id"),
                    self.name,
                    severity_after,
                    notes="Unable to treat due to missing supplies",
                    success=False,
                )
            self.current_goal = self.get_default_goal()
            return

        treatment_successful_this_tick = False
        severity_after = None

        if item_used_for_treatment == "Bandages" and target_patient.is_injured:
            reduction = random.randint(2, 3)
            if self.skills.get("Medicine", {}).get("level", 0) > 2:
                reduction += random.choice([0, 1])

            target_patient.injury_severity -= reduction
            severity_after = max(0, target_patient.injury_severity)
            self.add_memory(
                f"Applied Bandages to {target_patient.name}'s injuries, severity reduced by {reduction} to {severity_after}."
            )
            treatment_successful_this_tick = True
            if target_patient.injury_severity <= 0:
                target_patient.is_injured = False
                target_patient.injury_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their injuries!")
                world.add_event_log_message(
                    f"{target_patient.name} recovered from injuries thanks to {self.name}."
                )

        elif item_used_for_treatment == "Herbs" and target_patient.is_sick:
            reduction = random.randint(1, 2)
            if self.skills.get("Medicine", {}).get("level", 0) > 1:
                reduction += random.choice([0, 1])

            target_patient.sickness_severity -= reduction
            severity_after = max(0, target_patient.sickness_severity)
            self.add_memory(
                f"Administered Herbs to {target_patient.name} for sickness, severity reduced by {reduction} to {severity_after}."
            )
            treatment_successful_this_tick = True
            if target_patient.sickness_severity <= 0:
                target_patient.is_sick = False
                target_patient.sickness_severity = 0
                self.add_memory(f"{target_patient.name} has fully recovered from their sickness!")
                world.add_event_log_message(
                    f"{target_patient.name} recovered from sickness thanks to {self.name}."
                )

        elif item_used_for_treatment:
            severity_after = (
                target_patient.injury_severity
                if target_patient.is_injured and condition_focus == "injury"
                else target_patient.sickness_severity
            )
            self.add_memory(
                f"Tried to use {item_used_for_treatment} on {target_patient.name}, but it wasn't effective for their current condition."
            )

        if treatment_successful_this_tick:
            if hasattr(target_patient, "record_health_event"):
                treatment_type = "treatment"
                if item_used_for_treatment == "Bandages":
                    treatment_type = "injury_treated"
                elif item_used_for_treatment == "Herbs":
                    treatment_type = "sickness_treated"
                target_patient.record_health_event(
                    world,
                    treatment_type,
                    f"Received care from {self.name} using {item_used_for_treatment or 'aid'}.",
                    severity=severity_after,
                    tags=["treatment"],
                )
            self._grant_skill_experience("Medicine", 1.5, world)
            self._receive_payment(
                JOB_SALARIES.get("Provide Medical Care", 8),
                f"treating {target_patient.name}",
                world,
            )
        else:
            self._grant_skill_experience("Medicine", 0.2, world)

        if case and hasattr(world, "record_medical_treatment"):
            if severity_after is None:
                severity_after = (
                    target_patient.injury_severity
                    if condition_focus == "injury"
                    else target_patient.sickness_severity
                )
            world.record_medical_treatment(
                case.get("case_id"),
                self.name,
                severity_after,
                item_used=item_used_for_treatment,
                success=treatment_successful_this_tick,
            )

        self.current_goal = self.get_default_goal()
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

        if hasattr(world, "fulfill_campaign_promises"):
            world.fulfill_campaign_promises(self)

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

        if hasattr(world, "get_pending_law_draft_for"):
            pending_draft = world.get_pending_law_draft_for(self.name)
        else:
            pending_draft = None
        if pending_draft and (self.current_goal.type == GoalType.OVERSEE_SETTLEMENT):
            self.active_law_draft_id = pending_draft.get("id")
            self.add_memory(f"Draft for {pending_draft.get('title')} awaits my seal.")
            self.current_goal = Goal(
                GoalType.ENACT_SETTLEMENT_LAW,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"law_id": pending_draft.get("id")},
                priority=3,
            )
            return

        if hasattr(world, "peek_priority_law_petition"):
            petition = world.peek_priority_law_petition()
        else:
            petition = None
        if petition and petition.get("support", 0.0) >= 0.35 and self.current_goal.type == GoalType.OVERSEE_SETTLEMENT:
            if petition.get("id") != self.active_law_petition_id:
                self.add_memory(
                    f"Citizens press for {petition.get('title')} (support {petition.get('support', 0.0):.0%})."
                )
            self.active_law_petition_id = petition.get("id")
            self.current_goal = Goal(
                GoalType.REVIEW_LAW_PETITIONS,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"petition_id": petition.get("id")},
                priority=3,
            )
            return

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

    def _execute_review_law_petitions(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
            return

        goal_params = self.current_goal.parameters if self.current_goal else {}
        petition_id = goal_params.get("petition_id") or self.active_law_petition_id
        petition = None
        if petition_id and hasattr(world, "get_petition_by_id"):
            petition = world.get_petition_by_id(petition_id)
        if not petition and hasattr(world, "peek_priority_law_petition"):
            petition = world.peek_priority_law_petition()

        if not petition:
            self.add_memory("No legal petitions require action today.")
            self.active_law_petition_id = None
            self.current_goal = self.get_default_goal()
            return

        support = petition.get("support", 0.0)
        incident_count = petition.get("incident_count", 0)
        self.active_law_petition_id = petition.get("id")
        self.add_memory(
            f"Reviewing '{petition.get('title')}' — support {support:.0%}, incidents {incident_count}."
        )

        should_draft = support >= max(0.4, config.LAW_INTERVIEW_SUPPORT_THRESHOLD) or incident_count >= config.LAW_PETITION_THRESHOLD + 1
        if petition.get("status") == "drafting":
            should_draft = True

        if should_draft:
            self.current_goal = Goal(
                GoalType.DRAFT_SETTLEMENT_LAW,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"petition_id": petition.get("id")},
                priority=3,
            )
            return

        if hasattr(world, "record_petition_review"):
            world.record_petition_review(petition.get("id"), self.name, "defer")
        self.add_memory(f"Defer action on {petition.get('title')} until more evidence arrives.")
        self.active_law_petition_id = None
        self.current_goal = self.get_default_goal()

    def _execute_draft_settlement_law(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
            return

        goal_params = self.current_goal.parameters if self.current_goal else {}
        petition_id = goal_params.get("petition_id") or self.active_law_petition_id
        if not petition_id or not hasattr(world, "draft_law_from_petition"):
            self.current_goal = self.get_default_goal()
            return

        law_record = world.draft_law_from_petition(petition_id, self.name)
        if not law_record:
            self.add_memory("Struggled to turn the petition into a workable statute.")
            self.current_goal = self.get_default_goal()
            return

        self.active_law_draft_id = law_record.get("id")
        penalty = law_record.get("penalty", {})
        penalty_text = "fine" if penalty.get("type") == "fine" else penalty.get("type", "sanction")
        amount = penalty.get("amount")
        if amount:
            penalty_text = f"{penalty_text} of {amount} coins"
        self.add_memory(f"Drafted {law_record.get('title')} imposing {penalty_text}.")
        self.current_goal = Goal(
            GoalType.ENACT_SETTLEMENT_LAW,
            assignee_id=self.name,
            originator_id=self.name,
            parameters={"law_id": law_record.get("id")},
            priority=3,
        )

    def _execute_enact_settlement_law(self, world: 'World'):
        if self.job != "Mayor":
            self.current_goal = self.get_default_goal()
            return

        goal_params = self.current_goal.parameters if self.current_goal else {}
        law_id = goal_params.get("law_id") or self.active_law_draft_id
        if not law_id:
            pending = world.get_pending_law_draft_for(self.name) if hasattr(world, "get_pending_law_draft_for") else None
            if pending:
                law_id = pending.get("id")
        if not law_id or not hasattr(world, "enact_law"):
            self.current_goal = self.get_default_goal()
            return

        law = world.enact_law(law_id, self.name)
        if law:
            penalty = law.get("penalty", {})
            amount = penalty.get("amount")
            if amount:
                summary = f"penalty {amount} coins"
            else:
                summary = penalty.get("type", "sanctions")
            self.add_memory(f"Enacted {law.get('title')} with {summary}.")
        else:
            self.add_memory("Attempted to enact a law but the draft could not be located.")
        self.active_law_draft_id = None
        self.active_law_petition_id = None
        self.current_goal = self.get_default_goal()

    def _execute_maintain_peace(self, world: 'World'): # For Sheriff
        if self.job != "Sheriff":
            self.current_goal = self.get_default_goal()
            return

        active_case = world.get_case_in_session_for(self.name) if hasattr(world, "get_case_in_session_for") else None
        if active_case and (
            self.current_goal.type != GoalType.ATTEND_TRIAL
            or self.current_goal.parameters.get("case_id") != active_case.get("case_id")
        ):
            self.current_goal = Goal(
                GoalType.ATTEND_TRIAL,
                assignee_id=self.name,
                originator_id="CourtSummons",
                parameters={
                    "case_id": active_case.get("case_id"),
                    "location": getattr(world, "courthouse_location", world.market_location),
                },
            )
            return

        if self.active_crime_assignment:
            if self.current_goal.type != GoalType.INVESTIGATE_DISTURBANCE:
                self.current_goal = Goal(
                    GoalType.INVESTIGATE_DISTURBANCE,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"crime_id": self.active_crime_assignment},
                )
            return

        if hasattr(world, "assign_investigative_interview"):
            if self.active_interview_assignment and self.current_goal.type != GoalType.CONDUCT_WITNESS_INTERVIEW:
                self.current_goal = Goal(
                    GoalType.CONDUCT_WITNESS_INTERVIEW,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"assignment_id": self.active_interview_assignment.get("id")},
                    priority=3,
                )
                return
            assignment = world.assign_investigative_interview(self.name)
            if assignment:
                self.active_interview_assignment = assignment
                self.current_goal = Goal(
                    GoalType.CONDUCT_WITNESS_INTERVIEW,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"assignment_id": assignment.get("id")},
                    priority=3,
                )
                return

        prep_case = world.get_case_to_prepare(self.name) if hasattr(world, "get_case_to_prepare") else None
        if prep_case and (
            self.current_goal.type != GoalType.PREPARE_TRIAL_CASE
            or self.current_goal.parameters.get("case_id") != prep_case.get("case_id")
        ):
            self.current_goal = Goal(
                GoalType.PREPARE_TRIAL_CASE,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"case_id": prep_case.get("case_id")},
            )
            return

        incident = world.claim_next_crime(self.name) if hasattr(world, "claim_next_crime") else None
        if incident:
            self.active_crime_assignment = incident.get("id")
            self.crime_investigation_focus = incident.copy()
            suspect_name = incident.get("suspect", "unknown party")
            self.add_memory(
                f"Responding to theft report involving {suspect_name} at {incident.get('location_label', 'unknown site')}.")
            self.current_goal = Goal(
                GoalType.INVESTIGATE_DISTURBANCE,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={
                    "crime_id": incident.get("id"),
                    "suspect": incident.get("suspect"),
                    "location": incident.get("location"),
                },
            )
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

    def _execute_patrol_area(self, world: 'World'): # For Deputy
        if self.job != "Deputy":
            self.current_goal = self.get_default_goal()
            return

        if self.active_crime_assignment:
            if self.current_goal.type != GoalType.INVESTIGATE_DISTURBANCE:
                self.current_goal = Goal(
                    GoalType.INVESTIGATE_DISTURBANCE,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"crime_id": self.active_crime_assignment},
                )
            return

        if hasattr(world, "assign_investigative_interview"):
            if self.active_interview_assignment and self.current_goal.type != GoalType.CONDUCT_WITNESS_INTERVIEW:
                self.current_goal = Goal(
                    GoalType.CONDUCT_WITNESS_INTERVIEW,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"assignment_id": self.active_interview_assignment.get("id")},
                    priority=4,
                )
                return
            assignment = world.assign_investigative_interview(self.name)
            if assignment:
                self.active_interview_assignment = assignment
                self.current_goal = Goal(
                    GoalType.CONDUCT_WITNESS_INTERVIEW,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"assignment_id": assignment.get("id")},
                    priority=4,
                )
                return

        incident = world.claim_next_crime(self.name) if hasattr(world, "claim_next_crime") else None
        if incident:
            self.active_crime_assignment = incident.get("id")
            self.crime_investigation_focus = incident.copy()
            self.add_memory(
                f"Deputy {self.name} takes over patrol case {incident.get('id')} near {incident.get('location_label', 'the yards')}.")
            self.current_goal = Goal(
                GoalType.INVESTIGATE_DISTURBANCE,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={
                    "crime_id": incident.get("id"),
                    "suspect": incident.get("suspect"),
                    "location": incident.get("location"),
                },
            )
            return

        self.add_memory(f"Deputy {self.name} is patrolling their assigned area.")
        if random.random() < 0.3:
            dx = random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])
            if dx != 0 or dy != 0:
                if self.move(dx, dy, world):
                    self.add_memory(f"Patrolling... moved to ({self.x},{self.y}).")
                else:
                    self.add_memory("Patrolling... tried to move but was blocked.")
            else:
                self.add_memory("Patrolling... surveying current location.")
        else:
            self.add_memory("Patrolling... observing the area.")
        return

    def _execute_conduct_witness_interview(self, world: 'World'):
        if self.job not in {"Sheriff", "Deputy"}:
            self.current_goal = self.get_default_goal()
            return

        goal_params = self.current_goal.parameters if self.current_goal else {}
        assignment_id = goal_params.get("assignment_id")
        assignment = self.active_interview_assignment
        if not assignment or assignment.get("id") != assignment_id:
            assignment = world.get_interview_assignment_by_id(assignment_id) if hasattr(world, "get_interview_assignment_by_id") else None
            if not assignment and hasattr(world, "assign_investigative_interview"):
                assignment = world.assign_investigative_interview(self.name)
            self.active_interview_assignment = assignment

        if not assignment:
            self.current_goal = self.get_default_goal()
            return

        witness_name = assignment.get("witness")
        witness = world.get_character_by_name(witness_name) if hasattr(world, "get_character_by_name") else None
        if witness and (self.x, self.y) != (witness.x, witness.y):
            self.move_towards(witness.x, witness.y, world)
            self.add_memory(f"Heading to interview {witness_name} regarding case {assignment.get('case_id')}.")
            return

        security_skill = self.skills.get("Security", {}).get("level", 0)
        base_quality = 0.35 + 0.08 * security_skill
        if witness:
            relationship = self.get_relationship_score(witness.name)
            base_quality += max(-0.1, min(0.1, relationship / 120))
        base_quality += random.uniform(-0.1, 0.15)
        quality = max(0.1, min(1.0, base_quality))
        notes = f"Witness recounted events with {int(quality * 100)}% confidence."

        if hasattr(world, "record_interview_result"):
            world.record_interview_result(assignment.get("id"), self.name, quality, notes)

        self.add_memory(f"Interviewed {witness_name or 'a bystander'} for case {assignment.get('case_id')}.")
        self._grant_skill_experience("Security", 0.6, world)
        self.active_interview_assignment = None
        self.current_goal = self.get_default_goal()

    def _execute_investigate_disturbance(self, world: 'World'):
        goal_params = self.current_goal.parameters if self.current_goal else {}
        crime_id = goal_params.get("crime_id") or self.active_crime_assignment
        if not crime_id:
            self.active_crime_assignment = None
            self.crime_investigation_focus = None
            self.current_goal = self.get_default_goal()
            return

        incident = world.get_crime_by_id(crime_id) if hasattr(world, "get_crime_by_id") else None
        if not incident or incident.get("status") == "resolved":
            self.active_crime_assignment = None
            self.crime_investigation_focus = None
            self.current_goal = self.get_default_goal()
            return

        suspect_name = incident.get("suspect")
        suspect = world.get_character_by_name(suspect_name) if suspect_name else None
        location_data = incident.get("location") or goal_params.get("location")
        location_coords: Optional[Tuple[int, int]] = None
        if isinstance(location_data, dict):
            coords = location_data.get("coords")
            if coords:
                location_coords = (coords[0], coords[1])
        if suspect:
            location_coords = (suspect.x, suspect.y)

        if location_coords and (self.x, self.y) != location_coords:
            self.move_towards(location_coords[0], location_coords[1], world)
            if suspect:
                self.add_memory(f"Closing in on {suspect_name} regarding case {crime_id}.")
            else:
                self.add_memory(
                    f"Investigating disturbance near {incident.get('location_label', 'the reported site')} for case {crime_id}."
                )
            return

        security_skill = self.skills.get("Security", {}).get("level", 0)
        success_chance = min(0.95, 0.45 + 0.08 * security_skill + (0.05 if suspect else 0.0))
        investigation_success = random.random() < success_chance

        if investigation_success and suspect:
            recovered_amount = 0
            stolen_resource = incident.get("resource")
            if stolen_resource:
                available = suspect.inventory.get(stolen_resource, 0)
                if available > 0:
                    recovered_amount = min(available, incident.get("amount", available))
                    suspect.inventory[stolen_resource] = available - recovered_amount
                    if suspect.inventory[stolen_resource] <= 0:
                        suspect.inventory.pop(stolen_resource, None)
                    target_stockpile = None
                    if isinstance(location_data, dict):
                        target_stockpile = world.get_stockpile_by_name(location_data.get("stockpile"))
                    if target_stockpile and target_stockpile.is_allowed(stolen_resource):
                        added, actual = target_stockpile.add_item(stolen_resource, recovered_amount)
                        if added:
                            recovered_amount = actual
                            if world.game_time:
                                world.ledger.update_stockpile_record(
                                    target_stockpile.name,
                                    target_stockpile.inventory,
                                    world.game_time.current_day,
                                )
                    if recovered_amount > 0 and (not target_stockpile or not target_stockpile.is_allowed(stolen_resource)):
                        self.inventory[stolen_resource] = self.inventory.get(stolen_resource, 0) + recovered_amount

            suspect.update_reputation(-5, f"Apprehended for theft by {self.name}", world)
            suspect.update_mood_score(
                getattr(config, "MOOD_CHANGE_CAUGHT_STEALING", -15), "Apprehended for theft"
            )
            suspect.add_memory(f"Apprehended by {self.name} for theft case {crime_id}.")
            self.add_memory(f"Detained {suspect_name} and resolved case {crime_id}.")
            notes = (
                f"Suspect detained; recovered {recovered_amount} {incident.get('resource', 'goods')}"
                if recovered_amount
                else "Suspect detained"
            )
            evidence_strength = 0.6 + 0.1 * min(4, security_skill)
            if recovered_amount:
                evidence_strength += 0.15
            evidence_strength = min(1.0, evidence_strength)
            if hasattr(world, "resolve_crime_outcome"):
                world.resolve_crime_outcome(
                    crime_id,
                    "apprehended",
                    self.name,
                    caught=True,
                    notes=notes,
                    evidence_strength=evidence_strength,
                )
        elif investigation_success:
            self.add_memory(f"Secured the scene of case {crime_id}; suspect not present.")
            if hasattr(world, "resolve_crime_outcome"):
                world.resolve_crime_outcome(
                    crime_id,
                    "scene_secured",
                    self.name,
                    caught=False,
                    notes="Scene secured",
                    requeue=False,
                    evidence_strength=min(0.6, 0.35 + 0.05 * security_skill),
                )
        else:
            self.add_memory(f"Lost the trail for case {crime_id}; will revisit once new leads appear.")
            if hasattr(world, "resolve_crime_outcome"):
                world.resolve_crime_outcome(
                    crime_id,
                    "lost_trail",
                    self.name,
                    caught=False,
                    notes="Lead went cold",
                    requeue=True,
                    evidence_strength=0.1,
                )

        self.active_crime_assignment = None
        self.crime_investigation_focus = None
        self.current_goal = self.get_default_goal()

    def _execute_prepare_trial_case(self, world: 'World'):
        goal_params = self.current_goal.parameters if self.current_goal else {}
        case_id = goal_params.get("case_id")
        if not case_id or not hasattr(world, "get_case_by_id"):
            self.current_goal = self.get_default_goal()
            return

        case = world.get_case_by_id(case_id)
        if not case:
            self.current_goal = self.get_default_goal()
            return

        if case.get("status") in {"concluded", "cancelled"}:
            self.add_memory(f"Case {case_id} is already resolved.")
            self.current_goal = self.get_default_goal()
            return

        if case.get("status") == "in_session":
            self.current_goal = Goal(
                GoalType.ATTEND_TRIAL,
                assignee_id=self.name,
                originator_id="CourtSummons",
                parameters={
                    "case_id": case_id,
                    "location": getattr(world, "courthouse_location", world.market_location),
                },
            )
            return

        security_skill = self.skills.get("Security", {}).get("level", 0)
        prep_effort = 0.15 + 0.05 * security_skill
        updated_case = None
        if hasattr(world, "progress_case_preparation"):
            updated_case = world.progress_case_preparation(case_id, prep_effort, contributor=self.name)
        else:
            updated_case = case

        if random.random() < 0.4:
            self.add_memory(f"Reviewing testimony and evidence for case {case_id}.")

        self._grant_skill_experience("Security", 0.4, world)

        if updated_case and updated_case.get("preparedness", 0.0) >= 0.95:
            self.add_memory(f"Prepared case {case_id} for trial.")
            self.current_goal = self.get_default_goal()

    def _execute_attend_trial(self, world: 'World'):
        goal_params = self.current_goal.parameters if self.current_goal else {}
        case_id = goal_params.get("case_id")
        location = goal_params.get("location") or getattr(world, "courthouse_location", world.market_location)

        if location:
            target_x, target_y = location
            if (self.x, self.y) != (target_x, target_y):
                self.move_towards(target_x, target_y, world)
                return

        case = world.get_case_by_id(case_id) if case_id and hasattr(world, "get_case_by_id") else None
        if not case:
            self.add_memory("Attending civic hearing but no case was found.")
            self.current_goal = self.get_default_goal()
            return

        status = case.get("status")
        if status == "concluded":
            verdict = case.get("verdict", "resolved")
            self.add_memory(f"Witnessed conclusion of case {case_id}: verdict {verdict}.")
            self.current_goal = self.get_default_goal()
            return

        if random.random() < 0.35:
            self.add_memory(f"Listening to proceedings for case {case_id}.")

        if status != "in_session":
            self.current_goal = self.get_default_goal()

    def _execute_seek_medical_attention(self, world: 'World'):
        self.add_memory("Feeling unwell, seeking medical attention.")

        if hasattr(world, "register_medical_case"):
            if self.is_injured and self.injury_severity > 0:
                world.register_medical_case(
                    self.name,
                    "injury",
                    self.injury_severity,
                    reporter=self.name,
                    cause="Requested urgent help",
                    location=(self.x, self.y),
                )
            if self.is_sick and self.sickness_severity > 0:
                world.register_medical_case(
                    self.name,
                    "sickness",
                    self.sickness_severity,
                    reporter=self.name,
                    cause="Requested urgent help",
                    location=(self.x, self.y),
                )

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
        if self.job != "Reeve":
            self.current_goal = self.get_default_goal()
            return

        if not world.game_time:
            self.add_memory("I need the calendar to judge estate duties properly.")
            self.current_goal = self.get_default_goal()
            return

        today = world.game_time.current_day
        if self.last_estate_review_day == today:
            self.add_memory("Estate review already completed today; returning to other duties.")
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
            return

        focus_resources = self.current_goal.parameters.get("focus_resources", ["Food", "Wood", "Stone", "Herbs"])
        low_threshold = getattr(config, "MAYOR_RESOURCE_LOW_THRESHOLD", 20)
        high_threshold = getattr(config, "MAYOR_RESOURCE_HIGH_THRESHOLD", 150)

        summary_chunks: List[str] = []
        directives_issued: List[str] = []
        surplus_tasks: List[Dict[str, Any]] = []

        for resource in focus_resources:
            total_qty = world.get_total_resource_quantity(resource)
            summary_chunks.append(f"{resource}:{total_qty}")
            if total_qty < low_threshold:
                existing = world.resource_collection_directives.get(resource)
                if not existing or existing.get("expires_day", -1) <= today:
                    directive = world.set_resource_collection_directive(
                        resource,
                        max(3, low_threshold - total_qty),
                        duration_days=3,
                        reason=f"Estate shortage flagged by {self.name}",
                        originator=self.name,
                    )
                    directives_issued.append(f"Gather {directive['per_trip_quota']} {resource}")
                else:
                    directives_issued.append(f"Existing directive for {resource} remains in force")
            elif total_qty > high_threshold:
                severity = total_qty - high_threshold
                quantity_to_collect = max(1, min(10, severity // 2))
                surplus_tasks.append(
                    {
                        "resource": resource,
                        "quantity": quantity_to_collect,
                        "reason": f"Collect tithe from {resource} surplus",
                    }
                )

        bailiff_names = [name for name in self.subordinates_names if name]
        bailiffs = [world.get_character_by_name(name) for name in bailiff_names]
        bailiffs = [b for b in bailiffs if b and b.job == "Bailiff"]

        delegated = 0
        if surplus_tasks and bailiffs:
            for task in surplus_tasks:
                if not bailiffs:
                    break
                bailiff = bailiffs.pop(0)
                bailiff_goal = Goal(
                    GoalType.ASSIST_REEVE,
                    assignee_id=bailiff.name,
                    originator_id=self.name,
                    priority=3,
                    parameters={"estate_task": task.copy()},
                )
                bailiff.current_goal = bailiff_goal
                bailiff.add_memory(
                    f"{self.name} ordered me to collect {task['quantity']} {task['resource']} for estate tithe."
                )
                delegated += 1

        summary_text = ", ".join(summary_chunks) if summary_chunks else "no tracked resources"
        directive_text = "; ".join(directives_issued) if directives_issued else "no directives needed"
        world.add_event_log_message(
            f"{self.name} reviews the estate (resources: {summary_text}; directives: {directive_text};"
            f" bailiff tasks: {delegated})."
        )
        self.add_memory(
            f"Estate managed. Resources checked ({summary_text}). Directives noted: {directive_text}."
        )
        self.last_estate_review_day = today
        self.active_estate_orders = surplus_tasks
        self.current_goal.set_completed()
        self.current_goal = self.get_default_goal()

    def _execute_assist_reeve(self, world: 'World'):
        if self.job != "Bailiff":
            self.current_goal = self.get_default_goal()
            return

        estate_task = self.current_goal.parameters.get("estate_task")
        if not estate_task:
            self.add_memory("No estate task provided; returning to patrol duties.")
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
            return

        resource_name = estate_task.get("resource")
        quantity_target = max(1, int(estate_task.get("quantity", 1)))
        carried = self.inventory.get(resource_name, 0)

        if carried >= quantity_target:
            supervisor = world.get_character_by_name(self.supervisor_name) if self.supervisor_name else None
            if supervisor:
                if abs(self.x - supervisor.x) + abs(self.y - supervisor.y) > 1:
                    self.move_towards(supervisor.x, supervisor.y, world)
                    return
                self.inventory[resource_name] -= quantity_target
                if self.inventory[resource_name] <= 0:
                    del self.inventory[resource_name]
                unit_price = world.get_market_price(resource_name)
                revenue = unit_price * quantity_target
                world.treasury_coins += revenue
                supervisor.add_memory(
                    f"{self.name} delivered {quantity_target} {resource_name} for the estate tithe."
                )
                self.add_memory(
                    f"Delivered {quantity_target} {resource_name} to {supervisor.name}; treasury received {revenue} coins."
                )
                world.add_event_log_message(
                    f"{self.name} turns over {quantity_target} {resource_name} to {supervisor.name} for {revenue} coins of tithe."
                )
            else:
                stockpiles = world.get_stockpiles_for_resource(resource_name)
                if stockpiles:
                    deposit_target = min(
                        stockpiles,
                        key=lambda sp: min(abs(pt[0] - self.x) + abs(pt[1] - self.y) for pt in sp.access_points),
                    )
                    access_point = min(
                        deposit_target.access_points,
                        key=lambda loc: abs(loc[0] - self.x) + abs(loc[1] - self.y),
                    )
                    if (self.x, self.y) != access_point:
                        self.move_towards(access_point[0], access_point[1], world)
                        return
                    success, added = deposit_target.add_item(resource_name, carried)
                    if success and added:
                        self.inventory.pop(resource_name, None)
                        world.add_event_log_message(
                            f"{self.name} stores {added} {resource_name} in {deposit_target.name} awaiting tithe pickup."
                        )
                        if world.game_time:
                            world.ledger.update_stockpile_record(
                                deposit_target.name, deposit_target.inventory, world.game_time.current_day
                            )
                else:
                    self.add_memory("No stockpile available to hold the collected tithe.")

            self.current_goal.parameters["estate_task_completed"] = True
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
            return

        exhausted = self.current_goal.parameters.setdefault("exhausted_stockpiles", [])
        stockpiles = [sp for sp in world.get_stockpiles_for_resource(resource_name) if sp.name not in exhausted]
        if not stockpiles:
            self.add_memory(f"All stockpiles are empty of {resource_name}; reporting back to the reeve.")
            self.current_goal.set_failed(reason="No stockpile could fulfil the tithe request.")
            self.current_goal = self.get_default_goal()
            return

        target_stockpile = min(
            stockpiles,
            key=lambda sp: min(abs(pt[0] - self.x) + abs(pt[1] - self.y) for pt in sp.access_points),
        )
        access_point = min(
            target_stockpile.access_points,
            key=lambda loc: abs(loc[0] - self.x) + abs(loc[1] - self.y),
        )

        if (self.x, self.y) != access_point:
            self.move_towards(access_point[0], access_point[1], world)
            return

        needed = quantity_target - carried
        success, removed = target_stockpile.remove_item(resource_name, needed)
        if not success or removed <= 0:
            exhausted.append(target_stockpile.name)
            self.add_memory(
                f"{target_stockpile.name} had no spare {resource_name}; trying a different store."
            )
            return

        self.inventory[resource_name] = self.inventory.get(resource_name, 0) + removed
        if world.game_time:
            world.ledger.update_stockpile_record(
                target_stockpile.name, target_stockpile.inventory, world.game_time.current_day
            )
        world.add_event_log_message(
            f"{self.name} withdraws {removed} {resource_name} from {target_stockpile.name} for estate tithe."
        )
        self.add_memory(f"Collected {removed} {resource_name} from {target_stockpile.name} for the reeve.")

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
            today = world.game_time.current_day if world.game_time else None
            if today is not None and self.last_high_court_day == today:
                self.add_memory("The high court already convened today; dismissing the gathering.")
                self.current_goal.set_completed()
                self.current_goal = self.get_default_goal()
                return

            self.add_memory("All my vassals are present. The high court is now in session.")
            pressures = world.identify_resource_pressures()
            shortage_reports = [p for p in pressures if p["status"] == "shortage"]
            surplus_reports = [p for p in pressures if p["status"] == "surplus"]
            crime_count = len(world.pending_crimes)

            discussion_points = []
            if shortage_reports:
                focus = shortage_reports[0]
                discussion_points.append(
                    f"shortage of {focus['resource']} (only {focus['quantity']})"
                )
                world.set_resource_collection_directive(
                    focus["resource"],
                    max(3, focus["threshold"] - focus["quantity"]),
                    duration_days=3,
                    reason=f"High court decree by {self.name}",
                    originator=self.name,
                )
            if surplus_reports:
                focus = surplus_reports[0]
                discussion_points.append(
                    f"surplus {focus['resource']} (stocked at {focus['quantity']})"
                )
            if crime_count:
                discussion_points.append(f"{crime_count} unresolved crimes")

            summary = "; ".join(discussion_points) if discussion_points else "routine matters"
            world.add_event_log_message(
                f"{self.name} holds high court ({summary})."
            )
            world.add_notable_event(
                "HighCourt",
                {
                    "summary": f"{self.name}'s court addressed {summary}.",
                    "liege": self.name,
                    "vassal_count": len(self.vassals),
                },
            )

            for vassal_name in self.vassals:
                vassal = world.get_character_by_name(vassal_name)
                if not vassal:
                    continue
                relation_bonus = 2
                mood_bonus = 3
                if shortage_reports:
                    relation_bonus -= 1
                    vassal.update_mood_score(-2, "Court revealed shortages to address")
                if surplus_reports:
                    mood_bonus += 2
                self.modify_relationship(vassal_name, relation_bonus, world, reason="They attended my high court.")
                vassal.modify_relationship(self.name, relation_bonus - 1, world, reason="Attended their liege's court.")
                vassal.update_mood_score(mood_bonus, f"Participated in high court with {self.name}")

            if today is not None:
                self.last_high_court_day = today

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
        economic_report = getattr(world, "last_daily_economic_report", {}) or {}
        taxes = economic_report.get("tax_collected", 0)
        wages_paid = economic_report.get("wages_paid", 0)
        pressures = world.identify_resource_pressures()
        shortage = next((p for p in pressures if p["status"] == "shortage"), None)
        surplus = next((p for p in pressures if p["status"] == "surplus"), None)

        speech_segments = [
            f"Citizens, {speech_topic}.",
            f"Our treasury stands at {world.treasury_coins} coins",
        ]

        if taxes:
            speech_segments.append(f"tax collection brought in {taxes} coins yesterday")
        if wages_paid:
            speech_segments.append(f"and we met {wages_paid} coins of wages")
        if shortage:
            speech_segments.append(
                f"we must rally gatherers to raise {shortage['resource']} above {shortage['threshold']} units"
            )
        elif surplus:
            speech_segments.append(
                f"our surplus of {surplus['resource']} now reaches {surplus['quantity']} units—let's invest it wisely"
            )
        speech_segments.append(f"The weather is {world.weather.lower()}, yet our resolve stays bright.")
        speech_segments.append("Together we will keep the settlement thriving.")

        generated_speech_snippet = " ".join(speech_segments)

        self.add_memory(f"Gave a speech: \"{generated_speech_snippet}\"")
        world.add_event_log_message(f"Mayor {self.name} addresses the populace: \"{generated_speech_snippet}\"")

        self.current_goal = self.get_default_goal() # Return to overseeing or default state
        return

    def _execute_campaign_speech(self, world: 'World'):
        if not world.game_time:
            self.current_goal = self.get_default_goal()
            return

        rally_point = getattr(world, "market_location", (self.x, self.y))
        if abs(self.x - rally_point[0]) + abs(self.y - rally_point[1]) > 2:
            self.add_memory("Heading to the square to address voters.")
            self.move_towards(rally_point[0], rally_point[1], world)
            return

        parameters = self.current_goal.parameters or {}
        focus_summary = parameters.get("focus_summary") or "our settlement's future"
        pledges = world.campaign_promises.get(self.name, [])
        active_pledges = [p for p in pledges if p.get("status") == "pledged"]

        env_snapshot = {}
        if hasattr(world, "get_environment_snapshot") and callable(world.get_environment_snapshot):
            env_snapshot = world.get_environment_snapshot() or {}
        travel_speed = env_snapshot.get("travel_speed") or world.get_travel_speed_modifier()
        resource_notes = []
        for resource_name, entries in (env_snapshot.get("resource_multipliers") or {}).items():
            combined = 1.0
            for entry in entries:
                combined *= entry.get("multiplier", 1.0)
            if abs(combined - 1.0) > 0.01:
                resource_notes.append(f"{resource_name} x{combined:.2f}")

        speech_lines = [
            f"Citizens, I stand before you to talk about {focus_summary}.",
            f"Travel runs at {travel_speed:.2f}× pace—an edge we should seize.",
        ]
        if resource_notes:
            snippet = ", ".join(resource_notes[: config.ENVIRONMENT_TRAVEL_SNIPPET_LIMIT])
            speech_lines.append(f"Key yields today: {snippet}.")
        if active_pledges:
            leading = active_pledges[0]
            summary = leading.get("summary", "our goals")
            deadline = leading.get("deadline_day")
            if deadline:
                speech_lines.append(f"I will deliver on {summary} by day {deadline}.")
            else:
                speech_lines.append(f"I remain committed to {summary}.")
        elif pledges:
            speech_lines.append("Every promise kept strengthens our community.")
        else:
            speech_lines.append("Support me so we can keep prosperity flowing.")

        speech_excerpt = " ".join(speech_lines)
        self.add_memory(f"Campaign speech delivered: {speech_excerpt}")

        listeners = [
            char for char in world.get_nearby_characters(self, radius=4)
            if char.name != self.name
        ]
        for listener in listeners:
            relation_bonus = 2 + (1 if active_pledges else 0)
            listener.modify_relationship(self.name, relation_bonus, world, reason="Attended campaign speech")
            self.modify_relationship(listener.name, 1, world, reason="They attended my rally")
            listener.update_mood_score(2, f"Motivated by {self.name}'s campaign rally")

        if pledges:
            self.update_reputation(2, "Campaign speech reinforced pledges", world)
        else:
            self.update_reputation(1, "Campaign speech rallied citizens", world)

        audience_size = len(listeners)
        world.add_event_log_message(
            f"{self.name} campaigns about {focus_summary} for {audience_size} citizen{'s' if audience_size != 1 else ''}."
        )
        world.add_notable_event(
            "CampaignSpeech",
            {
                "summary": f"{self.name} rallied {audience_size} citizens about {focus_summary}.",
                "candidate": self.name,
                "audience": audience_size,
            },
        )

        self.last_campaign_speech_day = world.game_time.current_day
        self.current_goal.set_completed()
        self.current_goal = self.get_default_goal()

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

        phase_info = world.get_current_phase() if hasattr(world, "get_current_phase") else world.game_time.get_phase()
        self._apply_phase_behavior(world, phase_info)
        active_weather_event = world.get_active_weather_event() if hasattr(world, "get_active_weather_event") else None
        decision_profile = self._build_decision_profile(world)
        self._decision_profile = decision_profile
        if active_weather_event and self._should_seek_weather_shelter(active_weather_event):
            self._seek_weather_shelter(world, active_weather_event)

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

        if self.resting_at_home and self.current_goal.type not in [GoalType.REST_AT_HOME, GoalType.FIND_SHELTER]:
            if hasattr(world, "release_residential_spot"):
                world.release_residential_spot(self)
            self.resting_at_home = False
            self._rest_ticks = 0

        energy_level = self.needs.get("Energy", 100)
        rest_threshold = getattr(config, "ENERGY_THRESHOLD_REST", 40) + getattr(self, "_phase_rest_threshold_bonus", 0)
        rest_threshold += int(round(decision_profile.get("rest_threshold_adjustment", 0.0)))
        rest_threshold = max(0, min(config.NEED_SCORE_MAX, rest_threshold))
        if energy_level < rest_threshold and self.current_goal.type not in [GoalType.REST_AT_HOME, GoalType.FIND_SHELTER, GoalType.SEEK_MEDICAL_ATTENTION]:
            home_building = self._ensure_home_assignment(world)
            if home_building:
                self.add_memory(f"Exhausted—heading to {home_building.display_name} to rest.")
                self.current_goal = Goal(
                    GoalType.REST_AT_HOME,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"building_location": home_building.location},
                    priority=2,
                )
            else:
                self.add_memory("I am exhausted but have no bed. I need to find shelter.")
                self.current_goal = Goal(GoalType.FIND_SHELTER, assignee_id=self.name, originator_id=self.name, priority=3)

        thirst_level = self.needs.get("Thirst", 100)
        if thirst_level < getattr(config, "THIRST_THRESHOLD_DRINK", 55) and self.current_goal.type not in [GoalType.DRINK_WATER, GoalType.GATHER_WATER, GoalType.SEEK_TO_BUY_ITEM]:
            if self.inventory.get("Water", 0) > 0:
                self.add_memory("Feeling parched—I have water on hand to drink.")
                self.current_goal = Goal(GoalType.DRINK_WATER, assignee_id=self.name, originator_id=self.name, priority=2)
            elif world.get_total_resource_quantity("Water") > 0:
                self.add_memory("Thirsty—I'll check communal stores for water.")
                self.current_goal = Goal(GoalType.DRINK_WATER, assignee_id=self.name, originator_id=self.name, priority=2)
            else:
                self.add_memory("No water anywhere. I'll gather some fresh supplies.")
                self.current_goal = Goal(GoalType.GATHER_WATER, assignee_id=self.name, originator_id=self.name, priority=2)

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
                self.current_goal = Goal(
                    GoalType.WANDER,
                    assignee_id=self.name,
                    originator_id=self.name,
                    parameters={"reason": "Seeking solitude due to mood."},
                )  # Wander is a simple proxy for solitude

        if self.current_goal.type in [GoalType.IDLE, GoalType.WANDER] and energy_level < config.NEED_SCORE_MAX:
            passive_gain = getattr(config, "ENERGY_PASSIVE_RECOVERY_WHILE_IDLE", 0)
            if passive_gain > 0:
                self.needs["Energy"] = min(config.NEED_SCORE_MAX, energy_level + passive_gain)

        # --- Complex Need-Driven Goal/Action Biases ---
        # These are checked if not already in a critical goal state like SEEK_MEDICAL_ATTENTION or ASK_FOR_HELP

        # Safety Need Bias
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD and \
           self.current_goal.type not in [GoalType.SEEK_MEDICAL_ATTENTION, GoalType.ASK_FOR_HELP, GoalType.WANDER]: # Avoid overriding if already wandering for mood
            # If safety is critical, character might prioritize less risky actions or seek "safer" spots (proxied by Wander)
            wander_base = getattr(config, "SAFETY_CRITICAL_WANDER_BASE_CHANCE", 0.3)
            risk_modifier = max(0.35, decision_profile.get("risk_modifier", 1.0))
            wander_chance = wander_base / risk_modifier
            wander_chance = max(0.05, min(0.9, wander_chance))
            if random.random() < wander_chance:
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
                ask_multiplier = max(0.2, decision_profile.get("ask_for_help_multiplier", 1.0))
                ask_chance = config.ASK_FOR_HELP_CHANCE * ask_multiplier
                ask_chance = max(0.01, min(0.95, ask_chance))
                if random.random() < ask_chance:
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
        if self._process_builder_routine(world):
            return

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
            if not self._process_builder_routine(world):
                self._execute_wander(world)
            return
        elif self.current_goal.type == GoalType.PERFORM_WOODCUTTER_DUTIES: self._execute_perform_woodcutter_duties(world)
        elif self.current_goal.type == GoalType.PERFORM_STONEMASON_DUTIES: self._execute_perform_stonemason_duties(world)
        elif self.current_goal.type == GoalType.PERFORM_FARMER_DUTIES: self._execute_perform_farmer_duties(world)
        elif self.current_goal.type == GoalType.PERFORM_HUNTER_DUTIES: self._execute_perform_hunter_duties(world)
        elif self.current_goal.type == GoalType.PERFORM_FLETCHER_DUTIES: self._execute_perform_fletcher_duties(world)
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
            elif resource_name == "Water": self._execute_gather_water(world)
            else: self.current_goal = self.get_default_goal() # Unknown resource
        elif self.current_goal.type == GoalType.INITIATE_HAULING: self._execute_initiate_hauling(world)
        elif self.current_goal.type == GoalType.HAUL_RESOURCE_TO_STOCKPILE: self._execute_haul_resource(world)
        elif self.current_goal.type == GoalType.COUNT_STOCKPILE: self._execute_count_stockpile(world)

        # Management/Oversight Goals
        elif self.current_goal.type == GoalType.ASSESS_PRODUCTION_NEEDS: self._execute_assess_production_needs(world)
        elif self.current_goal.type == GoalType.MANAGE_SUBORDINATES: self._execute_manage_subordinates(world)
        elif self.current_goal.type == GoalType.MAINTAIN_LEDGER: self._execute_maintain_ledger(world)
        elif self.current_goal.type == GoalType.OVERSEE_SETTLEMENT: self._execute_oversee_settlement(world)
        elif self.current_goal.type == GoalType.REVIEW_LAW_PETITIONS: self._execute_review_law_petitions(world)
        elif self.current_goal.type == GoalType.DRAFT_SETTLEMENT_LAW: self._execute_draft_settlement_law(world)
        elif self.current_goal.type == GoalType.ENACT_SETTLEMENT_LAW: self._execute_enact_settlement_law(world)
        elif self.current_goal.type == GoalType.OVERSEE_MEDICAL_OPERATIONS: self._execute_oversee_medical_operations(world)
        elif self.current_goal.type == GoalType.PROVIDE_MEDICAL_CARE: self._execute_provide_medical_care(world)
        elif self.current_goal.type == GoalType.MAINTAIN_PEACE_IN_SETTLEMENT: self._execute_maintain_peace(world)
        elif self.current_goal.type == GoalType.PATROL_AREA: self._execute_patrol_area(world)
        elif self.current_goal.type == GoalType.INVESTIGATE_DISTURBANCE: self._execute_investigate_disturbance(world)
        elif self.current_goal.type == GoalType.PREPARE_TRIAL_CASE: self._execute_prepare_trial_case(world)
        elif self.current_goal.type == GoalType.CONDUCT_WITNESS_INTERVIEW: self._execute_conduct_witness_interview(world)
        elif self.current_goal.type == GoalType.ATTEND_TRIAL: self._execute_attend_trial(world)
        elif self.current_goal.type == GoalType.GIVE_SPEECH: self._execute_give_speech(world)
        elif self.current_goal.type == GoalType.CAMPAIGN_SPEECH: self._execute_campaign_speech(world)
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
        elif self.current_goal.type == GoalType.DRINK_WATER: self._execute_drink_water(world)
        elif self.current_goal.type == GoalType.FIND_SHELTER: self._execute_find_shelter(world)
        elif self.current_goal.type == GoalType.REST_AT_HOME: self._execute_rest_at_home(world)
        elif self.current_goal.type == GoalType.GATHER_WATER: self._execute_gather_water(world)
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
            current_social_interaction_chance += getattr(self, "_phase_social_bias", 0.0)
            if active_weather_event and active_weather_event.get("requires_shelter"):
                current_social_interaction_chance -= 0.15
            current_social_interaction_chance *= decision_profile.get("social_focus", 1.0)
            work_focus = decision_profile.get("work_focus", 1.0)
            if work_focus > 1.0:
                social_drain = (work_focus - 1.0) * getattr(config, "DECISION_SOCIAL_FROM_WORK_DRAIN", 0.0)
                current_social_interaction_chance *= max(0.1, 1.0 - social_drain)
            elif work_focus < 1.0:
                social_boost = min(0.4, (1.0 - work_focus) * getattr(config, "DECISION_SOCIAL_FROM_WORK_DRAIN", 0.0))
                current_social_interaction_chance *= 1.0 + social_boost
            current_social_interaction_chance = max(0.0, min(1.0, current_social_interaction_chance))
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

                                positive_threshold = getattr(config, "DECISION_RELATIONSHIP_POSITIVE_THRESHOLD", 60)
                                negative_threshold = getattr(config, "DECISION_RELATIONSHIP_NEGATIVE_THRESHOLD", -25)
                                social_focus = decision_profile.get("social_focus", 1.0)
                                if relationship_score >= positive_threshold:
                                    weight *= max(0.2, 1.0 + (social_focus - 1.0) * getattr(config, "DECISION_SOCIAL_POSITIVE_WEIGHT", 0.6))
                                elif relationship_score <= negative_threshold:
                                    weight *= max(0.05, 1.0 - (social_focus - 1.0) * getattr(config, "DECISION_SOCIAL_NEGATIVE_WEIGHT", 0.6))

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
            if "Kind" in self.traits:
                comfort_chance_modifier += 0.3
            if "Compassionate" in self.traits:
                comfort_chance_modifier += 0.4

            absolute_tick = None
            if world.game_time:
                absolute_tick = (
                    world.game_time.current_day * world.game_time.ticks_per_day
                    + world.game_time.current_tick
                )

            if random.random() < (config.REACTIVE_SOCIAL_BASE_CHANCE + comfort_chance_modifier):
                distressed_candidates: List[Tuple[float, Character]] = []
                for candidate in world.get_nearby_characters(self, radius=4):
                    if candidate.name == self.name or candidate.name not in self.known_characters:
                        continue
                    distress_score = 0.0
                    if candidate.mood in ["Sad", "Stressed", "Furious"]:
                        distress_score += 15
                    if candidate.is_sick:
                        distress_score += 10 + candidate.sickness_severity * 2
                    if candidate.is_injured:
                        distress_score += 8 + candidate.injury_severity * 2
                    belonging = candidate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT)
                    esteem = candidate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT)
                    distress_score += max(0, config.NEED_BELONGING_CRITICAL_THRESHOLD - belonging)
                    distress_score += 0.5 * max(0, config.NEED_ESTEEM_CRITICAL_THRESHOLD - esteem)
                    if candidate.needs.get('Hunger', 100) < config.CRITICAL_NEED_THRESHOLD_FOR_HELP:
                        distress_score += 5
                    if candidate.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
                        distress_score += 7

                    if distress_score < config.SOCIAL_DISTRESS_THRESHOLD:
                        continue

                    if absolute_tick is not None:
                        last_tick = self._comfort_cooldowns.get(candidate.name)
                        if last_tick is not None and absolute_tick - last_tick < config.ARGUMENT_RECENT_HISTORY_TICKS:
                            continue

                    distressed_candidates.append((distress_score, candidate))

                if distressed_candidates:
                    distressed_candidates.sort(key=lambda item: item[0], reverse=True)
                    _, target_for_comfort = distressed_candidates[0]
                    self.current_goal = Goal(
                        GoalType.OFFER_COMFORT,
                        assignee_id=self.name,
                        originator_id=self.name,
                        parameters={"target_char_name": target_for_comfort.name},
                    )
                    self.add_memory(
                        f"Noticed {target_for_comfort.name} struggling (distress {distressed_candidates[0][0]:.1f}). Offering comfort."
                    )
                    if absolute_tick is not None:
                        self._comfort_cooldowns[target_for_comfort.name] = absolute_tick

            # --- Potential for Argument Check ---
            if self.current_goal.type not in non_interruptible_social_goals:
                argument_candidates: List[Tuple[float, Character]] = []
                for other_char in world.get_nearby_characters(self, radius=3):
                    if other_char.name == self.name or other_char.name not in self.known_characters:
                        continue
                    relationship_score = self.get_relationship_score(other_char.name)
                    if relationship_score > config.ARGUMENT_RELATIONSHIP_THRESHOLD:
                        continue

                    tension_score = abs(relationship_score)
                    if self.mood in ["Furious", "Stressed"]:
                        tension_score += 10
                    if other_char.mood in ["Furious", "Stressed"]:
                        tension_score += 8
                    if "Hot-headed" in self.traits:
                        tension_score += 5
                    if "Hot-headed" in other_char.traits:
                        tension_score += 5

                    if absolute_tick is not None:
                        last_tick = self._argument_cooldowns.get(other_char.name)
                        if last_tick is not None and absolute_tick - last_tick < config.ARGUMENT_RECENT_HISTORY_TICKS:
                            continue

                    argument_candidates.append((tension_score, other_char))

                if argument_candidates:
                    argument_candidates.sort(key=lambda item: item[0], reverse=True)
                    top_score, target_char = argument_candidates[0]
                    if top_score > abs(config.ARGUMENT_RELATIONSHIP_THRESHOLD):
                        self.current_goal = Goal(
                            GoalType.ARGUE,
                            assignee_id=self.name,
                            originator_id=self.name,
                            parameters={"target_char_name": target_char.name},
                        )
                        self.add_memory(
                            f"Frustrations with {target_char.name} boiled over (tension {top_score:.1f}). Confronting them."
                        )
                        if absolute_tick is not None:
                            self._argument_cooldowns[target_char.name] = absolute_tick

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
        self._record_management_activity(world, f"review:{subordinate.name}")

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
        self._record_management_activity(world, f"warning:{subordinate.name}")


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
        self._record_management_activity(world, f"fired:{subordinate.name}")

        # Optional: Remove from world or mark inactive. For now, they become "Unemployed".
        # If you want to remove them from the simulation entirely:
        # world.characters.pop(sub_idx)
        # print(f"{subordinate.name} has been removed from the world.")
        # However, this could cause issues if other parts of the code expect the character to exist.
        # Keeping them as "Unemployed" is safer for now.

    def receive_oversight_update(
        self,
        supervisor: Optional['Character'],
        oversight_score: float,
        world: Optional['World'],
        summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        oversight_score = max(0.0, min(1.0, oversight_score))
        previous_score = self.supervisor_oversight
        self.supervisor_oversight = oversight_score
        if world and world.game_time:
            self.last_supervisor_oversight_day = world.game_time.current_day

        threshold = getattr(config, "LEADERSHIP_NEGLECT_THRESHOLD", 0.45)
        corruption_threshold = getattr(config, "LEADERSHIP_CORRUPTION_THRESHOLD", 0.25)

        if threshold > 0:
            self._neglect_slack_pressure = max(0.0, threshold - oversight_score) / threshold
        else:
            self._neglect_slack_pressure = 0.0

        if corruption_threshold > 0:
            self._neglect_illegal_pressure = max(0.0, corruption_threshold - oversight_score) / corruption_threshold
        else:
            self._neglect_illegal_pressure = 0.0

        if supervisor and self.supervisor_name == supervisor.name:
            if oversight_score >= threshold and previous_score < threshold:
                self.add_memory(f"{supervisor.name} checked in closely today—best stay sharp.")
            elif oversight_score < threshold and previous_score >= threshold:
                self.add_memory(f"Barely saw {supervisor.name} today; the crew had free rein.")

        if self._decision_profile is not None:
            adjusted_risk = 1.0 + (self._neglect_illegal_pressure * 0.25) - (oversight_score * 0.1)
            self._decision_profile["risk_modifier"] = max(0.5, min(1.5, adjusted_risk))

    def consider_misconduct_due_to_neglect(
        self,
        world: 'World',
        supervisor: Optional['Character'],
        oversight_score: float,
    ) -> Optional[Dict[str, Any]]:
        if not world or not world.game_time:
            return None

        corruption_threshold = getattr(config, "LEADERSHIP_CORRUPTION_THRESHOLD", 0.25)
        if corruption_threshold <= 0 or oversight_score >= corruption_threshold:
            return None

        pressure = max(
            self._neglect_illegal_pressure,
            (corruption_threshold - oversight_score) / corruption_threshold,
        )
        base_chance = getattr(config, "LEADERSHIP_ILLEGAL_BASE_CHANCE", 0.05)
        chance = base_chance * pressure
        chance += base_chance * getattr(
            config, "LEADERSHIP_ILLEGAL_PERSONALITY_MODIFIERS", {}
        ).get(self.personality, 0.0)
        trait_modifiers = getattr(config, "LEADERSHIP_ILLEGAL_TRAIT_MODIFIERS", {})
        for trait in self.traits:
            chance += base_chance * trait_modifiers.get(trait, 0.0)

        chance = max(0.0, min(1.0, chance))
        if chance <= 0 or random.random() >= chance:
            return None

        skim_amount = max(1, int(round(1 + pressure * getattr(config, "LEADERSHIP_ILLEGAL_MAX_SKIM", 6))))
        self.money += skim_amount

        day = world.game_time.current_day
        supervisor_name = supervisor.name if supervisor else None
        summary_text = f"{self.name} skimmed {skim_amount}c under lax oversight."
        incident_id = world._next_crime_id()
        incident = {
            "id": incident_id,
            "type": "corruption",
            "reported_day": day,
            "suspect": self.name,
            "supervisor": supervisor_name,
            "amount": skim_amount,
            "status": "pending",
            "caught": False,
            "summary": summary_text,
            "description": summary_text,
            "oversight": round(oversight_score, 3),
        }

        world.pending_crimes.append(incident)
        world.active_crimes[incident_id] = incident
        world._record_crime_history(incident)
        world.add_event_log_message(summary_text)

        self.add_memory(f"Pocketed {skim_amount}c while no one was watching our crew.")
        self.update_reputation(-5, "Skimmed funds under lax oversight", world)
        self.update_mood_score(
            getattr(config, "MOOD_CHANGE_MISCONDUCT_THRILL", 3),
            "Skimmed extra coins under lax oversight",
        )

        if supervisor and self.supervisor_name == supervisor.name:
            supervisor.add_memory(f"Rumors say {self.name} skimmed funds while I was absent.")
            supervisor.modify_relationship(
                self.name,
                -8,
                world,
                reason="Rumored misconduct under my watch",
            )

        return incident

    def get_relationship_score(self, target_char_name: str) -> int:
        """Returns the relationship score towards the target character, default 0."""
        return self.relationships.get(target_char_name, 0)

    def modify_relationship(self, target_char_name: str, value_change: int, world: 'World', reason: Optional[str] = None):
        """Modifies the relationship score with the target character."""
        if self.name == target_char_name: return # Cannot have a relationship with oneself

        previous_tier = self.get_relationship_tier(target_char_name)
        current_score = self.relationships.get(target_char_name, 0)
        new_score = current_score + value_change

        # Clamp score between -100 and 100
        new_score = max(-100, min(100, new_score))

        self.relationships[target_char_name] = new_score

        if reason:
            self.add_memory(f"My relationship with {target_char_name} changed by {value_change} to {new_score}. Reason: {reason}")
            # print(f"DEBUG: {self.name}'s relationship with {target_char_name} changed by {value_change} to {new_score}. Reason: {reason}")

        new_tier = self.get_relationship_tier(target_char_name)
        if new_tier != previous_tier:
            tier_direction = "deepened" if new_score >= current_score else "soured"
            tier_summary = (
                f"Bond with {target_char_name} {tier_direction} into {new_tier.lower()} territory."
                if new_tier not in {config.RELATIONSHIP_TIER_FAMILY, config.RELATIONSHIP_TIER_STRANGER}
                else f"Family ties with {target_char_name} shifted." if new_tier == config.RELATIONSHIP_TIER_FAMILY
                else f"Grew closer to {target_char_name}."
            )
            highlight_tiers = {
                "Soulmate": 3,
                "Close Friend": 2,
                "Friend": 2,
                "Rival": 2,
                "Archenemy": 3,
            }
            significance = highlight_tiers.get(new_tier, 1)
            tag_slug = new_tier.lower().replace(" ", "_")
            self.record_life_event(
                world,
                "relationship_tier_change",
                tier_summary,
                related=[target_char_name],
                tags=["relationship", tag_slug],
                significance=significance,
                propagate_to_family=False,
                details={"previous_tier": previous_tier, "new_tier": new_tier, "score": new_score},
            )

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

    def _ensure_home_assignment(self, world: 'World'):
        if not hasattr(world, "claim_residential_spot"):
            return None
        preferred_tier = world.determine_estate_tier(self) if hasattr(world, "determine_estate_tier") else None
        building = world.claim_residential_spot(self, preferred_tier=preferred_tier)
        if building:
            self.home_location = building.location
        return building

    def _execute_find_shelter(self, world: 'World'):
        building = self._ensure_home_assignment(world)
        if building:
            self.add_memory(f"Claimed a resting spot at {building.display_name}.")
            self.current_goal = Goal(
                GoalType.REST_AT_HOME,
                assignee_id=self.name,
                originator_id=self.name,
                parameters={"building_location": building.location},
                priority=2,
            )
            self._execute_rest_at_home(world)
            return

        self.add_memory("No housing available—finding a quiet place to recuperate under the stars.")
        self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name, priority=6)

    def _execute_rest_at_home(self, world: 'World'):
        building = self._ensure_home_assignment(world)
        if not building:
            self.resting_at_home = False
            self._rest_ticks = 0
            self.add_memory("I have no home to rest in. I will keep moving.")
            self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name, priority=6)
            return

        target_tile = building.location
        if (self.x, self.y) not in building.get_tiles_occupied():
            self.add_memory(f"Heading to {building.display_name} to rest.")
            self.move_towards(target_tile[0], target_tile[1], world)
            return

        self.resting_at_home = True
        self._rest_ticks += 1
        current_energy = self.needs.get("Energy", 80)
        gain = getattr(config, "ENERGY_REST_GAIN_PER_TICK", 5)
        self.needs["Energy"] = min(config.NEED_SCORE_MAX, current_energy + gain)

        if self._rest_ticks == 1:
            self.add_memory(f"Settled in at {building.display_name} to recover.")

        if self.needs["Energy"] >= getattr(config, "ENERGY_THRESHOLD_FULLY_RESTED", 95):
            self.add_memory("Feeling refreshed and ready to work again.")
            self.resting_at_home = False
            self._rest_ticks = 0
            if hasattr(world, "release_residential_spot"):
                world.release_residential_spot(self)
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()

    def _execute_drink_water(self, world: 'World'):
        water_blueprint = BLUEPRINTS.get("Water", {})
        thirst_satisfaction = water_blueprint.get("thirst_satisfaction", 40)
        if self.inventory.get("Water", 0) > 0:
            self.inventory["Water"] -= 1
            if self.inventory["Water"] <= 0:
                del self.inventory["Water"]
            self.needs["Thirst"] = min(
                config.NEED_SCORE_MAX,
                self.needs.get("Thirst", 60) + thirst_satisfaction,
            )
            self.add_memory("Enjoyed a drink of water.")
            self.update_mood_score(getattr(config, "MOOD_CHANGE_REPLENISHED_WATER", 3), "Drank fresh water")
            self.current_goal.set_completed()
            self.current_goal = self.get_default_goal()
            return

        pulled = world.withdraw_resource("Water", 1) if hasattr(world, "withdraw_resource") else 0
        if pulled > 0:
            self.inventory["Water"] = self.inventory.get("Water", 0) + pulled
            self.add_memory("Collected water from communal stores to drink.")
            self._execute_drink_water(world)
            return

        self.add_memory("No water available in stockpiles—I need to gather some.")
        self.current_goal = Goal(GoalType.GATHER_WATER, assignee_id=self.name, originator_id=self.name, priority=2)

    def _execute_gather_water(self, world: 'World'):
        task_loc = self.find_task_location("Draw Water", world)
        if not task_loc:
            self.add_memory("Could not find a water source nearby.")
            self.current_goal = self.get_default_goal()
            return

        if (self.x, self.y) != task_loc:
            self.move_towards(task_loc[0], task_loc[1], world)
            return

        if not self._execute_generic_task(world, "Draw Water"):
            return

        directive = world.get_resource_directive("Water") if hasattr(world, "get_resource_directive") else None
        per_trip_quota = directive.get("per_trip_quota") if directive else None
        if directive and world.game_time and directive.get("last_reminded_day") != world.game_time.current_day:
            directive["last_reminded_day"] = world.game_time.current_day
            self.add_memory(
                f"Leadership asks for {directive['per_trip_quota']} Water before returning."
            )

        inventory_water = self.inventory.get("Water", 0)
        if (
            self.get_inventory_load() >= self.max_inventory_items
            or (per_trip_quota is not None and inventory_water >= per_trip_quota)
        ):
            haul_params = {"resource": "Water", "quantity": inventory_water}
            self.add_memory("Water containers filled—preparing to deliver them to stockpiles.")
            self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters=haul_params)
            return

        if inventory_water >= 1 and self.needs.get("Thirst", 60) < getattr(config, "THIRST_THRESHOLD_DRINK", 60):
            self.current_goal = Goal(GoalType.DRINK_WATER, assignee_id=self.name, originator_id=self.name, priority=2)

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
            target_tool_count = target_char.inventory.get(item_name_needed, 0)
            equipped_matches = (
                target_char.equipped_tool is not None
                and target_char.equipped_tool.get("name") == item_name_needed
            )
            spare_tools = target_tool_count - (1 if equipped_matches else 0)
            if spare_tools > 0 or (target_tool_count > 0 and not equipped_matches):
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
                giving_equipped_tool = (
                    target_char.equipped_tool is not None
                    and target_char.equipped_tool.get("name") == item_name_needed
                    and target_char.inventory.get(item_name_needed, 0) <= 1
                )
                if giving_equipped_tool:
                    target_char.unequip_tool()

                current_tool_count = target_char.inventory.get(item_name_needed, 0)
                if current_tool_count > 0:
                    target_char.inventory[item_name_needed] = current_tool_count - 1
                    if target_char.inventory[item_name_needed] <= 0:
                        del target_char.inventory[item_name_needed]

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