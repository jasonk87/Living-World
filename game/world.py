from typing import TYPE_CHECKING, List # Ensure List is imported

if TYPE_CHECKING:
    from .character import Character # For type hinting

class World:
    SEASONS = ["Spring", "Summer", "Autumn", "Winter"]

    def __init__(self, grid_size: tuple[int, int] = (10, 10)):
        self.grid_size = grid_size
        self.grid = [["Grass" for _ in range(grid_size[1])] for _ in range(grid_size[0])]
        self.resources = {}
        self.season_index = 0
        self.season = World.SEASONS[self.season_index]
        self.weather = "Sunny"
        self.characters: List['Character'] = [] # Initialize empty list of characters

    def __str__(self):
        # Basic representation, can be expanded
        return f"World(Size: {self.grid_size}, Season: {self.season}, Weather: {self.weather}, Characters: {len(self.characters)})"

    def get_tile(self, x: int, y: int) -> str:
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            return self.grid[x][y]
        return "OutOfBounds"

    def set_tile(self, x: int, y: int, tile_type: str):
        if 0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]:
            self.grid[x][y] = tile_type
        else:
            print(f"Error: Coordinates ({x},{y}) are out of bounds for set_tile.")

    def add_resource(self, resource_name: str, location: tuple[int, int], tile_becomes: str = None):
        x, y = location
        if not (0 <= x < self.grid_size[0] and 0 <= y < self.grid_size[1]):
            print(f"Error: Cannot add resource at out-of-bounds location ({x},{y}).")
            return

        if resource_name not in self.resources:
            self.resources[resource_name] = []

        self.resources[resource_name].append(location)

        current_tile = self.get_tile(x,y)
        if tile_becomes:
            if current_tile != tile_becomes :
                self.set_tile(x, y, tile_becomes)
        elif current_tile == "Grass":
            self.set_tile(x,y, resource_name)

    def get_resources(self, resource_name: str) -> List[tuple[int, int]]:
        # Return a copy to prevent modification of internal list by callers if they .remove() etc.
        return list(self.resources.get(resource_name, []))

    def update_weather(self, new_weather: str):
        if self.weather != new_weather:
            self.weather = new_weather
            print(f"The weather has changed to {self.weather}.")

    def advance_season(self):
        self.season_index = (self.season_index + 1) % len(World.SEASONS)
        self.season = World.SEASONS[self.season_index]
        print(f"The season has changed to {self.season}.")

        current_weather = self.weather # Store current weather to avoid redundant "changed to Sunny" messages
        if self.season == "Winter": self.update_weather("Snowy")
        elif self.season == "Spring": self.update_weather("Rainy")
        elif self.season == "Summer": self.update_weather("Sunny")
        else: # Autumn
            if current_weather != "Cloudy": self.update_weather("Cloudy")


    def add_character(self, character: 'Character'):
        if character not in self.characters:
            self.characters.append(character)
            print(f"{character.name} has entered the world at ({character.x},{character.y}).")

    def remove_character(self, character: 'Character'):
        if character in self.characters:
            self.characters.remove(character)
            print(f"{character.name} has left the world.")

    def get_characters_at_location(self, x: int, y: int) -> List['Character']:
        return [char for char in self.characters if char.x == x and char.y == y]

    def get_nearby_characters(self, character: 'Character', radius: int = 1) -> List['Character']:
        """
        Finds characters within a given Manhattan distance radius of a character.
        Excludes the character themselves.
        """
        nearby = []
        for other_char in self.characters:
            if other_char.name == character.name:
                continue

            # Using Manhattan distance: |x1 - x2| + |y1 - y2|
            distance = abs(other_char.x - character.x) + abs(other_char.y - character.y)
            if distance <= radius:
                nearby.append(other_char)
        return nearby
