# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile
from .work_order import WorkOrder
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS, STRUCTURE_BLUEPRINTS # Added STRUCTURE_BLUEPRINTS
from .building import Building # Added Building
# from .furniture import Furniture # Commented out as it's not present after reset and not core to this test
# from .events_data import EVENT_DEFINITIONS # Commented out - file missing after reset
# from .event_manager import EventManager # Commented out - file missing after reset / depends on events_data
from . import config
import random
import curses
from typing import Optional, Dict, Any, List # Added List

def print_map_to_console(world: World, characters: List[Character]):
    grid_display = [["." for _ in range(world.grid_size[1])] for _ in range(world.grid_size[0])]
    for r_idx in range(world.grid_size[0]):
        for c_idx in range(world.grid_size[1]):
            grid_display[r_idx][c_idx] = world.get_tile(c_idx, r_idx) # world uses (x,y) for get_tile

    for char in characters:
        if 0 <= char.y < world.grid_size[0] and 0 <= char.x < world.grid_size[1]:
            grid_display[char.y][char.x] = char.name[0]

    print("\n--- World Map ---")
    for row in grid_display:
        print(" ".join(row))
    print("-----------------")

def main_simulation_logic(stdscr: Optional[curses.window]): # Combined logic, stdscr can be None
    # Curses setup (optional)
    world_win, info_win, log_win = None, None, None
    height, width = 24, 80
    world_view_height, world_view_width, info_panel_width, log_height = 14, 48, 32, 10

    if stdscr:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)
        stdscr.keypad(True)
        height, width = stdscr.getmaxyx()
        world_view_height = height - 10
        world_view_width = int(width * 0.6)
        info_panel_width = width - world_view_width
        log_height = 10
        world_win = curses.newwin(world_view_height, world_view_width, 0, 0)
        info_win = curses.newwin(height, info_panel_width, 0, world_view_width)
        log_win = curses.newwin(log_height, world_view_width, world_view_height, 0)

    # --- Game World Setup ---
    initial_setup_messages = []
    initial_setup_messages.append("--- Initializing Game World for Phased Construction Test ---")

    ticks_per_day = 10
    days_per_season = 10
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)
    # event_manager = EventManager(world_ref=game_world) # Commented out
    # event_manager.load_event_definitions(EVENT_DEFINITIONS) # Commented out

    game_world.stockpiles.clear()
    game_world.resources.clear()
    game_world.buildings.clear()
    game_world.work_orders.clear()
    game_world.characters.clear() # Clear characters from previous (reset) state

    # Stockpiles
    wood_stockpile = Stockpile(name="WoodStore", x=0, y=3, width=1, height=1, allowed_resources=["Wood"], total_capacity=100)
    wood_stockpile.add_item("Wood", 40) # Ensure enough for hut (req 30) + buffer
    game_world.add_stockpile(wood_stockpile)
    game_world.ledger.update_stockpile_record(wood_stockpile.name, wood_stockpile.inventory, game_time_obj.current_day)
    initial_setup_messages.append(f"Added WoodStore stockpile with {wood_stockpile.inventory.get('Wood',0)} Wood.")

    # Characters
    test_characters = []
    # manager_char = Character(name="Bossman", personality="Demanding", traits=["Strict"], job="Manager", x=5,y=5, rank="Manager", skills={})
    # game_world.add_character(manager_char)
    # test_characters.append(manager_char)
    # initial_setup_messages.append(f"  Added: {manager_char.name} (Job: {manager_char.job}) at ({manager_char.x},{manager_char.y})")

    liam_skills = {"Construction": 1}
    liam = Character(name="Liam", personality="Optimistic", traits=["Diligent"],
                      job="Builder", x=2,y=1, skills=liam_skills,
                      needs={"Hunger": 80, "Thirst": 70, "Energy": 100}) # Start with full energy
    # liam.set_supervisor(manager_char.name) # No supervisor for this test
    # manager_char.add_subordinate(liam.name)
    game_world.add_character(liam)
    test_characters.append(liam)
    construction_skill_level = 0
    if hasattr(liam, 'skills') and liam.skills and "Construction" in liam.skills and isinstance(liam.skills["Construction"], dict):
        construction_skill_level = liam.skills["Construction"].get("level", 0)
    initial_setup_messages.append(f"  Added: {liam.name} (Job: {liam.job}, Construction L{construction_skill_level}) at ({liam.x},{liam.y})")

    # Initial Build Order for Liam (Builder)
    hut_bp_key = "wooden_hut"
    hut_bp = STRUCTURE_BLUEPRINTS.get(hut_bp_key)
    if hut_bp:
        build_site_loc = (6,1)
        total_build_time_from_phases = sum(phase['work_required'] for phase in hut_bp.get('construction_phases', []))

        hut_build_wo = WorkOrder(
            order_type="BuildStructure",
            details={
                "structure_type": hut_bp_key,
                "location": build_site_loc,
                "required_resources": hut_bp["required_resources"],
                "size": hut_bp["size"],
                "build_time": total_build_time_from_phases, # For WO record, Building class recalculates
                "map_char_initial": hut_bp.get("map_char_initial", "X"), # Pass these for Building constructor
                "map_char_complete": hut_bp.get("map_char_complete", "B"),
                "construction_phases": hut_bp.get("construction_phases") # Pass phases
            },
            creation_day=1, priority=1
        )
        # Set status to InProgress and assign directly for the test scenario
        hut_build_wo.status = "InProgress"
        hut_build_wo.assigned_to = liam.name
        game_world.add_work_order(hut_build_wo)

        # Assign to Liam's attributes
        liam.active_build_order_id = hut_build_wo.order_id
        liam.current_building_project = hut_bp_key
        liam.building_site_target = build_site_loc
        liam.current_goal = "Execute Build Order" # Start him off with the correct goal
        initial_setup_messages.append(f"  Assigned Build WO for {hut_bp_key} (Total Work: {total_build_time_from_phases}) at {build_site_loc} to {liam.name}.")
    else:
        initial_setup_messages.append(f"ERROR: Blueprint for '{hut_bp_key}' not found!")

    # Log initial setup messages
    for msg in initial_setup_messages:
        print(msg) # For console
        game_world.add_event_log_message(msg) # For UI log

    game_world.add_event_log_message("--- Simulation: Phased Construction Test Starting ---")
    max_simulation_days = 20
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0
    selected_entity_details: Optional[Dict[str, Any]] = None
    cursor_y, cursor_x = 0, 0
    game_paused = False

    while running:
        key = -1
        if stdscr:
            key = stdscr.getch()

        if key == ord('q'): running = False; game_world.add_event_log_message("Quit command.")
        elif key == ord('p'):
            game_paused = not game_paused
            game_world.add_event_log_message("SIMULATION " + ("PAUSED" if game_paused else "RESUMED"))

        if not game_paused and running:
            new_day = game_time_obj.tick()
            current_total_ticks +=1
            # event_manager.process_active_events() # Commented out

            for char_to_act in list(game_world.characters):
                if char_to_act not in game_world.characters: continue
                if hasattr(char_to_act, 'process_status_effects'): # Check before calling
                    char_to_act.process_status_effects(game_world)
                char_to_act.decide_action(game_world)

            if new_day:
                day_msg = f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***"
                print(day_msg); game_world.add_event_log_message(day_msg)

                # Check for election day
                if hasattr(game_world.game_time, 'days_until_election') and game_world.game_time.days_until_election <= 0:
                    if hasattr(game_world, 'handle_election'):
                        game_world.handle_election()
                    else: # Should not happen if world.py is updated correctly
                        game_world.add_event_log_message("ERROR: Election due but handle_election method not found in world.")
                        # Manually reset timer to avoid constant trigger if method is missing
                        game_world.game_time.days_until_election = config.ELECTION_CYCLE_DAYS


                if not stdscr: print_map_to_console(game_world, game_world.characters)

                # event_manager.check_triggers() # Commented out
                for char_daily_reset in game_world.characters:
                    char_daily_reset.needs['Hunger'] = max(0, char_daily_reset.needs.get('Hunger', 100) - random.randint(10, 20))
                    char_daily_reset.needs['Thirst'] = max(0, char_daily_reset.needs.get('Thirst', 100) - random.randint(15, 25))
                    char_daily_reset.needs['Comfort'] = max(0, char_daily_reset.needs.get('Comfort', 100) - random.randint(3, 7))
                    if 'Social' in char_daily_reset.needs:
                        char_daily_reset.needs['Social'] = max(0, char_daily_reset.needs['Social'] - random.randint(3,7))
                    if hasattr(char_daily_reset, '_update_mood'): char_daily_reset._update_mood(game_world)
                    if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                       not char_daily_reset.active_work_order_id and \
                       not char_daily_reset.active_build_order_id and \
                       char_daily_reset.job != "Unemployed":
                        char_daily_reset.current_goal = char_daily_reset.job_default_goal()

                # Daily status for Liam
                if liam in game_world.characters:
                    building_being_worked_on = None
                    if liam.active_build_order_id:
                        build_order_obj = game_world.get_work_order_by_id(liam.active_build_order_id)
                        if build_order_obj and build_order_obj.details.get("location"):
                            building_being_worked_on = game_world.get_building_at(build_order_obj.details["location"][0], build_order_obj.details["location"][1])

                    liam_status_msg = (f"  STATUS: {liam.name} (Pos:({liam.x},{liam.y}), Goal='{liam.current_goal}', "
                                     f"Needs(H:{liam.needs.get('Hunger',0)} E:{liam.needs.get('Energy',0)}) Inv:{sum(liam.inventory.values())}, "
                                     f"BuildWO: {liam.active_build_order_id[:8] if liam.active_build_order_id else 'None'}")
                    if building_being_worked_on:
                        liam_status_msg += f" BuildingProg: {building_being_worked_on.current_progress:.1f}/{building_being_worked_on.build_time:.1f} Phase: {building_being_worked_on.get_current_phase_name()}"
                    print(liam_status_msg); game_world.add_event_log_message(liam_status_msg)

                if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                    game_world.advance_season(); last_season_change_day = game_time_obj.current_day

            if game_time_obj.current_day > max_simulation_days:
                msg = f"Simulation reached max days ({max_simulation_days})."; print(msg); game_world.add_event_log_message(msg)
                running = False

        if stdscr: # UI Update
            # Simplified UI for now, focusing on log
            if log_win:
                log_win.clear(); log_win.box(); log_win.addstr(0, 2, "Event Log")
                max_lines = log_height - 2
                start_index = max(0, len(game_world.event_log) - max_lines)
                for i, log_entry in enumerate(game_world.event_log[start_index:]):
                    if i < max_lines:
                        display_message = log_entry[:world_view_width - 4]
                        if len(log_entry) > world_view_width - 4: display_message = display_message[:-3] + "..."
                        try: log_win.addstr(i + 1, 1, display_message)
                        except curses.error: pass
                log_win.refresh()
            if world_win: # Basic map refresh
                world_win.clear(); world_win.box(); world_win.addstr(0,2, "Map")
                for r_idx in range(game_world.grid_size[0]):
                    for c_idx in range(game_world.grid_size[1]):
                        char_to_draw = game_world.get_tile(c_idx,r_idx)
                        ch_obj_at_loc = game_world.get_characters_at_location(c_idx,r_idx)
                        if ch_obj_at_loc: char_to_draw = ch_obj_at_loc[0].name[0]
                        if 1+r_idx < world_view_height -1 and 1+c_idx < world_view_width -1:
                             try: world_win.addch(1+r_idx, 1+c_idx, char_to_draw)
                             except: pass
                world_win.refresh()


    print(f"Final Time: {game_time_obj}")
    for char_final in test_characters:
        if char_final in game_world.characters:
            print(f"\n{char_final}")
            print(f"  Final Needs: {char_final.needs}")
            print(f"  Status Effects: {[s['name'] for s in char_final.status_effects] if hasattr(char_final, 'status_effects') else 'N/A'}")
            print(f"  Inventory: {char_final.inventory}")
            print(f"  Recent Memories (last 10):")
            for mem in char_final.memory[-10:]: print(f"    - {mem}")

    print("\n--- World Event Log (Last 50) ---")
    for log_entry in game_world.event_log[-50:]: print(log_entry)

if __name__ == "__main__":
    # For Curses UI:
    # curses.wrapper(main_simulation_logic)
    # For headless run:
    main_simulation_logic(None)
