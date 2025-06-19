# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile
from .work_order import WorkOrder
from . import config
import random

# Helper function to establish reporting lines
def set_reporting_line(supervisor: Character, subordinate: Character):
    subordinate.set_supervisor(supervisor.name)
    supervisor.add_subordinate(subordinate.name)
    # print(f"Hierarchy: {subordinate.name} reports to {supervisor.name}.") # Reduce noise

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM}")
    print("--------------------------")

    ticks_per_day = 3
    days_per_season = 3 # Shorter for faster season changes if needed for testing
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    # Stockpiles
    main_store = Stockpile(name="MainStore", x=3, y=3, width=2, height=2,
                           allowed_resources=["Wood", "Stone", "Wooden Chair", "Stone Axe"],
                           total_capacity=100)
    game_world.add_stockpile(main_store)
    wood_pile_1 = Stockpile(name="WoodPile1", x=0, y=4, width=1, height=1, # Adjusted y for less overlap with forest
                              allowed_resources=["Wood"], capacity_per_resource=50)
    game_world.add_stockpile(wood_pile_1)
    stone_pile_1 = Stockpile(name="StonePile1", x=8,y=4,width=1,height=1, # Adjusted y
                               allowed_resources=["Stone"], capacity_per_resource=40)
    game_world.add_stockpile(stone_pile_1)

    # Resources
    forest_loc = (0,0);
    for _ in range(30): game_world.add_resource("Wood", forest_loc, tile_becomes="Forest")
    rock_loc = (8,8);
    for _ in range(20): game_world.add_resource("Stone", rock_loc, tile_becomes="Rocks")
    # Clear starting character positions
    game_world.set_tile(1,0,"Grass"); game_world.set_tile(2,1,"Grass");
    game_world.set_tile(3,1,"Grass"); game_world.set_tile(4,1,"Grass");
    game_world.set_tile(7,8,"Grass") # For Balin


    # Characters
    thorin = Character(name="Thorin", personality="leaderly", traits=["Decisive", "Strategic"], job="Expedition Leader", x=4,y=1, skills={}, max_inventory_items=5, current_goal=None)
    borin = Character(name="Borin", personality="decisive", traits=["Fair", "Blunt"], job="Manager", x=3,y=1, skills={}, max_inventory_items=1, current_goal=None)
    elara = Character(name="Elara", personality="meticulous", traits=["Quiet", "Observant"], job="Bookkeeper", x=2,y=1, skills={}, max_inventory_items=1, current_goal=None)
    gimli = Character(name="Gimli", personality="diligent", traits=["Grumbling", "Strong"], job="Woodcutter", x=1,y=0, skills={"Woodcutting":5}, needs={"Wood":7}, max_inventory_items=5, current_goal=None)
    balin = Character(name="Balin", personality="sturdy", traits=["Patient", "Methodical"], job="Stonemason", x=7,y=8, skills={"Mining":5}, needs={"Stone":5}, max_inventory_items=4, current_goal=None)

    game_world.add_character(thorin); game_world.add_character(borin);
    game_world.add_character(elara); game_world.add_character(gimli);
    game_world.add_character(balin)

    # Setup Hierarchy
    # print("\n--- Setting Up Hierarchy ---") # Reduce noise
    set_reporting_line(supervisor=thorin, subordinate=borin)
    set_reporting_line(supervisor=borin, subordinate=elara)
    set_reporting_line(supervisor=borin, subordinate=gimli)
    set_reporting_line(supervisor=borin, subordinate=balin)

    # Work Orders
    wo1_details = {"item_name": "Wooden Chairs (x5)", "required_resources": {"Wood": 10}} # Needs 10 wood
    wo1 = WorkOrder(order_type="CraftItem", details=wo1_details, creation_day=game_time_obj.current_day, priority=1)
    game_world.add_work_order(wo1)
    wo2_details = {"item_name": "Stone Axes (x2)", "required_resources": {"Stone": 6, "Wood": 2}} # Needs 6 stone, 2 wood
    wo2 = WorkOrder(order_type="CraftItem", details=wo2_details, creation_day=game_time_obj.current_day, priority=2)
    game_world.add_work_order(wo2)

    print("\n--- Initial State ---")
    print(game_world)
    # ... (print grid, characters, stockpiles as needed for brevity) ...
    print("\nInitial Ledger State:"); print(game_world.ledger)
    print("Initial Work Orders:");
    for wo_init in game_world.work_orders: print(f"  {wo_init}")


    print("\n--- Simulation: Manager & Stale Data Check ---")
    max_simulation_days = 5
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

    while running:
        new_day = game_time_obj.tick()
        current_total_ticks +=1

        if new_day or game_time_obj.current_tick == 0 :
             print(f"\nTick {current_total_ticks} | {game_time_obj} | {game_world.season}, {game_world.weather}")
             if game_time_obj.current_tick == 0:
                for char_status in game_world.characters:
                     print(f"  {char_status.name} ({char_status.job}): Goal='{char_status.current_goal}', Pos=({char_status.x},{char_status.y}), Inv={char_status.inventory}")

        for char_to_act in list(game_world.characters):
            if char_to_act in game_world.characters:
                char_to_act.decide_action(game_world)

        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. ***")
            print("  Ledger Status on new day:"); print(f"{game_world.ledger}")
            print("  Work Order Status (Pending):")
            pending_wo_count = 0
            for wo_daily in game_world.work_orders:
                if wo_daily.status == "Pending":
                    print(f"    PENDING: ID: {wo_daily.order_id}, Item: {wo_daily.details.get('item_name') or wo_daily.details.get('structure_type')}")
                    pending_wo_count+=1
            if pending_wo_count == 0: print("    No pending work orders.")


            for char_daily_reset in game_world.characters:
                if char_daily_reset.current_goal in ["Wander", None, "Idle"]:
                    job = char_daily_reset.job
                    if job == "Manager": char_daily_reset.current_goal = "Manage Work Orders"
                    elif job == "Bookkeeper": char_daily_reset.current_goal = "Maintain Ledger"
                    elif job == "Woodcutter": char_daily_reset.current_goal = "Perform Woodcutter Duties"
                    elif job == "Stonemason": char_daily_reset.current_goal = "Perform Stonemason Duties"
                    elif job == "Expedition Leader": char_daily_reset.current_goal = "Oversee Expedition"

            if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                game_world.advance_season()
                last_season_change_day = game_time_obj.current_day

        if game_time_obj.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State ---")
    print(f"Final Time: {game_time_obj}")
    print(game_world)
    print("\nCharacters (Final):")
    for char_final in game_world.characters: print(char_final)
    print("\nStockpiles (Final):")
    for sp_final in game_world.stockpiles: print(f"  {sp_final}")
    print("\nFinal Ledger State:"); print(game_world.ledger)
    print("\nFinal Work Order Status:");
    for wo_final in game_world.work_orders: print(f"  {wo_final}")
    print(f"\nBorin (Manager) Final Memory (last 10): {borin.memory[-10:] if borin.memory else '[]'}")

if __name__ == "__main__":
    main()
