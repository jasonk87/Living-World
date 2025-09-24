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
    },
    "Food": {
        "type": "Consumable",
        "description": "A simple meal to satisfy hunger.",
        "hunger_satisfaction": 40 # Custom property for consumables
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

# --- Roles, Hierarchy, and Capabilities ---

# Defines the reporting structure for different jobs/roles.
# Key: Role/Job Title, Value: Supervisor's Role/Job Title (or None if top-level)
ROLE_HIERARCHY = {
    # Top Level
    "Mayor": None,

    # Report to Mayor
    "Manager": "Mayor",
    "Militia Commander": "Mayor",
    "Chief Medical Officer": "Mayor",
    "Sheriff": "Mayor",
    "Noble Lord": "Mayor",  # For settlement-level concerns, even if landed.
    "Duke": "Mayor",
    "Marquis": "Mayor",
    "Count": "Mayor",
    "Viscount": "Mayor",
    "Baron": "Mayor",       # Similar to Noble Lord, potentially higher standing.
    "Baroness": "Mayor",

    # Report to Manager
    "Master Craftsman": "Manager",
    "Bookkeeper": "Manager",
    "Builder": "Manager",
    "Woodcutter": "Manager",
    "Stonemason": "Manager",
    "Miner": "Manager", # Assuming Miner reports to Manager
    # TODO: Add other production worker roles as they are defined

    # Report to Militia Commander
    "Militia Captain": "Militia Commander",
    # TODO: Add individual soldier roles if they need direct hierarchy entry, e.g., "Militia Soldier": "Militia Captain"

    # Report to Chief Medical Officer
    "Medic": "Chief Medical Officer",

    # Report to Sheriff
    "Deputy": "Sheriff",
}

# Defines which jobs or ranks are considered part of the "nobility"
# This can be used for social interactions, access to certain areas, or game mechanics.
NOBLE_RANKS_OR_JOBS = ["Mayor", "Noble Lord", "Duke", "Marquis", "Count", "Viscount", "Baron", "Baroness"]

# Defines key official positions that the Mayor (or equivalent top leader) can appoint.
MAYORAL_APPOINTMENTS = ["Manager", "Militia Commander", "Chief Medical Officer", "Sheriff"]


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
        "job_default_goal": "Oversee Expedition" # Placeholder; needs better default e.g., "MaintainDefenses"
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
    "Baroness": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
        "job_default_goal": "Oversee Domain"
    },
    "Viscount": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
        "job_default_goal": "Oversee Domain"
    },
    "Count": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
        "job_default_goal": "Oversee Domain"
    },
    "Marquis": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
        "job_default_goal": "Oversee Domain"
    },
    "Duke": { # Largely same as Noble Lord, could have higher base influence or larger domain by convention
        "description": "A noble of significant standing, often with land and titles.",
        "reports_to": "Mayor",
        "responsibilities": ["Similar to Noble Lord, potentially with greater scope or expectation."],
        "capabilities": ["Similar to Noble Lord, potentially with greater impact or access."],
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
    "Miner": {"reports_to": "Manager", "job_default_goal": "Perform Miner Duties"} # Assuming a "Perform Miner Duties" goal
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

# --- Economy Data ---
JOB_SALARIES = {
    "Perform Woodcutter Duties": 5,
    "Perform Stonemason Duties": 5,
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
    "Food": 4, # Price to buy 1 unit of food
}

# --- Edicts Data ---
EDICTS = {
    "Tax_Hike": {
        "description": "Increases tax rate for a short period.",
        "duration": 10, # in days
        "effects": {"tax_rate_modifier": 0.05}
    },
    "Tax_Relief": {
        "description": "Decreases tax rate to improve citizen happiness.",
        "duration": 15,
        "effects": {"tax_rate_modifier": -0.02, "global_mood_modifier": 5}
    },
    "Increased_Production": {
        "description": "Mandates longer working hours to boost production.",
        "duration": 7,
        "effects": {"production_speed_modifier": 0.1, "global_mood_modifier": -5}
    },
    "Conscription": {
        "description": "Drafts citizens into the guard, increasing security.",
        "duration": 20,
        "effects": {"security_level_modifier": 10, "global_mood_modifier": -10}
    },
    "Festival_Day": {
        "description": "Declares a day of festival, boosting morale.",
        "duration": 1,
        "effects": {"global_mood_modifier": 15, "production_speed_modifier": -0.5}
    },
    "Curfew": {
        "description": "A curfew is enacted, increasing security but lowering morale.",
        "duration": 10,
        "effects": {"security_level_modifier": 5, "global_mood_modifier": -5}
    },
    "Militia_Training_Drill": {
        "description": "Militia are ordered to conduct training drills, increasing security but lowering productivity.",
        "duration": 5,
        "effects": {"security_level_modifier": 7, "production_speed_modifier": -0.1}
    }
}

ROLE_EDICTS = {
    "Mayor": ["Tax_Hike", "Tax_Relief", "Festival_Day", "Increased_Production"],
    "Sheriff": ["Conscription", "Curfew"],
    "Militia Commander": ["Conscription", "Militia_Training_Drill"],
    "Noble Lord": ["Tax_Hike", "Increased_Production"],
    "Baron": ["Tax_Hike", "Increased_Production"],
    "Baroness": ["Tax_Hike", "Increased_Production"],
    "Viscount": ["Tax_Hike", "Increased_Production"],
    "Count": ["Tax_Hike", "Increased_Production"],
    "Marquis": ["Tax_Hike", "Increased_Production"],
    "Duke": ["Tax_Hike", "Increased_Production"],
}
