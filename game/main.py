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
from game.job import Job
from game.building import Building
from game import config

import random
import curses # Keep for now, might be used by main_simulation_logic
from typing import Optional, Dict, Any, List
from copy import deepcopy

import http.server
import socketserver
import json
import threading
import time as py_time # Renamed to avoid conflict with game.time.Time
import urllib.request
import webbrowser
import signal

# --- Global Game State Variables ---
httpd = None
game_world: Optional[World] = None
game_time_obj: Optional[Time] = None
simulation_running = True # Controls the simulation loop
game_paused = False       # To pause/resume the simulation
SIMULATION_SPEED_MULTIPLIER = 1.0 # 1.0 is normal speed
BASE_TICK_SLEEP_DURATION = 0.2 # Seconds for 1x speed per tick
test_characters_list: List[Character] = [] # To store characters for final report

class GameEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Job):
            return o.to_dict()
        return super().default(o)

def advance_simulation_one_tick(world: World):
    """
    Advance the simulation by one tick.
    This function is now primarily for testing purposes.
    """
    # This directly calls the simulation logic for a single tick on the passed world.
    tick_simulation(world_to_tick=world)

# --- Simulation Logic ---
def initialize_game_world():
    global game_world, game_time_obj, test_characters_list

    initial_setup_messages = []
    initial_setup_messages.append("--- Initializing Game World (Server Mode) ---")

    ticks_per_day = config.TICKS_PER_DAY if hasattr(config, 'TICKS_PER_DAY') else 10 # Default if not in config
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    default_size = getattr(config, "MAP_DEFAULT_SIZE", (10, 10))
    game_world = World(grid_size=(int(default_size[0]), int(default_size[1])), game_time_ref=game_time_obj)

    test_characters_list = [] # Reset for this initialization

    # Stockpiles (example setup)
    wood_stockpile = Stockpile(
        name="WoodStore",
        x=0,
        y=3,
        width=1,
        height=1,
        allowed_resources=["Wood", "Lumber"],
        total_capacity=100,
    )
    wood_stockpile.add_item("Wood", 40)
    game_world.add_stockpile(wood_stockpile)
    game_world.economy.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)
    initial_setup_messages.append(f"Added WoodStore stockpile with {wood_stockpile.inventory.get('Wood',0)} Wood.")

    water_stockpile = Stockpile(name="WaterCasks", x=2, y=3, width=1, height=1, allowed_resources=["Water"], total_capacity=80)
    water_stockpile.add_item("Water", 24)
    game_world.add_stockpile(water_stockpile)
    game_world.economy.ledger.update_stockpile_record(water_stockpile.name, water_stockpile.inventory, game_time_obj.current_day)
    initial_setup_messages.append(f"Added WaterCasks stockpile with {water_stockpile.inventory.get('Water',0)} Water.")

    # Establish natural water sources for gathering
    game_world.add_resource("Water", (4, 0), tile_becomes="Water")
    game_world.add_resource("Water", (5, 0), tile_becomes="Water")

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


    # Add Duke and Baroness
    duke_skills = {"Leadership": 8, "Security": 5}
    duke = Character(name="Duke William", personality="Stern", traits=["Authoritative", "Just"],
                     job="Noble", x=7, y=7, skills=duke_skills, rank="Duke",
                     vassals=["Baroness Sofia"])
    game_world.add_character(duke)
    test_characters_list.append(duke)
    initial_setup_messages.append(f"  Added: {duke.name} (Job: {duke.job}, Rank: {duke.rank}) at ({duke.x},{duke.y})")

    baroness_skills = {"Leadership": 6, "Security": 4}
    baroness = Character(name="Baroness Sofia", personality="Charming", traits=["Diplomatic", "Ambitious"],
                         job="Noble", x=8, y=8, skills=baroness_skills, rank="Baroness",
                         liege="Duke William")
    game_world.add_character(baroness)
    test_characters_list.append(baroness)
    initial_setup_messages.append(f"  Added: {baroness.name} (Job: {baroness.job}, Rank: {baroness.rank}) at ({baroness.x},{baroness.y})")

    # Add subordinates for the Baroness
    reeve_skills = {"Leadership": 4}
    reeve = Character(name="Reeve Thomas", personality="Pragmatic", traits=["Organized"],
                      job="Reeve", x=9, y=9, skills=reeve_skills, rank="Reeve",
                      supervisor_name="Baroness Sofia")
    game_world.add_character(reeve)
    baroness.subordinates_names.append(reeve.name)
    test_characters_list.append(reeve)
    initial_setup_messages.append(f"  Added: {reeve.name} (Job: {reeve.job}, Rank: {reeve.rank}) at ({reeve.x},{reeve.y})")

    bailiff_skills = {"Security": 4}
    bailiff = Character(name="Bailiff John", personality="Gruff", traits=["Tough"],
                        job="Bailiff", x=1, y=9, skills=bailiff_skills, rank="Bailiff",
                        supervisor_name="Baroness Sofia")
    game_world.add_character(bailiff)
    baroness.subordinates_names.append(bailiff.name)
    test_characters_list.append(bailiff)
    initial_setup_messages.append(f"  Added: {bailiff.name} (Job: {bailiff.job}, Rank: {bailiff.rank}) at ({bailiff.x},{bailiff.y})")


    # Initial Build Order (Optional, can be removed if Mayor initiates projects)
    # hut_bp_key = "wooden_hut" ... (rest of build order setup from original main_simulation_logic)
    # For now, let's assume the Mayor will initiate projects.

    for msg in initial_setup_messages:
        if game_world: game_world.add_event_log_message(msg)

    if game_world: game_world.add_event_log_message("--- Simulation Server Initialized ---")


