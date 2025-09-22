import sys
import os
# Add the project root to sys.path
# Assumes main.py is in 'game/' and the project root is one directory up.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from game.character import Character
from game.world import World
from game.time import Time
from game.stockpile import Stockpile
from game.work_order import WorkOrder
from game.data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from game.building import Building
from game import config

import random
import curses # Keep for now, might be used by main_simulation_logic
from typing import Optional, Dict, Any, List

import http.server
import socketserver
import json
import threading
import time as py_time # Renamed to avoid conflict with game.time.Time
import mimetypes

# --- Global Game State Variables ---
game_world: Optional[World] = None
game_time_obj: Optional[Time] = None
simulation_running = True # Controls the simulation loop
game_paused = False       # To pause/resume the simulation
SIMULATION_SPEED_MULTIPLIER = 1.0 # 1.0 is normal speed
BASE_TICK_SLEEP_DURATION = 0.2 # Seconds for 1x speed per tick
test_characters_list: List[Character] = [] # To store characters for final report

# --- Simulation Logic ---
def initialize_game_world():
    global game_world, game_time_obj, test_characters_list

    initial_setup_messages = []
    initial_setup_messages.append("--- Initializing Game World (Server Mode) ---")

    ticks_per_day = config.TICKS_PER_DAY if hasattr(config, 'TICKS_PER_DAY') else 10 # Default if not in config
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    test_characters_list = [] # Reset for this initialization

    # Stockpiles (example setup)
    wood_stockpile = Stockpile(name="WoodStore", x=0, y=3, width=1, height=1, allowed_resources=["Wood"], total_capacity=100)
    wood_stockpile.add_item("Wood", 40)
    game_world.add_stockpile(wood_stockpile)
    game_world.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)
    initial_setup_messages.append(f"Added WoodStore stockpile with {wood_stockpile.inventory.get('Wood',0)} Wood.")

    # Characters (example setup)
    liam_skills = {"Construction": 2, "Crafting": 1, "Woodcutting": 1}
    liam = Character(name="Liam", personality="Optimistic", traits=["Diligent"],
                      job="Builder", x=2,y=1, skills=liam_skills, rank="Worker",
                      needs={"Hunger": 80, "Social": 60, "Energy": 100})
    game_world.add_character(liam)
    test_characters_list.append(liam)
    initial_setup_messages.append(f"  Added: {liam.name} (Job: {liam.job}) at ({liam.x},{liam.y})")

    # Add a potential Mayor candidate
    elara_skills = {"Leadership": 7, "Medicine": 2}
    elara = Character(name="Elara", personality="Wise", traits=["Intelligent", "Forgiving"],
                        job="Noble", x=5,y=5, skills=elara_skills, rank="Noble Lord",
                        needs={"Hunger": 85, "Social": 80, "Energy": 100})
    game_world.add_character(elara)
    test_characters_list.append(elara)
    initial_setup_messages.append(f"  Added: {elara.name} (Job: {elara.job}, Rank: {elara.rank}) at ({elara.x},{elara.y})")

    # Add a Woodcutter
    finn_skills = {"Woodcutting": 3, "Mining": 1}
    finn = Character(name="Finn", personality="Gruff", traits=["Strong"],
                        job="Woodcutter", x=1, y=8, skills=finn_skills, rank="Worker",
                        needs={"Hunger": 75, "Social": 40, "Energy": 100})
    game_world.add_character(finn)
    test_characters_list.append(finn)
    initial_setup_messages.append(f"  Added: {finn.name} (Job: {finn.job}) at ({finn.x},{finn.y})")


    # Initial Build Order (Optional, can be removed if Mayor initiates projects)
    # hut_bp_key = "wooden_hut" ... (rest of build order setup from original main_simulation_logic)
    # For now, let's assume the Mayor will initiate projects.

    for msg in initial_setup_messages:
        print(msg)
        if game_world: game_world.add_event_log_message(msg)

    if game_world: game_world.add_event_log_message("--- Simulation Server Initialized ---")


