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
