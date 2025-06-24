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
    game_world.add_character(gimli)
    game_world.add_character(elara)

    print("\n--- Initial State (Tool Usage Test) ---")
    print(f"Gimli: {gimli}")
    print(f"ToolShed: {tool_shed}")
    print(f"Ledger: {game_world.ledger}")
    print(f"Forest at (0,0): {game_world.get_tile(0,0)}")


    print("\n--- Simulation: Tool Usage & Durability ---")
    max_simulation_days = 3
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

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
            if char_to_act in game_world.characters:
                if char_to_act.name == "Gimli":
                    print_tick_header()
                    print(f"  Pre-Action {char_to_act.name}: Goal='{char_to_act.current_goal}', Tool='{char_to_act.equipped_tool.get('name') if char_to_act.equipped_tool else 'None'}', TaskProg={char_to_act.task_work_progress}, FetchInfo={char_to_act.fetching_tool_info}, Pos=({char_to_act.x},{char_to_act.y}), Inv={char_to_act.inventory}")

                char_to_act.decide_action(game_world)

                if char_to_act.name == "Gimli":
                    if header_printed_this_tick :
                         print(f"  Post-Action {char_to_act.name}: Goal='{char_to_act.current_goal}', Tool='{char_to_act.equipped_tool.get('name') if char_to_act.equipped_tool else 'None'}', TaskProg={char_to_act.task_work_progress}, FetchInfo={char_to_act.fetching_tool_info}, Pos=({char_to_act.x},{char_to_act.y}), Inv={char_to_act.inventory}")

        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. ***")
            if gimli.equipped_tool: print(f"  Gimli's {gimli.equipped_tool['name']} durability: {gimli.equipped_tool['durability']}")

            for char_daily_reset in game_world.characters:
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and not char_daily_reset.active_work_order_id :
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

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
