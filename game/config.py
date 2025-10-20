# game/config.py
# LLM Integration Settings
USE_LLM = False  # Set to True to attempt to use a real LLM
LLM_ENDPOINT = "http://localhost:11434/api/generate"  # Example for Ollama
LLM_MODEL = "llama2"  # Specify the model you want to use with Ollama
LLM_HAS_THINKING_TAGS = False # Set to True if your model uses <thinking>...</thinking> tags

# General Game Settings
TICKS_PER_DAY = 1
DAYS_PER_SEASON = 10 # Example, can be adjusted
MAX_SIMULATION_DAYS = 1 # Max days the simulation runs for in headless/test mode.

# Navigation & movement
IMPASSABLE_TERRAINS = {"Mountain", "Water", "DeepWater", "Chasm", "Void"}

# World Map Generation
MAP_DEFAULT_SIZE = (500, 500)
MAP_RANDOM_SEED = None  # Set to an int to make initial landscapes deterministic
MAP_GENERATION_DISABLED = False
MAP_RESERVED_CLEARING_RADIUS = 2
MAP_EDGE_BUFFER = 1
MAP_FEATURE_MARGIN = 1
MAP_RESERVED_COORDS = []

MAP_TERRAIN_FEATURES = [
    {
        "key": "water",
        "tile": "Water",
        "clusters": (2, 3),
        "radius": (3, 4),
        "scatter": (1, 2),
        "roughness": 0.45,
        "preserve_tiles": ["Water", "DeepWater"],
        "allow_overwrite": True,
    },
    {
        "key": "forest",
        "tile": "Forest",
        "clusters": (4, 6),
        "radius": (3, 4),
        "scatter": (1, 2),
        "roughness": 0.35,
        "avoid_tiles": ["Water", "DeepWater"],
    },
    {
        "key": "meadow",
        "tile": "Meadow",
        "clusters": (3, 4),
        "radius": (2, 3),
        "scatter": (1, 2),
        "roughness": 0.4,
        "avoid_tiles": ["Water", "DeepWater"],
    },
    {
        "key": "rockfield",
        "tile": "Rocks",
        "clusters": (2, 3),
        "radius": (2, 3),
        "scatter": 1,
        "roughness": 0.5,
        "avoid_tiles": ["Water", "DeepWater"],
    },
]

MAP_SCATTERED_TILES = [
    {"tile": "Clearing", "count": (12, 18), "avoid_tiles": ["Water", "DeepWater"]},
    {"tile": "Path", "count": (18, 26), "avoid_tiles": ["Water", "DeepWater"]},
]

MAP_RESOURCE_CLUSTERS = [
    {
        "resource": "Wood",
        "tile": "Wood",
        "clusters": (6, 8),
        "radius": (2, 3),
        "scatter": 1,
        "density": (6, 9),
        "prefer_feature": "forest",
        "base_tiles": ["Forest"],
    },
    {
        "resource": "Stone",
        "tile": "Stone",
        "clusters": (3, 4),
        "radius": (1, 2),
        "scatter": 1,
        "density": (4, 6),
        "prefer_feature": "rockfield",
        "base_tiles": ["Rocks", "Stone"],
    },
    {
        "resource": "Herbs",
        "tile": "Herbs",
        "clusters": (3, 4),
        "radius": (1, 2),
        "scatter": 1,
        "density": (4, 7),
        "prefer_feature": "meadow",
        "base_tiles": ["Meadow"],
        "allow_base_conversion": True,
        "paint_tile": "Meadow",
    },
    {
        "resource": "Food",
        "tile": "Fields",
        "clusters": (3, 4),
        "radius": (1, 2),
        "scatter": 1,
        "density": (5, 9),
        "base_tiles": ["Fields", "Meadow", "Grass"],
        "allow_base_conversion": True,
        "paint_tile": "Fields",
        "feature_key": "farmland",
    },
    {
        "resource": "Water",
        "tile": "Water",
        "clusters": (2, 3),
        "radius": (1, 2),
        "scatter": 0,
        "density": (3, 5),
        "prefer_feature": "water",
        "base_tiles": ["Water"],
        "allow_base_conversion": False,
    },
]

STRUCTURE_FOUNDATION_TILE = "Flagstone"

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

# Wealth & Business Simulation
WEALTH_HISTORY_MAX_ENTRIES = 45
WEALTH_STATUS_THRESHOLDS = {
    "destitute": 5,
    "modest": 20,
    "comfortable": 55,
    "prosperous": 110,
}
WEALTH_JEALOUSY_THRESHOLD = 35
WEALTH_JEALOUSY_RELATIONSHIP_HIT = -3
WEALTH_JEALOUSY_MOOD_PENALTY = -4
WEALTH_RESPECT_RELATIONSHIP_BONUS = 2
RETIREMENT_MIN_AGE = 55
RETIREMENT_WEALTH_THRESHOLD = 80
RETIREMENT_PERSONALITIES = ["Stoic", "Introspective", "Compassionate"]
RETIREMENT_DAILY_CHANCE = 0.25
NOBILITY_WEALTH_THRESHOLD = 160
NOBILITY_TITLE = "Noble Lord"
BUSINESS_INCOME_MOOD_BONUS = 2
BUSINESS_START_MIN_FUNDS = 45
BUSINESS_STARTUP_COST = 30
BUSINESS_MAX_OWNERSHIP = 2
BUSINESS_OWNER_DRAW = 6
BUSINESS_EMPLOYEE_WAGE = 4
BUSINESS_BASE_OPERATING_COST = 3
BUSINESS_CAPITAL_RETENTION = 0.55
BUSINESS_CAPITAL_PROFIT_FACTOR = 0.08
BUSINESS_DAILY_REVENUE_RANGE = (5, 13)
BUSINESS_REVENUE_VARIANCE = 0.25
BUSINESS_FAILURE_THRESHOLD = -18
BUSINESS_RECOVERY_BONUS = 0.12
BUSINESS_NETWORTH_MULTIPLIER = 1.2
BUSINESS_MAX_EMPLOYEES = 4
BUSINESS_REPUTATION_BONUS = 3
ENTREPRENEURIAL_PERSONALITIES = ["Ambitious", "Pragmatic", "Cheerful"]
ENTREPRENEURIAL_TRAITS = ["Resourceful", "Organized"]
BUSINESS_TEMPLATES = [
    {
        "key": "market_stall",
        "display_name": "Market Stall",
        "industry": "trade",
        "startup_cost": 24,
        "base_capital": 20,
        "revenue_range": (4, 9),
    },
    {
        "key": "artisan_workshop",
        "display_name": "Artisan Workshop",
        "industry": "crafting",
        "startup_cost": 30,
        "base_capital": 24,
        "revenue_range": (6, 12),
    },
    {
        "key": "wayside_tavern",
        "display_name": "Wayside Tavern",
        "industry": "hospitality",
        "startup_cost": 36,
        "base_capital": 28,
        "revenue_range": (7, 14),
    },
    {
        "key": "lumber_cooperative",
        "display_name": "Lumber Cooperative",
        "industry": "lumberworks",
        "startup_cost": 32,
        "base_capital": 26,
        "revenue_range": (6, 13),
    },
    {
        "key": "stonecutters_guild",
        "display_name": "Stonecutters' Guild",
        "industry": "stoneworks",
        "startup_cost": 34,
        "base_capital": 27,
        "revenue_range": (6, 12),
    },
    {
        "key": "village_apothecary",
        "display_name": "Village Apothecary",
        "industry": "herbalist",
        "startup_cost": 28,
        "base_capital": 22,
        "revenue_range": (5, 11),
    },
]

