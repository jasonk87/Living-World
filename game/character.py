# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any
import random
from .llm_integration import generate_dialogue
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from . import config
from .goal import Goal, GoalType, GoalStatus, DEFAULT_IDLE_GOAL, create_goal_from_job
from .rumor import Rumor
from .actions.action import Action, ActionStatus
from .actions.wander_action import WanderAction
from .actions.greet_action import GreetAction
from .actions.socialize_action import SocializeAction
from .actions.argue_action import ArgueAction
from .actions.ask_for_help_action import AskForHelpAction
from .actions.build_order_action import BuildOrderAction
from .actions.craft_order_action import CraftOrderAction
from .actions.formal_apology_action import FormalApologyAction
from .actions.gather_resource_action import GatherResourceAction
from .actions.haul_resource_action import HaulResourceAction
from .actions.introduce_action import IntroduceAction
from .actions.maintain_ledger_action import MaintainLedgerAction
from .actions.manage_subordinates_action import ManageSubordinatesAction
from .actions.offer_comfort_action import OfferComfortAction
from .actions.oversee_settlement_action import OverseeSettlementAction
from .actions.share_positive_news_action import SharePositiveNewsAction
from .actions.share_secret_action import ShareSecretAction
from .actions.small_talk_action import SmallTalkAction
from .actions.count_stockpile_action import CountStockpileAction
from .actions.fetch_tool_action import FetchToolAction


