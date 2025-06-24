# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile # Keep for potential future item interaction with events
from .work_order import WorkOrder # Keep for potential future event-driven WOs
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS
from .events_data import EVENT_DEFINITIONS
from .event_manager import EventManager
from . import config
import random

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM if hasattr(config, 'USE_LLM') else 'Not Set'}")
    print("--------------------------")

    ticks_per_day = 10
    days_per_season = 10
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)
    event_manager = EventManager(world_ref=game_world)
    event_manager.load_event_definitions(EVENT_DEFINITIONS)

    # Clear previous test setups
    game_world.stockpiles.clear()
    game_world.resources.clear()
    game_world.buildings.clear()
    game_world.work_orders.clear()

    # Add a basic ToolShed and some tools for workers
    tool_shed = Stockpile(name="ToolShed", x=1, y=1, width=1, height=1, allowed_resources=["Stone Axe", "Stone Pickaxe"], total_capacity=10)
    game_world.add_stockpile(tool_shed)
    tool_shed.add_item("Stone Axe", 1)
    tool_shed.add_item("Stone Pickaxe", 1)
    game_world.ledger.update_stockpile_record(tool_shed.name, tool_shed.inventory, game_time_obj.current_day)
    print(f"Pre-stocked ToolShed with 1 Stone Axe and 1 Stone Pickaxe.")

    wood_stockpile_test = Stockpile(name="WoodStore", x=0, y=3, width=1, height=1, allowed_resources=["Wood"], total_capacity=50)
    game_world.add_stockpile(wood_stockpile_test)
    game_world.ledger.update_stockpile_record(wood_stockpile_test.name, wood_stockpile_test.inventory, game_time_obj.current_day)
    print(f"Added WoodStore stockpile.")

    stone_stockpile_test = Stockpile(name="StoneStore", x=1, y=3, width=1, height=1, allowed_resources=["Stone"], total_capacity=50)
    game_world.add_stockpile(stone_stockpile_test)
    game_world.ledger.update_stockpile_record(stone_stockpile_test.name, stone_stockpile_test.inventory, game_time_obj.current_day)
    print(f"Added StoneStore stockpile.")


    # Setup for Event Testing
    print("\n--- Character Setup (Event Test) ---")

    # Add some resources for gathering tasks to test yield events
    game_world.set_tile(0,0,"Forest"); game_world.add_resource("Wood", (0,0))
    game_world.set_tile(0,1,"Forest"); game_world.add_resource("Wood", (0,1))
    game_world.set_tile(1,0,"Rocks"); game_world.add_resource("Stone", (1,0))

    # Characters
    event_test_chars = []
    char1 = Character(name="Eva", personality="Stoic", traits=[],
                      job="Woodcutter", x=2,y=2, skills={"Woodcutting": 5}, needs={'Social': 70, "Wood": 10})
    game_world.add_character(char1)
    event_test_chars.append(char1)
    print(f"  Added: {char1.name} (Job: {char1.job}) at ({char1.x},{char1.y})")

    char2 = Character(name="Liam", personality="Optimistic", traits=["Diligent"],
                      job="Stonemason", x=3,y=2, skills={"Mining": 5}, needs={'Social': 70, "Stone": 10})
    game_world.add_character(char2)
    event_test_chars.append(char2)
    print(f"  Added: {char2.name} (Job: {char2.job}) at ({char2.x},{char2.y})")

    # Add a crafter to test tool crafting event
    # To test tool crafting event, we need a workshop and resources for a tool
    # For simplicity, we'll skip building the workshop in this test and assume one exists if needed by a blueprint.
    # Or, use a tool that doesn't require a workshop. Let's use Stone Axe.
    char3 = Character(name="Crafty", personality="Inventive", traits=[],
                      job="Stonemasonry", x=4,y=2, skills={"Stonemasonry": 5}, needs={'Social': 70})
    game_world.add_character(char3)
    event_test_chars.append(char3)
    # Pre-give Crafty resources for a Stone Axe (Stone:2, Wood:1) to simplify test
    char3.inventory["Stone"] = 2
    char3.inventory["Wood"] = 1
    print(f"  Added: {char3.name} (Job: {char3.job}) at ({char3.x},{char3.y}), pre-stocked for Stone Axe.")


    print(f"\n--- Simulation: Event Test ---")
    max_simulation_days = 20 # Run for a bit longer to see events
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

    # Assign a task to Crafty to make a Stone Axe
    stone_axe_wo = WorkOrder(
        order_type="CraftItem",
        details={"item_name": "Stone Axe", "quantity": 1, "required_resources": BLUEPRINTS["Stone Axe"]["required_resources"]},
        creation_day=1, priority=1
    )
    stone_axe_wo.status = "Approved" # Set status after creation
    stone_axe_wo.assigned_to = char3.name # Assign after creation
    game_world.add_work_order(stone_axe_wo)
    char3.active_work_order_id = stone_axe_wo.order_id
    char3.current_goal = "Execute Craft Order" # Start Crafty on the WO


    while running:
        new_day = game_time_obj.tick()
        current_total_ticks +=1

        # Process active events (per tick)
        event_manager.process_active_events() # world_ref is accessed via self.world_ref

        for char_to_act in list(game_world.characters):
            if char_to_act not in game_world.characters: continue
            char_to_act.process_status_effects(game_world) # Process statuses before action
            char_to_act.decide_action(game_world)

        if new_day:
            print(f"\n*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")

            # Check for new event triggers (daily)
            event_manager.check_triggers() # world_ref is accessed via self.world_ref

            for char_daily_reset in game_world.characters:
                # Daily Social Need Decay (example, can be expanded for other needs)
                if 'Social' in char_daily_reset.needs:
                    social_decay_base = 5
                    # Example: 'Loner' trait might make social need decay slower if alone, or faster if forced to be social.
                    # For now, simple decay.
                    char_daily_reset.needs['Social'] = max(0, char_daily_reset.needs['Social'] - random.randint(3,7))

                # Reset goal if idle and not already trying to socialize or on a WO
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   not char_daily_reset.active_build_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

            # Display Active World Effects for testing
            if game_world.active_world_effects:
                print("  Active World Effects:")
                for key, effect_info in game_world.active_world_effects.items():
                    expires_in_ticks = effect_info.get('expires_tick', 0) - current_total_ticks
                    print(f"    - {key}: {effect_info.get('multiplier') or effect_info.get('bonus_details')} (expires in ~{expires_in_ticks / ticks_per_day:.1f} days)")

            # Daily status print for test characters
            for char_status in event_test_chars:
                if char_status in game_world.characters:
                    status_names = [s['name'] for s in char_status.status_effects]
                    print(f"  {char_status.name} (Pos:({char_status.x},{char_status.y}), Goal='{char_status.current_goal}', Social: {char_status.needs.get('Social', 50):.0f}, Statuses: {status_names}, Inv: {sum(char_status.inventory.values())})")

            if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                game_world.advance_season()
                last_season_change_day = game_time_obj.current_day

        if game_time_obj.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State ---")
    print(f"Final Time: {game_time_obj}")
    for char_final in event_test_chars:
        if char_final in game_world.characters:
            print(f"\n{char_final}") # Uses Character __str__
            print(f"  Final Needs: {char_final.needs}")
            print(f"  Status Effects: {[s['name'] for s in char_final.status_effects]}")
            print(f"  Inventory: {char_final.inventory}")
            print(f"  Recent Memories (last 10):")
            for mem in char_final.memory[-10:]:
                print(f"    - {mem}")

    print("\n--- World Event Log ---")
    for log_entry in game_world.event_log:
        print(log_entry)

if __name__ == "__main__":
    main()
