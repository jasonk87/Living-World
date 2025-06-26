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
    liam_skills = {"Construction": 1, "Leadership": 5} # Give Liam some leadership for potential Mayor candidacy
    liam = Character(name="Liam", personality="Optimistic", traits=["Diligent"],
                      job="Builder", x=2,y=1, skills=liam_skills, rank="Worker",
                      needs={"Hunger": 80, "Thirst": 70, "Energy": 100})
    game_world.add_character(liam)
    test_characters_list.append(liam)
    initial_setup_messages.append(f"  Added: {liam.name} (Job: {liam.job}) at ({liam.x},{liam.y})")

    # Add a potential Mayor candidate
    elara_skills = {"Leadership": 7, "Medicine": 2}
    elara = Character(name="Elara", personality="Wise", traits=["Intelligent", "Forgiving"],
                        job="Noble", x=5,y=5, skills=elara_skills, rank="Noble Lord")
    game_world.add_character(elara)
    test_characters_list.append(elara)
    initial_setup_messages.append(f"  Added: {elara.name} (Job: {elara.job}, Rank: {elara.rank}) at ({elara.x},{elara.y})")


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


            # Daily needs update and goal reset for idle characters
            for char_daily_reset in game_world.characters:
                char_daily_reset.needs['Hunger'] = max(0, char_daily_reset.needs.get('Hunger', 100) - random.randint(10, 20))
                char_daily_reset.needs['Thirst'] = max(0, char_daily_reset.needs.get('Thirst', 100) - random.randint(15, 25))
                # ... other needs updates
                if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                   not char_daily_reset.active_work_order_id and \
                   not char_daily_reset.active_build_order_id and \
                   char_daily_reset.job != "Unemployed":
                    char_daily_reset.current_goal = char_daily_reset.job_default_goal()

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
        global game_world, game_time_obj, game_paused, simulation_running, SIMULATION_SPEED_MULTIPLIER # Correct placement
        if self.path == '/game_state':
            if game_world and game_time_obj:
                # Ensure thread safety if accessing shared data that simulation thread modifies
                # For now, direct access, but consider locks for more complex state later

                # Create a simplified grid representation
                grid_repr = []
                if hasattr(game_world, 'grid') and game_world.grid:
                    for r_idx in range(game_world.grid_size[0]):
                        row_data = []
                        for c_idx in range(game_world.grid_size[1]):
                            row_data.append(game_world.get_tile(c_idx, r_idx)) # world uses (x,y) for get_tile
                        grid_repr.append(row_data)

                characters_repr = []
                if hasattr(game_world, 'characters'):
                    for char in game_world.characters:
                        characters_repr.append({
                            "name": char.name,
                            "x": char.x,
                            "y": char.y,
                            "job": char.job,
                            "goal": char.current_goal,
                            "is_sick": getattr(char, 'is_sick', False), # Add health status
                            "is_injured": getattr(char, 'is_injured', False),
                            "inventory_load": char.get_inventory_load()
                        })

                event_log_repr = game_world.event_log[-20:] if game_world else []

                buildings_repr = []
                if hasattr(game_world, 'buildings'):
                    for b in game_world.buildings:
                        buildings_repr.append({
                            "x": b.location[0], # Assuming building.location is (x,y)
                            "y": b.location[1],
                            "width": b.size[0], # Assuming building.size is (width, height)
                            "height": b.size[1],
                            "map_char": b.get_current_map_char(),
                            "display_name": b.display_name,
                            "structure_type": b.structure_type # Added for frontend differentiation
                        })
                if hasattr(game_world, 'stockpiles'): # Also include stockpiles as "buildings" for map display
                    for sp in game_world.stockpiles:
                        buildings_repr.append({
                            "x": sp.rect[0],
                            "y": sp.rect[1],
                            "width": sp.rect[2],
                            "height": sp.rect[3],
                            "map_char": "S", # Stockpile character
                            "display_name": sp.name,
                            "structure_type": "Stockpile"
                        })


                state = {
                    "day": game_time_obj.current_day,
                    "tick": game_time_obj.current_tick,
                    "ticks_per_day": game_time_obj.ticks_per_day,
                    "season": game_world.season,
                    "weather": game_world.weather,
                    "grid_size": game_world.grid_size,
                    "grid": grid_repr,
                    "characters": characters_repr,
                    "event_log": event_log_repr,
                    "is_paused": game_paused,
                    "days_until_election": getattr(game_time_obj, 'days_until_election', -1),
                    "current_speed_multiplier": SIMULATION_SPEED_MULTIPLIER
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*') # For local UI development
                self.end_headers()
                self.wfile.write(json.dumps(state).encode('utf-8'))
            else:
                self.send_response(503) # Service Unavailable
                self.end_headers()
                self.wfile.write(b"Game world not yet initialized.")
        elif self.path == '/toggle_pause':
            game_paused = not game_paused
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"paused": game_paused}).encode('utf-8'))
            if game_world: game_world.add_event_log_message(f"SIMULATION TOGGLED: {'PAUSED' if game_paused else 'RESUMED'}")
            # Duplicated log line below, removing it.
            # if game_world: game_world.add_event_log_message(f"SIMULATION TOGGLED: {'PAUSED' if game_paused else 'RESUMED'}")
            print(f"Game state toggled. Paused: {game_paused}")

        elif self.path.startswith('/set_speed'):
            # global SIMULATION_SPEED_MULTIPLIER # This was the problematic line if misplaced
            query_components = {}
            if '?' in self.path:
                query_string = self.path.split('?',1)[1]
                query_components = dict(qc.split("=") for qc in query_string.split("&"))

            try:
                multiplier = float(query_components.get('multiplier', 1.0))
                if multiplier <= 0: multiplier = 0.1 # Prevent zero or negative speed
                # SIMULATION_SPEED_MULTIPLIER is global, so assign directly
                # No, this is wrong. If a global is assigned in a function, it needs 'global' keyword.
                # The 'global' keyword for SIMULATION_SPEED_MULTIPLIER should be at the start of do_GET.
                # My previous fix was to put it at the start of do_GET, this comment is a bit misleading now.
                # The `global ... SIMULATION_SPEED_MULTIPLIER` at the start of do_GET handles this.
                __class__.SIMULATION_SPEED_MULTIPLIER = multiplier # This is incorrect, should assign to the global directly
                # Corrected assignment below:
                # global SIMULATION_SPEED_MULTIPLIER # This should be at the top of do_GET
                # SIMULATION_SPEED_MULTIPLIER = multiplier

                # Re-correction: The `global` statement at the top of `do_GET` makes `SIMULATION_SPEED_MULTIPLIER`
                # refer to the global one throughout `do_GET`. So, direct assignment is correct here.
                SIMULATION_SPEED_MULTIPLIER = multiplier


                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "new_speed_multiplier": SIMULATION_SPEED_MULTIPLIER}).encode('utf-8'))
                if game_world: game_world.add_event_log_message(f"Simulation speed set to {SIMULATION_SPEED_MULTIPLIER}x")
                print(f"Simulation speed set to {SIMULATION_SPEED_MULTIPLIER}x")
            except ValueError:
                self.send_error(400, "Invalid 'multiplier' value for set_speed")
            except Exception as e:
                self.send_error(500, f"Error setting speed: {e}")

        elif self.path.startswith('/character_info'):
            if not game_world:
                self.send_error(503, "Game world not initialized")
                return

            query_components = {}
            if '?' in self.path:
                query_string = self.path.split('?',1)[1]
                query_components = dict(qc.split("=") for qc in query_string.split("&"))

            char_name = query_components.get('name')
            if not char_name:
                self.send_error(400, "Missing 'name' parameter for character_info")
                return

            character = game_world.get_character_by_name(char_name)
            if character:
                char_data = {
                    "name": character.name,
                    "job": character.job,
                    "rank": character.rank,
                    "x": character.x,
                    "y": character.y,
                    "current_goal": character.current_goal,
                    "inventory": character.inventory,
                    "skills": {skill_name: data["level"] for skill_name, data in character.skills.items()}, # Simplified skills view
                    "needs": character.needs,
                    "is_sick": getattr(character, 'is_sick', False),
                    "sickness_severity": getattr(character, 'sickness_severity', 0),
                    "is_injured": getattr(character, 'is_injured', False),
                    "injury_severity": getattr(character, 'injury_severity', 0),
                    "appointed_by": getattr(character, 'appointed_by', None),
                    "supervisor_name": character.supervisor_name,
                    "subordinates_names": character.subordinates_names,
                    "memory": character.memory[-10:], # Last 10 memories
                    "personality": character.personality,
                    "traits": character.traits,
                    "performance_rating": getattr(character, 'performance_rating', "N/A"),
                    "warning_count": getattr(character, 'warning_count', 0)
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(char_data).encode('utf-8'))
            else:
                self.send_error(404, f"Character '{char_name}' not found")

        elif self.path.startswith('/building_info'):
            if not game_world:
                self.send_error(503, "Game world not initialized")
                return

            query_components = {}
            if '?' in self.path:
                query_string = self.path.split('?',1)[1]
                query_components = dict(qc.split("=") for qc in query_string.split("&"))

            try:
                x = int(query_components.get('x', -1))
                y = int(query_components.get('y', -1))
            except ValueError:
                self.send_error(400, "Invalid 'x' or 'y' parameters for building_info")
                return

            if x == -1 or y == -1:
                self.send_error(400, "Missing 'x' or 'y' parameters for building_info")
                return

            building = game_world.get_building_at(x,y)
            if building:
                building_data = {
                    "display_name": building.display_name,
                    "structure_type": building.structure_type,
                    "location": building.location,
                    "size": building.size,
                    "is_operational": building.is_operational,
                    "current_progress": getattr(building, 'current_progress', 0),
                    "build_time": getattr(building, 'build_time', 0), # Total work for all phases
                    "current_phase_name": building.get_current_phase_name() if hasattr(building, 'get_current_phase_name') else "N/A",
                    "map_char": building.get_current_map_char()
                }
                # If it's a stockpile or has inventory (like some workshops might)
                if hasattr(building, 'inventory'):
                    building_data["inventory"] = building.inventory
                if hasattr(building, 'allowed_resources'): # For stockpiles
                    building_data["allowed_resources"] = building.allowed_resources

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(building_data).encode('utf-8'))
            else:
                # Check if it's a stockpile, as they are separate from buildings in world lists
                stockpile_at_loc = None
                for sp in game_world.stockpiles:
                    sp_x, sp_y, sp_w, sp_h = sp.rect
                    if sp_x <= x < sp_x + sp_w and sp_y <= y < sp_y + sp_h:
                        stockpile_at_loc = sp
                        break
                if stockpile_at_loc:
                    stockpile_data = {
                        "display_name": stockpile_at_loc.name,
                        "structure_type": "Stockpile", # Generic type for UI
                        "location": (stockpile_at_loc.rect[0], stockpile_at_loc.rect[1]),
                        "size": (stockpile_at_loc.rect[2], stockpile_at_loc.rect[3]),
                        "is_operational": True, # Stockpiles are always "operational"
                        "inventory": stockpile_at_loc.inventory,
                        "allowed_resources": stockpile_at_loc.allowed_resources,
                        "map_char": "S" # Placeholder map char for stockpile
                    }
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(stockpile_data).encode('utf-8'))
                else:
                    self.send_error(404, f"No building or stockpile found at ({x},{y})")
        else:
            # Serve files from a 'ui' subdirectory if they exist (for the frontend)
            # This part makes SimpleHTTPRequestHandler serve files from 'ui' instead of current dir.
            # We need to ensure 'ui' directory exists at the project root.
            ui_dir = os.path.join(project_root, "ui")
            # Temporarily change directory for file serving. This is a bit hacky for SimpleHTTPRequestHandler.
            # A more robust server (Flask/FastAPI) would handle static files better.
            original_cwd = os.getcwd()
            try:
                os.chdir(ui_dir)
                # Remove leading '/' from self.path for SimpleHTTPRequestHandler
                super().do_GET(path=self.path.lstrip('/'))
            except FileNotFoundError:
                self.send_error(404, "File not found in UI directory or API endpoint not supported")
            finally:
                os.chdir(original_cwd) # Change back to original CWD

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
