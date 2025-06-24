# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS
from . import config
import random

# Helper function
def set_reporting_line(supervisor: Character, subordinate: Character):
    subordinate.set_supervisor(supervisor.name)
    supervisor.add_subordinate(subordinate.name)

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM}")
    print("--------------------------")

    ticks_per_day = 10
    days_per_season = 3 # Defined here
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    # --- Stockpiles ---
    wood_source_pile = Stockpile(name="WoodSupply", x=0, y=1, width=1, height=1,
                                 allowed_resources=["Wood"], capacity_per_resource=50)
    game_world.add_stockpile(wood_source_pile)
    wood_source_pile.add_item("Wood", 20)
    game_world.ledger.update_stockpile_record(wood_source_pile.name, wood_source_pile.inventory, game_time_obj.current_day)
    print(f"Pre-stocked {wood_source_pile.name} with 20 Wood. Ledger updated.")

    finished_goods_store = Stockpile(name="FinishedGoods", x=3, y=1, width=1, height=1,
                                     allowed_resources=["Wooden Chair", "Stone Axe", "Wooden Bed"], total_capacity=50)
    game_world.add_stockpile(finished_goods_store)
    game_world.ledger.update_stockpile_record(finished_goods_store.name, finished_goods_store.inventory, game_time_obj.current_day)

    # --- Resources in World (minimal for this test) ---
    forest_loc = (0,0)
    for _ in range(5):
        game_world.add_resource("Wood", forest_loc, tile_becomes="Forest")

    game_world.set_tile(1,1,"Grass"); game_world.set_tile(2,0,"Grass"); game_world.set_tile(1,0,"Grass"); game_world.set_tile(0,0,"Grass")


    # --- Characters ---
    dwalin = Character(name="Dwalin", personality="focused craftsman", traits=["Creative"], job="Master Craftsman", x=1, y=1,
                       skills={"Carpentry": 8, "Design": 7}, max_inventory_items=10, current_goal=None)
    dwalin.managed_item_targets = {"Wooden Chair": 1}

    borin = Character(name="Borin", personality="efficient manager", traits=["Pragmatic"], job="Manager", x=2,y=0,
                      skills={"Management": 7}, current_goal=None)

    elara = Character(name="Elara", personality="diligent bookkeeper", traits=["Meticulous"], job="Bookkeeper", x=1,y=0,
                      skills={"Accounting": 7}, max_inventory_items=1, current_goal=None)

    thorin = Character(name="Thorin", personality="stern leader", traits=["Decisive"], job="Expedition Leader", x=0,y=0,
                       skills={"Leadership": 8}, current_goal=None)
    gimli = Character(name="Gimli", personality="gruff but reliable", job="Woodcutter", traits=["Hard-working"], x=5,y=5,
                      skills={"Woodcutting":7, "Carpentry":5}, needs={"Wood":5}, max_inventory_items=5, current_goal=None)

    game_world.add_character(dwalin); game_world.add_character(borin);
    game_world.add_character(elara); game_world.add_character(thorin); game_world.add_character(gimli)

    # --- Hierarchy ---
    set_reporting_line(supervisor=thorin, subordinate=borin)
    set_reporting_line(supervisor=borin, subordinate=dwalin)
    set_reporting_line(supervisor=borin, subordinate=elara)
    set_reporting_line(supervisor=borin, subordinate=gimli)


    print("\n--- Initial State for Full Crafting Lifecycle Test ---")
    print(f"Dwalin (MC/Crafter): {dwalin}, Targets: {dwalin.managed_item_targets}")
    print(f"Borin (Manager): {borin}")
    print(f"Elara (Bookkeeper): {elara}")
    print(f"Wood Supply Stockpile: {wood_source_pile}")
    print(f"Finished Goods Stockpile: {finished_goods_store}")
    print(f"Initial Ledger: {game_world.ledger}")
    print("Initial Work Orders (should be empty):")
    for wo_init in game_world.work_orders: print(f"  {wo_init}")


    print("\n--- Simulation: Full Crafting Lifecycle ---")
    max_simulation_days = 4
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
                # More focused debug for Dwalin or active crafters
                if char_to_act.name == "Dwalin" or char_to_act.active_work_order_id:
                    print_tick_header()
                    print(f"  Pre-Action {char_to_act.name}: Goal='{char_to_act.current_goal}', WO='{char_to_act.active_work_order_id}', CraftState(M:{char_to_act.materials_gathered_for_wo},C:{char_to_act.items_crafted_for_wo},P:{char_to_act.crafting_progress}), Fetch:{char_to_act.resource_to_fetch}, Haul:{char_to_act.hauling_info}, Pos=({char_to_act.x},{char_to_act.y}), Inv={char_to_act.inventory}")

                char_to_act.decide_action(game_world)

                if char_to_act.name == "Dwalin" or char_to_act.active_work_order_id:
                    if header_printed_this_tick :
                         print(f"  Post-Action {char_to_act.name}: Goal='{char_to_act.current_goal}', WO='{char_to_act.active_work_order_id}', CraftState(M:{char_to_act.materials_gathered_for_wo},C:{char_to_act.items_crafted_for_wo},P:{char_to_act.crafting_progress}), Fetch:{char_to_act.resource_to_fetch}, Haul:{char_to_act.hauling_info}, Pos=({char_to_act.x},{char_to_act.y}), Inv={char_to_act.inventory}")

        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. ***")
            print("  Ledger Status on new day:"); print(f"  {game_world.ledger}")
            print("  Work Order Status:");
            if not game_world.work_orders: print("    No work orders.")
            else:
                for wo_daily in game_world.work_orders: print(f"    ID: {wo_daily.order_id[:8]}, Item: {wo_daily.details.get('item_name')}, Status: {wo_daily.status}, Assigned: {wo_daily.assigned_to}")

            for char_daily_reset in game_world.characters:
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and not char_daily_reset.active_work_order_id :
                    job = char_daily_reset.job
                    if job == "Master Craftsman": char_daily_reset.current_goal = "Assess Production Needs"
                    elif job == "Manager": char_daily_reset.current_goal = "Manage Work Orders"
                    elif job == "Bookkeeper": char_daily_reset.current_goal = "Maintain Ledger"
                    elif job == "Woodcutter": char_daily_reset.current_goal = "Perform Woodcutter Duties"
                    elif job == "Expedition Leader": char_daily_reset.current_goal = "Oversee Expedition"

            if (game_time_obj.current_day - last_season_change_day) >= days_per_season: # days_per_season is used here
                game_world.advance_season()
                last_season_change_day = game_time_obj.current_day

        if game_time_obj.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State ---")
    print(f"Final Time: {game_time_obj}")
    for char_final in game_world.characters:
        print(f"{char_final} (Mem Last 5: {char_final.memory[-5:] if char_final.memory else '[]'})")
    print("\nFinal Stockpiles:")
    print(f"  {wood_source_pile}")
    print(f"  {finished_goods_store}")
    print("\nFinal Ledger State:"); print(game_world.ledger)
    print("\nFinal Work Order Status:");
    if not game_world.work_orders: print("  No work orders at end.")
    else:
        for wo_final in game_world.work_orders: print(f"  {wo_final}")

if __name__ == "__main__":
    main()