BUSINESS_INDUSTRY_PROFILES = {
    "trade": {
        "inputs": {},
        "restock_days": 1,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.4,
        "skill_weights": {"Leadership": 0.5, "Diplomacy": 0.5},
        "skill_target": 8.0,
        "skill_weight": 0.35,
        "supply_weight": 0.15,
        "base_efficiency": 0.95,
        "efficiency_floor": 0.65,
        "efficiency_ceiling": 1.35,
        "sale_value_multiplier": 1.05,
        "sale_value_per_cycle": 0,
        "procurement_cost_multiplier": 0.15,
    },
    "crafting": {
        "inputs": {"Lumber": 2},
        "outputs": {"Furniture": 1},
        "restock_days": 2,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.6,
        "skill_weights": {"Carpentry": 1.0},
        "skill_target": 8.0,
        "skill_weight": 0.5,
        "supply_weight": 0.65,
        "base_efficiency": 0.82,
        "efficiency_floor": 0.35,
        "efficiency_ceiling": 1.6,
        "sale_value_multiplier": 1.0,
        "sale_value_per_cycle": 0,
        "procurement_cost_multiplier": 0.35,
    },
    "hospitality": {
        "inputs": {"Food": 2, "Water": 1, "Herbs": 1},
        "restock_days": 2,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.4,
        "skill_weights": {"Cooking": 0.7, "Leadership": 0.3},
        "skill_target": 6.0,
        "skill_weight": 0.45,
        "supply_weight": 0.7,
        "base_efficiency": 0.78,
        "efficiency_floor": 0.3,
        "efficiency_ceiling": 1.5,
        "sale_value_multiplier": 0.0,
        "sale_value_per_cycle": 12,
        "procurement_cost_multiplier": 0.3,
    },
    "lumberworks": {
        "inputs": {"Wood": 3},
        "outputs": {"Lumber": 2},
        "restock_days": 3,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.75,
        "skill_weights": {"Woodcutting": 0.6, "Carpentry": 0.4},
        "skill_target": 7.0,
        "skill_weight": 0.45,
        "supply_weight": 0.75,
        "base_efficiency": 0.76,
        "efficiency_floor": 0.28,
        "efficiency_ceiling": 1.65,
        "sale_value_multiplier": 0.9,
        "sale_value_per_cycle": 0,
        "procurement_cost_multiplier": 0.25,
        "deposit_outputs": False,
    },
    "stoneworks": {
        "inputs": {"Stone": 3},
        "restock_days": 3,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.6,
        "skill_weights": {"Masonry": 0.8, "Leadership": 0.2},
        "skill_target": 7.0,
        "skill_weight": 0.4,
        "supply_weight": 0.7,
        "base_efficiency": 0.74,
        "efficiency_floor": 0.25,
        "efficiency_ceiling": 1.55,
        "sale_value_multiplier": 0.0,
        "sale_value_per_cycle": 11,
        "procurement_cost_multiplier": 0.32,
    },
    "herbalist": {
        "inputs": {"Herbs": 2},
        "outputs": {"Bandages": 1},
        "restock_days": 2,
        "base_cycles": 1.0,
        "per_employee_cycles": 0.5,
        "skill_weights": {"Herbalism": 1.0},
        "skill_target": 6.0,
        "skill_weight": 0.55,
        "supply_weight": 0.6,
        "base_efficiency": 0.8,
        "efficiency_floor": 0.3,
        "efficiency_ceiling": 1.6,
        "sale_value_multiplier": 0.85,
        "sale_value_per_cycle": 4,
        "procurement_cost_multiplier": 0.28,
    },
}
JEALOUSY_THEFT_PRESSURE = 0.25

RESIDENTIAL_TIER_BLUEPRINTS = [
    {"status": "destitute", "blueprint": "wooden_hut"},
    {"status": "modest", "blueprint": "wooden_hut"},
    {"status": "comfortable", "blueprint": "stone_cottage"},
    {"status": "prosperous", "blueprint": "merchant_manor"},
    {"status": "noble", "blueprint": "noble_estate"},
]
RESIDENTIAL_TIER_PRIORITY = {
    "noble": 0,
    "prosperous": 1,
    "comfortable": 2,
    "modest": 3,
    "destitute": 4,
}
RESIDENTIAL_FALLBACK_TIER = "modest"
RESIDENTIAL_ANCHOR = (4, 4)

HOUSEHOLD_STYLE_MOMENTS = {
    "general": [
        {
            "group_summary": "shared a humble meal and spoke of the day's work",
            "solo_summary": "took a quiet moment to plan the days ahead",
            "memory": "Quiet evening",
            "mood_bonus": 2,
            "belonging_bonus": 2,
        }
    ],
    "hearthfire": [
        {
            "group_summary": "gathered around the hearth to savor a pot of stew",
            "solo_summary": "kept the hearth embers alive for tomorrow",
            "memory": "Hearthside evening",
            "mood_bonus": 4,
            "belonging_bonus": 6,
        },
        {
            "group_summary": "sang low songs while patching worn cloaks",
            "solo_summary": "hummed a folk tune to chase away the chill",
            "memory": "Songs by the fire",
            "mood_bonus": 3,
            "belonging_bonus": 4,
        },
    ],
    "artisan": [
        {
            "group_summary": "reviewed the day's craftwork and shared tips over bread",
            "solo_summary": "sketched tomorrow's designs beside the embers",
            "memory": "Workshop reflections",
            "mood_bonus": 3,
            "belonging_bonus": 3,
            "esteem_bonus": 2,
        },
        {
            "group_summary": "played a quick game of stones and laughed at close calls",
            "solo_summary": "sorted materials and admired careful handiwork",
            "memory": "Friendly games",
            "mood_bonus": 4,
            "belonging_bonus": 2,
        },
    ],
    "mercantile": [
        {
            "group_summary": "hosted guests in the parlor to trade tales and favors",
            "solo_summary": "balanced the ledgers in a quiet study",
            "memory": "Parlor conversations",
            "mood_bonus": 3,
            "belonging_bonus": 3,
            "esteem_bonus": 2,
        },
        {
            "group_summary": "planned new ventures over a rich supper spread",
            "solo_summary": "drafted trade letters deep into the night",
            "memory": "Ambitious plotting",
            "mood_bonus": 4,
            "belonging_bonus": 2,
            "esteem_bonus": 3,
        },
    ],
    "noble": [
        {
            "group_summary": "hosted a salon in the grand hall to debate governance",
            "solo_summary": "walked the marble hallways in thoughtful solitude",
            "memory": "Grand hall gathering",
            "mood_bonus": 5,
            "belonging_bonus": 3,
            "esteem_bonus": 3,
        },
        {
            "group_summary": "toured the library and shared verses of treasured tomes",
            "solo_summary": "studied histories beneath gilded lanterns",
            "memory": "Library stroll",
            "mood_bonus": 4,
            "belonging_bonus": 2,
            "esteem_bonus": 4,
        },
    ],
}

