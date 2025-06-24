# game/data.py
BLUEPRINTS = {
    "Wooden Chair": {
        "required_resources": {"Wood": 5},
        "job_skill_needed": "Carpentry",
        "type": "Furniture",
        "description": "A simple wooden chair for basic comfort.",
        "craft_time_per_unit": 5 # Ticks to craft one unit
    },
    "Stone Axe": {
        "required_resources": {"Stone": 2, "Wood": 1},
        "job_skill_needed": "Stonemasonry", # Or "Toolmaking"
        "type": "Tool",
        "description": "A sturdy axe for chopping wood or other tasks.",
        "craft_time_per_unit": 8
    },
    "Wooden Bed": {
        "required_resources": {"Wood": 15},
        "job_skill_needed": "Carpentry",
        "type": "Furniture",
        "description": "A basic wooden bed.",
        "craft_time_per_unit": 20
    },
    "Iron Pickaxe": { # Example of a more advanced item
        "required_resources": {"Iron Ingot": 3, "Wood": 1}, # Assuming "Iron Ingot" is a processed resource
        "job_skill_needed": "Blacksmithing",
        "type": "Tool",
        "description": "A durable pickaxe for mining.",
        "craft_time_per_unit": 15
    }
}
