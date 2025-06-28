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
    },
    "Herbs": {
        "type": "Resource", # Gatherable raw material
        "description": "Medicinal herbs with healing properties."
        # No crafting time or required resources as it's gathered.
    },
    "Bandages": {
        "required_resources": {"Herbs": 2},
        "job_skill_needed": "Medicine", # New skill for crafting/using medical items
        "type": "MedicalSupply", # A more specific type for medical items
        "description": "Simple bandages for treating injuries.",
        "craft_time_per_unit": 3
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
    "Gather Herbs": {
        "required_tool_type": None, # Could require a "Gathering Pouch" or similar later
        "skill_used": "Herbalism",   # New skill for finding and gathering herbs
        "resource_produced": "Herbs",
        "base_yield": 1,
        "base_time_per_yield": 4    # Ticks to gather one unit of herbs
    },
    "Treat Patient": {
        "required_tool_type": None, # Could require "Medical Kit" later
        "skill_used": "Medicine",    # Skill for diagnosis and treatment
        "resource_produced": None,   # Action modifies patient's state, doesn't produce item
        "base_yield": 1,             # Represents 1 unit of "treatment progress/action"
        "base_time_per_yield": 5,    # Ticks for one treatment action
        # "consumed_resources": {"Bandages": 1} # Or handled by execution logic
    },
    "Oversee Medical Operations": { # For the Chief Medical Officer (CMO)
        "required_tool_type": None,
        "skill_used": "Medicine", # High-level medical planning and oversight
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Continuous oversight task
    },
    "Provide Medical Care": { # For Medics
        "required_tool_type": None, # Specific actions like "Treat Patient" might consume items
        "skill_used": "Medicine",   # General medical duties
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Represents general readiness/duty
    },
    "Maintain Peace in Settlement": { # For Sheriff
        "required_tool_type": None, # Could be "Badge" or "Weapon" later
        "skill_used": "Security",   # New skill for law enforcement, order, and investigation
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Continuous oversight/presence task
    },
    "Patrol Area": { # For Deputy
        "required_tool_type": None,
        "skill_used": "Security",
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Represents active patrolling
    },
    "Give Speech": { # For Mayor
        "required_tool_type": None,
        "skill_used": "Leadership", # Oratory could be part of Leadership or a new Charisma skill
        "resource_produced": None,  # Indirectly affects morale or opinion
        "base_yield": 0,
        "base_time_per_yield": 0 # Action takes a certain number of ticks, not yield-based
    },
    "Seek Medical Attention": {
        "required_tool_type": None,
        "skill_used": None, # Not a skilled task, but a state-driven need
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Goal is to reach a medic/clinic
    },
    "Greet Character": {
        "required_tool_type": None,
        "skill_used": "Social", # Or None, or a new "Social" skill
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Interaction, not yield-based
    },
    "Introduce Self to Stranger": {
        "description": "Character introduces themselves to an unknown character.",
        "required_tool_type": None,
        "skill_used": "Social",
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Short interaction, similar to greeting
    },
    "Small Talk": {
        "description": "Character engages in a brief, casual conversation with a known acquaintance.",
        "required_tool_type": None,
        "skill_used": "Social",
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Represents a short social exchange
    },
    "Share Positive News": {
        "description": "Character shares a piece of positive news or light gossip with an acquaintance.",
        "required_tool_type": None,
        "skill_used": "Social",
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Short social interaction
    },
    "Offer Comfort": {
        "description": "Character offers comfort or sympathy to someone in a negative state (e.g., sick, injured).",
        "required_tool_type": None,
        "skill_used": "Social", # Could also be influenced by an "Empathy" skill/trait
        "resource_produced": None,
        "base_yield": 0,
        "base_time_per_yield": 0 # Short interaction
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