HOUSEHOLD_COMFORT_MAX = 100.0
HOUSEHOLD_COMFORT_DECAY_BASE = 1.4
HOUSEHOLD_COMFORT_EMPTY_DECAY = 2.5
HOUSEHOLD_COMFORT_GOOD_THRESHOLD = 62.0
HOUSEHOLD_COMFORT_RULES = [
    {
        "key": "hearth_fire",
        "name": "Keep the Hearth",
        "resource": "Wood",
        "base_amount": 1.0,
        "per_resident": 0.5,
        "minimum": 1,
        "interval_days": 1,
        "style_multipliers": {"hearthfire": 1.2, "artisan": 1.0, "mercantile": 0.85, "noble": 0.7},
        "tier_multipliers": {"prosperous": 1.15, "noble": 1.3},
        "success_ratio": 0.75,
        "comfort_gain": 14.0,
        "comfort_penalty": 12.0,
        "decay": 3.0,
        "mood_bonus": 4,
        "mood_penalty": -6,
        "need_bonus": {"Belonging": 4, "Safety": 3},
        "need_penalty": {"Belonging": -6, "Safety": -6},
        "success_memory": "Enjoyed a warm hearth inside {building}.",
        "partial_memory": "Shared embers to stretch the hearth fire in {building}.",
        "failure_memory": "Shivered through the night in {building} after the fire died.",
    },
    {
        "key": "fine_furnishings",
        "name": "Refresh Furnishings",
        "resource": "Furniture",
        "base_amount": 0.0,
        "per_resident": 0.25,
        "minimum": 1,
        "interval_days": 4,
        "tier_multipliers": {"comfortable": 0.9, "prosperous": 1.35, "noble": 1.6},
        "success_ratio": 0.6,
        "comfort_gain": 16.0,
        "comfort_penalty": 10.0,
        "decay": 2.0,
        "mood_bonus": 3,
        "mood_penalty": -4,
        "need_bonus": {"Esteem": 4},
        "need_penalty": {"Esteem": -5},
        "success_memory": "Polished the furnishings of {building} and felt proud of the home.",
        "partial_memory": "Managed a token tidy-up in {building}, but finer touches are lacking.",
        "failure_memory": "Furniture in {building} has gone shabby—spirits fell.",
    },
]

NEIGHBORHOOD_BLOCK_SIZE = 6
NEIGHBORHOOD_MIN_HOUSEHOLDS = 2
NEIGHBORHOOD_GATHERING_BASE_CHANCE = 0.35
NEIGHBORHOOD_SPIRIT_WEIGHT = 0.45
NEIGHBORHOOD_EXTRA_HOUSEHOLD_BONUS = 0.04
NEIGHBORHOOD_MOMENTS = {
    "general": [
        {
            "summary": "Neighbors along {neighborhood} shared a potluck outside {host}.",
            "memory": "Neighborhood potluck",
            "mood_bonus": 3,
            "belonging_bonus": 4,
            "spirit_delta": 0.02,
        },
        {
            "summary": "{attendee_count} villagers swapped stories by lantern light near {host} in {neighborhood}.",
            "memory": "Lantern stories",
            "mood_bonus": 2,
            "belonging_bonus": 3,
            "esteem_bonus": 1,
            "spirit_delta": 0.015,
        },
    ],
    "hearthfire": [
        {
            "summary": "{host_name} invited the lane for ember-warm ballads in {neighborhood} outside {host}.",
            "memory": "Firelit ballads",
            "mood_bonus": 4,
            "belonging_bonus": 5,
            "spirit_delta": 0.025,
        },
        {
            "summary": "Families gathered around {host} in {neighborhood} to roast root vegetables and share blessings.",
            "memory": "Roasted roots",
            "mood_bonus": 3,
            "belonging_bonus": 4,
            "esteem_bonus": 1,
            "spirit_delta": 0.02,
        },
    ],
    "artisan": [
        {
            "summary": "Craftsfolk lined the stoops near {host} in {neighborhood} to compare handiwork and trade tips.",
            "memory": "Craft stoop circle",
            "mood_bonus": 3,
            "belonging_bonus": 3,
            "esteem_bonus": 2,
            "spirit_delta": 0.02,
        },
        {
            "summary": "Sketchbooks and samples filled the tables as neighbors gathered at {host} in {neighborhood} for a maker's critique.",
            "memory": "Maker's critique",
            "mood_bonus": 2,
            "belonging_bonus": 2,
            "esteem_bonus": 3,
            "spirit_delta": 0.018,
        },
    ],
    "mercantile": [
        {
            "summary": "Merchants staged a curbside tasting outside {host} in {neighborhood}, bartering delights and news.",
            "memory": "Curbside tasting",
            "mood_bonus": 3,
            "belonging_bonus": 2,
            "esteem_bonus": 2,
            "spirit_delta": 0.02,
        },
        {
            "summary": "Ledgers and laughter mingled as {attendee_count} entrepreneurs met outside {host} in {neighborhood} to plot ventures.",
            "memory": "Merchant moot",
            "mood_bonus": 2,
            "belonging_bonus": 2,
            "esteem_bonus": 3,
            "spirit_delta": 0.018,
        },
    ],
    "noble": [
        {
            "summary": "{host_name} opened the courtyard of {host} in {neighborhood} for a lantern promenade and policy debate.",
            "memory": "Lantern promenade",
            "mood_bonus": 4,
            "belonging_bonus": 3,
            "esteem_bonus": 4,
            "spirit_delta": 0.03,
        },
        {
            "summary": "Envoys and nobles convened at {host} in {neighborhood} for a tasting of cellar reserves and whispered alliances.",
            "memory": "Cellar conclave",
            "mood_bonus": 3,
            "belonging_bonus": 2,
            "esteem_bonus": 4,
            "spirit_delta": 0.028,
        },
    ],
}

