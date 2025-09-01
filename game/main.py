import sys
import os
import json
import threading
import time as py_time
from typing import Optional, Dict, Any, List

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, jsonify, request, send_from_directory
from game.character import Character
from game.world import World
from game.time import Time
from game.stockpile import Stockpile
from game.work_order import WorkOrder
from game.goal import Goal, GoalType
from game.data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS
from game.building import Building
from game import config

# --- Global Game State Variables ---
game_world: Optional[World] = None
game_time_obj: Optional[Time] = None
simulation_running = True
game_paused = False
SIMULATION_SPEED_MULTIPLIER = 1.0
BASE_TICK_SLEEP_DURATION = 0.2

# --- Custom JSON Encoder ---
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Goal):
            return obj.to_dict()
        if isinstance(obj, GoalType):
            return obj.name
        return json.JSONEncoder.default(self, obj)

# --- Flask App Setup ---
ui_folder_path = os.path.join(project_root, 'ui')
app = Flask(__name__, static_folder=ui_folder_path, static_url_path='')
app.json_encoder = CustomJSONEncoder

# --- Simulation Logic (largely unchanged) ---
def initialize_game_world():
    global game_world, game_time_obj
    print("--- Initializing Game World (Flask Mode) ---")
    game_time_obj = Time(ticks_per_day=config.TICKS_PER_DAY)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)

    wood_stockpile = Stockpile(name="WoodStore", x=0, y=3, width=1, height=1, allowed_resources=["Wood"], total_capacity=100)
    wood_stockpile.add_item("Wood", 40)
    game_world.add_stockpile(wood_stockpile)
    game_world.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)

    liam_skills = {"Construction": 1, "Leadership": 5}
    liam = Character(name="Liam", personality="Optimistic", traits=["Diligent"], job="Builder", x=2, y=1, skills=liam_skills, rank="Worker")
    game_world.add_character(liam)

    elara_skills = {"Leadership": 7, "Medicine": 2}
    elara = Character(name="Elara", personality="Wise", traits=["Intelligent", "Forgiving"], job="Noble", x=5, y=5, skills=elara_skills, rank="Noble Lord")
    game_world.add_character(elara)
    print("--- Game World Initialized ---")

def tick_simulation():
    # This function remains largely the same as before
    global game_world, game_time_obj, simulation_running, game_paused
    if not game_world or not game_time_obj: return
    if not game_paused and simulation_running:
        new_day = game_time_obj.tick()
        for char in list(game_world.characters):
            if char in game_world.characters:
                char.decide_action(game_world)
        if new_day:
            print(f"*** NEW DAY: Day {game_time_obj.current_day} ***")
            # Daily updates can be added back here if needed

def simulation_thread_func():
    print("Simulation thread started.")
    while simulation_running:
        if not game_paused:
            tick_simulation()
        py_time.sleep(max(0.01, BASE_TICK_SLEEP_DURATION / (SIMULATION_SPEED_MULTIPLIER or 1.0)))
    print("Simulation thread finished.")

# --- API Endpoints ---
@app.route('/game_state')
def get_game_state():
    global game_world, game_time_obj, game_paused, SIMULATION_SPEED_MULTIPLIER
    if not game_world or not game_time_obj:
        return jsonify({"error": "Game not initialized"}), 503

    # This logic is copied from the old handler
    grid_repr = [
        [game_world.get_tile(c, r) for c in range(game_world.grid_size[1])]
        for r in range(game_world.grid_size[0])
    ]
    characters_repr = [char.to_dict() for char in game_world.characters]
    buildings_repr = [b.to_dict() for b in game_world.buildings]
    stockpiles_repr = [sp.to_dict() for sp in game_world.stockpiles]

    state = {
        "day": game_time_obj.current_day,
        "tick": game_time_obj.current_tick,
        "ticks_per_day": game_time_obj.ticks_per_day,
        "season": game_world.season,
        "weather": game_world.weather,
        "grid_size": game_world.grid_size,
        "grid": grid_repr,
        "characters": characters_repr,
        "buildings": buildings_repr + stockpiles_repr, # Combine for rendering
        "event_log": game_world.event_log[-20:],
        "is_paused": game_paused,
        "current_speed_multiplier": SIMULATION_SPEED_MULTIPLIER
    }
    return jsonify(state)

@app.route('/character_info')
def get_character_info():
    char_name = request.args.get('name')
    if not char_name or not game_world:
        return jsonify({"error": "Character name required or game not initialized"}), 400

    character = game_world.get_character_by_name(char_name)
    if character:
        return jsonify(character.to_dict())
    return jsonify({"error": "Character not found"}), 404

@app.route('/building_info')
def get_building_info():
    x = request.args.get('x', type=int)
    y = request.args.get('y', type=int)
    if x is None or y is None or not game_world:
        return jsonify({"error": "x and y coordinates required or game not initialized"}), 400

    building = game_world.get_building_at(x, y)
    if building:
        return jsonify(building.to_dict())

    # Also check for stockpiles
    for sp in game_world.stockpiles:
        if sp.rect[0] <= x < sp.rect[0] + sp.rect[2] and sp.rect[1] <= y < sp.rect[1] + sp.rect[3]:
            return jsonify(sp.to_dict())

    return jsonify({"error": "Building or stockpile not found"}), 404

@app.route('/toggle_pause', methods=['POST'])
def toggle_pause():
    global game_paused
    game_paused = not game_paused
    print(f"Game state toggled. Paused: {game_paused}")
    return jsonify({"paused": game_paused})

@app.route('/set_speed', methods=['POST'])
def set_speed():
    global SIMULATION_SPEED_MULTIPLIER
    multiplier = request.args.get('multiplier', 1.0, type=float)
    if multiplier <= 0: multiplier = 0.1
    SIMULATION_SPEED_MULTIPLIER = multiplier
    print(f"Simulation speed set to {SIMULATION_SPEED_MULTIPLIER}x")
    return jsonify({"status": "success", "new_speed_multiplier": SIMULATION_SPEED_MULTIPLIER})

# --- Static File Serving ---
@app.route('/')
def serve_index():
    return send_from_directory(ui_folder_path, 'index.html')

@app.route('/<path:path>')
def serve_static_file(path):
    return send_from_directory(ui_folder_path, path)

# --- Main Execution ---
if __name__ == "__main__":
    initialize_game_world()

    sim_thread = threading.Thread(target=simulation_thread_func, daemon=True)
    sim_thread.start()

    print(f"Flask server starting... Serving UI from: {ui_folder_path}")
    print("Access UI at http://localhost:8000/")

    # Use waitress as a production-ready server
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)

    # Signal simulation thread to stop when server is shut down
    simulation_running = False
    if sim_thread.is_alive():
        sim_thread.join()

    print("Exited gracefully.")
