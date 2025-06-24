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

    # --- Character Setup for Phase 3 Testing: Trait-based Task Performance ---

    # Remove Phase 2 characters for cleaner logs, or keep them if combined testing is desired.
    # For now, let's remove Phase 2 specific characters to focus on task performance traits.
    phase2_chars = [char for char in game_world.characters if "_P2" in char.name or "Boris_" in char.name or "Flora_" in char.name]
    for p2c in phase2_chars:
        if p2c in game_world.characters: game_world.remove_character(p2c)
    if gimli in game_world.characters: game_world.remove_character(gimli)
    if elara in game_world.characters: game_world.remove_character(elara)


    # Worker Set 1: Woodcutters
    woody_normal = Character(name="Woody_Normal", personality="neutral", traits=[], job="Woodcutter", x=1,y=1, skills={"Woodcutting":5}, needs={"Wood":20})
    woody_lazy = Character(name="Woody_Lazy", personality="laid-back", traits=["Lazy"], job="Woodcutter", x=1,y=2, skills={"Woodcutting":5}, needs={"Wood":20})
    woody_diligent = Character(name="Woody_Diligent", personality="hard-working", traits=["Diligent"], job="Woodcutter", x=1,y=3, skills={"Woodcutting":5}, needs={"Wood":20})
    woody_strong = Character(name="Woody_Strong", personality="robust", traits=["Strong"], job="Woodcutter", x=1,y=4, skills={"Woodcutting":5}, needs={"Wood":20})
    woody_focused_lazy = Character(name="Woody_FocusedLazy", personality="intense", traits=["Focused", "Lazy"], job="Woodcutter", x=1,y=5, skills={"Woodcutting":5}, needs={"Wood":20}) # Focused should override Lazy

    game_world.add_character(woody_normal)
    game_world.add_character(woody_lazy)
    game_world.add_character(woody_diligent)
    game_world.add_character(woody_strong)
    game_world.add_character(woody_focused_lazy)

    # Worker Set 2: Bookkeepers
    booky_normal = Character(name="Booky_Normal", personality="neutral", traits=[], job="Bookkeeper", x=3,y=1)
    booky_careless = Character(name="Booky_Careless", personality="absent-minded", traits=["Careless"], job="Bookkeeper", x=3,y=2)

    game_world.add_character(booky_normal)
    game_world.add_character(booky_careless)

    # Ensure there's at least one stockpile with some items for Bookkeepers to (mis)count
    if not wood_stockpile.inventory: # Add some items if empty for consistent testing
        wood_stockpile.add_item("Wood", 10) # So bookkeepers have something to count.
        game_world.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)


    print(f"\n--- Character Setup (Phase 3 - Task Performance Traits) ---")
    for char in [woody_normal, woody_lazy, woody_diligent, woody_strong, woody_focused_lazy, booky_normal, booky_careless]:
        print(f"  {char.name} (Job: {char.job}, Traits: {char.traits}, Personality: {char.personality})")
    print(f"Initial Wood in {wood_stockpile.name}: {wood_stockpile.inventory.get('Wood',0)}")

    print("\n--- Simulation: Trait-Driven Task Performance ---")
    max_simulation_days = 5 # Shorter sim, focus on task differences over a few days
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

    # Store initial inventory/ledger state for comparison if needed, or rely on prints
    initial_ledger_wood = game_world.ledger.get_total_resource_count("Wood")


    while running:
        new_day = game_time_obj.tick()
        current_total_ticks +=1

        header_printed_this_tick = False
        def print_tick_header():
            nonlocal header_printed_this_tick
            if not header_printed_this_tick:
                print(f"\nTick {current_total_ticks} | {game_time_obj} | {game_world.season}, {game_world.weather}")
                header_printed_this_tick = True

        # --- Log specific trait-triggered events ---
        # This requires characters to log memories when traits trigger, which they now do.
        # We can iterate memories or just observe print statements from character methods.

        for char_to_act in list(game_world.characters):
            if char_to_act not in game_world.characters: continue

            # Store pre-action state for logging trait effects
            pre_action_inv = char_to_act.inventory.copy()
            pre_action_tool_dur = char_to_act.equipped_tool['durability'] if char_to_act.equipped_tool else None

            char_to_act.decide_action(game_world) # This is where traits will affect actions

            # Log changes potentially due to traits
            if char_to_act.job == "Woodcutter":
                wood_gathered_this_tick = char_to_act.inventory.get("Wood", 0) - pre_action_inv.get("Wood", 0)
                if wood_gathered_this_tick > 0 : # Implicitly logs yield differences
                    pass # Already printed by _execute_generic_task

            if char_to_act.equipped_tool and pre_action_tool_dur is not None:
                if char_to_act.equipped_tool['durability'] < pre_action_tool_dur -1 : # More than 1 durability lost
                    print_tick_header()
                    print(f"  TOOL WEAR: {char_to_act.name}'s {char_to_act.equipped_tool['name']} lost {pre_action_tool_dur - char_to_act.equipped_tool['durability']} durability (Traits: {char_to_act.traits}).")


        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")
            for char_daily_reset in game_world.characters:
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

            # Daily status print for task performance characters
            for char_status in [woody_normal, woody_lazy, woody_diligent, woody_strong, woody_focused_lazy, booky_normal, booky_careless]:
                if char_status in game_world.characters:
                     print(f"  {char_status.name} (Job: {char_status.job}, Traits: {char_status.traits}): Goal='{char_status.current_goal}', Inv: {char_status.inventory.get('Wood',0)} Wood. Tool: {char_status.equipped_tool['name'] if char_status.equipped_tool else 'None'}")


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