# Career & Profession Simulation
CAREER_DEFAULT_STAGE = "Apprentice"
CAREER_STAGE_THRESHOLDS = {
    "Apprentice": 0,
    "Journeyman": 3,
    "Master": 6,
    "Luminary": 9,
}
CAREER_STAGE_REPUTATION_BONUS = {
    "Journeyman": 1,
    "Master": 2,
    "Luminary": 3,
}
CAREER_SATISFACTION_BASELINE = 0.62
CAREER_SATISFACTION_DECAY = 0.05
CAREER_SATISFACTION_GAIN = 0.08
CAREER_IDLE_DECAY = 0.04
CAREER_WEALTH_SATISFACTION_BONUS = 0.08
CAREER_WEALTH_SATISFACTION_PENALTY = 0.1
CAREER_SATISFACTION_MOOD_BONUS = 6
CAREER_SATISFACTION_MOOD_PENALTY = -8
CAREER_BURNOUT_THRESHOLD = 0.35
CAREER_AMBITION_THRESHOLD = 0.85
CAREER_PROGRESS_PATIENCE_DAYS = 10
CAREER_MAX_HISTORY = 16
CAREER_TENURE_MILESTONES = [10, 30, 90]
CAREER_PERSONALITY_MODIFIERS = {
    "Ambitious": {"promotion_pressure": 0.18, "satisfaction_bonus": 0.02},
    "Stoic": {"stability_bonus": 0.05},
    "Pragmatic": {"wealth_bonus": 0.04},
    "Cheerful": {"satisfaction_bonus": 0.04},
    "Introspective": {"learning_bonus": 0.1},
}
CAREER_TRAIT_MODIFIERS = {
    "Diligent": {"xp_bonus": 0.25, "satisfaction_floor": 0.2},
    "Resourceful": {"xp_bonus": 0.15},
    "Organized": {"promotion_pressure": -0.05, "satisfaction_bonus": 0.03},
    "Compassionate": {"service_bonus": 0.05},
    "Curious": {"learning_bonus": 0.08},
    "Patient": {"burnout_resistance": 0.1},
}
CAREER_FOCUS_MOOD_BONUS = {
    "service": 2,
    "leadership": 3,
    "craft": 2,
}
PROFESSION_TRACK_DEFINITIONS = {
    "Farmer": {"skill": "Farming", "daily_xp": 1.4, "wealth_expectation": "modest", "focus": "agrarian"},
    "Woodcutter": {"skill": "Woodcutting", "daily_xp": 1.5, "wealth_expectation": "modest", "focus": "lumber"},
    "Stonemason": {"skill": "Stonemasonry", "daily_xp": 1.5, "wealth_expectation": "comfortable", "focus": "stone"},
    "Hunter": {"skill": "Hunting", "daily_xp": 1.45, "wealth_expectation": "comfortable", "focus": "agrarian"},
    "Herbalist": {"skill": "Herbalism", "daily_xp": 1.35, "wealth_expectation": "comfortable", "focus": "service"},
    "Builder": {"skill": "Construction", "daily_xp": 1.3, "wealth_expectation": "comfortable", "focus": "craft"},
    "Fletcher": {"skill": "Fletching", "daily_xp": 1.4, "wealth_expectation": "comfortable", "focus": "craft"},
    "Blacksmith": {"skill": "Blacksmithing", "daily_xp": 1.5, "wealth_expectation": "prosperous", "focus": "craft"},
    "Bookkeeper": {"skill": "Administration", "daily_xp": 1.2, "wealth_expectation": "comfortable", "focus": "service"},
    "Manager": {"skill": "Leadership", "daily_xp": 1.25, "wealth_expectation": "prosperous", "focus": "leadership"},
    "Chancellor": {"skill": "Leadership", "daily_xp": 1.3, "wealth_expectation": "prosperous", "focus": "leadership"},
    "Mayor": {"skill": "Leadership", "daily_xp": 1.35, "wealth_expectation": "prosperous", "focus": "leadership"},
    "Reeve": {"skill": "Leadership", "daily_xp": 1.3, "wealth_expectation": "prosperous", "focus": "leadership"},
    "Steward": {"skill": "Administration", "daily_xp": 1.25, "wealth_expectation": "prosperous", "focus": "service"},
    "Bailiff": {"skill": "Security", "daily_xp": 1.2, "wealth_expectation": "comfortable", "focus": "security"},
    "Sheriff": {"skill": "Security", "daily_xp": 1.4, "wealth_expectation": "prosperous", "focus": "security"},
    "Marshal": {"skill": "Security", "daily_xp": 1.4, "wealth_expectation": "prosperous", "focus": "security"},
    "Spymaster": {"skill": "Security", "daily_xp": 1.28, "wealth_expectation": "prosperous", "focus": "security"},
    "Deputy": {"skill": "Security", "daily_xp": 1.25, "wealth_expectation": "comfortable", "focus": "security"},
    "Scout": {"skill": "Scouting", "daily_xp": 1.3, "wealth_expectation": "modest", "focus": "agrarian"},
    "Militia Soldier": {"skill": "Security", "daily_xp": 1.2, "wealth_expectation": "modest", "focus": "security"},
    "Medic": {"skill": "Medicine", "daily_xp": 1.35, "wealth_expectation": "comfortable", "focus": "service"},
    "Chief Medical Officer": {"skill": "Medicine", "daily_xp": 1.4, "wealth_expectation": "prosperous", "focus": "service"},
    "default": {"skill": None, "daily_xp": 1.0, "wealth_expectation": "modest", "focus": "general"},
}

# Workforce & Logistics
DEFAULT_WORK_SHIFT_TICKS = 6
WORK_SHIFT_DEFINITIONS = {
    "logging": {
        "title": "Logging Crews",
        "jobs": ["Woodcutter"],
        "task": "Chop Wood",
        "resource": "Wood",
        "skill": "Woodcutting",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 6,
        "hauler_jobs": ["Builder"],
        "hauler_capacity": 12,
        "skill_yield_bonus": 0.12,
        "preferred_stockpiles": ["Lumber Yard", "Central Stockpile"],
    },
    "quarry": {
        "title": "Quarry Team",
        "jobs": ["Stonemason", "Miner"],
        "task": "Mine Stone",
        "resource": "Stone",
        "skill": "Mining",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 5,
        "hauler_jobs": ["Builder"],
        "hauler_capacity": 10,
        "skill_yield_bonus": 0.1,
        "preferred_stockpiles": ["Masonry Yard", "Central Stockpile"],
    },
    "fields": {
        "title": "Field Hands",
        "jobs": ["Farmer"],
        "task": "Tend Fields",
        "resource": "Food",
        "skill": "Farming",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 8,
        "hauler_jobs": ["Farmer"],
        "hauler_capacity": 8,
        "skill_yield_bonus": 0.1,
        "preferred_stockpiles": ["Granary", "Central Stockpile"],
    },
    "iron_mine": {
        "title": "Iron Miners",
        "jobs": ["Miner"],
        "task": "Mine Iron Ore",
        "resource": "Iron Ore",
        "skill": "Mining",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 4,
        "hauler_jobs": ["Miner", "Builder"],
        "hauler_capacity": 9,
        "skill_yield_bonus": 0.09,
        "preferred_stockpiles": ["Ore Yard", "Central Stockpile"],
    },
    "sawmill": {
        "title": "Sawmill Crew",
        "jobs": ["Sawyer"],
        "task": "Saw Lumber",
        "resource": "Lumber",
        "skill": "Carpentry",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 5,
        "hauler_jobs": ["Builder", "Laborer"],
        "hauler_capacity": 10,
        "skill_yield_bonus": 0.1,
        "inputs": {"Wood": 2},
        "preferred_stockpiles": ["Lumber Yard", "Central Stockpile"],
        "discrete_output": True,
    },
    "carpentry": {
        "title": "Carpenter's Shop",
        "jobs": ["Carpenter"],
        "task": "Assemble Furniture",
        "resource": "Furniture",
        "skill": "Carpentry",
        "shift_ticks": 6,
        "carry_capacity_per_worker": 4,
        "hauler_jobs": ["Laborer", "Builder"],
        "hauler_capacity": 8,
        "skill_yield_bonus": 0.11,
        "inputs": {"Lumber": 2},
        "preferred_stockpiles": ["Workshop Store", "Central Stockpile"],
        "discrete_output": True,
    },
}

