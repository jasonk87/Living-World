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

    # --- Character Setup for Phase 2 Testing ---
    # Subordinate
    elara_p2 = Character(name="Elara_P2", personality="diligent", traits=["Focused"], job="Bookkeeper",
                         x=4,y=4, skills={}, max_inventory_items=1, current_goal=None)
    game_world.add_character(elara_p2)

    # Supervisor 1: Strict and dislikes Elara_P2 initially
    boris_strict = Character(name="Boris_Strict", personality="Demanding", traits=["Strict", "Impatient"],
                             job="Manager", rank="Baron", x=5,y=5, skills={}, max_inventory_items=2)
    game_world.add_character(boris_strict)
    set_reporting_line(supervisor=boris_strict, subordinate=elara_p2)
    boris_strict.modify_relationship(elara_p2.name, -40, game_world, reason="Initial bad impression") # Negative start
    elara_p2.modify_relationship(boris_strict.name, -20, game_world, reason="Feels scrutinized")


    # Subordinate for Kind Supervisor
    pip = Character(name="Pip_P2", personality="cheerful", traits=["Careless"], job="Bookkeeper", # Careless bookkeeper
                    x=4,y=5, skills={}, max_inventory_items=1, current_goal=None)
    game_world.add_character(pip)

    # Supervisor 2: Kind and likes Pip_P2 initially
    flora_kind = Character(name="Flora_Kind", personality="Forgiving", traits=["Kind", "Patient"],
                           job="Manager", rank="Baron", x=5,y=6, skills={}, max_inventory_items=2)
    game_world.add_character(flora_kind)
    set_reporting_line(supervisor=flora_kind, subordinate=pip)
    flora_kind.modify_relationship(pip.name, 40, game_world, reason="Initial good impression") # Positive start
    pip.modify_relationship(flora_kind.name, 30, game_world, reason="Feels supported")

    # Keep Gimli for other activities if needed, or remove if focusing only on management
    # game_world.add_character(gimli)
    if gimli in game_world.characters: game_world.remove_character(gimli) # Remove Gimli for cleaner logs
    if elara in game_world.characters: game_world.remove_character(elara) # Remove old Elara

    print(f"\n--- Management Setup (Phase 2) ---")
    print(f"{boris_strict.name} ({boris_strict.personality}, Traits: {boris_strict.traits}) manages {elara_p2.name}. Initial Rel: {boris_strict.get_relationship_score(elara_p2.name)}")
    print(f"{elara_p2.name} supervised by {boris_strict.name}. Initial Rel to Sup: {elara_p2.get_relationship_score(boris_strict.name)}")
    print(f"{flora_kind.name} ({flora_kind.personality}, Traits: {flora_kind.traits}) manages {pip.name}. Initial Rel: {flora_kind.get_relationship_score(pip.name)}")
    print(f"{pip.name} supervised by {flora_kind.name}. Initial Rel to Sup: {pip.get_relationship_score(flora_kind.name)}")


    print("\n--- Initial State (Management Test - Phase 2) ---")
    print(f"ToolShed: {tool_shed}") # Stockpiles are relevant for Bookkeepers
    print(f"Ledger before sim: {game_world.ledger.records}")


    print("\n--- Simulation: Personality-Driven Management Actions ---")
    max_simulation_days = 20 # Increased to observe management cycles
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0
    # elara_last_action_day = 0 # No longer needed

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
            original_relationship_to_supervisor = None
            original_supervisor_relationship_to_char = None

            if char_to_act.supervisor_name:
                supervisor = next((c for c in game_world.characters if c.name == char_to_act.supervisor_name), None)
                if supervisor:
                    original_relationship_to_supervisor = char_to_act.get_relationship_score(supervisor.name)
                    original_supervisor_relationship_to_char = supervisor.get_relationship_score(char_to_act.name)

            # Simulate Bookkeepers being lazy sometimes to make ledgers stale
            if char_to_act.job == "Bookkeeper" and (char_to_act.name == elara_p2.name or char_to_act.name == pip.name) :
                # Make them lazy on certain days to test supervisor reactions
                if game_time_obj.current_day > 2 and game_time_obj.current_day % 3 == 0 : # Day 3, 6, 9 etc.
                    if char_to_act.current_goal == "Maintain Ledger" or char_to_act.current_goal == "Count Stockpile":
                        # Only make one of them lazy per trigger, to vary inputs to supervisors
                        if (char_to_act.name == elara_p2.name and random.random() < 0.6) or \
                           (char_to_act.name == pip.name and random.random() < 0.6 and pip.traits == ["Careless"]): # Pip is more likely to be lazy if careless
                            print_tick_header()
                            print(f"  SIMULATING LAZINESS: {char_to_act.name} ({char_to_act.personality}) decides to idle instead of '{char_to_act.current_goal}'.")
                            char_to_act.current_goal = "Idle"
                            # To ensure ledger becomes stale for sure during test period:
                            if game_world.stockpiles:
                                sp_to_make_stale = game_world.stockpiles[0]
                                if game_world.ledger.records.get(sp_to_make_stale.name):
                                    game_world.ledger.records[sp_to_make_stale.name]["last_updated_day"] = game_time_obj.current_day - (config.STALE_THRESHOLD_DAYS + 5)
                                    print(f"  DEBUG: Manually made {sp_to_make_stale.name} ledger entry stale for {char_to_act.name} to be reviewed on.")

            char_to_act.decide_action(game_world)

            # Log management related changes
            if char_to_act.job == "Manager": # For Boris_Strict or Flora_Kind
                if original_goal != char_to_act.current_goal and char_to_act.current_goal == "Idle" and original_goal == "Manage Subordinates":
                    print_tick_header()
                    print(f"  MANAGER ACTIVITY: {char_to_act.name} ({char_to_act.personality}) completed 'Manage Subordinates' cycle, now Idle.")

            if char_to_act.supervisor_name: # For Elara_P2 or Pip_P2
                supervisor = next((c for c in game_world.characters if c.name == char_to_act.supervisor_name), None)
                if supervisor:
                    new_relationship_to_supervisor = char_to_act.get_relationship_score(supervisor.name)
                    new_supervisor_relationship_to_char = supervisor.get_relationship_score(char_to_act.name)

                    if original_relationship_to_supervisor != new_relationship_to_supervisor:
                        print_tick_header()
                        print(f"  REL CHANGE: {char_to_act.name}'s rel with {supervisor.name} ({supervisor.personality}): {original_relationship_to_supervisor} -> {new_relationship_to_supervisor}")
                    if original_supervisor_relationship_to_char != new_supervisor_relationship_to_char:
                        print_tick_header()
                        print(f"  REL CHANGE: {supervisor.name}'s ({supervisor.personality}) rel with {char_to_act.name}: {original_supervisor_relationship_to_char} -> {new_supervisor_relationship_to_char}")


                if original_performance != char_to_act.performance_rating:
                    print_tick_header()
                    print(f"  PERF CHANGE: {char_to_act.name}'s performance changed from '{original_performance}' to '{char_to_act.performance_rating}' (Super: {char_to_act.supervisor_name}).")
                if original_warnings != char_to_act.warning_count:
                    print_tick_header()
                    print(f"  WARN CHANGE: {char_to_act.name} now has {char_to_act.warning_count} warnings (Super: {char_to_act.supervisor_name}).")
                if char_to_act.job == "Unemployed" and original_performance != "Fired":
                    print_tick_header()
                    print(f"  JOB STATUS CHANGE: {char_to_act.name} is now '{char_to_act.job}'. Was supervised by {char_to_act.supervisor_name or 'N/A'}.")


        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")
            for char_daily_reset in game_world.characters:
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

            # Daily status print for relevant characters
            for char_status in [boris_strict, elara_p2, flora_kind, pip]:
                if char_status in game_world.characters:
                    sup_name = char_status.supervisor_name
                    rel_to_sup_str = ""
                    if sup_name:
                        sup_char = next((c for c in game_world.characters if c.name == sup_name), None)
                        if sup_char:
                             rel_to_sup_str = f" RelToSup ({sup_char.personality}): {char_status.get_relationship_score(sup_name)}"

                    print(f"  {char_status.name} ({char_status.personality}, {char_status.job}, Rank:{char_status.rank}): Goal='{char_status.current_goal}', Perf='{char_status.performance_rating}', Warns='{char_status.warning_count}'{rel_to_sup_str}")
                elif char_status.job == "Unemployed" or char_status.performance_rating == "Fired": # If fired they might still be in the list but as Unemployed.
                     print(f"  INFO: {char_status.name} is {char_status.job} / {char_status.performance_rating}.")
                # else: print(f"  INFO: {char_status.name} is no longer in the world's active character list.")


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
