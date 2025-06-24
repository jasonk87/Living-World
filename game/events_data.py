# game/events_data.py

EVENT_DEFINITIONS = {
    "good_harvest_boost": {
        "description": "Favorable conditions hint at a good harvest!",
        "message": "The weather has been perfect! Resources like Wood and Stone seem more abundant.",
        "trigger": {"type": "random_daily", "chance": 0.05}, # 5% chance per day
        "effects": [
            {"type": "modify_resource_yield", "resource_type": "Wood", "multiplier": 1.5, "duration_days": 2},
            {"type": "modify_resource_yield", "resource_type": "Stone", "multiplier": 1.2, "duration_days": 1}
        ],
        "duration_days": 2 # Overall duration the event itself is noted or active at a world level
    },
    "minor_illness_random": {
        "description": "A minor bug is going around.",
        "message": "{character_name} isn't feeling too well today and is now Sick.",
        "trigger": {"type": "random_daily_target_character", "chance_per_char": 0.02}, # 2% chance per character per day
        "effects": [
            {"type": "add_character_status", "status_name": "Sick", "duration_days": 3,
             "modifiers": {"work_speed_multiplier": 0.8, "social_need_decay_multiplier": 1.5, "energy_decay_multiplier": 1.2} }
            # Modifiers will be applied by the Character class when processing status effects
        ],
        # Duration of the illness is on the status effect itself. Event is instantaneous once triggered for a char.
    },
    "tool_boost_inspiration": {
        "description": "Local craftspeople feel inspired, leading to better quality tools!",
        "message": "A wave of inspiration has struck! Newly crafted tools might be more durable.",
        "trigger": {"type": "random_daily", "chance": 0.03},
        "effects": [
            {"type": "modify_crafting_output", "item_type": "Tool", "bonus": {"durability_multiplier": 1.2}, "duration_days": 2}
        ],
        "duration_days": 2
    }
}