# Training & Apprenticeships
TRAINING_ESTEEM_BOOST = 3
TRAINING_PROGRAM_DEFINITIONS = {
    "construction_basics": {
        "title": "Construction Basics Workshop",
        "skill": "Construction",
        "focus_jobs": ["Builder", "Master Craftsman"],
        "target_level": 2,
        "min_level": 0,
        "capacity": 3,
        "duration_days": 2,
        "daily_exp_gain": 6.5,
        "instructor_roles": ["Master Craftsman", "Manager"],
    },
    "field_agronomy": {
        "title": "Field Agronomy Clinic",
        "skill": "Farming",
        "focus_jobs": ["Farmer"],
        "target_level": 2,
        "min_level": 0,
        "capacity": 4,
        "duration_days": 3,
        "daily_exp_gain": 5.0,
        "instructor_roles": ["Farmer", "Chief Medical Officer"],
    },
    "triage_rotation": {
        "title": "Triage Rotation Drills",
        "skill": "Medicine",
        "focus_jobs": ["Medic", "Chief Medical Officer"],
        "target_level": 3,
        "min_level": 1,
        "capacity": 2,
        "duration_days": 3,
        "daily_exp_gain": 7.0,
        "instructor_roles": ["Chief Medical Officer"],
    },
}

# Cultural Life & Festivals
CULTURAL_SPIRIT_BASELINE = 0.45
CULTURAL_SPIRIT_DECAY = 0.02
CULTURAL_EVENT_LIBRARY = {
    "Spring": [
        {
            "key": "first_bloom_festival",
            "name": "First Bloom Festival",
            "anchor_day": 4,
            "duration": 2,
            "description": "Villagers braid garlands and share herbal tonics as the valley greens again.",
            "belonging_bonus": 12,
            "esteem_bonus": 4,
            "social_bonus": 10,
            "mood_bonus": 10,
            "community_spirit_delta": 0.12,
            "travel_speed_multiplier": 1.05,
            "market_price_adjustment": {"Herbs": 0.9, "Food": 0.95},
            "flavor": [
                "Herbalists exchange new remedies beside the communal fountain.",
                "Children chase ribbons beneath freshly hung wreaths.",
            ],
        },
        {
            "key": "planters_oath",
            "name": "Planters' Oath",
            "anchor_day": 7,
            "duration": 1,
            "description": "Farmers pledge to steward the fields and trade seedlings at the long tables.",
            "belonging_bonus": 8,
            "esteem_bonus": 3,
            "social_bonus": 6,
            "mood_bonus": 6,
            "community_spirit_delta": 0.08,
            "resource_yield_bonus": [{"resource": "Food", "multiplier": 1.1}],
            "flavor": [
                "Seed packets swap hands faster than scribes can tally pledges.",
                "Elders press soil blessings into eager apprentices' palms.",
            ],
        },
    ],
    "Summer": [
        {
            "key": "sunpeak_tourney",
            "name": "Sunpeak Tourney",
            "anchor_day": 4,
            "duration": 2,
            "description": "Friendly contests spill across the meadow while merchants hawk chilled cordials.",
            "belonging_bonus": 10,
            "esteem_bonus": 6,
            "social_bonus": 9,
            "mood_bonus": 12,
            "community_spirit_delta": 0.14,
            "travel_speed_multiplier": 1.08,
            "flavor": [
                "Crowds roar as archers loose volleys toward painted targets.",
                "Vendors ring bells, promising respite from the blazing sun.",
            ],
        },
        {
            "key": "river_revel",
            "name": "River Revel",
            "anchor_day": 8,
            "duration": 1,
            "description": "Lantern skiffs drift downstream while storytellers trade sailor myths.",
            "belonging_bonus": 9,
            "esteem_bonus": 4,
            "social_bonus": 8,
            "mood_bonus": 8,
            "community_spirit_delta": 0.1,
            "market_price_adjustment": {"Water": 0.92},
            "flavor": [
                "Musicians keep time with the river's current on hand drums and lutes.",
                "Families launch lanterns, whispering wishes into the warm night air.",
            ],
        },
    ],
    "Autumn": [
        {
            "key": "harvest_home",
            "name": "Harvest Home Supper",
            "anchor_day": 5,
            "duration": 2,
            "description": "A banquet of roasted roots and ciders thanks the hands that gathered the yield.",
            "belonging_bonus": 14,
            "esteem_bonus": 6,
            "social_bonus": 12,
            "mood_bonus": 12,
            "community_spirit_delta": 0.16,
            "market_price_adjustment": {"Food": 0.85},
            "resource_yield_bonus": [{"resource": "Food", "multiplier": 1.08}],
            "flavor": [
                "Tavern fiddlers strike quick reels while platters circle the square.",
                "Cellars open their casks to toast a season safely stored away.",
            ],
        },
        {
            "key": "lantern_vigil",
            "name": "Lantern Vigil",
            "anchor_day": 9,
            "duration": 1,
            "description": "Quiet processions honor ancestors as autumn fog rolls between cottages.",
            "belonging_bonus": 7,
            "esteem_bonus": 4,
            "social_bonus": 5,
            "mood_bonus": 6,
            "community_spirit_delta": 0.09,
            "flavor": [
                "A hush settles as bells toll through the misty hillside.",
                "Candles glow in every window, guiding travelers back to warmth.",
            ],
        },
    ],
    "Winter": [
        {
            "key": "deepwinter_gifts",
            "name": "Deepwinter Gift Exchange",
            "anchor_day": 3,
            "duration": 2,
            "description": "Neighbors craft tokens by hearthlight and share stews that chase away the chill.",
            "belonging_bonus": 13,
            "esteem_bonus": 5,
            "social_bonus": 10,
            "mood_bonus": 11,
            "community_spirit_delta": 0.15,
            "market_price_adjustment": {"Wood": 0.95, "Arrow Bundle": 1.05},
            "flavor": [
                "Laughter mingles with the crackle of pine logs in the gathering hall.",
                "Children dart between tables, arms overflowing with ribbons and sweets.",
            ],
        },
        {
            "key": "thaw_dreams",
            "name": "Thaw Dreams Council",
            "anchor_day": 7,
            "duration": 1,
            "description": "Citizens chart spring ambitions while mapmakers spread parchment across the dais.",
            "belonging_bonus": 9,
            "esteem_bonus": 5,
            "social_bonus": 7,
            "mood_bonus": 7,
            "community_spirit_delta": 0.11,
            "travel_speed_multiplier": 1.03,
            "flavor": [
                "Ideas for new workshops spark rapid sketches and eager applause.",
                "Cooks pass steaming mugs as debates over next season's plans grow lively.",
            ],
        },
    ],
}

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