def tick_simulation():
    global game_world, game_time_obj, simulation_running, game_paused, test_characters_list

    if not game_world or not game_time_obj:
        print("Error: Game world or time object not initialized.")
        simulation_running = False
        return

    if not game_paused and simulation_running:
        new_day = game_time_obj.tick()
        # current_total_ticks +=1 # This was local, can be re-added if needed for other metrics

        for char_to_act in list(game_world.characters): # Iterate over a copy if list might change
            if char_to_act not in game_world.characters: continue # If character was removed (e.g. fired and despawned)
            # if hasattr(char_to_act, 'process_status_effects'): char_to_act.process_status_effects(game_world) # If status effects exist
            char_to_act.decide_action(game_world)

        if new_day:
            day_msg = f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***"
            print(day_msg); game_world.add_event_log_message(day_msg)

            if hasattr(game_time_obj, 'days_until_election') and game_time_obj.days_until_election <= 0:
                if hasattr(game_world, 'handle_election'):
                    game_world.handle_election()
                else:
                    game_world.add_event_log_message("ERROR: Election due but handle_election method not found in world.")
                    if hasattr(config, 'ELECTION_CYCLE_DAYS'):
                         game_time_obj.days_until_election = config.ELECTION_CYCLE_DAYS

            # Daily rumor update
            if hasattr(game_world, 'update_rumors_daily'):
                game_world.update_rumors_daily()


            # Daily updates for needs, rumors, etc.
            game_world.update_character_needs()
            game_world.update_rumors_daily()

            # Daily status checks (sickness, injury) and goal resets for idle characters
            for char_daily_reset in game_world.characters:
                # Sickness & Injury Chance
                if not char_daily_reset.is_sick and random.random() < 0.005: # 0.5% chance per day to get sick
                    char_daily_reset.is_sick = True
                    char_daily_reset.sickness_severity = random.randint(1, 3) # Mild sickness
                    game_world.add_event_log_message(f"{char_daily_reset.name} has fallen ill (Severity: {char_daily_reset.sickness_severity}).")
                    char_daily_reset.add_memory("Fell ill.")
                    char_daily_reset.needs['Safety'] = max(config.NEED_SCORE_MIN, char_daily_reset.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 15) # Sickness reduces safety
                    char_daily_reset.add_memory(f"Sickness reduced my safety. Safety: {char_daily_reset.needs['Safety']}")


                injury_chance = 0.002 # Base 0.2% chance
                if char_daily_reset.job in ["Builder", "Woodcutter", "Stonemason", "Miner"]: # Example risky jobs
                    injury_chance = 0.005 # 0.5% for riskier jobs
                if not char_daily_reset.is_injured and random.random() < injury_chance:
                    char_daily_reset.is_injured = True
                    char_daily_reset.injury_severity = random.randint(1, 3) # Mild injury
                    game_world.add_event_log_message(f"{char_daily_reset.name} has been injured (Severity: {char_daily_reset.injury_severity}).")
                    char_daily_reset.add_memory("Got injured.")
                    char_daily_reset.needs['Safety'] = max(config.NEED_SCORE_MIN, char_daily_reset.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 20) # Injury significantly reduces safety
                    char_daily_reset.add_memory(f"Injury reduced my safety. Safety: {char_daily_reset.needs['Safety']}")

                # Reset goal for idle characters so they re-evaluate their primary job goal
                if char_daily_reset.current_goal.type in [GoalType.IDLE, GoalType.WANDER] and \
                   not char_daily_reset.active_work_order_id and \
                   not char_daily_reset.active_build_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.get_default_goal()

            # Season advancement
            days_per_season = config.DAYS_PER_SEASON if hasattr(config, 'DAYS_PER_SEASON') else 10 # Default if not in config
            # Need to track last_season_change_day or current day relative to season start
            if game_time_obj.current_day % days_per_season == 1 and game_time_obj.current_day > 1 : # Simple modulo check
                 game_world.advance_season()


        max_simulation_days = config.MAX_SIMULATION_DAYS if hasattr(config, 'MAX_SIMULATION_DAYS') else 20
        if game_time_obj.current_day > max_simulation_days:
            msg = f"Simulation reached max days ({max_simulation_days}). Stopping simulation thread."; print(msg); game_world.add_event_log_message(msg)
            simulation_running = False # Stop the simulation thread

