# game/goal.py
from enum import Enum, auto
from typing import Optional, Dict, Any, List
from .goal_runtime import GoalPriority
from .goal_runtime import GoalPriority

class GoalType(Enum):
    # General & Maintenance
    IDLE = auto()
    WANDER = auto()
    MAINTAIN_LEDGER = auto() # Bookkeeper
    COUNT_STOCKPILE = auto() # Bookkeeper
    ASSESS_PRODUCTION_NEEDS = auto() # Master Craftsman

    # Resource Gathering & Hauling
    HUNT = auto()
    GATHER_RESOURCE = auto() # Generic, params will specify what (e.g. {"resource_name": "Wood"})
    GATHER_WOOD = auto() # Specific version of GATHER_RESOURCE
    GATHER_STONE = auto() # Specific version of GATHER_RESOURCE
    GATHER_HERBS = auto() # Specific version of GATHER_RESOURCE
    GATHER_WATER = auto()

    HAUL_RESOURCE_TO_STOCKPILE = auto()
    INITIATE_HAULING = auto() # Intermediate step for haulers

    # Crafting & Building
    EXECUTE_CRAFT_ORDER = auto()
    EXECUTE_BUILD_ORDER = auto()
    FETCH_RESOURCE_FOR_WO = auto() # For crafting
    FETCH_RESOURCE_FOR_BUILD = auto() # For building

    # Farming
    TILL_SOIL = auto()
    PLANT_SEEDS = auto()
    HARVEST_CROP = auto()

    # Management & Leadership (Higher Level)
    OVERSEE_SETTLEMENT = auto() # Mayor
    MANAGE_SUBORDINATES = auto() # Manager, Noble Lord, etc.
    MANAGE_APPOINTMENTS = auto() # Mayor
    ISSUE_STRATEGIC_DIRECTIVE = auto() # Mayor, other leaders
    ENACT_POLICY = auto() # Mayor
    REVIEW_LAW_PETITIONS = auto() # Mayor
    DRAFT_SETTLEMENT_LAW = auto() # Mayor
    ENACT_SETTLEMENT_LAW = auto() # Mayor
    APPROVE_MAJOR_PROJECT = auto() # Mayor
    HOST_EVENT = auto() # Mayor, Nobles (e.g. GiveSpeech, HoldMeeting)
    GIVE_SPEECH = auto() # Specific HOST_EVENT type
    CAMPAIGN_SPEECH = auto() # Election trail promise rally

    # Military & Security
    MAINTAIN_DEFENSES = auto() # Militia Commander
    ORGANIZE_PATROLS = auto() # Militia Commander
    TRAIN_MILITIA_UNITS = auto() # Militia Commander
    LEAD_FORCE = auto() # Militia Commander
    MAINTAIN_PEACE_IN_SETTLEMENT = auto() # Sheriff
    PATROL_AREA = auto() # Deputy, Militia Captain
    INVESTIGATE_DISTURBANCE = auto() # Sheriff
    PREPARE_TRIAL_CASE = auto() # Sheriff legal prep
    CONDUCT_WITNESS_INTERVIEW = auto() # Sheriff & Deputies
    ATTEND_TRIAL = auto() # Court appearances

    # Medical
    OVERSEE_MEDICAL_OPERATIONS = auto() # CMO
    PROVIDE_MEDICAL_CARE = auto() # Medic (umbrella goal)
    # GATHER_HERBS is already listed above
    TREAT_PATIENT = auto() # Medic (specific action)
    SEEK_MEDICAL_ATTENTION = auto() # Any character

    # Social
    GREET_CHARACTER = auto()
    INTRODUCE_SELF_TO_STRANGER = auto()
    SMALL_TALK = auto()
    SHARE_POSITIVE_NEWS = auto()
    OFFER_COMFORT = auto()
    ASK_FOR_HELP = auto()
    ARGUE = auto()
    SHARE_SECRET = auto() # Added
    FORMAL_APOLOGY = auto() # Added
    PRAISE_CHARACTER = auto()
    MAKE_NEW_FRIEND = auto()
    SHARE_RUMOR = auto()

    # Economic
    SEEK_TO_BUY_ITEM = auto()

    # Need-Driven & Prosocial
    EAT_FOOD = auto()
    DRINK_WATER = auto()
    FIND_SHELTER = auto()
    REST_AT_HOME = auto()
    SEEK_RECOGNITION = auto() # Esteem
    IMPROVE_DWELLING = auto() # Safety
    HELP_FRIEND = auto() # Belonging / Relationship

    # Noble Specific
    OVERSEE_DOMAIN = auto() # Landed Nobles
    COLLECT_REVENUE_FROM_DOMAIN = auto() # Landed Nobles
    ISSUE_DOMAIN_EDICT = auto() # Landed Nobles
    REPORT_TO_LIEGE = auto() # Vassals
    ATTEND_COURT_SOCIAL_EVENT = auto() # All Nobles
    ATTEMPT_TO_INFLUENCE_NOBLE = auto() # All Nobles
    HOST_SOCIAL_GATHERING = auto() # All Nobles
    MANAGE_ESTATE = auto() # Reeve
    ASSIST_REEVE = auto() # Bailiff
    HOLD_HIGH_COURT = auto() # Liege
    ATTEND_HIGH_COURT = auto() # Vassal

    # Utility / Intermediate
    FETCH_TOOL = auto()

    # Job default umbrella goals (if not covered by more specific leadership goals)
    PERFORM_BUILDER_DUTIES = auto()
    PERFORM_WOODCUTTER_DUTIES = auto()
    PERFORM_STONEMASON_DUTIES = auto()
    PERFORM_MINER_DUTIES = auto()
    PERFORM_FARMER_DUTIES = auto()
    PERFORM_HUNTER_DUTIES = auto()
    PERFORM_FLETCHER_DUTIES = auto()
    PERFORM_SAWYER_DUTIES = auto()
    PERFORM_CARPENTER_DUTIES = auto()
    PERFORM_SMELTER_DUTIES = auto()
    PERFORM_BLACKSMITH_DUTIES = auto()

    GO_TO_WORK = auto()

    PURSUE_JOB = auto()
    IMPROVE_SKILL = auto()
    CRAFT_MASTERPIECE = auto()
    EARN_MONEY = auto()
    BUILD_STRUCTURE = auto()
    INCREASE_REPUTATION = auto()


class GoalStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    DELEGATED = auto()

class Goal:
    def __init__(self, goal_type: GoalType,
                 originator_id: Optional[str] = None, # Character name or "System"
                 assignee_id: Optional[str] = None, # Character name responsible for this goal
                 priority: GoalPriority = GoalPriority.MEDIUM,
                 parameters: Optional[Dict[str, Any]] = None,
                 status: GoalStatus = GoalStatus.PENDING):
        self.type = goal_type
        self.originator_id = originator_id
        self.assignee_id = assignee_id
        self.priority = priority
        self.parameters = parameters if parameters is not None else {} # Ensure it's a dict
        self.status = status
        self.sub_goals: List['Goal'] = [] # For breaking down complex goals

    def __str__(self):
        goal_type_name = self.type.name if self.type else "NoGoalType"
        status_name = self.status.name if self.status else "NoStatus"
        priority_name = self.priority.name if isinstance(self.priority, GoalPriority) else str(self.priority)
        return (f"Goal(Type: {goal_type_name}, Prio: {priority_name}, "
                f"Assignee: {self.assignee_id or 'Any'}, Status: {status_name}, "
                f"Params: {self.parameters}, Orig: {self.originator_id or 'Self'})")

    # Convenience methods
    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE

    def is_complete(self) -> bool:
        return self.status == GoalStatus.COMPLETED

    def set_active(self):
        self.status = GoalStatus.ACTIVE

    def set_completed(self):
        self.status = GoalStatus.COMPLETED

    def set_failed(self, reason: Optional[str] = None):
        self.status = GoalStatus.FAILED
        if reason: self.parameters["failure_reason"] = reason

    def set_cancelled(self, reason: Optional[str] = None):
        self.status = GoalStatus.CANCELLED
        if reason: self.parameters["cancellation_reason"] = reason

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Goal object to a dictionary for JSON serialization."""
        return {
            "type": self.type.name,
            "originator_id": self.originator_id,
            "assignee_id": self.assignee_id,
            "priority": self.priority.name,
            "parameters": self.parameters,
            "status": self.status.name,
            "sub_goals": [sg.to_dict() for sg in self.sub_goals]
        }

# Default goal instance for characters when they have nothing else to do.
# Assignee will be set by the character itself.
def DEFAULT_IDLE_GOAL(assignee_id: str) -> Goal:
    return Goal(GoalType.IDLE, originator_id="System", assignee_id=assignee_id, priority=GoalPriority.IDLE)

def create_goal_from_job(job_name: str, char_name: str, priority: GoalPriority = GoalPriority.MEDIUM) -> Optional[Goal]:
    """
    Creates a default Goal object based on a character's job title or a goal string.
    """
    goal_str_upper = job_name.replace(" ", "_").upper()
    try:
        goal_type_enum = GoalType[goal_str_upper]
        return Goal(goal_type_enum, originator_id="SystemAssignment", assignee_id=char_name, priority=priority)
    except KeyError:
        pass

    from .data import ROLE_DETAILS
    role_detail = ROLE_DETAILS.get(job_name)
    if role_detail and role_detail.get("job_default_goal"):
        goal_str_upper = role_detail["job_default_goal"].replace(" ", "_").upper()
        try:
            goal_type_enum = GoalType[goal_str_upper]
            return Goal(goal_type_enum, originator_id="SystemAssignment", assignee_id=char_name, priority=priority)
        except KeyError:
            pass

    mapping = {
        "Perform Builder Duties": GoalType.PERFORM_BUILDER_DUTIES,
        "Perform Woodcutter Duties": GoalType.PERFORM_WOODCUTTER_DUTIES,
        "Perform Stonemason Duties": GoalType.PERFORM_STONEMASON_DUTIES,
        "Perform Miner Duties": GoalType.PERFORM_MINER_DUTIES,
        "Perform Farmer Duties": GoalType.PERFORM_FARMER_DUTIES,
        "Perform Hunter Duties": GoalType.PERFORM_HUNTER_DUTIES,
        "Perform Fletcher Duties": GoalType.PERFORM_FLETCHER_DUTIES,
        "Perform Sawyer Duties": GoalType.PERFORM_SAWYER_DUTIES,
        "Perform Carpenter Duties": GoalType.PERFORM_CARPENTER_DUTIES,
        "Perform Smelter Duties": GoalType.PERFORM_SMELTER_DUTIES,
        "Perform Blacksmith Duties": GoalType.PERFORM_BLACKSMITH_DUTIES,
        "Assess Production Needs": GoalType.ASSESS_PRODUCTION_NEEDS,
        "Manage Subordinates": GoalType.MANAGE_SUBORDINATES,
        "Maintain Ledger": GoalType.MAINTAIN_LEDGER,
        "Oversee Expedition": GoalType.MAINTAIN_DEFENSES,
        "Oversee Settlement": GoalType.OVERSEE_SETTLEMENT,
        "Oversee Medical Operations": GoalType.OVERSEE_MEDICAL_OPERATIONS,
        "Provide Medical Care": GoalType.PROVIDE_MEDICAL_CARE,
        "Maintain Peace in Settlement": GoalType.MAINTAIN_PEACE_IN_SETTLEMENT,
        "Patrol Area": GoalType.PATROL_AREA,
        "Oversee Domain": GoalType.OVERSEE_DOMAIN,
        "Lead Unit": GoalType.PATROL_AREA,
    }

    default_goal_str = role_detail.get("job_default_goal") if role_detail else job_name
    if default_goal_str in mapping:
        return Goal(mapping[default_goal_str], originator_id="SystemAssignment", assignee_id=char_name, priority=priority)

    if job_name == "Hunt":
        return Goal(GoalType.HUNT, originator_id="SystemAssignment", assignee_id=char_name, priority=priority)

    if job_name == "Unemployed":
        return Goal(GoalType.WANDER, originator_id="SystemAssignment", assignee_id=char_name, priority=GoalPriority.LOW)

    return Goal(GoalType.IDLE, originator_id="SystemAssignment", assignee_id=char_name, priority=GoalPriority.IDLE)