def tick_simulation(world_to_tick: Optional[World] = None):
    global game_world, game_time_obj, simulation_running, game_paused

    current_world = world_to_tick if world_to_tick else game_world
    if not current_world or not current_world.game_time:
        if not world_to_tick: # Only stop the global loop if not a test
            simulation_running = False
        return

    if not game_paused and (simulation_running or world_to_tick is not None):
        new_day = current_world.game_time.tick()
        if hasattr(current_world, "update_day_phase"):
            current_world.update_day_phase()

        current_world.update_animals()
        current_world.update_crops()

        for char_to_act in list(current_world.characters):
            if char_to_act not in current_world.characters: continue
            char_to_act.decide_action(current_world)

        if new_day:
            day_msg = f"*** NEW DAY: Day {current_world.game_time.current_day}. Weather: {current_world.weather}, Season: {current_world.season} ***"
            current_world.add_event_log_message(day_msg)

            if hasattr(current_world, "daily_environment_tick"):
                current_world.daily_environment_tick()

            # ... (rest of the daily updates, using current_world) ...
            if hasattr(current_world, 'handle_election'):
                current_world.handle_election()

            if hasattr(current_world, 'update_rumors_daily'):
                current_world.update_rumors_daily()

            if hasattr(current_world, 'process_legal_system_daily'):
                current_world.process_legal_system_daily()

            if hasattr(current_world, 'process_healthcare_daily'):
                current_world.process_healthcare_daily()

            for character in current_world.characters:
                if hasattr(character, "needs") and hasattr(character.needs, "process_daily_decay"):
                    character.needs.process_daily_decay()

            days_per_season = config.DAYS_PER_SEASON if hasattr(config, 'DAYS_PER_SEASON') else 10
            if current_world.game_time.current_day % days_per_season == 1 and current_world.game_time.current_day > 1:
                current_world.advance_season()

        if not world_to_tick: # Only check max days for the global simulation
            max_simulation_days = config.MAX_SIMULATION_DAYS if hasattr(config, 'MAX_SIMULATION_DAYS') else 20
            if current_world.game_time.current_day > max_simulation_days:
                msg = f"Simulation reached max days ({max_simulation_days}). Stopping simulation thread."
                current_world.add_event_log_message(msg)
                simulation_running = False

