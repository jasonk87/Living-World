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
    "Arrow Bundle": {
        "required_resources": {"Wood": 2},
        "job_skill_needed": "Fletching",
        "type": "Ammunition",
        "description": "A bundle of arrows ready for archers and hunters.",
        "craft_time_per_unit": 4
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
    },
    "Food": {
        "type": "Consumable",
        "description": "A simple meal to satisfy hunger.",
        "hunger_satisfaction": 40 # Custom property for consumables
    },
    "Water": {
        "type": "Consumable",
        "description": "Stored drinking water drawn from nearby wells and streams.",
        "thirst_satisfaction": 45
    },
    "Iron Ore": {
        "type": "Resource",
        "description": "Raw iron ore, needs to be smelted."
    },
    "Iron Ingot": {
        "required_resources": {"Iron Ore": 2},
        "job_skill_needed": "Smelting",
        "type": "Resource",
        "description": "A bar of refined iron.",
        "craft_time_per_unit": 7
    },
    "Iron Axe": {
        "required_resources": {"Iron Ingot": 2, "Wood": 1},
        "job_skill_needed": "Blacksmithing",
        "type": "Tool",
        "tool_type": "Axe",
        "max_durability": 120,
        "description": "A sturdy iron axe for efficient woodcutting.",
        "craft_time_per_unit": 12
    }
}

# --- Demographic Pools & Archetypes ---

CITIZEN_NAME_POOL = {
    "given": [
        "Aldric", "Bryn", "Calla", "Dain", "Eira", "Fen", "Galen", "Helena", "Ivor", "Jora",
        "Kael", "Lysa", "Merrit", "Nia", "Oren", "Perrin", "Quinn", "Rowan", "Sera", "Tavin",
        "Ulric", "Vela", "Wren", "Yorik", "Zara",
    ],
    "surnames": [
        "Stonebrook", "Ironvale", "Thornfield", "Riverwynd", "Oakenshield", "Stormwatch",
        "Ashgrove", "Frostmere", "Goldbarrow", "Nightbloom",
    ],
}

CITIZEN_PERSONALITY_POOL = [
    "Optimistic",
    "Stoic",
    "Pragmatic",
    "Cheerful",
    "Introspective",
    "Ambitious",
]

CITIZEN_TRAIT_POOL = [
    "Diligent",
    "Curious",
    "Compassionate",
    "Organized",
    "Tough",
    "Patient",
    "Resourceful",
]