# Leadership oversight tuning
LEADERSHIP_ROLE_TITLES = {
    "Mayor",
    "Chancellor",
    "Manager",
    "Militia Commander",
    "Marshal",
    "Sheriff",
    "Chief Medical Officer",
    "Reeve",
    "Steward",
    "Spymaster",
    "Noble Lord",
    "Baron",
    "Baroness",
    "Duke",
    "Duchess",
}
LEADERSHIP_OVERSIGHT_BASELINE = 0.35
LEADERSHIP_OVERSIGHT_SKILL_WEIGHT = 0.06
LEADERSHIP_OVERSIGHT_ACTION_WEIGHT = 0.2
LEADERSHIP_OVERSIGHT_RELATIONSHIP_WEIGHT = 0.2
LEADERSHIP_OVERSIGHT_PERSONALITY_BONUS = {
    "Charismatic": 0.05,
    "Resolute": 0.04,
    "Demanding": 0.03,
    "Aloof": -0.06,
    "Lenient": -0.04,
}
LEADERSHIP_OVERSIGHT_TRAIT_BONUS = {
    "Diligent": 0.08,
    "Organized": 0.05,
    "Strict": 0.03,
    "Careless": -0.08,
    "Lazy": -0.12,
}
LEADERSHIP_NEGLECT_THRESHOLD = 0.45
LEADERSHIP_CORRUPTION_THRESHOLD = 0.25
LEADERSHIP_HIGH_WATERMARK = 0.78
LEADERSHIP_SLACKING_BASE_CHANCE = 0.12
LEADERSHIP_ILLEGAL_BASE_CHANCE = 0.05
LEADERSHIP_ILLEGAL_PERSONALITY_MODIFIERS = {
    "Rebellious": 0.3,
    "Impulsive": 0.18,
    "Stoic": -0.12,
    "Aloof": 0.12,
    "Honorable": -0.3,
}
LEADERSHIP_ILLEGAL_TRAIT_MODIFIERS = {
    "Greedy": 0.4,
    "Devious": 0.35,
    "Honest": -0.45,
    "Diligent": -0.2,
    "Careless": 0.15,
}
LEADERSHIP_ILLEGAL_MAX_SKIM = 6
MOOD_CHANGE_MISCONDUCT_THRILL = 3
FIRING_WARNING_THRESHOLD = 3 # Number of warnings before firing is likely

# Military organization & external threats
MILITIA_STRUCTURE_DEFAULTS = {
    "readiness_baseline": 0.32,
    "squad_size": 6,
    "minimum_squads": 2,
    "skill_weight": 0.08,
    "captain_skill_weight": 0.05,
    "oversight_weight": 0.18,
    "persistence": 0.72,
    "max_skill_benchmark": 6.0,
    "alert_threshold": 0.45,
    "critical_threshold": 0.25,
}
MILITIA_SQUAD_ROLES = [
    "Militia Soldier",
    "Scout",
]
MILITIA_SECURITY_MODIFIER = 0.35

ENEMY_RAID_PROFILE = {
    "base_chance": 0.04,
    "readiness_factor": 0.7,
    "difficulty": 1.4,
    "severity_weights": {
        "skirmish": 0.55,
        "raid": 0.3,
        "onslaught": 0.15,
    },
    "severity_difficulty": {
        "skirmish": 0.8,
        "raid": 1.0,
        "onslaught": 1.35,
    },
    "resource_targets": ["Food", "Wood", "Stone", "Herbs"],
    "losses": {
        "skirmish": (1, 3),
        "raid": (3, 6),
        "onslaught": (6, 12),
    },
    "max_log_entries": 6,
}

# Skill System
BASE_EXP_TO_NEXT_LEVEL = 50.0
EXP_LEVEL_SCALING_FACTOR = 1.5

# Mayor Oversight Thresholds
MAYOR_RESOURCE_LOW_THRESHOLD = 20  # Mayor becomes concerned if key resources drop below this
MAYOR_RESOURCE_HIGH_THRESHOLD = 150 # Mayor recognizes an abundance when stores exceed this

# Governance & Law System
LAW_PETITION_CRIME_WINDOW = 6  # Days of incident history the mayor reviews when weighing petitions
LAW_PETITION_THRESHOLD = 3     # Minimum repeated incidents before citizens file a formal petition
LAW_BASE_FINE_AMOUNT = 15      # Default fine the mayor levies when enacting civic laws
LAW_SUPPORT_ESCALATION = 0.08  # Daily support drift for unattended petitions
LAW_INTERVIEW_SUPPORT_THRESHOLD = 0.45  # Petitions over this support will demand witness interviews
LAW_INTERVIEW_EVIDENCE_BONUS = 0.2      # Max evidence boost a strong interview can contribute
LAW_CASE_PREP_BASELINE = 0.35           # Minimum evidence strength a drafted law starts with

# Medical System Thresholds
MEDICAL_SUPPLY_LOW_THRESHOLD = 5 # Chief Medical Officer acts when medical supplies fall below this

# Health Simulation Defaults
HEALTH_PROFILE_DEFAULTS = {
    "base_vitality": 74,
    "vitality_variance": 6,
    "base_immunity": 0.6,
    "immunity_variance": 0.12,
    "base_stress": 0.18,
}
HEALTH_RECENT_EVENT_LIMIT = 10
HEALTH_NEED_THRESHOLDS = {
    "Hunger": 60,
    "Thirst": 60,
    "Energy": 55,
    "Safety": 65,
    "Belonging": 55,
}
HEALTH_NEED_RECOVERY_MARGIN = 18
HEALTH_VITALITY_NEED_WEIGHTS = {
    "Hunger": 6.0,
    "Thirst": 6.0,
    "Energy": 7.5,
    "Safety": 4.5,
    "Belonging": 3.5,
}
HEALTH_VITALITY_RECOVERY_BONUS = 2.6
HEALTH_STRESS_NEED_WEIGHT = 0.12
HEALTH_STRESS_RECOVERY_RATE = 0.08
HEALTH_IMMUNITY_VITALITY_WEIGHT = 0.32
HEALTH_IMMUNITY_STRESS_WEIGHT = 0.45
HEALTH_IMMUNITY_FLOOR = 0.05
HEALTH_IMMUNITY_CEILING = 0.95
HEALTH_VITALITY_FLOOR = 0.0
HEALTH_VITALITY_CEILING = 100.0
HEALTH_STRESS_FLOOR = 0.0
HEALTH_STRESS_CEILING = 1.0

