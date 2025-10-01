# game/config.py
# LLM Integration Settings
USE_LLM = False  # Set to True to attempt to use a real LLM
LLM_ENDPOINT = "http://localhost:11434/api/generate"  # Example for Ollama
LLM_MODEL = "llama2"  # Specify the model you want to use with Ollama
LLM_HAS_THINKING_TAGS = False # Set to True if your model uses <thinking>...</thinking> tags

# General Game Settings
TICKS_PER_DAY = 10
DAYS_PER_SEASON = 10 # Example, can be adjusted
MAX_SIMULATION_DAYS = 20 # Max days the simulation runs for in headless/test mode.

# Day & Night Phases
DAY_PHASE_CONFIG = [
    {"key": "dawn", "name": "Dawn Preparations", "start_tick": 0, "description": "Citizens rise, stretch, and ready for the day."},
    {"key": "work", "name": "Workday", "start_tick": 2, "description": "Work crews report to duties and production ramps up."},
    {"key": "supper", "name": "Supper Break", "start_tick": 5, "description": "Communal meal hour where canteens open and rations are shared."},
    {"key": "evening", "name": "Evening Gatherings", "start_tick": 6, "description": "Leisure and social events blossom around hearths and taverns."},
    {"key": "night", "name": "Night Rest", "start_tick": 8, "description": "Quiet hours as households settle into their beds."},
]

PHASE_BEHAVIOR_TWEAKS = {
    "dawn": {"job_focus": 1, "social_bonus": -0.05},
    "work": {"job_focus": 2, "social_bonus": -0.1},
    "supper": {"meal_focus": True, "social_bonus": 0.15},
    "evening": {"social_bonus": 0.3},
    "night": {"force_rest": True, "social_bonus": -0.25},
}

QUIET_HOURS_START_TICK = 8
COMMUNAL_MEAL_WINDOW = (5, 6)

# Resource Node Durability & Regrowth
RESOURCE_NODE_DURABILITY = {
    "Wood": 6,
    "Stone": 8,
    "Herbs": 4,
    "Food": 5,
    "Water": 999,  # Springs and wells do not deplete under normal circumstances
}

RESOURCE_NODE_DEPLETED_TILES = {
    "Wood": "Clearing",
    "Stone": "Rubble",
    "Herbs": "Trampled",
    "Food": "Fallow",
}

RESOURCE_NODE_REGROWTH_DAYS = {
    "Wood": 6,
    "Stone": 12,
    "Herbs": 3,
    "Food": 4,
}

# Weather Event Definitions
WEATHER_EVENT_DEFINITIONS = {
    "Blizzard": {
        "seasons": ["Winter"],
        "weather": ["Snowy", "Cloudy"],
        "base_chance": 0.25,
        "duration_days": (1, 2),
        "severity_range": (2, 4),
        "travel_speed_multiplier": 0.6,
        "resource_yield": {"Wood": 0.75, "Herbs": 0.5},
        "market_multipliers": {"Wood": 1.15},
        "requires_shelter": True,
        "hazards": {"type": "cold", "mood_penalty": -6},
    },
    "Heat Wave": {
        "seasons": ["Summer"],
        "weather": ["Sunny"],
        "base_chance": 0.2,
        "duration_days": (1, 3),
        "severity_range": (1, 3),
        "travel_speed_multiplier": 0.8,
        "resource_yield": {"Water": 0.6, "Food": 0.9},
        "market_multipliers": {"Water": 1.25},
        "requires_shelter": True,
        "hazards": {"type": "heat", "mood_penalty": -8},
    },
    "Tempest Storm": {
        "seasons": ["Spring", "Autumn"],
        "weather": ["Rainy", "Cloudy"],
        "base_chance": 0.22,
        "duration_days": (1, 2),
        "severity_range": (1, 3),
        "travel_speed_multiplier": 0.7,
        "resource_yield": {"Stone": 0.85, "Herbs": 0.9},
        "market_multipliers": {"Herbs": 1.1},
        "requires_shelter": False,
        "hazards": {"type": "storm", "mood_penalty": -4},
    },
}

WEATHER_EVENT_MESSAGE_LIMIT = 4