def simulation_thread_func(world_instance: Optional[World] = None):
    global simulation_running

    # If a specific world is passed (for tests), use it. Otherwise, use the global one.
    target_world = world_instance if world_instance else game_world

    while simulation_running or world_instance:
        if not game_paused:
            tick_simulation(target_world)

        current_sleep_duration = BASE_TICK_SLEEP_DURATION
        if SIMULATION_SPEED_MULTIPLIER > 0:
            current_sleep_duration /= SIMULATION_SPEED_MULTIPLIER

        py_time.sleep(max(0.01, current_sleep_duration))

        # For tests, we don't want an infinite loop. The test runner will stop it.
        # This is a simple way to break out if it's a test run. A more robust
        # mechanism might be a dedicated flag on the world object.
        if world_instance:
            break

        current_sleep_duration = BASE_TICK_SLEEP_DURATION
        if SIMULATION_SPEED_MULTIPLIER > 0: # Avoid division by zero or negative multipliers
            current_sleep_duration /= SIMULATION_SPEED_MULTIPLIER

        py_time.sleep(max(0.01, current_sleep_duration)) # Ensure a minimum sleep to prevent overly tight loops

# --- HTTP Server Logic ---
PORT = 5000


def trigger_initial_ui_fetch(port: int, delay: float = 0.5, attempts: int = 5) -> None:
    """Warm the UI by requesting the index page (and fall back to opening a browser)."""

    def _fetch() -> None:
        url = f"http://localhost:{port}/"
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(url):
                    return
            except Exception as exc:  # noqa: BLE001 - log and continue retries
                py_time.sleep(delay)

        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001 - best-effort browser launch
            pass

    threading.Thread(target=_fetch, daemon=True).start()

def signal_handler(sig, frame):
    """Gracefully shut down the server and simulation."""
    global simulation_running, httpd
    simulation_running = False
    if httpd:
        # Shutdown httpd in a separate thread to avoid deadlocks
        threading.Thread(target=httpd.shutdown).start()

