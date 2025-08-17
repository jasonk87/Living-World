# game/server.py
import http.server
import socketserver
import json
import os
from typing import TYPE_CHECKING, Dict, Callable
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from .game_manager import Game

class GameDataHandler(http.server.SimpleHTTPRequestHandler):
    game: 'Game' = None

    def __init__(self, *args, **kwargs):
        self.routes = {
            '/game_state': self.send_game_state,
            '/toggle_pause': self.handle_toggle_pause,
            '/set_speed': self.handle_set_speed,
            '/character_info': self.send_character_info,
            '/building_info': self.send_building_info,
        }
        super().__init__(*args, **kwargs)

    def get_query_components(self) -> Dict[str, str]:
        parsed_path = urlparse(self.path)
        return {k: v[0] for k, v in parse_qs(parsed_path.query).items()}

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        handler = self.routes.get(path)
        if handler:
            handler()
        else:
            self.serve_ui_files()

    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

    def send_game_state(self):
        if not self.game or not self.game.world or not self.game.time:
            self.send_error(503, "Game world not yet initialized.")
            return
        # ... (rest of the method is the same)
        world = self.game.world
        time = self.game.time

        grid_repr = [[world.get_tile(c, r) for c in range(world.grid_size[1])] for r in range(world.grid_size[0])]

        characters_repr = [{
            "name": char.name, "x": char.x, "y": char.y, "job": char.job,
            "goal": str(char.current_goal), "is_sick": getattr(char, 'is_sick', False),
            "is_injured": getattr(char, 'is_injured', False),
            "inventory_load": char.get_inventory_load(),
            "known_characters": getattr(char, 'known_characters', []),
            "dialogue_history_count": len(getattr(char, 'dialogue_history', []))
        } for char in world.characters]

        buildings_repr = []
        for b in world.buildings:
            buildings_repr.append({
                "x": b.location[0], "y": b.location[1], "width": b.size[0], "height": b.size[1],
                "map_char": b.get_current_map_char(), "display_name": b.display_name,
                "structure_type": b.structure_type
            })
        for sp in world.stockpiles:
            buildings_repr.append({
                "x": sp.rect[0], "y": sp.rect[1], "width": sp.rect[2], "height": sp.rect[3],
                "map_char": "S", "display_name": sp.name, "structure_type": "Stockpile"
            })

        state = {
            "day": time.current_day, "tick": time.current_tick, "ticks_per_day": time.ticks_per_day,
            "season": world.season, "weather": world.weather, "grid_size": world.grid_size,
            "grid": grid_repr, "characters": characters_repr, "buildings": buildings_repr,
            "event_log": world.event_log[-20:], "is_paused": self.game.game_paused,
            "days_until_election": getattr(time, 'days_until_election', -1),
            "current_speed_multiplier": self.game.simulation_speed_multiplier
        }
        self.send_json_response(state)

    def handle_toggle_pause(self):
        self.game.toggle_pause()
        self.send_json_response({"paused": self.game.game_paused})

    def handle_set_speed(self):
        query_components = self.get_query_components()
        try:
            multiplier = float(query_components.get('multiplier', '1.0'))
            self.game.set_speed(multiplier)
            self.send_json_response({"status": "success", "new_speed_multiplier": self.game.simulation_speed_multiplier})
        except ValueError:
            self.send_error(400, "Invalid 'multiplier' value for set_speed")

    def send_character_info(self):
        if not self.game.world:
            self.send_error(503, "Game world not initialized")
            return

        query = self.get_query_components()
        char_name = query.get('name')
        if not char_name:
            self.send_error(400, "Missing 'name' parameter")
            return

        character = self.game.world.get_character_by_name(char_name)
        if character:
            char_data = {
                "name": character.name, "job": character.job, "rank": character.rank,
                "x": character.x, "y": character.y, "current_goal": str(character.current_goal),
                "inventory": character.inventory,
                "skills": {s: d["level"] for s, d in character.skills.items()},
                "needs": character.needs, "is_sick": getattr(character, 'is_sick', False),
                "sickness_severity": getattr(character, 'sickness_severity', 0),
                "is_injured": getattr(character, 'is_injured', False),
                "injury_severity": getattr(character, 'injury_severity', 0),
                "appointed_by": getattr(character, 'appointed_by', None),
                "supervisor_name": character.supervisor_name,
                "subordinates_names": character.subordinates_names,
                "memory": character.memory[-10:], "personality": character.personality,
                "traits": character.traits, "performance_rating": getattr(character, 'performance_rating', "N/A"),
                "warning_count": getattr(character, 'warning_count', 0),
                "known_characters": getattr(character, 'known_characters', []),
                "relationships": getattr(character, 'relationships', {}),
                "opinions": getattr(character, 'opinions', {}),
                "dialogue_history": getattr(character, 'dialogue_history', [])[-10:]
            }
            self.send_json_response(char_data)
        else:
            self.send_error(404, f"Character '{char_name}' not found")

    def send_building_info(self):
        if not self.game.world:
            self.send_error(503, "Game world not initialized")
            return

        query = self.get_query_components()
        try:
            x, y = int(query.get('x', -1)), int(query.get('y', -1))
        except ValueError:
            self.send_error(400, "Invalid 'x' or 'y' parameters")
            return

        if x == -1 or y == -1:
            self.send_error(400, "Missing 'x' or 'y' parameters")
            return

        building = self.game.world.get_building_at(x,y)
        if building:
            building_data = {
                "display_name": building.display_name, "structure_type": building.structure_type,
                "location": building.location, "size": building.size,
                "is_operational": building.is_operational,
                "current_progress": getattr(building, 'current_progress', 0),
                "build_time": getattr(building, 'build_time', 0),
                "current_phase_name": building.get_current_phase_name(),
                "map_char": building.get_current_map_char()
            }
            if hasattr(building, 'inventory'): building_data["inventory"] = building.inventory
            if hasattr(building, 'allowed_resources'): building_data["allowed_resources"] = building.allowed_resources
            self.send_json_response(building_data)
        else:
            # Check for stockpiles as well
            stockpile = self.game.world.get_stockpile_at(x, y) # Assumes World has get_stockpile_at
            if stockpile:
                stockpile_data = {
                    "display_name": stockpile.name, "structure_type": "Stockpile",
                    "location": (stockpile.rect[0], stockpile.rect[1]),
                    "size": (stockpile.rect[2], stockpile.rect[3]), "is_operational": True,
                    "inventory": stockpile.inventory, "allowed_resources": stockpile.allowed_resources,
                    "map_char": "S"
                }
                self.send_json_response(stockpile_data)
            else:
                self.send_error(404, f"No building or stockpile at ({x},{y})")

    def serve_ui_files(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(project_root, "ui")
        if not os.path.exists(ui_dir):
            self.send_error(404, "UI directory not found.")
            return

        original_cwd = os.getcwd()
        try:
            os.chdir(ui_dir)
            super().do_GET()
        finally:
            os.chdir(original_cwd)

def create_handler_factory(game_instance: 'Game'):
    class CustomGameDataHandler(GameDataHandler):
        game = game_instance
    return CustomGameDataHandler

def run_server(game_instance: 'Game', port: int = 8000):
    handler_class = create_handler_factory(game_instance)
    httpd = None
    try:
        with socketserver.TCPServer(("", port), handler_class) as httpd:
            print(f"Serving HTTP on port {port}...")
            httpd.serve_forever()
    except KeyboardInterrupt:
        if httpd:
            httpd.server_close()
    except Exception as e:
        print(f"Server error: {e}")
        if httpd:
            httpd.server_close()