# Population Churn Balancing
POPULATION_BIRTH_BASE_CHANCE = 0.08
POPULATION_MIGRATION_BASE_CHANCE = 0.12
POPULATION_DEPARTURE_BASE_CHANCE = 0.08
POPULATION_EVENT_COOLDOWN_DAYS = 2
POPULATION_BELONGING_THRESHOLD_FOR_BIRTH = 60
POPULATION_SURPLUS_THRESHOLD_FOR_MIGRATION = 6
POPULATION_DEPARTURE_MOOD_THRESHOLD = -35
POPULATION_DEPARTURE_HOMELESS_WEIGHT = 0.35
DEFAULT_CHILD_NEEDS = {
    "Hunger": 65,
    "Thirst": 65,
    "Energy": 100,
    "Social": 80,
    "Safety": 55,
    "Belonging": 85,
    "Esteem": 45,
}

# Economy & Survival Balancing
STARTING_TREASURY_COINS = 350
DAILY_BASE_TAX_INCOME = 18
DAILY_FOOD_CONSUMPTION_PER_CITIZEN = 1
DAILY_WATER_CONSUMPTION_PER_CITIZEN = 1
STARVATION_HUNGER_PENALTY = 15
DEHYDRATION_THIRST_PENALTY = 20
MOOD_CHANGE_STARVING = -12
MOOD_CHANGE_DEHYDRATED = -14
MOOD_CHANGE_REPLENISHED_WATER = 4
MOOD_CHANGE_RESTED_IN_HOME = 4
MOOD_CHANGE_HOMELESS_SLEEP = -8
BELONGING_PENALTY_HOMELESS_SLEEP = 6
ENERGY_PENALTY_HOMELESS_SLEEP = 12
MOOD_CHANGE_PAYMENT_DELAY = -6
MAX_SURPLUS_SALE_PER_DAY = 12
THEFT_BASE_CHANCE = 0.04
THEFT_DESPERATION_SCALE = 0.35
THEFT_HUNGER_THRESHOLD = 35
THEFT_LOW_FUNDS_THRESHOLD = 4
THEFT_MAX_QUANTITY = 3
THEFT_DETECTION_BASE = 0.35
MOOD_CHANGE_CAUGHT_STEALING = -18
MOOD_CHANGE_STOLE_SUCCESS = 3


# Environment Modelling
SEASON_ENVIRONMENT_MODIFIERS = {
    "Spring": {
        "resource_yield": {"Herbs": 1.15, "Food": 1.05},
        "market_prices": {"Herbs": 0.95},
        "travel_speed": 1.0,
    },
    "Summer": {
        "resource_yield": {"Wood": 1.1, "Food": 1.1},
        "market_prices": {"Food": 0.9},
        "travel_speed": 1.05,
    },
    "Autumn": {
        "resource_yield": {"Food": 1.2, "Wood": 0.95},
        "market_prices": {"Food": 1.0},
        "travel_speed": 1.0,
    },
    "Winter": {
        "resource_yield": {"Wood": 0.8, "Herbs": 0.5},
        "market_prices": {"Food": 1.25},
        "travel_speed": 0.85,
    },
}

WEATHER_ENVIRONMENT_MODIFIERS = {
    "Sunny": {
        "resource_yield": {"Stone": 1.05},
        "market_prices": {},
        "travel_speed": 1.05,
    },
    "Cloudy": {
        "resource_yield": {},
        "market_prices": {},
        "travel_speed": 0.95,
    },
    "Rainy": {
        "resource_yield": {"Herbs": 1.25},
        "market_prices": {"Herbs": 0.9},
        "travel_speed": 0.9,
    },
    "Snowy": {
        "resource_yield": {"Wood": 0.85, "Stone": 0.8},
        "market_prices": {"Wood": 1.1},
        "travel_speed": 0.75,
    },
}

ENVIRONMENT_PRICE_ELASTICITY = 0.05
ENVIRONMENT_TRAVEL_SNIPPET_LIMIT = 3

# Campaign & Governance Balancing
CAMPAIGN_SPEECH_COOLDOWN_DAYS = 2


# Other game settings (can be added later)
STALE_THRESHOLD_DAYS = 2 # Days after which ledger data is considered stale for manager decisions
MANAGEMENT_REVIEW_INTERVAL_DAYS = 5 # How often managers review subordinates
FIRING_WARNING_THRESHOLD = 3 # Number of warnings before firing is likely

# Skill System
BASE_EXP_TO_NEXT_LEVEL = 50.0
EXP_LEVEL_SCALING_FACTOR = 1.5

# Mayor Oversight Thresholds
MAYOR_RESOURCE_LOW_THRESHOLD = 20  # Mayor becomes concerned if key resources drop below this
MAYOR_RESOURCE_HIGH_THRESHOLD = 150 # Mayor recognizes an abundance when stores exceed this