if TYPE_CHECKING:
    from .world import World
    from .actions.action import Action
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
                 family_members: Optional[List[str]] = None): # New family_members parameter
        self.name = name; self.personality = personality; self.traits = traits;
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
                self.current_goal: Goal = DEFAULT_IDLE_GOAL(assignee_id=self.name, originator_id="SystemInit")

        # Ensure assignee_id is always set on the initial goal
        if self.current_goal.assignee_id is None:
            self.current_goal.assignee_id = self.name
        if not self.current_goal.originator_id: # Ensure originator is set if not already
            self.current_goal.originator_id = self.name if self.current_goal.goal_type != GoalType.IDLE else "SystemInit"

        self.max_inventory_items = max_inventory_items
        # self.hauling_info attribute is fully removed. Logic relies on current_goal.parameters.
        # self.counting_target_stockpile_name: Optional[str] = None # Attribute removed.
        self.supervisor_name: Optional[str] = None; self.subordinates_names: List[str] = []
        self.managed_item_targets: Dict[str, int] = {}; self.order_cooldown: Dict[str, int] = {}
        self.active_work_order_id: Optional[str] = None; self.crafting_progress: int = 0
        self.materials_gathered_for_wo: bool = False; self.items_crafted_for_wo: bool = False

        self.rank: str = rank
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

        # The goal_action_map has been removed and is replaced by the _action_factory method.

    def get_default_goal(self) -> Goal:
        """Returns the default goal for the character based on their job."""
        return create_goal_from_job(self.job or "Unemployed", self.name)

    def update_mood_score(self, change: int, reason: str):
        """Updates mood score and determines the new mood level."""
        if change == 0:
            return
        self.mood_score += change
        self.mood_score = max(config.MOOD_SCORE_MIN, min(config.MOOD_SCORE_MAX, self.mood_score))
        self.add_memory(f"Mood changed by {change} to {self.mood_score} because: {reason}.")
        self._determine_mood_level()

    def update_reputation(self, change: int, reason: str):
        """Updates reputation score."""
        if change == 0:
            return
        self.reputation_score += change
        self.add_memory(f"My reputation changed by {change} to {self.reputation_score} because: {reason}.")

    def get_inventory_load(self) -> int:
        """Returns the total number of items in the inventory."""
        return sum(self.inventory.values())

    def _reset_crafting_state(self):
        """Resets all attributes related to an active craft work order."""
        self.active_work_order_id = None
        self.crafting_progress = 0
        self.materials_gathered_for_wo = False
        self.items_crafted_for_wo = False
        self.workshop_location = None
        self.resource_to_fetch = None

    def _reset_building_state(self):
        """Resets all attributes related to an active build order."""
        self.active_build_order_id = None
        self.materials_gathered_for_build = False
        self.building_site_target = None
        self.current_building_project = None

    def add_subordinate(self, subordinate_name: str):
        """Adds a subordinate to the character's list of subordinates."""
        if subordinate_name not in self.subordinates_names:
            self.subordinates_names.append(subordinate_name)

    def remove_subordinate(self, subordinate_name: str):
        """Removes a subordinate from the character's list of subordinates."""
        if subordinate_name in self.subordinates_names:
            self.subordinates_names.remove(subordinate_name)

    def _action_factory(self, goal: Goal) -> Optional[Action]:
        """Creates an Action instance based on the current goal."""
        if goal.goal_type == GoalType.WANDER or goal.goal_type == GoalType.IDLE:
            return WanderAction(self)

        # Social Actions
        if goal.goal_type == GoalType.GREET_CHARACTER:
            target_name = goal.parameters.get("target_char_name")
            return GreetAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.INTRODUCE_SELF_TO_STRANGER:
            target_name = goal.parameters.get("target_char_name")
            return IntroduceAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.SMALL_TALK:
            target_name = goal.parameters.get("target_char_name")
            return SmallTalkAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.SHARE_POSITIVE_NEWS:
            target_name = goal.parameters.get("target_char_name")
            return SharePositiveNewsAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.OFFER_COMFORT:
            target_name = goal.parameters.get("target_char_name")
            return OfferComfortAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.ASK_FOR_HELP:
            return AskForHelpAction(self) # Parameters are read inside the action
        if goal.goal_type == GoalType.ARGUE:
            target_name = goal.parameters.get("target_char_name")
            return ArgueAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.SHARE_SECRET:
            target_name = goal.parameters.get("target_char_name")
            return ShareSecretAction(self, target_name) if target_name else None
        if goal.goal_type == GoalType.FORMAL_APOLOGY:
            target_name = goal.parameters.get("target_char_name")
            return FormalApologyAction(self, target_name) if target_name else None

        # Resource & Hauling Actions
        if goal.goal_type == GoalType.GATHER_RESOURCE:
            return GatherResourceAction(self)
        if goal.goal_type == GoalType.HAUL_RESOURCE_TO_STOCKPILE:
            return HaulResourceAction(self)

        # Job-specific & Management Actions
        if goal.goal_type == GoalType.EXECUTE_BUILD_ORDER:
            return BuildOrderAction(self)
        if goal.goal_type == GoalType.EXECUTE_CRAFT_ORDER:
            return CraftOrderAction(self)
        if goal.goal_type == GoalType.MAINTAIN_LEDGER:
            return MaintainLedgerAction(self)
        if goal.goal_type == GoalType.MANAGE_SUBORDINATES:
            return ManageSubordinatesAction(self)
        if goal.goal_type == GoalType.OVERSEE_SETTLEMENT:
            return OverseeSettlementAction(self)
        if goal.goal_type == GoalType.COUNT_STOCKPILE:
            return CountStockpileAction(self)
        if goal.goal_type == GoalType.FETCH_TOOL:
            return FetchToolAction(self)

        return None

    def _determine_mood_level(self) -> str:
        """Determines descriptive mood based on mood_score."""
        sorted_mood_levels = sorted(config.MOOD_LEVELS.items(), key=lambda item: item[1], reverse=True)
        current_mood_name = "Neutral"
        for mood_name, threshold in sorted_mood_levels:
            if self.mood_score >= threshold:
                current_mood_name = mood_name
                break
        if self.mood != current_mood_name:
            self.add_memory(f"My mood changed to {current_mood_name} (Score: {self.mood_score}).")
            self.mood = current_mood_name
        return self.mood

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
            self.needs['Esteem'] = min(config.NEED_SCORE_MAX, self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) + 5)
            self.add_memory(f"Leveling up my {skill_name} skill to {skill_data['level']} boosted my esteem. Esteem: {self.needs['Esteem']}")

    def _update_mood_from_critical_needs(self):
        """Checks critical complex needs and updates mood accordingly."""
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD:
            self.update_mood_score(config.MOOD_CHANGE_SAFETY_CRITICAL, "Critically low safety")
        if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            self.update_mood_score(config.MOOD_CHANGE_BELONGING_CRITICAL, "Critically low belonging")
        if self.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) < config.NEED_ESTEEM_CRITICAL_THRESHOLD:
            self.update_mood_score(config.MOOD_CHANGE_ESTEEM_CRITICAL, "Critically low esteem")

    def _process_learned_rumor(self, rumor: Rumor, world: 'World'):
        """Processes a newly learned rumor, potentially affecting opinions of the rumor's subject."""
        if rumor.subject_char_id == self.name:
            return
        if rumor.current_strength < config.MIN_RUMOR_STRENGTH_FOR_OPINION_EFFECT:
            return
        opinion_tag_key = "rumor_impression_positive" if rumor.is_positive else "rumor_impression_negative"
        if rumor.subject_char_id not in self.opinions:
            self.opinions[rumor.subject_char_id] = {}
        opinion_change_magnitude = rumor.current_strength * config.RUMOR_OPINION_EFFECT_STRENGTH_FACTOR
        opinion_delta = int(round(min(opinion_change_magnitude, config.MAX_OPINION_CHANGE_FROM_RUMOR)))
        if not rumor.is_positive:
            opinion_delta *= -1
        current_opinion_score = self.opinions[rumor.subject_char_id].get(opinion_tag_key, 0)
        new_opinion_score = max(-10, min(10, current_opinion_score + opinion_delta))
        if new_opinion_score != current_opinion_score:
            self.opinions[rumor.subject_char_id][opinion_tag_key] = new_opinion_score
            self._update_relationship_from_opinions(rumor.subject_char_id, world)

    def _update_relationship_from_opinions(self, target_name: str, world: 'World'):
        if target_name not in self.opinions:
            return
        opinion_tags = self.opinions.get(target_name, {})
        if not opinion_tags:
            return
        overall_impression_score = sum(opinion_tags.values())
        adjustment_factor = 0.1
        relationship_adjustment = int(round(overall_impression_score * adjustment_factor))
        relationship_adjustment = max(-1, min(1, relationship_adjustment))
        if relationship_adjustment != 0:
            self.modify_relationship(target_name, relationship_adjustment, world, reason=f"General impression ({overall_impression_score}) led to adjustment.")

    def _process_nearby_listeners(self, world: 'World', target_char: 'Character', interaction_type: str, initiator_traits: List[str], target_traits: List[str]):
        """Processes characters who might be listening to an interaction."""
        for listener in world.characters:
            if listener.name == self.name or listener.name == target_char.name:
                continue
            if listener.current_goal.type not in [GoalType.IDLE, GoalType.WANDER]:
                continue
            distance_to_initiator = abs(listener.x - self.x) + abs(listener.y - self.y)
            if distance_to_initiator <= 2:
                # Simplified listener logic
                pass

    def _execute_perform_woodcutter_duties(self, world: 'World'):
        if self.job != "Woodcutter":
            self.current_goal = self.get_default_goal()
            return
        quota = self.current_goal.parameters.get("quota", 5)
        inv_val = self.inventory.get("Wood", 0)
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0:
            self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters={"resource": "Wood"})
        elif inv_val < quota:
            self.current_goal = Goal(GoalType.GATHER_RESOURCE, assignee_id=self.name, originator_id=self.name, parameters={"resource_name": "Wood", "task_name": "Chop Wood", "quota": quota})
        else:
            self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters={"resource": "Wood"})
        # Do not recursively call decide_action. The main loop will do it.
        return

    def _execute_perform_stonemason_duties(self, world: 'World'):
        if self.job != "Stonemason":
            self.current_goal = self.get_default_goal()
            return
        quota = self.current_goal.parameters.get("quota", 5)
        inv_val = self.inventory.get("Stone", 0)
        if self.get_inventory_load() >= self.max_inventory_items and inv_val > 0:
            self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters={"resource": "Stone"})
        elif inv_val < quota:
            self.current_goal = Goal(GoalType.GATHER_RESOURCE, assignee_id=self.name, originator_id=self.name, parameters={"resource_name": "Stone", "task_name": "Mine Stone", "quota": quota})
        else:
            self.current_goal = Goal(GoalType.INITIATE_HAULING, assignee_id=self.name, originator_id=self.name, parameters={"resource": "Stone"})
        # Do not recursively call decide_action. The main loop will do it.
        return

    def _execute_initiate_hauling(self, world: 'World'):
        res = self.current_goal.parameters.get("resource")
        if not res or self.inventory.get(res, 0) == 0:
            self.current_goal = self.get_default_goal()
            return
        sps = [s_obj for s_obj in world.get_stockpiles_for_resource(res) if s_obj.has_space_for(res, 1)]
        if not sps:
            self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name)
            return
        sp_chosen = sps[0]
        new_params = self.current_goal.parameters.copy()
        new_params["target_stockpile_name"] = sp_chosen.name
        new_params["quantity_to_haul"] = self.inventory.get(res, 0)
        self.current_goal = Goal(GoalType.HAUL_RESOURCE_TO_STOCKPILE, assignee_id=self.name, originator_id=self.name, parameters=new_params)
        # Do not recursively call decide_action. The main loop will do it.
        return

    def add_memory(self, e: str):
        self.memory.append(e)
        self.memory = self.memory[-20:]

    def move(self, dx: int, dy: int, world: 'World') -> bool:
        new_x, new_y = self.x + dx, self.y + dy
        if not (0 <= new_x < world.grid_size[0] and 0 <= new_y < world.grid_size[1]):
            return False
        if world.get_tile(new_x, new_y) in ["Water", "Mountain"]:
            return False
        if world.get_building_at(new_x, new_y) is not None:
            return False
        if world.get_characters_at_location(new_x, new_y):
            return False
        self.x = new_x
        self.y = new_y
        return True

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx = target_x - self.x
        dy = target_y - self.y
        if dx > 0: dx = 1
        elif dx < 0: dx = -1
        if dy > 0: dy = 1
        elif dy < 0: dy = -1
        if dx == 0 and dy == 0:
            return
        if self.move(dx, dy, world):
            return
        if dx != 0 and self.move(dx, 0, world):
            return
        if dy != 0 and self.move(0, dy, world):
            return

    def decide_action(self, world: 'World'):
        if not world.game_time:
            self.current_goal = DEFAULT_IDLE_GOAL(self.name)
            return

        # Update mood based on critical complex needs
        self._update_mood_from_critical_needs()

        # Health check: If severely sick or injured, character may change goal
        # Thresholds for "severe" can be defined in config later
        # For now, let's use severity > 5 as a trigger to seek help.
        if self.current_goal.goal_type != GoalType.SEEK_MEDICAL_ATTENTION: # Avoid interrupting if already seeking help
            if self.is_sick and self.sickness_severity > 5:
                self.add_memory(f"Feeling very sick (Severity: {self.sickness_severity}). Need medical attention.")
                self.update_mood_score(config.MOOD_CHANGE_NEED_CRITICAL * 2, f"Severely sick (severity: {self.sickness_severity})") # Larger mood hit for severe sickness
                self.current_goal = Goal(GoalType.SEEK_MEDICAL_ATTENTION, assignee_id=self.name, originator_id=self.name)
            elif self.is_injured and self.injury_severity > 5:
                self.add_memory(f"Badly injured (Severity: {self.injury_severity}). Need medical attention.")
                self.update_mood_score(config.MOOD_CHANGE_NEED_CRITICAL * 2, f"Severely injured (severity: {self.injury_severity})") # Larger mood hit
                self.current_goal = Goal(GoalType.SEEK_MEDICAL_ATTENTION, assignee_id=self.name, originator_id=self.name)

        # Mood-driven goal check (simple example: seek solitude if very sad/stressed)
        # This should ideally be before job-default goals but after critical needs like medical attention.
        if self.current_goal.goal_type not in [GoalType.SEEK_MEDICAL_ATTENTION, GoalType.ASK_FOR_HELP]: # Don't override critical states
            if self.mood in ["Sad", "Stressed", "Furious"] and random.random() < config.MOOD_DRIVEN_GOAL_CHANCE:
                # For now, SEEK_SOLITUDE will just make them Wander.
                # A more complex implementation could make them avoid others or go to a quiet spot.
                self.add_memory(f"Feeling {self.mood}, I need some time alone.")
                self.current_goal = Goal(GoalType.WANDER, assignee_id=self.name, originator_id=self.name, details="Seeking solitude due to mood.") # Wander is a simple proxy for solitude

        # If goal changed to Seek Medical Attention, execute that immediately this tick.
        if self.current_goal.goal_type == GoalType.SEEK_MEDICAL_ATTENTION:
            pass # Let it fall through to goal execution or _execute_generic_task check

        # --- Complex Need-Driven Goal/Action Biases ---
        # These are checked if not already in a critical goal state like SEEK_MEDICAL_ATTENTION or ASK_FOR_HELP

        # Safety Need Bias
        if self.needs.get('Safety', config.NEED_SAFETY_DEFAULT) < config.NEED_SAFETY_CRITICAL_THRESHOLD and \
           self.current_goal.goal_type not in [GoalType.SEEK_MEDICAL_ATTENTION, GoalType.ASK_FOR_HELP, GoalType.WANDER]: # Avoid overriding if already wandering for mood
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
        if self.current_goal.goal_type not in critical_goal_types_for_ask_check:
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


        # If current goal is to perform builder duties, check for build orders
        if self.current_goal.goal_type == GoalType.PERFORM_BUILDER_DUTIES:
            # If already has an active order, switch goal to executing it
            if self.active_build_order_id:
                order = world.get_work_order_by_id(self.active_build_order_id)
                if order:
                    self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                             parameters={"order_id": order.order_id,
                                                         "structure_type": order.details.get("structure_type"),
                                                         "location": order.details.get("location")})
                    # Return so the dispatcher can pick up the new EXECUTE_BUILD_ORDER goal
                    return
                else: # Active order ID is invalid, reset state
                    self._reset_building_state()

            # Try to claim a new build order
            approved_build_orders = world.get_approved_build_orders()
            if approved_build_orders:
                order_to_take = approved_build_orders[0]  # Simplistic: take the first one
                order_to_take.status = "InProgress"
                order_to_take.assigned_to = self.name
                self._reset_building_state()
                self.active_build_order_id = order_to_take.order_id
                self.add_memory(f"Claimed Build WO {order_to_take.order_id} for {order_to_take.details.get('structure_type')}.")
                # Set goal to execute the order we just claimed
                self.current_goal = Goal(GoalType.EXECUTE_BUILD_ORDER, assignee_id=self.name, originator_id=self.name,
                                         parameters={"order_id": order_to_take.order_id,
                                                     "structure_type": order_to_take.details.get("structure_type"),
                                                     "location": order_to_take.details.get("location")})
                return # Let dispatcher handle the new goal
            else:
                # No build orders available, so the duty is done for now. Go idle.
                self.add_memory("No build orders available for Builder Duties.")
                self.current_goal = self.get_default_goal()

        # Fallback to job default goal if current goal is None or explicitly Idle/Wander
        if self.current_goal is None or self.current_goal.goal_type in [GoalType.IDLE, GoalType.WANDER]:
            new_default_goal = self.get_default_goal()
            if self.current_goal is None or self.current_goal.goal_type != new_default_goal.goal_type:
                self.current_goal = new_default_goal

        # --- Goal Execution Dispatcher ---
        action = self._action_factory(self.current_goal)

        if action:
            goal_before_action = self.current_goal
            status = action.execute(world)
            # If the action completed and did NOT change the goal itself, get the default goal.
            if (status == ActionStatus.COMPLETED or status == ActionStatus.FAILED) and self.current_goal == goal_before_action:
                self.current_goal = self.get_default_goal()
            # If status is RUNNING, or if the action itself set a new goal, the current goal remains for the next tick.
        else:
            # Handle high-level goals that don't map to a single action
            if self.current_goal.goal_type == GoalType.PERFORM_WOODCUTTER_DUTIES:
                self._execute_perform_woodcutter_duties(world)
            elif self.current_goal.goal_type == GoalType.PERFORM_STONEMASON_DUTIES:
                self._execute_perform_stonemason_duties(world)
            elif self.current_goal.goal_type == GoalType.INITIATE_HAULING:
                self._execute_initiate_hauling(world)
            # ... other high-level goal handlers
            else:
                # If no action and no handler, default to wander.
                # The WanderAction will be created by the factory and executed.
                # We set the goal to Wander so the factory can pick it up.
                self.current_goal = Goal(GoalType.WANDER, self.name, self.name)


        # --- Social Interaction Initiation ---
        # This block is for proactive social interactions.
        # It's checked if the character's current goal is idle or wandering.
        if self.current_goal.goal_type in [GoalType.IDLE, GoalType.WANDER]:
            self._initiate_social_interaction(world)

        # --- Reactive Social Interaction Checks ---
        # These checks can interrupt non-critical, non-social goals.
        self._check_for_reactive_social_interactions(world)

        return # End of decide_action

    def find_task_location(self, task_name: str, world: 'World') -> Optional[Tuple[int, int]]:
        """Finds a suitable location in the world to perform a given task."""
        task_to_tile_map = {
            "Chop Wood": "Forest",
            "Mine Stone": "Mountain",
            "Mine Iron Ore": "Mountain",
            "Gather Herbs": "Forest" # Assuming herbs are in forests for now
        }

        required_tile = task_to_tile_map.get(task_name)
        if not required_tile:
            return None # Task doesn't have a specific location type

        # Simple scan for the first available tile.
        for y in range(world.grid_size[1]):
            for x in range(world.grid_size[0]):
                if world.get_tile(x, y) == required_tile:
                    # Could add more complex logic here, e.g., find closest, check if occupied
                    return (x, y)
        return None

    def _initiate_social_interaction(self, world: 'World'):
        """Determines if a character should proactively start a social interaction."""
        current_social_interaction_chance = config.SOCIAL_INTERACTION_CHANCE
        if self.needs.get('Social', 70) < config.LOW_SOCIAL_NEED_THRESHOLD:
            current_social_interaction_chance += config.SOCIAL_INTERACTION_CHANCE_LOW_NEED_BONUS
        if self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < config.NEED_BELONGING_CRITICAL_THRESHOLD:
            current_social_interaction_chance += 0.15
        elif self.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) < (config.NEED_BELONGING_CRITICAL_THRESHOLD + 20):
            current_social_interaction_chance += 0.05

        mood_social_mod = config.MOOD_EFFECT_SOCIAL_SUCCESS_MOD.get(self.mood, 0.0)
        current_social_interaction_chance = max(0.01, min(0.95, current_social_interaction_chance + mood_social_mod))

        if random.random() >= current_social_interaction_chance:
            return

        potential_targets = []
        for other_char in world.characters:
            if other_char.name == self.name: continue
            distance = abs(self.x - other_char.x) + abs(self.y - other_char.y)
            if distance > 5: continue

            recently_interacted = any(
                (entry.get("target") == other_char.name or entry.get("initiator") == other_char.name) and
                world.game_time and (world.game_time.current_day - entry.get("day", -100)) < 1
                for entry in reversed(self.dialogue_history[-3:])
            )
            if not recently_interacted:
                potential_targets.append(other_char)

        if not potential_targets:
            return

        # Simplified weighting and selection logic
        target_char = random.choice(potential_targets)

        interaction_goal_type = None
        if target_char.name not in self.known_characters:
            interaction_goal_type = GoalType.INTRODUCE_SELF_TO_STRANGER
        else:
            roll = random.random()
            if roll < 0.3 + (0.2 if "Chatty" in self.traits else 0.0):
                interaction_goal_type = GoalType.SHARE_POSITIVE_NEWS
            elif roll < 0.8:
                interaction_goal_type = GoalType.SMALL_TALK
            else:
                interaction_goal_type = GoalType.GREET_CHARACTER

        if interaction_goal_type:
            self.current_goal = Goal(interaction_goal_type, assignee_id=self.name, originator_id=self.name,
                                     parameters={"target_char_name": target_char.name})
            self.add_memory(f"Decided to '{interaction_goal_type.name}' with {target_char.name}.")

    def _check_for_reactive_social_interactions(self, world: 'World'):
        """Checks for and potentially triggers reactive social goals like offering comfort or arguing."""
        non_interruptible_social_goals = [
            GoalType.OFFER_COMFORT, GoalType.ARGUE, GoalType.ASK_FOR_HELP, GoalType.FORMAL_APOLOGY, GoalType.SHARE_SECRET
        ]
        if self.current_goal.goal_type in non_interruptible_social_goals:
            return

        # Check for offering comfort
        comfort_chance = config.REACTIVE_SOCIAL_BASE_CHANCE + (0.3 if "Kind" in self.traits else 0) + (0.4 if "Compassionate" in self.traits else 0)
        if random.random() < comfort_chance:
            for char_in_need in world.characters:
                is_distressed = (char_in_need.mood in ["Sad", "Stressed"] or char_in_need.is_sick or char_in_need.is_injured)
                is_nearby = abs(self.x - char_in_need.x) + abs(self.y - char_in_need.y) <= 4
                if char_in_need.name != self.name and char_in_need.name in self.known_characters and is_distressed and is_nearby:
                    self.current_goal = Goal(GoalType.OFFER_COMFORT, self.name, self.name, {"target_char_name": char_in_need.name})
                    self.add_memory(f"Noticed {char_in_need.name} seems distressed. Decided to offer comfort.")
                    return # Triggered a reactive goal, so we're done for this check

        # Check for starting an argument
        argue_chance = config.REACTIVE_SOCIAL_BASE_CHANCE + (0.15 if "Hot-headed" in self.traits else 0)
        if random.random() < argue_chance:
            for other_char in world.characters:
                is_antagonistic = self.get_relationship_score(other_char.name) < -40 or ("Hot-headed" in self.traits and "Hot-headed" in other_char.traits)
                is_nearby = abs(self.x - other_char.x) + abs(self.y - other_char.y) <= 2
                if other_char.name != self.name and other_char.name in self.known_characters and is_antagonistic and is_nearby:
                    self.current_goal = Goal(GoalType.ARGUE, self.name, self.name, {"target_char_name": other_char.name})
                    self.add_memory(f"Feeling confrontational towards {other_char.name}. Decided to argue.")
                    return


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
        subordinate.current_goal = Goal(GoalType.IDLE, originator_id=self.name, assignee_id=subordinate.name)
        subordinate.assigned_tasks = []
        subordinate.performance_rating = "Fired"
        subordinate.update_mood_score(config.MOOD_CHANGE_FIRED, f"Fired from job as {original_job}")
        subordinate.needs['Belonging'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - 25) # Major hit to belonging
        subordinate.add_memory(f"Being fired made me lose my sense of belonging with my work group. Belonging: {subordinate.needs['Belonging']}")
        subordinate.needs['Esteem'] = max(config.NEED_SCORE_MIN, subordinate.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - 30) # Huge esteem hit
        subordinate.add_memory(f"Being fired crushed my esteem. Esteem: {subordinate.needs['Esteem']}")

        rep_change_reason = f"Was fired from job as {original_job} by {self.name}"
        subordinate.update_reputation(config.REPUTATION_CHANGE_FIRED, rep_change_reason)
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
            # world.add_rumor(new_rumor) # This is now handled by the event bus
            world.event_bus.post("RUMOR_CREATED", new_rumor)

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
            self.update_reputation(config.REPUTATION_CHANGE_APOLOGY_ACCEPTED, rep_change_reason)
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
            target_char.update_reputation(config.REPUTATION_CHANGE_HELPED_OTHER, rep_change_reason)
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