# game/data.py
BLUEPRINTS = {
    "Wooden Chair": {
        "required_resources": {"Wood": 5},
        "job_skill_needed": "Carpentry",
        "type": "Furniture",
        "description": "A simple wooden chair for basic comfort.",
        "craft_time_per_unit": 5
    },
    "Stone Axe": {
        "required_resources": {"Stone": 2, "Wood": 1}, # Cost to make a Stone Axe
        "job_skill_needed": "Stonemasonry", # Skill to make the axe
        "type": "Tool",
        "tool_type": "Axe",       # What category of tool it is
        "max_durability": 50,     # How many primary uses it has
        "description": "A basic axe, better than bare hands for chopping wood.",
        "craft_time_per_unit": 8
    },
    "Stone Pickaxe": {
        "required_resources": {"Stone": 3, "Wood": 1}, # Cost to make a Stone Pickaxe
        "job_skill_needed": "Stonemasonry",
        "type": "Tool",
        "tool_type": "Pickaxe",   # What category of tool it is
        "max_durability": 60,
        "description": "A simple pickaxe for mining stone and soft ores.",
        "craft_time_per_unit": 10
    },
    "Wooden Bed": {
        "required_resources": {"Wood": 15},
        "job_skill_needed": "Carpentry",
        "type": "Furniture",
        "description": "A basic wooden bed for improved rest.",
        "craft_time_per_unit": 20
    },
    "Iron Pickaxe": { # Example of a more advanced item
        "required_resources": {"Iron Ingot": 3, "Wood": 1}, # Assuming "Iron Ingot" is a processed resource
        "job_skill_needed": "Blacksmithing",
        "type": "Tool",
        "tool_type": "Pickaxe",
        "max_durability": 150,
        "description": "A durable pickaxe for efficient mining.",
        "craft_time_per_unit": 15,
        "required_workshop_type": "small_workshop" # Requires a Small Workshop
    },
    "FoodRation": {
        "type": "Consumable",
        "effects": {"Hunger": 50, "Thirst": 5}, # Satisfies 50 Hunger, 5 Thirst
        "description": "Basic sustenance, not very tasty but fills the stomach."
        # No crafting recipe for now, assume it's found or provisioned
    },
    "CleanWater": {
        "type": "Consumable",
        "effects": {"Thirst": 40}, # Satisfies 40 Thirst
        "description": "Potable water, essential for survival."
        # No crafting recipe for now
    }
    # Add other items as needed, e.g., "Wooden Shield", "Stone Hammer"
}

# Defines tasks that may require tools, the skill they use, and what they produce.
# This helps decouple the action (e.g., "Chop Wood") from the specific tool item (e.g., "Stone Axe").
JOB_TASK_DEFINITIONS = {
    "Chop Wood": {
        "required_tool_type": "Axe", # Category of tool needed
        "skill_used": "Woodcutting",   # Skill that performs/improves this task
        "resource_produced": "Wood",   # Primary resource yielded by this task
        "base_yield": 1,               # How much is produced per successful action/tick of work
        "base_time_per_yield": 3      # Ticks of work for one unit of base_yield (can be modified by skill/tool)
    },
    "Mine Stone": {
        "required_tool_type": "Pickaxe",
        "skill_used": "Mining",
        "resource_produced": "Stone",
        "base_yield": 1,
        "base_time_per_yield": 4
    },
    "Mine Iron Ore": {
        "required_tool_type": "Pickaxe", # Better pickaxe might be more effective
        "skill_used": "Mining",
        "resource_produced": "Iron Ore", # A new raw material
        "base_yield": 1,
        "base_time_per_yield": 6
    },
    "Construct Building": { # Generic task for working on any building
        "required_tool_type": None, # Could add "Hammer" later
        "skill_used": "Construction",
        "resource_produced": None, # Does not directly produce a portable resource
        "base_yield": 1, # Represents 1 unit of "build progress"
        "base_time_per_yield": 1 # How many ticks to apply 1 unit of build progress (can be modified by skill/traits)
    },
    "Socialize": {
        "required_tool_type": None,
        "skill_used": None, # Could add a "Social" skill later
        "resource_produced": None,
        "base_yield": 1, # Represents one successful social interaction "unit"
        "base_time_per_yield": 5 # Ticks to complete one social interaction
    },
    # Future task examples:
    # "Till Soil": {"required_tool_type": "Hoe", "skill_used": "Farming", "resource_produced": "Tilled Plot"},
    # "Construct Wall Segment": {"required_tool_type": "Hammer", "skill_used": "Construction", "resource_produced": "Wall Section"},
    # "Hunt Small Game": {"required_tool_type": "Spear", "skill_used": "Hunting", "resource_produced": "Raw Meat"}
}

# It might also be useful to define tool types if they have specific properties beyond what's in blueprints
# For now, tool_type in BLUEPRINTS and required_tool_type in JOB_TASK_DEFINITIONS serve this.

STRUCTURE_BLUEPRINTS = {
    "wooden_hut": {
        "display_name": "Wooden Hut",
        "size": (2, 2), # width, height
        "required_resources": {"Wood": 30},
        "build_time": 50, # Amount of "work"
        "functionality": {"provides_shelter": 1}, # Can shelter 1 person
        "required_skill": {"Construction": 1}, # Skill and level needed
        "map_char_initial": "h.", # Under construction
        "map_char_complete": "H"   # Completed
    },
    "small_workshop": {
        "display_name": "Small Workshop",
        "size": (3, 2), # width, height
        "required_resources": {"Wood": 50, "Stone": 20},
        "build_time": 100,
        "functionality": {"allows_crafting_category": ["Basic Tools", "Simple Furniture"]}, # Categories of items craftable here
        "required_skill": {"Construction": 3},
        "map_char_initial": "w.", # Under construction
        "map_char_complete": "W"   # Completed
    },
    "simple_bed": {
        "display_name": "Simple Bed",
        "size": (1, 2), # width, height (a single tile bed, long shape)
        "required_resources": {"Wood": 10, "Plant Fiber": 5}, # Added Plant Fiber as example
        "build_time": 20,
        "functionality": {"provides_rest_quality": 1.5, "provides_comfort": 10}, # Rest quality multiplier, comfort bonus
        "required_skill": {"Construction": 1},
        "map_char_initial": "b.",
        "map_char_complete": "B"
    },
    "construction_site": { # A generic site, perhaps for displaying build orders on map before construction starts
        "display_name": "Construction Site",
        "size": (1,1), # Placeholder size, actual building size will be used when creating the Building object
        "map_char_initial": "X", # Character to display on map for a planned construction
        "map_char_complete": "X" # Should not complete, really, it's a placeholder visual
    }
}