# Medical System Thresholds
MEDICAL_SUPPLY_LOW_THRESHOLD = 5 # Chief Medical Officer acts when medical supplies fall below this

# Governance Configs
ELECTION_CYCLE_DAYS = 30 # How often mayoral elections are held
CAMPAIGN_PROMISE_DEFAULT_WINDOW = 4
CAMPAIGN_PROMISE_DEADLINES = {
    "resource_drive": 6,
    "trade_policy": 4,
    "community_event": 3,
}
CAMPAIGN_PROMISE_FAILURE_REPUTATION = -6
MOOD_CHANGE_CAMPAIGN_PROMISE_FAILED = -12

# Social Interaction
REACTIVE_SOCIAL_BASE_CHANCE = 0.05 # Base chance for reactive social interactions like offering comfort
SOCIAL_INTERACTION_CHANCE = 0.10 # Chance per tick (if idle/wandering) to initiate a social interaction like greeting (Increased for testing)
SOCIAL_NEED_DECAY_RATE_PER_DAY = 10 # How much social need decays each day (0-100 scale)
SOCIAL_FULFILLMENT_GREET_INTRODUCE = 5 # Social points gained from a greeting or introduction
SOCIAL_FULFILLMENT_SMALL_TALK = 8      # Social points from small talk
SOCIAL_FULFILLMENT_POSITIVE_NEWS = 7   # Social points from sharing positive news
SOCIAL_FULFILLMENT_OFFER_COMFORT_INITIATOR = 10 # Social points for offering comfort
SOCIAL_FULFILLMENT_OFFER_COMFORT_TARGET = 12  # Social points for receiving comfort (higher as it's a direct positive)
SOCIAL_FULFILLMENT_LISTEN_POSITIVE = 2 # Minor social gain from overhearing positive/neutral interactions
LOW_SOCIAL_NEED_THRESHOLD = 30 # Below this, character might actively seek more social interaction
VERY_LOW_SOCIAL_NEED_THRESHOLD = 15 # Below this, other negative effects might occur (mood, productivity - future)
SOCIAL_INTERACTION_CHANCE_LOW_NEED_BONUS = 0.03 # Additional chance to interact if social need is low
CRITICAL_NEED_THRESHOLD_FOR_HELP = 10 # e.g., if Hunger drops below this, might ask for food
ASK_FOR_HELP_CHANCE = 0.25 # Base chance to ask for help when in critical need and a suitable target is nearby
SOCIAL_DISTRESS_THRESHOLD = 25 # Score above which comfort is attempted
ARGUMENT_RELATIONSHIP_THRESHOLD = -40 # Relationship score below which arguments may trigger
ARGUMENT_RECENT_HISTORY_TICKS = 4 # Avoid arguing repeatedly within these ticks

# Mood System Configs
MOOD_SCORE_MIN = -100
MOOD_SCORE_MAX = 100
MOOD_SCORE_NEUTRAL_START = 0

# Mood Levels (Score Thresholds and Names)
# Thresholds are lower bounds. e.g. score > 75 is Ecstatic.
MOOD_LEVELS = {
    "Ecstatic": 75,
    "Happy": 50,
    "Content": 20,
    "Neutral": -20, # Neutral is a band around 0
    "Displeased": -50,
    "Sad": -75,
    "Furious": -90, # Reserved for very strong negative triggers, might override Sad/Stressed
    "Stressed": -60 # Might be a parallel mood or override others depending on source
}
# Note: For simplicity, Furious and Stressed might be special flags rather than just score-based.
# Or, specific events directly set these moods bypassing score temporarily.

# Base Mood Change Values (Examples - can be tuned extensively)
MOOD_CHANGE_POSITIVE_SOCIAL = 5
MOOD_CHANGE_NEGATIVE_SOCIAL = -10
MOOD_CHANGE_SUCCESSFUL_TASK_MAJOR = 10 # e.g. completing a WO
MOOD_CHANGE_SUCCESSFUL_TASK_MINOR = 3  # e.g. gathering one unit of resource
MOOD_CHANGE_FAILED_TASK = -5
MOOD_CHANGE_NEED_CRITICAL = -8         # Per critical need, per check
MOOD_CHANGE_NEED_FULFILLED_FROM_CRITICAL = 10
MOOD_CHANGE_NEED_FULFILLED = 4
MOOD_CHANGE_TOOL_BROKE = -7
MOOD_CHANGE_RECEIVED_WARNING = -15
MOOD_CHANGE_FIRED = -50
MOOD_CHANGE_PROMOTED = 20 # Example for future use
MOOD_CHANGE_NEW_FRIEND = 10 # Example for future use
MOOD_CHANGE_GOT_PAID = 2 # A small boost for getting paid for work