class GameDataHandler(http.server.SimpleHTTPRequestHandler):
    def _parse_query_components(self):
        if '?' in self.path:
            query_string = self.path.split('?', 1)[1]
            return dict(qc.split("=") for qc in query_string.split("&"))
        return {}

    def _send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, cls=GameEncoder).encode('utf-8'))

    def _get_grid_repr(self, world):
        """Generates a 2D array representation of the game world grid."""
        return [
            [world.get_tile(c_idx, r_idx) for c_idx in range(world.grid_size[1])]
            for r_idx in range(world.grid_size[0])
        ]

    def _get_characters_repr(self, world):
        """Generates a list of dictionary representations of characters for the main UI."""
        chars_repr = []
        for char in world.characters:
            char_data = char.to_dict()
            # The UI expects a simplified top-level object for rendering efficiency
            char_data.update({
                "x": char.x,
                "y": char.y,
                "health": char.health.get_health_summary(),
                "current_goal": char.current_goal.type if char.current_goal else "Idle"
            })
            chars_repr.append(char_data)
        return chars_repr

    def _get_buildings_repr(self, world):
        """Generates a list of dictionary representations of buildings and stockpiles."""
        buildings_repr = [b.to_dict() for b in world.buildings]
        for sp in world.stockpiles:
            buildings_repr.append(sp.to_dict())
        return buildings_repr

    def _handle_game_state(self):
        """Handles the /game_state API endpoint."""
        global game_world, game_time_obj
        if not (game_world and game_time_obj):
            self.send_error(503, "Game world not yet initialized.")
            return

        state = {
            "day": game_time_obj.current_day,
            "tick": game_time_obj.current_tick,
            "ticks_per_day": game_time_obj.ticks_per_day,
            "season": game_world.season,
            "weather": game_world.weather,
            "grid_size": game_world.grid_size,
            "grid": self._get_grid_repr(game_world),
            "map_revision": game_world.map_revision,
            "characters": self._get_characters_repr(game_world),
            "buildings": self._get_buildings_repr(game_world),
            "event_log": game_world.event_log[-20:],
            "is_paused": game_paused,
            "days_until_election": getattr(game_time_obj, 'days_until_election', -1),
            "current_speed_multiplier": SIMULATION_SPEED_MULTIPLIER,
            "economy": {
                "treasury": game_world.economy.treasury_coins,
                "daily_report": game_world.economy.last_daily_economic_report,
            },
            "crime": {
                "pending_crimes": len(game_world.crime.pending_crimes)
            }
        }
        self._send_json_response(state)

    def _handle_toggle_pause(self):
        global game_paused
        game_paused = not game_paused
        self._send_json_response({"paused": game_paused})
        if game_world:
            game_world.add_event_log_message(f"SIMULATION TOGGLED: {'PAUSED' if game_paused else 'RESUMED'}")

    def _handle_set_speed(self):
        global SIMULATION_SPEED_MULTIPLIER
        query_components = self._parse_query_components()
        try:
            multiplier = float(query_components.get('multiplier', 1.0))
            SIMULATION_SPEED_MULTIPLIER = max(0.1, multiplier)
            self._send_json_response({"status": "success", "new_speed_multiplier": SIMULATION_SPEED_MULTIPLIER})
            if game_world:
                game_world.add_event_log_message(f"Simulation speed set to {SIMULATION_SPEED_MULTIPLIER}x")
        except (ValueError, TypeError):
            self.send_error(400, "Invalid 'multiplier' value for set_speed")

    def _handle_character_info(self):
        global game_world
        if not game_world:
            self.send_error(503, "Game world not initialized")
            return

        query_components = self._parse_query_components()
        char_name = query_components.get('name')
        if not char_name:
            self.send_error(400, "Missing 'name' parameter for character_info")
            return

        character = game_world.get_character_by_name(char_name)
        if character:
            self._send_json_response(character.to_dict_detailed())
        else:
            self.send_error(404, f"Character '{char_name}' not found")

    def _handle_building_info(self):
        global game_world
        if not game_world:
            self.send_error(503, "Game world not initialized")
            return

        query_components = self._parse_query_components()
        try:
            x = int(query_components.get('x', -1))
            y = int(query_components.get('y', -1))
        except (ValueError, TypeError):
            self.send_error(400, "Invalid 'x' or 'y' parameters")
            return

        if x == -1 or y == -1:
            self.send_error(400, "Missing 'x' or 'y' parameters")
            return

        building = game_world.get_building_at(x, y)
        if building:
            self._send_json_response(building.to_dict_detailed())
            return

        for sp in game_world.stockpiles:
            sp_x, sp_y, sp_w, sp_h = sp.rect
            if sp_x <= x < sp_x + sp_w and sp_y <= y < sp_y + sp_h:
                self._send_json_response(sp.to_dict_detailed())
                return

        self.send_error(404, f"No building or stockpile found at ({x},{y})")

    def do_GET(self):
        if self.path == '/game_state':
            self._handle_game_state()
        elif self.path == '/toggle_pause':
            self._handle_toggle_pause()
        elif self.path.startswith('/set_speed'):
            self._handle_set_speed()
        elif self.path.startswith('/character_info'):
            self._handle_character_info()
        elif self.path.startswith('/building_info'):
            self._handle_building_info()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/create_work_order':
            if not game_world or not game_time_obj:
                self.send_error(503, "Game world not initialized")
                return

            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                order_data = json.loads(post_data)

                order_type = order_data.get('order_type')
                details = order_data.get('details')
                priority = order_data.get('priority', 1)

                if not order_type or not details:
                    self.send_error(400, "Missing 'order_type' or 'details' in request body")
                    return

                new_order = WorkOrder(
                    order_type=order_type,
                    details=details,
                    priority=priority,
                    creation_day=game_time_obj.current_day
                )
                game_world.add_work_order(new_order)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    "status": "success",
                    "message": "Work order created successfully",
                    "order_id": new_order.order_id
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))

            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON in request body")
            except Exception as e:
                self.send_error(500, f"Error creating work order: {e}")
        else:
            self.send_error(404, "Endpoint not found")

# --- Main Execution ---
import sys

def run_server(port: int = PORT, set_signals: bool = True, world_instance: Optional[World] = None) -> None:
    """Start the simulation loop and HTTP server on the requested port."""
    global httpd, game_world, game_time_obj
    if set_signals:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    if world_instance:
        game_world = world_instance
        if game_world.game_time:
            game_time_obj = game_world.game_time
    else:
        initialize_game_world()

    # Pass the world_instance to the simulation thread if it exists
    sim_thread = threading.Thread(
        target=simulation_thread_func,
        args=(world_instance,) if world_instance else (),
        daemon=True
    )
    sim_thread.start()

    ui_dir = os.path.join(project_root, "ui")

    class Handler(GameDataHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ui_dir, **kwargs)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Handler) as httpd_instance:
        httpd = httpd_instance
        trigger_initial_ui_fetch(port)
        httpd.serve_forever()



if __name__ == "__main__":
    run_server()
