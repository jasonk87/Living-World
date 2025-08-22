# game/game_manager.py
import random
from typing import Optional, List
from .world import World
from .time import Time
from .character import Character
from .stockpile import Stockpile
from .events import EventBus
from .goal import GoalType
from .managers.election_manager import ElectionManager
from .managers.rumor_manager import RumorManager
from . import config

class Game:
    """
    Manages the overall game state and simulation loop.
    """
    def __init__(self):
        # Simulation control
        self.simulation_running: bool = True
        self.game_paused: bool = False
        self.simulation_speed_multiplier: float = 1.0
        self.base_tick_sleep_duration: float = 0.2  # Seconds for 1x speed per tick

        # Game world and time
        self.world: World
        self.time: Time
        self.event_bus: EventBus
        self.election_manager: ElectionManager
        self.rumor_manager: RumorManager
        self.test_characters_list: List[Character] = [] # To store characters for final report

        self._initialize_game_world()

    def _initialize_game_world(self):
        """
        Sets up the initial state of the game world, including time, characters, and stockpiles.
        """
        initial_setup_messages = []
        initial_setup_messages.append("--- Initializing Game World ---")

        ticks_per_day = config.TICKS_PER_DAY if hasattr(config, 'TICKS_PER_DAY') else 10
        self.time = Time(ticks_per_day=ticks_per_day)
        self.event_bus = EventBus()
        self.world = World(grid_size=(10, 10), game_time_ref=self.time, game_ref=self, event_bus_ref=self.event_bus)

        # Initialize managers and subscribe them to events
        self.election_manager = ElectionManager(self.world)
        self.rumor_manager = RumorManager(self.world, self.event_bus)

        self.test_characters_list = [] # Reset for this initialization

        # Load scenario data
        from .scenario import ScenarioLoader # Local import to avoid circular dependency issues if scenario module grows
        scenario = ScenarioLoader.load_from_file('scenarios/default.json')
        initial_setup_messages.append(f"--- Loading Scenario: {scenario.name} ---")
        initial_setup_messages.append(f"{scenario.description}")

        # Initialize from scenario
        for sp_data in scenario.starting_stockpiles:
            stockpile = Stockpile(
                name=sp_data.name,
                x=sp_data.x, y=sp_data.y,
                width=sp_data.width, height=sp_data.height,
                allowed_resources=sp_data.allowed_resources,
                total_capacity=sp_data.total_capacity
            )
            for item, qty in sp_data.initial_inventory.items():
                stockpile.add_item(item, qty)
            self.world.add_stockpile(stockpile)
            self.world.ledger.update_stockpile_record(stockpile.name, stockpile.inventory, self.time.current_day)
            initial_setup_messages.append(f"Added {stockpile.name} stockpile with {stockpile.inventory}.")

        for char_data in scenario.starting_characters:
            character = Character(
                name=char_data.name,
                personality=char_data.personality,
                traits=char_data.traits,
                skills=char_data.skills,
                job=char_data.job,
                rank=char_data.rank,
                x=char_data.x,
                y=char_data.y,
                needs=char_data.needs,
                family_members=char_data.family_members
            )
            self.world.add_character(character)
            self.test_characters_list.append(character)
            initial_setup_messages.append(f"  Added: {character.name} (Job: {character.job}) at ({character.x},{character.y})")

        # Buildings can be added here if any are in the scenario
        for build_data in scenario.starting_buildings:
            # This part will require the Building class and its dependencies
            # For now, we'll just log it. A full implementation would create Building objects.
            initial_setup_messages.append(f"  Scenario includes building: {build_data.structure_type} at {build_data.location} (not yet implemented).")


        for msg in initial_setup_messages:
            print(msg)
            self.world.add_event_log_message(msg)

        self.world.add_event_log_message("--- Simulation Initialized ---")


    def tick(self):
        """
        Advances the simulation by one tick. This is the main simulation logic moved from main.py.
        """
        if self.game_paused or not self.simulation_running:
            return

        new_day = self.time.tick()

        for char_to_act in list(self.world.characters):
            if char_to_act not in self.world.characters: continue
            char_to_act.decide_action(self.world)

        if new_day:
            self._process_daily_updates()

        max_simulation_days = config.MAX_SIMULATION_DAYS if hasattr(config, 'MAX_SIMULATION_DAYS') else 20
        if self.time.current_day > max_simulation_days:
            msg = f"Simulation reached max days ({max_simulation_days}). Stopping simulation."
            print(msg)
            self.world.add_event_log_message(msg)
            self.simulation_running = False

    def _process_daily_updates(self):
        """Handles all updates that occur at the start of a new day."""
        day_msg = f"*** NEW DAY: Day {self.time.current_day}. Weather: {self.world.weather}, Season: {self.world.season} ***"
        print(day_msg)
        self.world.add_event_log_message(day_msg)

        if hasattr(self.time, 'days_until_election') and self.time.days_until_election <= 0:
            self.election_manager.handle_election()

        self.rumor_manager.update_rumors_daily()

        for char in self.world.characters:
            self._update_character_daily(char)

        days_per_season = config.DAYS_PER_SEASON if hasattr(config, 'DAYS_PER_SEASON') else 10
        if self.time.current_day % days_per_season == 1 and self.time.current_day > 1:
             self.world.advance_season()

    def _update_character_daily(self, character: Character):
        """Handles daily updates for a single character."""
        # Sickness & Injury Chance
        if not character.is_sick and random.random() < 0.005: # 0.5% chance
            character.is_sick = True
            character.sickness_severity = random.randint(1, 3)
            self.world.add_event_log_message(f"{character.name} has fallen ill (Severity: {character.sickness_severity}).")
            character.add_memory("Fell ill.")
            character.needs_component.needs['Safety'] = max(config.NEED_SCORE_MIN, character.needs_component.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 15)
            character.add_memory(f"Sickness reduced my safety. Safety: {character.needs_component.needs['Safety']}")

        injury_chance = 0.002
        if character.job in ["Builder", "Woodcutter", "Stonemason", "Miner"]:
            injury_chance = 0.005
        if not character.is_injured and random.random() < injury_chance:
            character.is_injured = True
            character.injury_severity = random.randint(1, 3)
            self.world.add_event_log_message(f"{character.name} has been injured (Severity: {character.injury_severity}).")
            character.add_memory("Got injured.")
            character.needs_component.needs['Safety'] = max(config.NEED_SCORE_MIN, character.needs_component.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - 20)
            character.add_memory(f"Injury reduced my safety. Safety: {character.needs_component.needs['Safety']}")

        # Needs Decay
        character.needs_component.needs['Hunger'] = max(0, character.needs_component.needs.get('Hunger', 100) - random.randint(10, 20))
        character.needs_component.needs['Thirst'] = max(0, character.needs_component.needs.get('Thirst', 100) - random.randint(15, 25))
        character.needs_component.needs['Energy'] = max(0, character.needs_component.needs.get('Energy', 100) - random.randint(10, 15))

        current_social_need = character.needs_component.needs.get('Social', 70)
        decay_amount = config.SOCIAL_NEED_DECAY_RATE_PER_DAY
        if "Loner" in character.traits: decay_amount *= 0.5
        if "Outgoing" in character.traits: decay_amount *= 1.5
        character.needs_component.needs['Social'] = max(0, current_social_need - int(decay_amount))

        character.needs_component.needs['Safety'] = max(config.NEED_SCORE_MIN, character.needs_component.needs.get('Safety', config.NEED_SAFETY_DEFAULT) - config.NEED_SAFETY_DECAY_DAILY)
        character.needs_component.needs['Belonging'] = max(config.NEED_SCORE_MIN, character.needs_component.needs.get('Belonging', config.NEED_BELONGING_DEFAULT) - config.NEED_BELONGING_DECAY_DAILY)
        character.needs_component.needs['Esteem'] = max(config.NEED_SCORE_MIN, character.needs_component.needs.get('Esteem', config.NEED_ESTEEM_DEFAULT) - config.NEED_ESTEEM_DECAY_DAILY)

        if not character.current_goal or character.current_goal.goal_type in [GoalType.IDLE, GoalType.WANDER]:
            if not character.active_work_order_id and not character.active_build_order_id and character.job != "Unemployed":
                character.current_goal = character.get_default_goal()

    def toggle_pause(self):
        self.game_paused = not self.game_paused
        self.world.add_event_log_message(f"SIMULATION TOGGLED: {'PAUSED' if self.game_paused else 'RESUMED'}")
        print(f"Game state toggled. Paused: {self.game_paused}")

    def set_speed(self, multiplier: float):
        if multiplier <= 0:
            multiplier = 0.1
        self.simulation_speed_multiplier = multiplier
        self.world.add_event_log_message(f"Simulation speed set to {self.simulation_speed_multiplier}x")
        print(f"Simulation speed set to {self.simulation_speed_multiplier}x")

    def get_final_report(self):
        """Generates a final report of the simulation."""
        report = []
        report.append(f"Final Time: {self.time}")
        for char_final in self.test_characters_list:
            if char_final in self.world.characters:
                report.append(f"\n{char_final}")
                report.append(f"  Final Needs: {char_final.needs_component.needs}")
                report.append(f"  Inventory: {char_final.inventory}")
                report.append(f"  Recent Memories (last 10):")
                for mem in char_final.memory[-10:]:
                    report.append(f"    - {mem}")
        report.append("\n--- World Event Log (Last 50) ---")
        for log_entry in self.world.event_log[-50:]:
            report.append(log_entry)
        return "\n".join(report)