# Mood Effects (Examples - can be tuned)
# Productivity: 1.0 is baseline.
MOOD_EFFECT_PRODUCTIVITY = {
    "Ecstatic": 1.2,
    "Happy": 1.1,
    "Content": 1.05,
    "Neutral": 1.0,
    "Displeased": 0.9,
    "Sad": 0.75,
    "Stressed": 0.8,
    "Furious": 0.5 # Hard to work when furious
}

# Social Success Chance Modifier (additive: +0.1 means +10% chance)
MOOD_EFFECT_SOCIAL_SUCCESS_MOD = {
    "Ecstatic": 0.15,
    "Happy": 0.1,
    "Content": 0.05,
    "Neutral": 0.0,
    "Displeased": -0.05,
    "Sad": -0.1,
    "Stressed": -0.1,
    "Furious": -0.25
}

# Chance to initiate specific mood-driven goals (if mood is very low/high)
MOOD_DRIVEN_GOAL_CHANCE = 0.1 # e.g. 10% chance per tick if mood is extreme

# Relationship System Configs
RELATIONSHIP_SCORE_MIN = -100
RELATIONSHIP_SCORE_MAX = 100
RELATIONSHIP_SCORE_NEUTRAL_START = 0
RELATIONSHIP_SCORE_FAMILY_BASE = 50 # Family members start with a significant positive bias

# Reputation System Configs (Basic)
REPUTATION_SCORE_MIN = -100
REPUTATION_SCORE_MAX = 100
REPUTATION_CHANGE_HELPED_OTHER = 2
REPUTATION_CHANGE_APOLOGY_ACCEPTED = 1
REPUTATION_CHANGE_FIRED = -5
REPUTATION_EFFECT_ON_INITIAL_RELATIONSHIP = 0.1 # e.g. 10 reputation = +1 initial relationship score
REPUTATION_EFFECT_ON_WILLINGNESS_TO_HELP = 0.005 # e.g. 10 reputation = +0.05 to willingness chance

# Relationship Tiers (Score Thresholds - lower bound for each tier)
# Order matters for get_relationship_tier lookup (highest score first)
RELATIONSHIP_TIERS = [
    ("Soulmate", 90), # Example, could be special romantic partner tier
    ("Close Friend", 70),
    ("Friend", 40),
    ("Friendly Acquaintance", 15),
    ("Neutral", -15),
    ("Disliked", -40),
    ("Rival", -70),
    ("Archenemy", -90) # Lowest numerical bound, anything below is Archenemy
]
# Special Tiers (not score-based, but set directly)
RELATIONSHIP_TIER_FAMILY = "Family"
RELATIONSHIP_TIER_STRANGER = "Stranger" # For characters not in relationships dict yet

# Social Interaction Modifiers based on Relationship Tier (example for 'Ask for Help' success chance)
# Values are additive modifiers to a base success chance.
RELATIONSHIP_ASK_FOR_HELP_MODIFIERS = {
    "Soulmate": 0.40,
    "Close Friend": 0.30,
    "Friend": 0.20,
    "Friendly Acquaintance": 0.10,
    "Neutral": 0.0,
    "Disliked": -0.15,
    "Rival": -0.30,
    "Archenemy": -0.50,
    "Family": 0.35, # Family usually very willing
    "Stranger": -0.10 # Less likely to help a stranger
}

# Relationship point changes from interactions might be scaled by existing tier
# Example: A successful "Offer Comfort" to a "Friend" might be +5, but to a "Rival" might be +2 (harder to improve bad relations)
# This can be implemented in the _execute methods directly.

# Family Dynamics
FAMILY_RELATIONSHIP_SPLASH_FACTOR = 0.25 # How much of a relationship change is "splashed" to family members

