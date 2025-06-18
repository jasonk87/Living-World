# game/main.py
from .character import Character
from .world import World
from .time import Time
from . import config
import random

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM}")
    if config.USE_LLM:
        print(f"LLM_ENDPOINT: {config.LLM_ENDPOINT}")
        print(f"LLM_MODEL: {config.LLM_MODEL}")
        print(f"LLM_HAS_THINKING_TAGS: {config.LLM_HAS_THINKING_TAGS}")
    print("--------------------------")

    ticks_per_day = 3
    days_per_season = 4 # Shorter seasons for faster cycles
    game_time = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(5, 5))

    # Resources
    wood_loc = (0,1) # Define a specific wood location
    for _ in range(15): game_world.add_resource("Wood", wood_loc, tile_becomes="Forest")
    game_world.add_resource("Stone", (2,3), tile_becomes="Rocks")
    game_world.set_tile(0,0,"Grass") # Gimli's start tile
    game_world.set_tile(2,2,"Grass") # Elara's start tile


    # Characters
    gimli = Character(name="Gimli", personality="gruff and focused", traits=["Hard-working", "Likes routine"],
                      skills={"Woodcutting": 10}, x=0, y=0,
                      needs={"Wood": 7}, job="Woodcutter",
                      current_goal=None) # Initial goal will be set by AI based on job

    elara = Character(name="Elara", personality="kind and observant", traits=["Patient", "Enjoys quiet"],
                      skills={"healing": 4}, x=2, y=2,
                      needs={}, job=None, current_goal="Wander")

    game_world.add_character(gimli)
    game_world.add_character(elara)

    print("\n--- Initial State ---")
    print(game_world)
    print("World Grid (Initial):")
    for r_idx in range(game_world.grid_size[0]):
        print([game_world.get_tile(r_idx,c_idx) for c_idx in range(game_world.grid_size[1])])
    print(f"Resources Map (Initial): {game_world.resources}")
    print(f"Time (Initial): {game_time}")
    print(f"Gimli: {gimli}")
    print(f"Elara: {elara}")


    print("\n--- AI Simulation with Woodcutter Job ---")
    max_simulation_days = 10 # Simulate for enough days to see job cycles
    last_season_change_day = game_time.current_day
    running = True
    current_total_ticks = 0

    while running:
        new_day = game_time.tick()
        current_total_ticks +=1

        if new_day or game_time.current_tick == 0 :
             print(f"\nTick {current_total_ticks} | {game_time} | {game_world.season}, {game_world.weather}")

        # AI decision making for each character
        # print(f"--- Characters Acting (Day {game_time.current_day}, Tick {game_time.current_tick}) ---")
        for char_to_act in list(game_world.characters):
            if char_to_act in game_world.characters:
                # print(f"Deciding for {char_to_act.name} (Goal: {char_to_act.current_goal}, Job: {char_to_act.job}, Inv: {char_to_act.inventory})")
                char_to_act.decide_action(game_world)

        if new_day:
            print(f"*** NEW DAY: Day {game_time.current_day}. Gimli wood: {gimli.inventory.get('Wood',0)}. Elara pos:({elara.x},{elara.y}) ***")
            # Daily job goal reset for Woodcutter if they finished a cycle
            if gimli.job == "Woodcutter" and gimli.current_goal not in ["Perform Woodcutter Duties", "Gather Wood", "Stockpile Wood"]:
                print(f"New day for Woodcutter Gimli. Current goal: '{gimli.current_goal}'. Re-evaluating duties.")
                gimli.current_goal = "Perform Woodcutter Duties" # Prompt re-evaluation of job needs

            if (game_time.current_day - last_season_change_day) >= days_per_season:
                game_world.advance_season()
                last_season_change_day = game_time.current_day

        if game_time.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State After Woodcutter Job Simulation ---")
    print(f"Final Time: {game_time}")
    print(game_world)
    for char_final in game_world.characters:
        print(f"Character: {char_final.name}, Pos: ({char_final.x},{char_final.y}), Job: {char_final.job}, Goal: {char_final.current_goal}")
        print(f"  Inv: {char_final.inventory}")
        print(f"  Memory (last 5): {char_final.memory[-5:]}")
        print(f"  Relationships: {char_final.relationships}")
    print("Final World Grid:")
    for r_idx in range(game_world.grid_size[0]):
        print([game_world.get_tile(r_idx,c_idx) for c_idx in range(game_world.grid_size[1])])
    print(f"Final Remaining Resources in World: {game_world.resources}")

if __name__ == "__main__":
    main()