HEALTH_SICKNESS_MODEL = {
    "base_chance": 0.008,
    "vitality_weight": 0.22,
    "immunity_weight": 0.35,
    "exposure_bonus": 0.06,
    "exposure_radius": 2,
    "severity_range": (1.0, 4.0),
    "worsen_threshold": 36,
    "worsen_chance": 0.18,
    "recovery_vitality": 70,
    "recovery_rate": 0.9,
    "recovery_immunity_bonus": 0.05,
}

HEALTH_INJURY_MODEL = {
    "base_chance": 0.0015,
    "job_risk": {
        "Builder": 0.003,
        "Woodcutter": 0.0035,
        "Stonemason": 0.0025,
        "Miner": 0.004,
        "Hunter": 0.003,
        "Militia": 0.0025,
    },
    "vitality_weight": 0.015,
    "severity_range": (1.0, 5.0),
    "worsen_threshold": 40,
    "worsen_chance": 0.14,
    "recovery_vitality": 68,
    "recovery_rate": 0.8,
}

HEALTH_CRITICAL_VITALITY = 32
HEALTH_CRITICAL_SEVERITY = 7.0

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

# Decision-Making Weights
DECISION_BASE_WEIGHTS = {
    "work_focus": 1.0,
    "social_focus": 1.0,
    "rest_threshold_adjustment": 0.0,
    "ask_for_help_multiplier": 1.0,
    "risk_modifier": 1.0,
}
DECISION_PERSONALITY_BIASES = {
    "Ambitious": {"work_focus": 0.25, "risk_modifier": 0.1},
    "Cautious": {"risk_modifier": -0.25, "rest_threshold_adjustment": 4.0},
    "Gregarious": {"social_focus": 0.35},
    "Stoic": {"social_focus": -0.2},
    "Nurturing": {"social_focus": 0.2, "ask_for_help_multiplier": 0.2},
    "Brooding": {"social_focus": -0.15, "rest_threshold_adjustment": 1.5},
}
DECISION_TRAIT_BIASES = {
    "Generous": {"ask_for_help_multiplier": 0.35},
    "Empathetic": {"social_focus": 0.25, "ask_for_help_multiplier": 0.25},
    "Organized": {"work_focus": 0.15},
    "Lazy": {"work_focus": -0.35, "rest_threshold_adjustment": 6.0},
    "Brave": {"risk_modifier": 0.25},
    "Hotheaded": {"risk_modifier": 0.15, "social_focus": -0.1},
    "Brooding": {"social_focus": -0.1, "rest_threshold_adjustment": 1.0},
}
DECISION_JOB_FOCUS = {
    "Builder": {"work_focus": 0.12},
    "Farmer": {"work_focus": 0.1},
    "Hunter": {"risk_modifier": 0.1},
    "Merchant": {"social_focus": 0.15},
    "Innkeeper": {"social_focus": 0.2},
    "Herbalist": {"ask_for_help_multiplier": 0.1, "rest_threshold_adjustment": -1.0},
    "Guard": {"risk_modifier": 0.15},
}
DECISION_MEMORY_LOOKBACK = 25
DECISION_MEMORY_KEYWORD_EFFECTS = {
    "completed": {"work_focus": 0.05},
    "boosted": {"work_focus": 0.04},
    "earned": {"work_focus": 0.04},
    "failed": {"work_focus": -0.06, "rest_threshold_adjustment": 1.5},
    "argument": {"social_focus": -0.06, "rest_threshold_adjustment": 1.5},
    "comfort": {"social_focus": 0.05, "ask_for_help_multiplier": 0.05},
    "rumor": {"social_focus": -0.02},
    "unsafe": {"risk_modifier": -0.12, "rest_threshold_adjustment": 2.0},
    "injured": {"risk_modifier": -0.15, "rest_threshold_adjustment": 2.5},
    "sick": {"risk_modifier": -0.15, "rest_threshold_adjustment": 2.5},
    "hungry": {"work_focus": -0.03, "ask_for_help_multiplier": 0.1},
    "enjoyed": {"social_focus": 0.04},
    "gathered": {"work_focus": 0.03},
}
DECISION_RELATIONSHIP_POSITIVE_THRESHOLD = 60
DECISION_RELATIONSHIP_NEGATIVE_THRESHOLD = -25
DECISION_RELATIONSHIP_POSITIVE_BONUS = 0.05
DECISION_RELATIONSHIP_NEGATIVE_PENALTY = -0.06
DECISION_RELATIONSHIP_STRESS_REST = 1.2
DECISION_SOCIAL_POSITIVE_WEIGHT = 0.6
DECISION_SOCIAL_NEGATIVE_WEIGHT = 0.6
DECISION_JOB_SATISFACTION_WEIGHT = 0.45
DECISION_BURNOUT_REST_BONUS = 3.5
DECISION_SOCIAL_FROM_WORK_DRAIN = 0.45
SAFETY_CRITICAL_WANDER_BASE_CHANCE = 0.3

# Personal Pursuits & Passions
PERSONAL_PURSUIT_SLOTS = 3
PERSONAL_PURSUIT_PROGRESS_PER_DAY = 0.22
PERSONAL_PURSUIT_NEED_GAIN_DEFAULT = 5
PERSONAL_PURSUIT_MOOD_BONUS_DEFAULT = 3
PERSONAL_PURSUIT_LOG_MAX = 18
PERSONAL_PURSUIT_ENGAGE_THRESHOLD = 0.65
PERSONAL_PURSUIT_LOW_ENERGY_THRESHOLD = 45
PERSONAL_PURSUIT_LOW_ENERGY_PENALTY = 0.45
PERSONAL_PURSUIT_NEED_DRIVE_THRESHOLD = 55
PERSONAL_PURSUIT_NEED_WEIGHT = 0.018
PERSONAL_PURSUIT_LOW_MOOD_THRESHOLD = -20
PERSONAL_PURSUIT_LOW_MOOD_BONUS = 0.3
PERSONAL_PURSUIT_STREAK_BONUS = 0.1
PERSONAL_PURSUIT_STREAK_PROGRESS_BONUS = 0.16
PERSONAL_PURSUIT_STREAK_FORGET_DAYS = 3
PERSONAL_PURSUIT_SCORE_PROGRESS_SCALE = 0.12
PERSONAL_PURSUIT_LIFE_EVENT_PROGRESS = 1.0

