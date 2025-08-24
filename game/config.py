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

# Other game settings (can be added later)
STALE_THRESHOLD_DAYS = 2 # Days after which ledger data is considered stale for manager decisions
MANAGEMENT_REVIEW_INTERVAL_DAYS = 5 # How often managers review subordinates
FIRING_WARNING_THRESHOLD = 3 # Number of warnings before firing is likely

# Skill System
BASE_EXP_TO_NEXT_LEVEL = 50.0
EXP_LEVEL_SCALING_FACTOR = 1.5

# Mayor Specific Configs (Initial placeholders)
MAYOR_RESOURCE_LOW_THRESHOLD = 20  # Example: Mayor concerned if key resource drops below this
MAYOR_RESOURCE_HIGH_THRESHOLD = 150 # Example: Mayor notes abundance if key resource is above this

# Medical System Configs (Initial Placeholders)
MEDICAL_SUPPLY_LOW_THRESHOLD = 5 # Example: CMO concerned if Herbs/Bandages drop below this

# Governance Configs
ELECTION_CYCLE_DAYS = 30 # How often mayoral elections are held

# Social Interaction
REACTIVE_SOCIAL_BASE_CHANCE = 0.05 # Base chance to react to someone's state (e.g., offer comfort)
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
MOOD_CHANGE_TOOL_BROKE = -7
MOOD_CHANGE_RECEIVED_WARNING = -15
MOOD_CHANGE_FIRED = -50
MOOD_CHANGE_PROMOTED = 20 # Example for future use
MOOD_CHANGE_NEW_FRIEND = 10 # Example for future use

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

# Trait System Configs
# These are chances (0.0 to 1.0) for certain traits to trigger their effects each tick.
LAZY_TRAIT_SKIP_CHANCE = 0.25       # Chance for a Lazy character to do no work on a tick
DILIGENT_TRAIT_BONUS_CHANCE = 0.25  # Chance for a Diligent character to get extra work progress
CARELESS_TRAIT_MISHAP_CHANCE = 0.1  # Chance for a Careless character to wear down tools faster or make mistakes
STRONG_TRAIT_BONUS_YIELD_CHANCE = 0.2 # Chance for a Strong character to get extra resources

# Rumor System Configs
RUMOR_STRENGTH_DECAY_DAILY = 5 # How much strength a rumor loses each day
MIN_RUMOR_STRENGTH_TO_SPREAD = 10 # Rumor must have at least this strength to be considered for spreading
RUMOR_MAX_STRENGTH = 100
RUMOR_INITIAL_STRENGTH_SMALL_EVENT = 30  # e.g., for an accepted apology
RUMOR_INITIAL_STRENGTH_SIGNIFICANT_EVENT = 60 # e.g., for being fired, or a major heroic act
REPUTATION_FOR_RUMOR_THRESHOLD = 3 # Minimum absolute reputation change to potentially start a rumor (e.g. if rep changes by +/-3 or more)
RUMOR_SPREAD_CHANCE_BASE = 0.1 # Base chance to spread a rumor during certain social interactions
RUMOR_SPREAD_CHATTY_BONUS = 0.15 # Additional chance if character is "Chatty"
RUMOR_OPINION_EFFECT_STRENGTH_FACTOR = 0.1 # e.g. rumor strength 50 * 0.1 = 5 opinion points
MIN_RUMOR_STRENGTH_FOR_OPINION_EFFECT = 20 # Rumor needs this strength to affect opinion
MAX_OPINION_CHANGE_FROM_RUMOR = 5 # Max opinion points a single rumor instance can change

# Complex Needs System
NEED_SCORE_MIN = 0
NEED_SCORE_MAX = 100
NEED_SAFETY_DEFAULT = 70
NEED_BELONGING_DEFAULT = 60 # Social is primary, this is a deeper sense of community
NEED_ESTEEM_DEFAULT = 50

NEED_SAFETY_DECAY_DAILY = 3
NEED_BELONGING_DECAY_DAILY = 5 # Decays a bit faster, encouraging social upkeep
NEED_ESTEEM_DECAY_DAILY = 2

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