MIGRANT_ARCHETYPES = [
    {
        "job": "Farmer",
        "personality": "Steadfast",
        "traits": ["Diligent", "Patient"],
        "skills": {"Farming": 2},
    },
    {
        "job": "Woodcutter",
        "personality": "Pragmatic",
        "traits": ["Tough", "Resourceful"],
        "skills": {"Woodcutting": 2},
    },
    {
        "job": "Hunter",
        "personality": "Observant",
        "traits": ["Curious", "Resourceful"],
        "skills": {"Hunting": 2},
    },
    {
        "job": "Stonemason",
        "personality": "Methodical",
        "traits": ["Organized", "Patient"],
        "skills": {"Stonemasonry": 2},
    },
    {
        "job": "Herbalist",
        "personality": "Gentle",
        "traits": ["Compassionate", "Curious"],
        "skills": {"Herbalism": 2},
    },
]

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
    "Smelt Iron Ingot": {
        "required_tool_type": None, # Requires a forge/smelter building, not a hand tool
        "required_building": "smelting",
        "skill_used": "Smelting",
        "resource_produced": "Iron Ingot",
        "base_yield": 1,
        "base_time_per_yield": 8
    },
    "Smith Iron Axe": {
        "required_tool_type": "Hammer", # Blacksmith hammer
        "required_building": "blacksmithing",
        "skill_used": "Blacksmithing",
        "resource_produced": "Iron Axe",
        "base_yield": 1,
        "base_time_per_yield": 15
    },
    "Saw Lumber": {
        "required_tool_type": "Saw",
        "skill_used": "Carpentry",
        "resource_produced": "Lumber",
        "base_yield": 1,
        "base_time_per_yield": 3,
    },
    "Assemble Furniture": {
        "required_tool_type": "Hammer",
        "skill_used": "Carpentry",
        "resource_produced": "Furniture",
        "base_yield": 1,
        "base_time_per_yield": 4,
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
    "Tend Fields": {
        "required_tool_type": None,
        "skill_used": "Farming",
        "resource_produced": "Food",
        "base_yield": 1,
        "base_time_per_yield": 4
    },
    "Hunt Game": {
        "required_tool_type": None,
        "skill_used": "Hunting",
        "resource_produced": "Food",
        "base_yield": 1,
        "base_time_per_yield": 5
    },
    "Fletch Arrows": {
        "required_tool_type": None,
        "skill_used": "Fletching",
        "resource_produced": "Arrow Bundle",
        "base_yield": 1,
        "base_time_per_yield": 3
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
    "Draw Water": {
        "required_tool_type": None,
        "skill_used": "Labor",
        "resource_produced": "Water",
        "base_yield": 1,
        "base_time_per_yield": 3
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
    "Ask for Help": {
        "description": "Character asks another for help with a task, a resource, or a tool.",
        "required_tool_type": None,
        "skill_used": "Social",
        "resource_produced": None, # Indirectly might lead to resource acquisition or task progress
        "base_yield": 0,
        "base_time_per_yield": 0 # Interaction time
    },
    "Offer Help": {
        "description": "Character proactively offers help or a resource to someone they perceive as needing it.",
        "required_tool_type": None,
        "skill_used": "Social", # Also influenced by traits like "Kind", "Generous"
        "resource_produced": None, # Can result in resource transfer or task assistance
        "base_yield": 0,
        "base_time_per_yield": 0 # Interaction time
    },
    "Argue": {
        "description": "Characters engage in a heated disagreement.",
        "required_tool_type": None,
        "skill_used": "Social", # Or perhaps a 'Temperament' related skill/check
        "resource_produced": None, # Results in relationship/opinion changes
        "base_yield": 0,
        "base_time_per_yield": 0 # Short, impactful interaction
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
        "functionality": {
            "provides_shelter": 2,
            "tags": ["indoor", "residential", "housing"],
            "wealth_tier": "modest",
        },
        "required_skill": {"Construction": 1},
        "map_char_initial": ".", # Initial representation on map before construction starts
        "map_char_complete": "H",
        "interior_tile": "Floor",
        "tile_layout": [
            ["WoodWall", "WoodWall"],
            ["Bedroll", "Hearth"],
        ],
        "amenities": ["Shared hearth", "Sleeping pallets"],
        "household_style": "hearthfire",
    },
    "stone_cottage": {
        "display_name": "Stone Cottage",
        "size": (3, 3),
        "required_resources": {"Wood": 40, "Stone": 45},
        "construction_phases": [
            {"name": "Foundation", "work_required": 20, "map_char_during": "_"},
            {"name": "Walls", "work_required": 28, "map_char_during": "#"},
            {"name": "Roof & Hearth", "work_required": 22, "map_char_during": "^"}
        ],
        "functionality": {
            "provides_shelter": 3,
            "tags": ["indoor", "residential", "housing"],
            "wealth_tier": "comfortable",
        },
        "required_skill": {"Construction": 3},
        "map_char_initial": ".",
        "map_char_complete": "C",
        "interior_tile": "Flagstone",
        "tile_layout": [
            ["StoneWall", "StoneWall", "StoneWall"],
            ["Bed", "Flagstone", "Bed"],
            ["Chest", "Hearth", "Table"],
        ],
        "amenities": ["Sturdy bunks", "Warm hearth", "Provision chest"],
        "household_style": "artisan",
    },
    "merchant_manor": {
        "display_name": "Merchant Manor",
        "size": (4, 3),
        "required_resources": {"Wood": 60, "Stone": 70, "Furniture": 4},
        "construction_phases": [
            {"name": "Estate Footing", "work_required": 28, "map_char_during": "_"},
            {"name": "Grand Hall", "work_required": 36, "map_char_during": "M"},
            {"name": "Finishes", "work_required": 24, "map_char_during": "m"}
        ],
        "functionality": {
            "provides_shelter": 5,
            "tags": ["indoor", "residential", "housing"],
            "wealth_tier": "prosperous",
        },
        "required_skill": {"Construction": 4},
        "map_char_initial": ".",
        "map_char_complete": "M",
        "interior_tile": "Parquet",
        "tile_layout": [
            ["StoneWall", "StoneWall", "StoneWall", "StoneWall"],
            ["Dining", "Parquet", "Parquet", "Study"],
            ["Garden", "Parlor", "Parlor", "Garden"],
        ],
        "amenities": ["Formal dining table", "Parlor for guests", "Private study"],
        "household_style": "mercantile",
    },
    "noble_estate": {
        "display_name": "Noble Estate",
        "size": (4, 4),
        "required_resources": {"Wood": 80, "Stone": 120, "Furniture": 8},
        "construction_phases": [
            {"name": "Manor Grounds", "work_required": 32, "map_char_during": "_"},
            {"name": "Wing Construction", "work_required": 48, "map_char_during": "N"},
            {"name": "Great Hall", "work_required": 36, "map_char_during": "n"},
            {"name": "Finishing Touches", "work_required": 28, "map_char_during": "^"}
        ],
        "functionality": {
            "provides_shelter": 6,
            "tags": ["indoor", "residential", "housing"],
            "wealth_tier": "noble",
        },
        "required_skill": {"Construction": 5},
        "map_char_initial": ".",
        "map_char_complete": "N",
        "interior_tile": "Marble",
        "tile_layout": [
            ["StoneWall", "StoneWall", "StoneWall", "StoneWall"],
            ["Marble", "GrandHall", "GrandHall", "Marble"],
            ["Garden", "Library", "Library", "Garden"],
            ["Courtyard", "Courtyard", "Courtyard", "Courtyard"],
        ],
        "amenities": ["Grand hall", "Private library", "Garden courtyard"],
        "household_style": "noble",
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
        "functionality": {"allows_crafting_category": ["Basic Tools", "Simple Furniture", "smelting", "blacksmithing"], "tags": ["indoor", "workshop", "crafting_general"]},
        "required_skill": {"Construction": 3},
        "map_char_initial": ".",
        "map_char_complete": "W"
    },
    "construction_site": {
        "display_name": "Construction Site",
        "size": (1,1),
        "map_char_initial": "X",
        "map_char_complete": "X",
        "functionality": {"tags": ["construction", "progress_marker"]},
        "required_resources": {},
        "construction_phases": [{"name": "Site Preparation", "work_required": 1, "map_char_during": "X"}]
    }
}

# --- Roles, Hierarchy, and Capabilities ---

# Defines the reporting structure for different jobs/roles.
# Key: Role/Job Title, Value: Supervisor's Role/Job Title (or None if top-level)
ROLE_HIERARCHY = {
    # Top Level
    "Mayor": None,

    # Report to Mayor
    "Manager": "Mayor",
    "Chancellor": "Mayor",
    "Militia Commander": "Mayor",
    "Marshal": "Militia Commander",
    "Chief Medical Officer": "Mayor",
    "Sheriff": "Mayor",
    "Noble Lord": "Mayor",  # For settlement-level concerns, even if landed.
    "Baron": "Mayor",       # Similar to Noble Lord, potentially higher standing.
    "Duke": "Mayor",
    "Duchess": "Mayor",

    # Report to Manager
    "Master Craftsman": "Manager",
    "Bookkeeper": "Manager",
    "Builder": "Manager",
    "Woodcutter": "Manager",
    "Stonemason": "Manager",
    "Miner": "Manager",
    "Smelter": "Manager",
    "Blacksmith": "Manager",
    "Farmer": "Manager",
    "Hunter": "Manager",
    "Fletcher": "Master Craftsman",
    "Expedition Leader": "Militia Commander",

    # Report to Militia Commander
    "Militia Captain": "Militia Commander",
    "Militia Soldier": "Militia Captain",
    "Scout": "Militia Captain",

    # Report to Chief Medical Officer
    "Medic": "Chief Medical Officer",

    # Report to Sheriff
    "Deputy": "Sheriff",

    # Report to Baron/Baroness
    "Steward": "Baron",
    "Reeve": "Steward",
    "Bailiff": "Steward",

    # Report to Chancellor
    "Spymaster": "Chancellor",
}

# Defines which jobs or ranks are considered part of the "nobility"
# This can be used for social interactions, access to certain areas, or game mechanics.
NOBLE_RANKS_OR_JOBS = [
    "Mayor",
    "Noble Lord",
    "Baron",
    "Baroness",
    "Duke",
    "Duchess",
    "Chancellor",
    "Steward",
    "Marshal",
    "Spymaster",
]

# Defines key official positions that the Mayor (or equivalent top leader) can appoint.
MAYORAL_APPOINTMENTS = [
    "Manager",
    "Militia Commander",
    "Chief Medical Officer",
    "Sheriff",
    "Chancellor",
    "Marshal",
    "Spymaster",
]


# Design documentation for Role Responsibilities and Capabilities.
# This is not directly parsed by the game logic yet but serves as a blueprint for AI development.
ROLE_DETAILS = {
    "Mayor": {
        "description": "The elected or appointed leader of the settlement.",
        "responsibilities": [
            "Overall settlement well-being and strategic direction.",
            "Final authority on major projects and policies.",
            "Managing top-level official appointments.",
            "Representing the settlement in external affairs (if applicable)."
        ],
        "capabilities": [
            "IssueStrategicDirective(target_role, details_dict)",
            "EnactPolicy(policy_name, policy_details)",
            "AppointKeyOfficial(character_name, role_to_appoint)",
            "FireKeyOfficial(character_name)",
            "ApproveMajorProject(project_name, project_details)",
            "HostEvent(event_type, details)", # e.g., HoldTownMeeting, GiveSpeech
            "AllocateSettlementBudget(category, amount)" # Future
        ],
        "job_default_goal": "Oversee Settlement" # From character.py
    },
    "Chancellor": {
        "description": "Chief administrator who coordinates civic policy and the mayoral council.",
        "reports_to": "Mayor",
        "responsibilities": [
            "Maintaining cohesion between economic, civic, and noble offices.",
            "Auditing performance of appointed officials and nobles.",
            "Drafting decrees or policy proposals for the mayor's approval.",
            "Stewarding the settlement council agenda and priorities."
        ],
        "capabilities": [
            "ReviewOfficialPerformance(official_name, findings)",
            "ProposeSettlementDecree(decree_name, justification)",
            "ConveneCouncilSession(topic, participants)",
            "ReassignStaffBetweenOffices(staff_name, target_office)",
            "ManageSubordinates(subordinate_name, action_type, details)",
        ],
        "job_default_goal": "Oversee Settlement"
    },
    "Manager": {
        "description": "Oversees civilian production, construction, and resource management.",
        "reports_to": "Mayor",
        "responsibilities": [
            "Managing workforce for production and gathering.",
            "Ensuring resource availability for projects and consumption.",
            "Overseeing construction of non-military structures.",
            "Maintaining efficiency in production chains."
        ],
        "capabilities": [
            "CreateWorkOrder(type, details)", # CraftItem, BuildStructure, GatherResource
            "AssignWorkerToTask(worker_name, task_details, priority)",
            "PrioritizeProductionQueue(item_or_project_name, new_priority)",
            "RequestResourcesOrTools(item_name, quantity, reason)",
            "ManageSubordinates(subordinate_name, action_type, details)", # Review, Warn, Fire (for workers like Craftsmen, Bookkeeper)
            "ReportToSupervisor(report_type, details_dict)" # e.g., production_status, resource_levels
        ],
        "job_default_goal": "Manage Subordinates" # From character.py, covers work order approval too
    },
    "Militia Commander": {
        "description": "Responsible for the settlement's defense and military readiness.",
        "reports_to": "Mayor",
        "responsibilities": [
            "Organizing settlement defense against external threats.",
            "Training and equipping the militia.",
            "Maintaining order during emergencies (assisting Sheriff).",
            "Leading military operations as directed."
        ],
        "capabilities": [
            "OrganizePatrolSchedule(area, frequency, squad_composition_details)",
            "InitiateMilitiaTrainingDrill(drill_type, duration)",
            "RequestArmsAndArmor(item_list_and_quantities)",
            "RecruitMilitiaMember(candidate_character_name)", # or just "RecruitMilitia(quantity_needed)"
            "LeadForce(target_location_or_objective, force_composition_details)", # For defense or expeditions
            "ManageSubordinates(subordinate_name, action_type, details)", # For Militia Captains
            "ReportToSupervisor(report_type, details_dict)" # e.g., readiness_status, threat_assessment
        ],
        "job_default_goal": "Maintain Defenses"
    },
    "Marshal": {
        "description": "Senior military officer charged with discipline across the guard and militia.",
        "reports_to": "Militia Commander",
        "responsibilities": [
            "Inspecting patrol readiness and battlefield drills.",
            "Coordinating joint operations with the Sheriff during crises.",
            "Setting response plans for major threats to the settlement.",
            "Reviewing conduct of captains, sergeants, and veteran guards."
        ],
        "capabilities": [
            "InspectGarrisonUnit(unit_name, findings)",
            "IssueBattlePlan(plan_name, objectives)",
            "ReassignCaptain(captain_name, new_post)",
            "EscalateThreatReport(threat_summary, recipients)",
            "ManageSubordinates(subordinate_name, action_type, details)",
        ],
        "job_default_goal": "Maintain Defenses"
    },
    "Sheriff": {
        "description": "Maintains day-to-day peace and enforces local laws.",
        "reports_to": "Mayor",
        "responsibilities": [
            "Enforcing settlement laws and policies.",
            "Investigating minor crimes and disturbances.",
            "Ensuring public safety in common areas."
        ],
        "capabilities": [
            "AssignPatrolArea(deputy_name, area_name, schedule_details)",
            "InvestigateDisturbance(location, witness_names)",
            "DetainCharacter(character_name, reason, duration_or_next_step)", # Requires jail system
            "ReportCrimeAndOrderStats(period_summary)",
            "ManageSubordinates(subordinate_name, action_type, details)", # For Deputies
            "RequestAssistanceFromMilitia(reason_for_request)" # In major situations
        ],
        "job_default_goal": "Maintain Peace in Settlement" # From character.py
    },
    "Spymaster": {
        "description": "Keeper of intelligence networks and covert investigations.",
        "reports_to": "Chancellor",
        "responsibilities": [
            "Collecting rumors and reports about corruption, threats, or unrest.",
            "Coordinating covert checks on officials, guilds, and nobles.",
            "Advising leadership on hidden risks and leverage points.",
            "Deploying trusted agents to observe sensitive situations."
        ],
        "capabilities": [
            "AssignInformant(target_area, objective)",
            "CompileDossier(subject_name, findings)",
            "RecommendSecuritySweep(location, rationale)",
            "BriefLeadershipOnIntel(summary, recipients)",
            "ManageSubordinates(subordinate_name, action_type, details)",
        ],
        "job_default_goal": "Maintain Peace in Settlement"
    },
    "Chief Medical Officer": {
        "description": "Oversees public health and medical services.",
        "reports_to": "Mayor",
        "responsibilities": [
            "Managing medical facilities and personnel (Medics).",
            "Ensuring availability of medical supplies.",
            "Developing and implementing public health strategies (e.g., sanitation, disease prevention).",
            "Handling medical emergencies and outbreaks."
        ],
        "capabilities": [
            "AssignMedicToDuty(medic_name, duty_type, location_or_patient)", # e.g., clinic_duty, patient_care
            "RequestMedicalSupplies(item_name, quantity)",
            "ImplementPublicHealthMeasure(measure_name, details)", # e.g., QuarantineArea, SanitationCampaign
            "OverseeMedicalTrainingProgram(program_details)",
            "ManageSubordinates(subordinate_name, action_type, details)", # For Medics
            "ReportHealthStatusToSupervisor(summary_of_settlement_health, outbreaks, supply_levels)"
        ],
        "job_default_goal": "Oversee Medical Operations" # From character.py
    },
    "Noble Lord": { # Can also apply to Baron, or have Baron as a more senior version
        "description": "A person of high social standing, may or may not have direct land responsibilities.",
        "reports_to": "Mayor", # For settlement context; could be None/other if purely feudal outside settlement
        "responsibilities": [
            "(If Landed) Managing their personal domain/estate: ensuring its productivity, welfare of its inhabitants, and contributing agreed resources/levies to the settlement.",
            "(If Courtier/Unlanded) Advising the Mayor or other high nobles, undertaking special assignments (e.g., diplomatic), social maneuvering, upholding noble customs."
        ],
        "capabilities": [
            # Landed Noble Capabilities
            "CollectRevenueFromDomain(revenue_type)", # e.g., taxes, tithes
            "IssueDomainEdict(edict_details, scope_is_own_domain_only)",
            "ManageDomainWorkersAndResources(project_name, resource_allocation)",
            "RaiseLevyFromDomain(number_of_troops, equipment_level_details)", # Local forces
            # General Noble Capabilities
            "AttendCourtOrSocialEvent(event_name)",
            "AttemptToInfluenceNoble(target_noble_name, decision_or_opinion_to_influence, method_of_influence)",
            "UndertakeSpecialAssignment(assignment_details, given_by_whom)", # e.g., diplomatic mission
            "HostSocialGathering(guest_list, purpose_of_gathering)"
        ],
        "job_default_goal": "Oversee Domain" # (if landed), or "MaintainInfluence" (if courtier) - needs refinement in Character.job_default_goal
    },
    "Baron": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
        "job_default_goal": "Oversee Domain"
    },
    "Steward": {
        "description": "An appointed official who oversees day-to-day operations of a noble estate.",
        "reports_to": "Baron",
        "responsibilities": [
            "Balancing estate ledgers and supply stores.",
            "Directing reeves and bailiffs in maintenance and collection duties.",
            "Reporting estate performance and incidents to their liege.",
            "Hosting visitors or dignitaries on behalf of the noble household."
        ],
        "capabilities": [
            "ReviewEstateLedger(section, findings)",
            "AssignEstateTask(target_role, task_details)",
            "ReportEstateStatusToLiege(summary)",
            "HostEstateGathering(event_details)",
            "ManageSubordinates(subordinate_name, action_type, details)",
        ],
        "job_default_goal": "Manage Estate"
    },
    "Duke": {
        "description": "A high-ranking noble, ruler of a duchy, and liege to Barons.",
        "reports_to": "Mayor", # For settlement-level coordination
        "responsibilities": ["Overseeing their domain (duchy).", "Managing vassal Barons.", "Contributing to the realm's high council.", "Upholding justice and order within their lands."],
        "capabilities": ["All capabilities of a Baron, but with greater scope.", "HoldHighCourt(case_details)", "BestowTitlesOrLands(character_name, title_details)", "CommandVassalForces(objective_details)"],
        "job_default_goal": "Oversee Domain"
    },
    "Duchess": { # Assuming Duchess has same role and capabilities as Duke
        "description": "A high-ranking noble, ruler of a duchy, and liege to Barons.",
        "reports_to": "Mayor",
        "responsibilities": ["Overseeing their domain (duchy).", "Managing vassal Barons.", "Contributing to the realm's high council.", "Upholding justice and order within their lands."],
        "capabilities": ["All capabilities of a Baron, but with greater scope.", "HoldHighCourt(case_details)", "BestowTitlesOrLands(character_name, title_details)", "CommandVassalForces(objective_details)"],
        "job_default_goal": "Oversee Domain"
    },
    # --- Lower Tier Roles ---
    "Master Craftsman": {
        "description": "A highly skilled artisan supervising a specific type of workshop.",
        "reports_to": "Manager",
        "responsibilities": [
            "Overseeing production in their workshop type (e.g., Blacksmith, Carpenter).",
            "Training apprentices and journeymen.",
            "Ensuring quality of crafted goods.",
            "Maintaining tools and equipment for their workshop.",
            "Fulfilling crafting work orders assigned by the Manager."
        ],
        "capabilities": [
            "TrainApprentice(apprentice_name, skill_to_train)",
            "InspectCraftedItemQuality(item_id_or_batch)",
            "RequestWorkshopSuppliesOrMaintenance(details)",
            "RecommendCraftingPriorities(based_on_skill_and_available_mats_for_their_shop_type)"
        ],
        "job_default_goal": "Assess Production Needs" # From character.py (might need to be more workshop-specific)
    },
    "Militia Captain": {
        "description": "Leads a squad or unit within the militia.",
        "reports_to": "Militia Commander",
        "responsibilities": [
            "Leading their assigned unit in patrols, training, and combat.",
            "Ensuring discipline and readiness of their squad.",
            "Reporting to the Militia Commander."
        ],
        "capabilities": [
            "ExecutePatrolOrder(route_details, squad_members)",
            "LeadSquadInCombat(tactics_details)",
            "ReportSquadStatus(readiness, morale, equipment_needs)"
        ],
        "job_default_goal": "Lead Unit" # Needs to be added to Character.job_default_goal
    },
    "Deputy": {
        "description": "Assists the Sheriff in maintaining peace and order.",
        "reports_to": "Sheriff",
        "responsibilities": [
            "Performing patrols as assigned.",
            "Assisting in investigations.",
            "Responding to minor disturbances."
        ],
        "capabilities": [
            "PerformPatrol(area_name)",
            "QuestionWitnessOrSuspect(character_name)",
            "ReportIncidentDetails(incident_log)"
        ],
        "job_default_goal": "Patrol Area" # From character.py
    },
    "Medic": {
        "description": "Provides medical care to the sick and injured.",
        "reports_to": "Chief Medical Officer",
        "responsibilities": [
            "Treating patients directly.",
            "Assisting the CMO in managing medical supplies and facilities.",
            "Gathering herbs or compounding medicines if needed."
        ],
        "capabilities": [
            "TreatPatient(patient_name, ailment_details, treatment_method)",
            "RequestSpecificMedicalSupply(item_name, quantity_needed_urgently)",
            "GatherHerbsInArea(area_name)"
        ],
        "job_default_goal": "Provide Medical Care" # From character.py
    },
    "Bookkeeper": {
        "description": "Maintains the settlement's financial and resource records.",
        "reports_to": "Manager",
        "responsibilities": ["Accurately recording resource movements in stockpiles.", "Preparing financial summaries if/when economy is added."],
        "capabilities": ["CountStockpileContents(stockpile_name)", "UpdateLedgerRecord(stockpile_name, inventory_data, current_day)"],
        "job_default_goal": "Maintain Ledger" # From character.py
    },
    # Generic worker roles
    "Builder": {"reports_to": "Manager", "job_default_goal": "Perform Builder Duties"},
    "Woodcutter": {"reports_to": "Manager", "job_default_goal": "Perform Woodcutter Duties"},
    "Stonemason": {"reports_to": "Manager", "job_default_goal": "Perform Stonemason Duties"},
    "Miner": {"reports_to": "Manager", "job_default_goal": "Perform Miner Duties"},
    "Smelter": {"reports_to": "Manager", "job_default_goal": "Perform Smelter Duties"},
    "Blacksmith": {"reports_to": "Manager", "job_default_goal": "Perform Blacksmith Duties"},
    "Farmer": {
        "description": "Cultivates crops and keeps granaries stocked for the settlement.",
        "reports_to": "Manager",
        "responsibilities": [
            "Preparing, planting, and harvesting farmland parcels.",
            "Maintaining irrigation trenches and soil health.",
            "Delivering harvested food to approved stockpiles."
        ],
        "capabilities": [
            "TillField(field_location)",
            "HarvestCrop(field_location, crop_type)",
            "DeliverHarvest(stockpile_name, quantity)"
        ],
        "job_default_goal": "Perform Farmer Duties"
    },
    "Hunter": {
        "description": "Supplies meat and hides by ranging beyond the palisade.",
        "reports_to": "Manager",
        "responsibilities": [
            "Scouting and tracking game trails.",
            "Harvesting meat and useful materials from prey.",
            "Alerting the militia if dangerous beasts encroach."
        ],
        "capabilities": [
            "TrackGame(area_name)",
            "HuntGame(target_species)",
            "DressKill(resource_name)"
        ],
        "job_default_goal": "Perform Hunter Duties"
    },
    "Fletcher": {
        "description": "Crafts and maintains ammunition for hunters and militia units.",
        "reports_to": "Master Craftsman",
        "responsibilities": [
            "Producing arrows, bolts, and fletching supplies.",
            "Inspecting projectile stock for damage.",
            "Requesting feathers, wood, and arrowheads from stockpiles."
        ],
        "capabilities": [
            "CraftArrows(batch_size)",
            "InspectQuiver(quiver_owner)",
            "RequestFletchingMaterials(resource, quantity)"
        ],
        "job_default_goal": "Perform Fletcher Duties"
    },
    "Scout": {
        "description": "Reconnoiters nearby regions and provides early warning of threats.",
        "reports_to": "Militia Captain",
        "responsibilities": [
            "Patrolling the settlement perimeter.",
            "Reporting suspicious activity or terrain changes.",
            "Guiding expeditions along safe routes."
        ],
        "capabilities": [
            "ReconArea(area_name)",
            "ReportFindings(superior_name, details)",
            "MarkSafeTrail(trail_name)"
        ],
        "job_default_goal": "Patrol Area"
    },
    "Militia Soldier": {
        "description": "Front-line defender who responds to alarms and patrol orders.",
        "reports_to": "Militia Captain",
        "responsibilities": [
            "Standing watch on assigned posts.",
            "Responding quickly to raids or internal disturbances.",
            "Maintaining weapons and basic armor."
        ],
        "capabilities": [
            "StandWatch(post_name)",
            "RespondToAlarm(location)",
            "MaintainWeapon(weapon_name)"
        ],
        "job_default_goal": "Patrol Area"
    },

    "Reeve": {
        "description": "An official appointed by a noble to supervise their estate or manor.",
        "reports_to": "Baron",
        "responsibilities": ["Managing the day-to-day work on the estate.", "Overseeing peasants and laborers.", "Ensuring production quotas are met."],
        "capabilities": ["AssignPeasantToTask(peasant_name, task_details)", "ReportEstateStatus(production_summary, issues)"],
        "job_default_goal": "Manage Estate"
    },
    "Bailiff": {
        "description": "An official who assists the Reeve and enforces the lord's will.",
        "reports_to": "Baron", # Or could report to Reeve
        "responsibilities": ["Assisting the Reeve.", "Collecting fines and rents.", "Maintaining order among the local peasants."],
        "capabilities": ["CollectRent(peasant_name, amount)", "EnforceManorRule(rule_details, peasant_name)"],
        "job_default_goal": "Assist Reeve"
    }
}

# Update JOB_TASK_DEFINITIONS with default goals for new roles if they perform specific tasks
# For roles that are purely decision-making, their "task" is their job_default_goal in character.py,
# which then calls specific _execute_ methods.

# Example: If Militia Commander has a default task beyond "Oversee Expedition"
# JOB_TASK_DEFINITIONS["Maintain Defenses"] = {
#     "skill_used": "Leadership", # or "Strategy"
#     # ... other fields if it's a task that can be "worked on"
# }
# Ensure character.py's job_default_goal() is updated for these.
# For now, the ROLE_DETAILS includes a "job_default_goal" field for easy reference to Character.py

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .building import Workplace


class Job:
    """Represents a character's job."""

    def __init__(self, title: str, workplace: "Workplace", salary: int):
        self.title = title
        self.workplace = workplace
        self.salary = salary

    def to_dict(self):
        return {
            "title": self.title,
            "workplace": self.workplace.display_name if self.workplace else "Unknown",
            "salary": self.salary,
        }


# --- Economy Data ---
JOB_SALARIES = {
    "Perform Woodcutter Duties": 5,
    "Perform Stonemason Duties": 5,
    "Perform Miner Duties": 6,
    "Perform Smelter Duties": 7,
    "Perform Blacksmith Duties": 8,
    "Perform Farmer Duties": 5,
    "Perform Hunter Duties": 6,
    "Perform Fletcher Duties": 7,
    "Assess Production Needs": 10, # Master Craftsman creating a WO
    "Manage Subordinates": 3, # Manager reviewing a WO
    "Maintain Ledger": 4, # Bookkeeper counting a stockpile
    "Provide Medical Care": 8, # Medic treating a patient
    "Execute Craft Order": 10, # Generic payment for completing a craft WO
    "Execute Build Order": 25, # Generic payment for completing a build WO
}

MARKET_PRICES = {
    "Stone Axe": 15,
    "Stone Pickaxe": 20,
    "Wooden Chair": 10,
    "Bandages": 5,
    "Wood": 2, # Price to buy 1 unit of wood
    "Stone": 3, # Price to buy 1 unit of stone
    "Iron Ore": 6,
    "Iron Ingot": 15,
    "Iron Axe": 40,
    "Lumber": 5,
    "Furniture": 18,
    "Food": 4, # Price to buy 1 unit of food
    "Water": 2,
    "Arrow Bundle": 8,
}