PERSONAL_PURSUITS_LIBRARY = {
    "storykeeping": {
        "name": "Storykeeping",
        "category": "Culture",
        "base_weight": 1.05,
        "need_focus": "Belonging",
        "need_gain": 7,
        "mood_bonus": 5,
        "progress_per_day": 0.24,
        "skill_gain": {"Oratory": 0.6},
        "memory_template": "Shared stories with neighbours, tending our oral history.",
        "milestone_summary": "Completed a new tale cycle to share with the settlement.",
        "tags": ["community", "art"],
    },
    "craft_mastery": {
        "name": "Craft Mastery",
        "category": "Artisan",
        "base_weight": 1.1,
        "need_focus": "Esteem",
        "need_gain": 6,
        "mood_bonus": 4,
        "progress_per_day": 0.28,
        "skill_gain": {"Crafting": 0.7},
        "memory_template": "Worked on a personal craft project to hone my skills.",
        "milestone_summary": "Completed a signature piece that showcases growing mastery.",
        "tags": ["craft", "focus"],
    },
    "herbalism_study": {
        "name": "Herbalism Study",
        "category": "Nature",
        "base_weight": 0.95,
        "need_focus": "Safety",
        "need_gain": 5,
        "mood_bonus": 3,
        "progress_per_day": 0.23,
        "skill_gain": {"Herbalism": 0.65},
        "memory_template": "Catalogued herbs and remedies gathered from the wilds.",
        "milestone_summary": "Documented a new remedy to help keep neighbours healthy.",
        "tags": ["healing", "study"],
    },
    "community_bonding": {
        "name": "Community Bonding",
        "category": "Service",
        "base_weight": 1.0,
        "need_focus": "Belonging",
        "need_gain": 8,
        "mood_bonus": 5,
        "progress_per_day": 0.2,
        "skill_gain": {"Diplomacy": 0.5},
        "memory_template": "Organised time with neighbours to strengthen our bonds.",
        "milestone_summary": "Coordinated a community effort that brought settlers closer together.",
        "tags": ["community", "service"],
    },
    "venture_planning": {
        "name": "Venture Planning",
        "category": "Enterprise",
        "base_weight": 0.9,
        "need_focus": "Esteem",
        "need_gain": 6,
        "mood_bonus": 3,
        "progress_per_day": 0.21,
        "skill_gain": {"Commerce": 0.6},
        "memory_template": "Sketched out ideas to grow a personal venture.",
        "milestone_summary": "Drafted a concrete plan that could launch a new enterprise.",
        "tags": ["wealth", "planning"],
    },
}

PERSONAL_PURSUIT_PERSONALITY_WEIGHTS = {
    "Gregarious": {"community_bonding": 0.4, "storykeeping": 0.25},
    "Ambitious": {"venture_planning": 0.45, "craft_mastery": 0.3},
    "Curious": {"storykeeping": 0.3, "herbalism_study": 0.25},
    "Stoic": {"craft_mastery": 0.25},
    "Nurturing": {"community_bonding": 0.35, "herbalism_study": 0.2},
}

PERSONAL_PURSUIT_TRAIT_WEIGHTS = {
    "Organized": {"craft_mastery": 0.35, "venture_planning": 0.2},
    "Resourceful": {"herbalism_study": 0.3, "venture_planning": 0.25},
    "Generous": {"community_bonding": 0.45},
    "Diligent": {"craft_mastery": 0.25},
    "Patient": {"herbalism_study": 0.25},
    "Curious": {"storykeeping": 0.25, "herbalism_study": 0.2},
    "Compassionate": {"community_bonding": 0.3},
}

PERSONAL_PURSUIT_JOB_WEIGHTS = {
    "Innkeeper": {"community_bonding": 0.4, "storykeeping": 0.2},
    "Herbalist": {"herbalism_study": 0.5},
    "Merchant": {"venture_planning": 0.45},
    "Builder": {"craft_mastery": 0.3},
    "Scribe": {"storykeeping": 0.5},
}

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

# Romance & Household Dynamics
ROMANCE_DAILY_BASE_CHANCE = 0.08  # Base chance a single citizen seeks romance on a given day
ROMANCE_PERSONALITY_INCLINATIONS = {
    "Romantic": 0.35,
    "Dreamer": 0.2,
    "Stoic": -0.2,
    "Pragmatic": -0.05,
    "Cheerful": 0.1,
    "Gloomy": -0.15,
    "Ambitious": -0.05,
}
ROMANCE_TRAIT_INFLUENCES = {
    "Affectionate": 0.25,
    "Charming": 0.2,
    "Jealous": -0.1,
    "Cold": -0.25,
    "Loyal": 0.1,
    "Impulsive": 0.15,
    "Brooding": -0.1,
}
ROMANCE_RELATIONSHIP_THRESHOLD_TO_DATE = 25
ROMANCE_RELATIONSHIP_THRESHOLD_TO_COMMIT = 55
ROMANCE_MIN_DAYS_BEFORE_UNION = 6
ROMANCE_COMMITMENT_PERSONALITY_MODIFIERS = {
    "Pragmatic": 0.1,
    "Romantic": 0.2,
    "Stoic": -0.2,
    "Impulsive": 0.15,
    "Loyal": 0.15,
    "Ambitious": -0.05,
}
ROMANCE_BREAKUP_REL_THRESHOLD = -20
ROMANCE_BREAKUP_BASE_CHANCE = 0.04
ROMANCE_DIVORCE_REL_THRESHOLD = -45
ROMANCE_DIVORCE_BASE_CHANCE = 0.06
ROMANCE_DIVORCE_TRAIT_BONUS = {
    "Jealous": 0.05,
    "Impulsive": 0.04,
    "Loyal": -0.05,
    "Patient": -0.05,
}
FAMILY_CHILD_DESIRE_BASE = 0.12
FAMILY_CHILD_PERSONALITY_BONUS = {
    "Nurturing": 0.25,
    "Cheerful": 0.1,
    "Stoic": -0.1,
    "Ambitious": -0.05,
}
FAMILY_CHILD_TRAIT_BONUS = {
    "Family-Oriented": 0.3,
    "Jealous": -0.05,
    "Selfish": -0.1,
    "Generous": 0.05,
}
FAMILY_CHILD_MIN_AGE = 18
FAMILY_CHILD_MAX_AGE = 45
FAMILY_CHILD_MIN_BELONGING = 55
FAMILY_CHILD_COOLDOWN_DAYS = 18
FAMILY_CHILD_HOUSING_REQUIREMENT = 1

# Reputation System Configs (Basic)
REPUTATION_SCORE_MIN = -100
REPUTATION_SCORE_MAX = 100
REPUTATION_CHANGE_HELPED_OTHER = 2
REPUTATION_CHANGE_APOLOGY_ACCEPTED = 1
REPUTATION_CHANGE_FIRED = -5
REPUTATION_EFFECT_ON_INITIAL_RELATIONSHIP = 0.1 # e.g. 10 reputation = +1 initial relationship score
REPUTATION_EFFECT_ON_WILLINGNESS_TO_HELP = 0.005 # e.g. 10 reputation = +0.05 to willingness chance

# Reputation Tiers (Score Thresholds - lower bound for each tier)
# Order matters for lookup (highest score first)
REPUTATION_TIERS = [
    ("Venerated", 80),
    ("Respected", 50),
    ("Upstanding", 20),
    ("Neutral", -20),
    ("Unsavory", -50),
    ("Shunned", -80),
    ("Despised", -101) # Catch-all for the lowest scores
]

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

# Personal histories & family chronicles
LIFE_HISTORY_MAX_EVENTS = 120
LIFE_HISTORY_HIGHLIGHT_THRESHOLD = 2
FAMILY_HISTORY_MAX_EVENTS = 80

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