def simulation_thread_func():
    global simulation_running
    print("Simulation thread started.")
    while simulation_running:
        if not game_paused:
            tick_simulation()

        current_sleep_duration = BASE_TICK_SLEEP_DURATION
        if SIMULATION_SPEED_MULTIPLIER > 0: # Avoid division by zero or negative multipliers
            current_sleep_duration /= SIMULATION_SPEED_MULTIPLIER

        py_time.sleep(max(0.01, current_sleep_duration)) # Ensure a minimum sleep to prevent overly tight loops

    print("Simulation thread finished.")
    # Print final character states after simulation stops
    if game_world and test_characters_list:
        print(f"Final Time: {game_time_obj}")
        for char_final in test_characters_list:
            if char_final in game_world.characters: # Check if still in world
                print(f"\n{char_final}")
                print(f"  Final Needs: {char_final.needs}")
                print(f"  Inventory: {char_final.inventory}")
                print(f"  Recent Memories (last 10):")
                for mem in char_final.memory[-10:]: print(f"    - {mem}")
        print("\n--- World Event Log (Last 50) ---")
        for log_entry in game_world.event_log[-50:]: print(log_entry)


# --- HTTP Server Logic ---
PORT = 8000
class GameDataHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global game_world, game_time_obj, game_paused, simulation_running, SIMULATION_SPEED_MULTIPLIER
        if self.path == '/game_state':
            if game_world and game_time_obj:
                # This is the full, correct data structure for the game state
                grid_repr = [[game_world.get_tile(c, r) for c in range(game_world.grid_size[1])] for r in range(game_world.grid_size[0])]
                characters_repr = [char.to_dict() for char in game_world.characters]
                event_log_repr = game_world.event_log[-20:]
                buildings_repr = [b.to_dict() for b in (game_world.buildings or []) + (game_world.stockpiles or [])]
                state = {
                    "day": game_time_obj.current_day, "tick": game_time_obj.current_tick,
                    "ticks_per_day": game_time_obj.ticks_per_day, "season": game_world.season,
                    "weather": game_world.weather, "grid_size": game_world.grid_size,
                    "grid": grid_repr, "characters": characters_repr, "event_log": event_log_repr,
                    "is_paused": game_paused, "days_until_election": getattr(game_time_obj, 'days_until_election', -1),
                    "current_speed_multiplier": SIMULATION_SPEED_MULTIPLIER,
                    "buildings": buildings_repr
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(state, default=lambda o: o.to_dict() if hasattr(o, 'to_dict') else str(o)).encode('utf-8'))
            else:
                self.send_error(503, "Game world not initialized")

        # Add other API endpoints here as elif blocks

        else:
            # Fallback to serving files from the 'ui' directory
            original_cwd = os.getcwd()
            ui_path = os.path.join(project_root, 'ui')
            try:
                os.chdir(ui_path)
                super().do_GET()
            finally:
                os.chdir(original_cwd)

    def do_POST(self):
        global game_paused, SIMULATION_SPEED_MULTIPLIER
        if self.path == '/toggle_pause':
            game_paused = not game_paused
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"paused": game_paused}).encode('utf-8'))
        elif self.path.startswith('/set_speed'):
            # ... (logic for set_speed)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_error(404, "Endpoint not found")



# --- Main Execution ---
if __name__ == "__main__":
    initialize_game_world()

    sim_thread = threading.Thread(target=simulation_thread_func, daemon=True)
    sim_thread.start()

    httpd = None
    try:
        with socketserver.TCPServer(("", PORT), GameDataHandler) as httpd:
            print(f"Serving HTTP on port {PORT}...")
            print("Game simulation running in background. Access UI at http://localhost:8000/ (assuming index.html in ui folder)")
            print("Press Ctrl+C to stop server and simulation.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCtrl+C received. Shutting down server and simulation...")
    finally:
        simulation_running = False # Signal simulation thread to stop
        if httpd:
            httpd.shutdown() # Stop the HTTP server
            httpd.server_close() # Release the port
        if sim_thread.is_alive():
            sim_thread.join() # Wait for simulation thread to finish

    print("Exited gracefully.")
