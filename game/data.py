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
        "craft_time_per_unit": 15
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
        "required_tool_type": None,
        "skill_used": "Construction",
        "resource_produced": None,
        "base_yield": 1, # Represents 1 unit of "build progress"
        "base_time_per_yield": 1
    },
    # Future task examples:
    # "Till Soil": {"required_tool_type": "Hoe", "skill_used": "Farming", "resource_produced": "Tilled Plot"},
    # "Construct Wall Segment": {"required_tool_type": "Hammer", "skill_used": "Construction", "resource_produced": "Wall Section"},
    # "Hunt Small Game": {"required_tool_type": "Spear", "skill_used": "Hunting", "resource_produced": "Raw Meat"}
    "Oversee Settlement": {
        "required_tool_type": None,
        "skill_used": "Leadership", # Skill related to governance and decision-making
        "resource_produced": None,  # Mayor's actions are indirect
        "base_yield": 0,            # No direct resource yield from this task
        "base_time_per_yield": 0    # Not applicable as it's not a yield-based task
    },
}

# It might also be useful to define tool types if they have specific properties beyond what's in blueprints
# For now, tool_type in BLUEPRINTS and required_tool_type in JOB_TASK_DEFINITIONS serve this.

STRUCTURE_BLUEPRINTS = {
    "wooden_hut": {
        "display_name": "Wooden Hut",
        "size": (2, 2),
        "required_resources": {"Wood": 30},
        "construction_phases": [
            {"name": "Site Preparation", "work_required": 10, "map_char_during": "."},
            {"name": "Foundation", "work_required": 15, "map_char_during": "_"},
            {"name": "Framing Walls", "work_required": 15, "map_char_during": "|"},
            {"name": "Roofing", "work_required": 10, "map_char_during": "^"}
        ],
        "functionality": {"provides_shelter": 1, "tags": ["indoor", "residential", "housing"]},
        "required_skill": {"Construction": 1},
        "map_char_initial": ".", # Initial representation on map before construction starts
        "map_char_complete": "H"
    },
    "small_workshop": {
        "display_name": "Small Workshop",
        "size": (3, 2),
        "required_resources": {"Wood": 50, "Stone": 20},
        "construction_phases": [
            {"name": "Foundation", "work_required": 25, "map_char_during": "_"},
            {"name": "Walls & Basic Setup", "work_required": 50, "map_char_during": "w"},
            {"name": "Tool Racks & Finishing", "work_required": 25, "map_char_during": "W"}
        ],
        "functionality": {"allows_crafting_category": ["Basic Tools", "Simple Furniture"], "tags": ["indoor", "workshop", "crafting_general"]},
        "required_skill": {"Construction": 3},
        "map_char_initial": ".",
        "map_char_complete": "W"
    },
    # Example of a placeholder for a planned, but not yet started, construction site marker if needed by UI
    "construction_site": {
        "display_name": "Construction Site",
        "size": (1,1),
        "map_char_initial": "X",
        "map_char_complete": "X" # Should not complete as this type
    }
}
