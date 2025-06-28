# game/config.py
# LLM Integration Settings
USE_LLM = False  # Set to True to attempt to use a real LLM
LLM_ENDPOINT = "http://localhost:11434/api/generate"  # Example for Ollama
LLM_MODEL = "llama2"  # Specify the model you want to use with Ollama
LLM_HAS_THINKING_TAGS = False # Set to True if your model uses <thinking>...</thinking> tags

# Other game settings (can be added later)
# e.g., TICKS_PER_DAY = 10
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
SOCIAL_INTERACTION_CHANCE = 0.02 # Chance per tick (if idle/wandering) to initiate a social interaction like greeting
