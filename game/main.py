# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS
from . import config
import random

def set_reporting_line(supervisor: Character, subordinate: Character):
    subordinate.set_supervisor(supervisor.name)
    supervisor.add_subordinate(subordinate.name)

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM if hasattr(config, 'USE_LLM') else 'Not Set'}")
    print("--------------------------")

    ticks_per_day = 10
    days_per_season = 3
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    # Stockpiles
    tool_shed = Stockpile(name="ToolShed", x=2, y=1, width=1, height=1,
                          allowed_resources=["Stone Axe", "Stone Pickaxe"], total_capacity=10)
    game_world.add_stockpile(tool_shed)
    tool_shed.add_item("Stone Axe", 1)
    game_world.ledger.update_stockpile_record(tool_shed.name, tool_shed.inventory, game_time_obj.current_day)
    print(f"Pre-stocked {tool_shed.name} with 1 Stone Axe. Ledger updated.")

    wood_stockpile = Stockpile(name="WoodPile", x=0, y=3, width=1, height=1,
                               allowed_resources=["Wood"], capacity_per_resource=50)
    game_world.add_stockpile(wood_stockpile)
    game_world.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)

    # Resources in world
    forest_loc = (0,0); game_world.set_tile(0,0,"Forest"); game_world.add_resource("Wood", forest_loc)
    forest_loc2 = (0,1); game_world.set_tile(0,1,"Forest"); game_world.add_resource("Wood", forest_loc2)
    rock_loc = (8,8); game_world.set_tile(8,8,"Rocks"); game_world.add_resource("Stone", rock_loc)
    game_world.set_tile(1,1,"Grass")


    # Characters
    gimli = Character(name="Gimli", personality="determined", traits=["Strong", "Resourceful"], job="Woodcutter", x=1,y=1,
                      skills={"Woodcutting":7},
                      needs={"Wood":5}, max_inventory_items=5, current_goal=None)

    elara = Character(name="Elara", personality="observant", traits=["Quiet"], job="Bookkeeper", x=4,y=4, skills={}, max_inventory_items=1, current_goal=None)

    # Management Test Setup
    boris = Character(name="Boris", personality="stern", traits=["Organized"], job="Manager", rank="Baron", x=5,y=5, skills={}, max_inventory_items=2)
    boris.managed_item_targets = {"Stone Axe": 2} # So Manager has something to approve/deny potentially

    game_world.add_character(gimli)
    game_world.add_character(elara)
    game_world.add_character(boris)

    # Set up reporting line: Boris manages Elara
    set_reporting_line(supervisor=boris, subordinate=elara)
    print(f"\n--- Management Setup ---")
    print(f"{boris.name} is Manager (Rank: {boris.rank}). Supervisor of: {boris.subordinates_names}")
    print(f"{elara.name} is Bookkeeper. Supervisor: {elara.supervisor_name}. Performance: {elara.performance_rating}")


    print("\n--- Initial State (Management Test) ---")
    print(f"Gimli: {gimli}")
    print(f"ToolShed: {tool_shed}")
    print(f"Ledger: {game_world.ledger}")
    print(f"Forest at (0,0): {game_world.get_tile(0,0)}")
    print(f"Boris the Manager: {boris}")
    print(f"Elara the Bookkeeper: {elara}")


    print("\n--- Simulation: Management Actions ---")
    max_simulation_days = 20 # Increased to observe management cycles
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0
    elara_last_action_day = 0 # For forcing Elara to be lazy

    while running:
        new_day = game_time_obj.tick()
        current_total_ticks +=1

        header_printed_this_tick = False
        def print_tick_header():
            nonlocal header_printed_this_tick
            if not header_printed_this_tick:
                print(f"\nTick {current_total_ticks} | {game_time_obj} | {game_world.season}, {game_world.weather}")
                header_printed_this_tick = True

        for char_to_act in list(game_world.characters):
            if char_to_act not in game_world.characters: continue # Character might have been fired/removed

            original_goal = char_to_act.current_goal
            original_performance = char_to_act.performance_rating
            original_warnings = char_to_act.warning_count

            # Simulate Elara being lazy sometimes
            if char_to_act.name == "Elara" and char_to_act.job == "Bookkeeper":
                # Make Elara lazy if too much time has passed since last "action" (simulated)
                # Forcing her to not update ledger to test Boris's reaction
                if game_time_obj.current_day > 3 and game_time_obj.current_day % 4 == 0 and elara_last_action_day < game_time_obj.current_day:
                     # On day 4, 8, 12 etc. if she hasn't "worked" that day.
                    if char_to_act.current_goal == "Maintain Ledger" or char_to_act.current_goal == "Count Stockpile":
                        print_tick_header()
                        print(f"  SIMULATING LAZINESS: {elara.name} decides to idle instead of '{char_to_act.current_goal}'.")
                        char_to_act.current_goal = "Idle" # Force her to be idle
                        # To make ledger stale, we can also directly manipulate ledger update day for testing
                        if game_world.stockpiles:
                            sp_to_make_stale = game_world.stockpiles[0]
                            if game_world.ledger.records.get(sp_to_make_stale.name): # Check if record exists
                                game_world.ledger.records[sp_to_make_stale.name]["last_updated_day"] = game_time_obj.current_day - (config.STALE_THRESHOLD_DAYS + 5 if hasattr(config, 'STALE_THRESHOLD_DAYS') else 7)
                                print(f"  DEBUG: Manually made {sp_to_make_stale.name} ledger entry stale for testing.")
                    elara_last_action_day = game_time_obj.current_day


            char_to_act.decide_action(game_world)

            # Log management related changes
            if char_to_act.name == boris.name: # Boris is the manager
                if original_goal != char_to_act.current_goal and char_to_act.current_goal == "Idle" and original_goal == "Manage Subordinates":
                    print_tick_header()
                    print(f"  MANAGER ACTIVITY: {boris.name} completed 'Manage Subordinates' cycle, now Idle.")

            if char_to_act.name == elara.name: # Elara is the subordinate
                if original_performance != char_to_act.performance_rating:
                    print_tick_header()
                    print(f"  PERFORMANCE CHANGE: {elara.name}'s performance changed from '{original_performance}' to '{char_to_act.performance_rating}' (Supervisor: {elara.supervisor_name}).")
                if original_warnings != char_to_act.warning_count:
                    print_tick_header()
                    print(f"  WARNING COUNT CHANGE: {elara.name} now has {char_to_act.warning_count} warnings (Supervisor: {elara.supervisor_name}).")
                if char_to_act.job == "Unemployed" and original_performance != "Fired": # Check if just got fired
                    print_tick_header()
                    print(f"  JOB STATUS CHANGE: {elara.name} is now '{char_to_act.job}'. Was supervised by {boris.name}.")


        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")
            # if gimli.equipped_tool: print(f"  Gimli's {gimli.equipped_tool['name']} durability: {gimli.equipped_tool['durability']}")

            for char_daily_reset in game_world.characters:
                # If idle, not working on a WO, and not fired, try to get a job default goal
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

            # Daily status print for relevant characters
            if boris in game_world.characters: print(f"  {boris.name} (Manager): Goal='{boris.current_goal}', Subordinates='{len(boris.subordinates_names)}'")
            if elara in game_world.characters: print(f"  {elara.name} (Bookkeeper): Goal='{elara.current_goal}', Performance='{elara.performance_rating}', Warnings='{elara.warning_count}', Supervisor='{elara.supervisor_name}'")
            else: print(f"  INFO: Elara is no longer in the world's character list (presumably fired and removed).")


            if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                game_world.advance_season()
                last_season_change_day = game_time_obj.current_day

        if game_time_obj.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State ---")
    print(f"Final Time: {game_time_obj}")
    for char_final in game_world.characters:
        print(char_final)
    print(f"ToolShed Final: {tool_shed}")
    print(f"WoodPile Final: {wood_stockpile}")

if __name__ == "__main__":
    main()
