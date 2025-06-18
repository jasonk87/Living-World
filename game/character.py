# game/character.py
from typing import TYPE_CHECKING, Optional, Dict, List
import random # Ensure random is imported
from .llm_integration import generate_dialogue

if TYPE_CHECKING:
    from .world import World
    from .character import Character as OtherCharacter

class Character:
    def __init__(self, name: str, personality: str, traits: list[str],
                 skills: dict[str, int], x: int = 0, y: int = 0,
                 needs: Optional[Dict[str, int]] = None,
                 current_goal: Optional[str] = None,
                 job: Optional[str] = None): # Added job
        self.name = name
        self.personality = personality
        self.traits = traits
        self.skills = skills
        self.x = x
        self.y = y
        self.inventory = {}
        self.memory = []
        self.needs = needs if needs is not None else {} # Job needs can be stored here
        self.current_goal = current_goal
        self.relationships: Dict[str, str] = {}
        self.job = job # Assign job

    def __str__(self):
        return f"Character(Name: {self.name}, Job: {self.job}, Pos: ({self.x},{self.y}), Goal: {self.current_goal}, Inv: {self.inventory})"

    def add_memory(self, event: str):
        self.memory.append(event)

    def get_skill_level(self, skill_name: str) -> int:
        return self.skills.get(skill_name, 0)

    def interact(self, other_character: 'OtherCharacter', world: 'World'):
        if other_character.name == self.name: return
        context_key = "seeing again"
        if other_character.name not in self.relationships:
            self.relationships[other_character.name] = "Met"
            other_character.relationships[self.name] = "Met"
            self.add_memory(f"Met {other_character.name} at ({self.x},{self.y}).")
            other_character.add_memory(f"Met {self.name} at ({other_character.x},{other_character.y}).")
            context_key = "first meeting"

        dialogue_context = f"{self.name} is meeting {other_character.name} for the first time." if context_key == "first meeting" \
                           else f"{self.name} is encountering {other_character.name} again."

        generated_line_A = generate_dialogue(self, other_character, dialogue_context, world.weather)
        print(f"{self.name} (to {other_character.name}): {generated_line_A}")
        self.add_memory(f"Said to {other_character.name}: '{generated_line_A}'")

        context_for_B_reply = f"{other_character.name} is responding to {self.name} who just said: '{generated_line_A}'."
        generated_line_B = generate_dialogue(other_character, self, context_for_B_reply, world.weather)
        print(f"{other_character.name} (to {self.name}): {generated_line_B}")
        other_character.add_memory(f"Said to {self.name}: '{generated_line_B}'")

    def move(self, dx: int, dy: int, world: 'World'):
        new_x, new_y = self.x + dx, self.y + dy
        if 0 <= new_x < world.grid_size[0] and 0 <= new_y < world.grid_size[1]:
            # Check if target tile is occupied by another character
            occupying_chars = [c for c in world.get_characters_at_location(new_x, new_y) if c.name != self.name]
            if occupying_chars:
                # print(f"{self.name} wants to move to ({new_x},{new_y}), but it's occupied by {occupying_chars[0].name}. Cannot move.")
                return # Stay in place if target is occupied by another character.

            self.x = new_x
            self.y = new_y
            # print(f"{self.name} moves to ({self.x},{self.y}). Job: {self.job}, Goal: {self.current_goal}") # Reduced noise
        # else:
            # print(f"{self.name} failed to move to ({new_x},{new_y}) - out of bounds.") # Reduced noise
        pass

    def move_towards(self, target_x: int, target_y: int, world: 'World'):
        dx = target_x - self.x
        dy = target_y - self.y
        if dx > 0: dx = 1
        elif dx < 0: dx = -1
        if dy > 0: dy = 1
        elif dy < 0: dy = -1
        if dx != 0 or dy != 0:
            self.move(dx, dy, world)
        # else: already at target

    def find_nearest_resource(self, resource_name: str, world: 'World') -> Optional[tuple[int, int]]:
        locations = world.get_resources(resource_name) # Gets a copy
        if not locations: return None

        # Prefer current location if valid
        if (self.x, self.y) in locations:
             tile_type = world.get_tile(self.x, self.y)
             if (resource_name == "Wood" and tile_type == "Forest") or \
                (resource_name == "Stone" and tile_type == "Rocks") or \
                tile_type == resource_name:
                 return (self.x, self.y)

        # Simple "nearest": first one found that matches tile type. Could be improved.
        for loc in locations:
            tile_type = world.get_tile(loc[0], loc[1])
            if (resource_name == "Wood" and tile_type == "Forest") or \
               (resource_name == "Stone" and tile_type == "Rocks") or \
               tile_type == resource_name:
                return loc
        return None


    def gather_resource(self, resource_name: str, world: 'World'):
        current_pos = (self.x, self.y)
        current_tile_type = world.get_tile(self.x, self.y)

        tile_is_resource_source = (resource_name == "Wood" and current_tile_type == "Forest") or \
                                  (resource_name == "Stone" and current_tile_type == "Rocks") or \
                                  (current_tile_type == resource_name)

        if tile_is_resource_source and resource_name in world.resources and current_pos in world.resources.get(resource_name, []):
            self.inventory[resource_name] = self.inventory.get(resource_name, 0) + 1
            world.resources[resource_name].remove(current_pos)

            print(f"{self.name} gathered {resource_name} at ({self.x},{self.y}). Inv: {self.inventory.get(resource_name,0)}. Goal: {self.current_goal}")
            self.add_memory(f"Gathered {resource_name} at ({self.x},{self.y})")

            # If all resources of this type are gone from this specific list in world.resources for this location
            if not world.resources.get(resource_name, []) or current_pos not in world.resources.get(resource_name, []):
                # And if the tile was specifically named for the resource (Forest for Wood, Rocks for Stone)
                if (resource_name == "Wood" and current_tile_type == "Forest") or \
                   (resource_name == "Stone" and current_tile_type == "Rocks"):
                    world.set_tile(self.x, self.y, "Grass")
                    # print(f"All {resource_name} at ({self.x},{self.y}) gathered, tile changed to Grass.")
        # else:
            # print(f"{self.name} cannot gather {resource_name} at ({self.x},{self.y}) on {current_tile_type}.") # Reduced noise
        pass

    def build(self, structure_type: str, world: 'World') -> bool:
        # ... (build logic from previous step, ensure it's complete) ...
        return False # Placeholder if not filled from previous step

    def decide_action(self, world: 'World'):
        # Interaction Check (Prioritized if character is idle/wandering or job allows some flexibility)
        if self.current_goal in [None, "Wander", "Idle", "Perform Woodcutter Duties", "Stockpile Wood"]:
            nearby_chars = world.get_nearby_characters(self, radius=1) # Manhattan distance
            if nearby_chars:
                other_char_to_interact = random.choice(nearby_chars)
                # Interact only if on the SAME tile, after moving, or if proximity itself is enough.
                # For this iteration, let's say interaction happens if they are on the same tile.
                # The "Wander" logic should try to avoid co-location, so this might be rare unless one is stationary.
                # To make it more likely for demo: if nearby (radius 1) AND one is receptive.
                if self.x == other_char_to_interact.x and self.y == other_char_to_interact.y: # Actual same tile
                    print(f"{self.name} (Goal: {self.current_goal}) is on same tile as {other_char_to_interact.name} and interacts.")
                    self.interact(other_char_to_interact, world)
                    return # Interaction takes the turn
                # else: # Nearby but not same tile
                #    print(f"{self.name} notices {other_char_to_interact.name} nearby, but not on same tile.")


        # print(f"--- {self.name} (Job: {self.job}, Goal: {self.current_goal}) deciding ---") # Reduced noise

        # Job-specific goal setting
        if self.job == "Woodcutter":
            if self.current_goal not in ["Perform Woodcutter Duties", "Gather Wood", "Stockpile Wood"] or \
               self.current_goal in ["Wander", None, "Idle"]: # If not on a job task, or was wandering/idle
                self.current_goal = "Perform Woodcutter Duties"
                # print(f"{self.name} (Woodcutter) sets goal to: Perform Woodcutter Duties.")

        # Goal-driven actions
        if self.current_goal == "Perform Woodcutter Duties":
            wood_quota = self.needs.get("Wood", 5)
            if self.inventory.get("Wood", 0) < wood_quota:
                self.current_goal = "Gather Wood"
                # print(f"{self.name} (Woodcutter) needs wood ({self.inventory.get('Wood',0)}/{wood_quota}). Goal: Gather Wood.")
                self.decide_action(world)
            else:
                self.current_goal = "Stockpile Wood"
                # print(f"{self.name} (Woodcutter) quota met ({self.inventory.get('Wood',0)}). Goal: Stockpile Wood.")
                self.decide_action(world)

        elif self.current_goal == "Stockpile Wood":
            print(f"{self.name} (Woodcutter) has 'stockpiled' {self.inventory.get('Wood',0)} wood. Job cycle complete.")
            # To simulate actual stockpiling, we could remove some/all wood from inventory
            # self.inventory["Wood"] = 0
            self.current_goal = "Wander" # Or "Idle", or None. Then job check will pick it up next day.

        elif self.current_goal == "Gather Wood":
            # Determine needed wood: if it's for job, use job quota, else personal need (e.g. shelter)
            if self.job == "Woodcutter" and "Perform Woodcutter Duties" in self.memory : # A bit of a hack to see if it's job-related gathering
                 needed_wood = self.needs.get("Wood", 5) # Job quota
            else: # Personal need, e.g. for shelter (not currently in this test)
                 needed_wood = self.needs.get("Wood", 1) # Default personal need if not specified

            if self.inventory.get("Wood", 0) >= needed_wood:
                if self.job == "Woodcutter":
                    self.current_goal = "Perform Woodcutter Duties" # Go back to check if quota met / stockpile
                    # print(f"{self.name} (Woodcutter) finished gathering a batch of wood. Re-evaluating duties.")
                else: # Non-job related wood gathering
                    self.current_goal = "Wander" # Or whatever the previous goal was
                self.decide_action(world)
            else:
                wood_loc = self.find_nearest_resource("Wood", world)
                if wood_loc:
                    if (self.x, self.y) == wood_loc:
                        self.gather_resource("Wood", world)
                    else:
                        self.move_towards(wood_loc[0], wood_loc[1], world)
                else:
                    # print(f"{self.name} needs Wood, but no Wood found in the world.")
                    self.current_goal = "Wander"

        elif self.current_goal == "Wander":
            # print(f"{self.name} is Wandering.") # Reduced noise
            possible_moves = []
            # Try to move to an adjacent, non-blocking, empty tile
            for dx_try, dy_try in [(0,1), (0,-1), (1,0), (-1,0)]:
                target_x, target_y = self.x + dx_try, self.y + dy_try
                if 0 <= target_x < world.grid_size[0] and 0 <= target_y < world.grid_size[1] and \
                   world.get_tile(target_x, target_y) not in ["Water", "Mountain", "Forest", "Rocks"] and \
                   not world.get_characters_at_location(target_x, target_y):
                    possible_moves.append((dx_try, dy_try))

            if possible_moves:
                dx, dy = random.choice(possible_moves)
                self.move(dx, dy, world)
            # else: print(f"{self.name} is stuck or chose not to move while wandering.")

        else: # Idle or unknown goal
            if self.job == "Woodcutter":
                # print(f"{self.name} (Woodcutter) was idle or had unknown goal '{self.current_goal}'. Checking duties.")
                self.current_goal = "Perform Woodcutter Duties"
                self.decide_action(world)
            elif self.current_goal is None or self.current_goal == "Idle":
                # print(f"{self.name} is truly idle.")
                if random.random() < 0.3: self.current_goal = "Wander"
            else:
                # print(f"{self.name} has unhandled goal: {self.current_goal}. Will Wander.")
                self.current_goal = "Wander"
        pass # End of decide_action