# Rumor System Configs
RUMOR_STRENGTH_DECAY_DAILY = 5 # How much strength a rumor loses each day
MIN_RUMOR_STRENGTH_TO_SPREAD = 10 # Rumor must have at least this strength to be considered for spreading
RUMOR_MAX_STRENGTH = 100
RUMOR_INITIAL_STRENGTH_SMALL_EVENT = 30  # e.g., for an accepted apology
RUMOR_INITIAL_STRENGTH_SIGNIFICANT_EVENT = 60 # e.g., for being fired, or a major heroic act
REPUTATION_FOR_RUMOR_THRESHOLD = 3 # Minimum absolute reputation change to potentially start a rumor (e.g. if rep changes by +/-3 or more)
RUMOR_SPREAD_STRENGTH_INCREASE = 10 # How much strength a rumor gains when successfully spread
RUMOR_SPREAD_CHANCE_BASE = 0.1 # Base chance to spread a rumor during certain social interactions
RUMOR_SPREAD_CHATTY_BONUS = 0.15 # Additional chance if character is "Chatty"
RUMOR_OPINION_EFFECT_STRENGTH_FACTOR = 0.1 # e.g. rumor strength 50 * 0.1 = 5 opinion points
MIN_RUMOR_STRENGTH_FOR_OPINION_EFFECT = 20 # Rumor needs this strength to affect opinion
MAX_OPINION_CHANGE_FROM_RUMOR = 5 # Max opinion points a single rumor instance can change
DAILY_RUMOR_SPREAD_ATTEMPTS = 3 # How many passive rumor propagation attempts occur each day
RUMOR_PASSIVE_RELATIONSHIP_POSITIVE = 3 # Relationship boost towards the subject when a positive rumor spreads passively
RUMOR_PASSIVE_RELATIONSHIP_NEGATIVE = -4 # Relationship change towards the subject for negative rumors shared passively
RUMOR_PASSIVE_SUBJECT_REACTION_BONUS = 1 # How the subject feels about listeners believing a positive story
RUMOR_PASSIVE_SUBJECT_REACTION_PENALTY = -2 # How the subject reacts when others believe a negative tale about them

# Complex Needs System
HUNGER_THRESHOLD_EAT = 45 # Below this, character will try to eat
THIRST_THRESHOLD_DRINK = 60 # Below this, characters will seek water
ENERGY_THRESHOLD_REST = 45 # Below this, characters look for rest
ENERGY_THRESHOLD_FULLY_RESTED = 92 # Energy level that ends resting behavior
ENERGY_REST_GAIN_PER_TICK = 6 # How much energy is restored per rest tick
ENERGY_PASSIVE_RECOVERY_WHILE_IDLE = 1 # Minor energy recovered when idle and safe
HUNGER_DECAY_RATE_PER_TICK = 0.5 # How much hunger decays each tick
NEED_SCORE_MIN = 0
NEED_SCORE_MAX = 100
NEED_SAFETY_DEFAULT = 70
NEED_BELONGING_DEFAULT = 60 # Social is primary, this is a deeper sense of community
NEED_ESTEEM_DEFAULT = 50

NEED_SAFETY_DECAY_DAILY = 3
NEED_BELONGING_DECAY_DAILY = 5 # Decays a bit faster, encouraging social upkeep
NEED_ESTEEM_DECAY_DAILY = 2

# Environment-to-Consumption Coupling
ENVIRONMENT_SCARCITY_CONSUMPTION_SCALE = 0.75 # How aggressively low yields increase daily ration demand
ENVIRONMENT_ABUNDANCE_CONSUMPTION_SCALE = 0.4 # How much plentiful yields lower daily ration demand
ENVIRONMENT_SCARCITY_MOOD_PENALTY = -4 # Mood impact when rations are stretched due to scarcity
ENVIRONMENT_ABUNDANCE_MOOD_BONUS = 2 # Mood boost when abundance makes meals generous
ENVIRONMENT_CONSUMPTION_MINIMUM = 1 # Never consume fewer than this many rations per citizen

# Critical Thresholds for Needs (when they start causing significant mood/behavioral changes)
NEED_SAFETY_CRITICAL_THRESHOLD = 20
NEED_BELONGING_CRITICAL_THRESHOLD = 25
NEED_ESTEEM_CRITICAL_THRESHOLD = 15

# Mood changes related to complex needs
MOOD_CHANGE_SAFETY_CRITICAL = -12
MOOD_CHANGE_BELONGING_CRITICAL = -10
MOOD_CHANGE_ESTEEM_CRITICAL = -8
MOOD_CHANGE_SAFETY_FULFILLED = 10      # When safety significantly improves from low
MOOD_CHANGE_BELONGING_FULFILLED = 8    # When belonging significantly improves
MOOD_CHANGE_ESTEEM_FULFILLED = 7       # When esteem significantly improves
