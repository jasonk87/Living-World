# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS # Removed unused STRUCTURE_BLUEPRINTS for this test
from . import config
import random

def main():
    print("--- Game Configuration ---")
    print(f"USE_LLM: {config.USE_LLM if hasattr(config, 'USE_LLM') else 'Not Set'}")
    print("--------------------------")

    ticks_per_day = 10
    days_per_season = 10 # Longer season for more social time
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    # Clear any pre-existing stockpiles or resources if needed for a clean test
    game_world.stockpiles.clear()
    game_world.resources.clear()
    game_world.buildings.clear()


    # --- Character Setup for Social Interaction Test ---
    print("\n--- Character Setup (Social Interaction Test) ---")

    social_test_chars = []

    char1 = Character(name="Alice", personality="Outgoing", traits=["Friendly", "Charismatic"],
                      job="Idle", x=3,y=3, skills={}, needs={'Social': 15})
    game_world.add_character(char1)
    social_test_chars.append(char1)
    print(f"  Added: {char1.name} (Traits: {char1.traits}, SocialNeed: {char1.needs.get('Social')}) at ({char1.x},{char1.y})")

    char2 = Character(name="Bob", personality="Grumpy", traits=["Loner", "Grumpy"],
                      job="Idle", x=4,y=3, skills={}, needs={'Social': 10})
    game_world.add_character(char2)
    social_test_chars.append(char2)
    print(f"  Added: {char2.name} (Traits: {char2.traits}, SocialNeed: {char2.needs.get('Social')}) at ({char2.x},{char2.y})")

    char3 = Character(name="Charlie", personality="Neutral", traits=[],
                      job="Idle", x=3,y=4, skills={}, needs={'Social': 25}) # Starts a bit higher
    game_world.add_character(char3)
    social_test_chars.append(char3)
    print(f"  Added: {char3.name} (Traits: {char3.traits}, SocialNeed: {char3.needs.get('Social')}) at ({char3.x},{char3.y})")

    # Make sure some ground is walkable
    for r in range(2,6):
        for c in range(2,6):
            game_world.set_tile(r,c,"Grass")


    print(f"\n--- Simulation: Social Interaction Test ---")
    max_simulation_days = 7 # Shorter simulation focused on social interactions
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

    while running:
        new_day = game_time_obj.tick()
        current_total_ticks +=1

        header_printed_this_tick = False
        def print_tick_header(): # Simple closure for tick header
            nonlocal header_printed_this_tick
            if not header_printed_this_tick:
                # print(f"\nTick {current_total_ticks} | {game_time_obj} | {game_world.season}, {game_world.weather}")
                header_printed_this_tick = True

        for char_to_act in list(game_world.characters):
            if char_to_act not in game_world.characters: continue

            # Optional: Print per-tick character state for deep debugging social choices
            # print_tick_header()
            # print(f"  - {char_to_act.name} (Pos:({char_to_act.x},{char_to_act.y}), Goal: {char_to_act.current_goal}, Social: {char_to_act.needs.get('Social')})")
            char_to_act.decide_action(game_world)


        if new_day:
            print(f"\n*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")

            for char_daily_reset in game_world.characters:
                # Social Need Decay
                if 'Social' in char_daily_reset.needs:
                    char_daily_reset.needs['Social'] = max(0, char_daily_reset.needs['Social'] - random.randint(3,7)) # Randomize decay slightly

                # Reset goal if idle and not already trying to socialize
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   not char_daily_reset.active_build_order_id and \
                   char_daily_reset.job != "Unemployed": # and char_daily_reset.current_goal != "Socialize": # Avoid interrupting an ongoing attempt
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()


            # Daily status print for test characters
            for char_status in social_test_chars:
                if char_status in game_world.characters:
                    rel_scores = {name: score for name, score in char_status.relationships.items() if name in [c.name for c in social_test_chars]}
                    print(f"  {char_status.name} (Pos:({char_status.x},{char_status.y}), Goal='{char_status.current_goal}', SocialNeed: {char_status.needs.get('Social', 50):.0f}, Relationships: {rel_scores})")
                    # Print last few memories related to socialization
                    social_mems = [mem for mem in char_status.memory if "ocializ" in mem or "chat" in mem or "exchange" in mem or "relationship" in mem][-3:]
                    for mem in social_mems:
                        print(f"    Mem: {mem}")


            if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                game_world.advance_season()
                last_season_change_day = game_time_obj.current_day

        if game_time_obj.current_day > max_simulation_days:
            print(f"\nSimulation reached max days ({max_simulation_days}).")
            running = False

    print("\n--- Final State ---")
    print(f"Final Time: {game_time_obj}")
    for char_final in social_test_chars:
        if char_final in game_world.characters:
            print(f"\n{char_final}")
            print(f"  Final Needs: {char_final.needs}")
            print(f"  Relationships:")
            for other_char_name, score in char_final.relationships.items():
                 if other_char_name in [c.name for c in social_test_chars]: # Only show relationships with other test chars
                    print(f"    - With {other_char_name}: {score}")
            print(f"  Recent Social Memories:")
            social_mems = [mem for mem in char_final.memory if "ocializ" in mem or "chat" in mem or "exchange" in mem or "relationship" in mem][-5:]
            for mem in social_mems:
                print(f"    - {mem}")

if __name__ == "__main__":
    main()
