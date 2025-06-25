# game/main.py
from .character import Character
from .world import World
from .time import Time
from .stockpile import Stockpile # Keep for potential future item interaction with events
from .work_order import WorkOrder # Keep for potential future event-driven WOs
from .data import BLUEPRINTS, JOB_TASK_DEFINITIONS
from .events_data import EVENT_DEFINITIONS
from .event_manager import EventManager
from . import config
import random
import curses # Import curses

def main_simulation(stdscr): # Renamed main to main_simulation, takes stdscr
    # Curses setup
    curses.curs_set(0) # Hide cursor
    stdscr.nodelay(True) # Non-blocking input
    stdscr.timeout(100) # Timeout for getch() in ms, affects tick rate (e.g., 100ms = 10 FPS max for UI updates)
    stdscr.keypad(True) # Enable keypad mode for special keys like arrow keys

    height, width = stdscr.getmaxyx()

    # Define window dimensions
    world_view_height = height - 10 # Reserve 10 lines for log and potentially status bar
    world_view_width = int(width * 0.6) # 60% for world view
    info_panel_width = width - world_view_width
    log_height = 10

    # Create windows
    world_win = curses.newwin(world_view_height, world_view_width, 0, 0)
    info_win = curses.newwin(height, info_panel_width, 0, world_view_width) # Full height for info panel
    log_win = curses.newwin(log_height, world_view_width, world_view_height, 0) # Log window below world view

    # Placeholder draw functions for now
    def draw_world_view(win, world: World, current_cursor_x: int, current_cursor_y: int): # Added cursor params
        win.clear()
        win.box()
        win.addstr(0, 2, "World View")

        # Draw grid and entities
        for r_idx in range(world.grid_size[0]): # r_idx is effectively y
            for c_idx in range(world.grid_size[1]): # c_idx is effectively x
                char_to_draw = "."

                # Bounds check for drawing area within the window
                draw_y, draw_x = r_idx + 1, c_idx + 1 # +1 for border offset
                if draw_y >= world_view_height -1 or draw_x >= world_view_width -1 : continue

                # Determine character to draw based on game state
                chars_at_loc = world.get_characters_at_location(c_idx, r_idx) # World uses (x,y)
                if chars_at_loc:
                    char_to_draw = chars_at_loc[0].name[0]
                else:
                    tile_content = world.get_tile(c_idx, r_idx) # World uses (x,y)
                    if tile_content == "Forest": char_to_draw = "F"
                    elif tile_content == "Rocks": char_to_draw = "R"
                    elif tile_content == "Water": char_to_draw = "~"
                    elif tile_content == "Mountain": char_to_draw = "^"
                    elif tile_content != "Grass": # Likely a building part
                         char_to_draw = tile_content

                # Draw the character, highlight if it's the cursor position
                attributes = curses.A_NORMAL
                if c_idx == current_cursor_x and r_idx == current_cursor_y:
                    attributes = curses.A_REVERSE # Highlight cursor

                try:
                    win.addch(draw_y, draw_x, char_to_draw, attributes)
                except curses.error:
                    pass
        win.refresh()

    def draw_char_info_view(win, entity_details: Optional[Dict[str, Any]], world: World): # New function
        win.clear()
        win.box()
        win.addstr(0, 2, "Entity Information")

        if entity_details:
            y_offset = 2
            max_width = info_panel_width - 4 # Account for box and padding

            def add_info_line(text, y_offset):
                win.addstr(y_offset, 2, text[:max_width])
                return y_offset + 1

            entity_type = entity_details.get("type")
            y_offset = add_info_line(f"Type: {entity_type}", y_offset)

            if entity_type == "character":
                char_obj = entity_details.get("object")
                if isinstance(char_obj, Character):
                    y_offset = add_info_line(f"Name: {char_obj.name}", y_offset)
                    y_offset = add_info_line(f"Job: {char_obj.job}", y_offset)
                    y_offset = add_info_line(f"Goal: {char_obj.current_goal}", y_offset)
                    y_offset = add_info_line(f"Pos: ({char_obj.x},{char_obj.y})", y_offset)
                    y_offset = add_info_line(f"Social Need: {char_obj.needs.get('Social', 'N/A')}", y_offset)
                    statuses = [s['name'] for s in char_obj.status_effects]
                    y_offset = add_info_line(f"Statuses: {', '.join(statuses) if statuses else 'None'}", y_offset)
                    y_offset = add_info_line(f"Inventory: {sum(char_obj.inventory.values())} items", y_offset)
                    if char_obj.relationships:
                        y_offset = add_info_line("Relationships:", y_offset)
                        for name, score in char_obj.relationships.items():
                            y_offset = add_info_line(f"  - {name}: {score}", y_offset)
                            if y_offset >= height -2 : break # Stop if out of window space
            elif entity_type == "building":
                b_obj = entity_details.get("object")
                if isinstance(b_obj, Building):
                    y_offset = add_info_line(f"Name: {b_obj.display_name}", y_offset)
                    y_offset = add_info_line(f"Type: {b_obj.structure_type}", y_offset)
                    y_offset = add_info_line(f"Location: {b_obj.location}", y_offset)
                    y_offset = add_info_line(f"Progress: {b_obj.current_progress}/{b_obj.build_time}", y_offset)
                    y_offset = add_info_line(f"Operational: {b_obj.is_operational}", y_offset)
            elif entity_type == "tile":
                y_offset = add_info_line(f"Coords: ({entity_details.get('x')},{entity_details.get('y')})", y_offset)
                y_offset = add_info_line(f"Terrain: {entity_details.get('tile_type')}", y_offset)
                if entity_details.get("resource"):
                    y_offset = add_info_line(f"Resource: {entity_details.get('resource')}", y_offset)
            else:
                y_offset = add_info_line("No entity selected or unknown type.", y_offset)
        else:
            win.addstr(2, 2, "Move cursor (arrow keys) and press Enter to inspect.")

        win.refresh()


    def draw_ui(world, selected_entity_details=None, current_cursor_x=0, current_cursor_y=0): # Modified signature
        log_win.clear()
        log_win.box()
        log_win.addstr(0, 2, "Event Log")
        draw_log_view(log_win, world, log_height) # log_height is global in main_simulation

        draw_world_view(world_win, world, current_cursor_x, current_cursor_y)
        draw_char_info_view(info_win, selected_entity_details, world)


    def draw_log_view(win, world: World, window_height: int):
        # win.clear() # Clearing is done by draw_ui or at start of this func now
        # win.box() # Boxing is done by draw_ui
        win.addstr(0, 2, "Event Log")

        max_lines = window_height - 2  # Account for box border
        start_index = max(0, len(world.event_log) - max_lines)

        for i, log_entry in enumerate(world.event_log[start_index:]):
            if i < max_lines:
                # Truncate long messages to fit window width
                max_msg_width = world_view_width - 4 # Account for borders and a little padding
                display_message = log_entry[:max_msg_width]
                if len(log_entry) > max_msg_width:
                    display_message = display_message[:-3] + "..."

                try:
                    win.addstr(i + 1, 1, display_message)
                except curses.error:
                    pass # Avoid crashing if text doesn't fit, though truncation should help
        win.refresh()

    # --- Original main() content starts here, adapted for curses ---
    # print("--- Game Configuration ---") # Will be logged to UI later as well, or just to console before curses starts
    # print(f"USE_LLM: {config.USE_LLM if hasattr(config, 'USE_LLM') else 'Not Set'}") # Log this before curses init
    # print("--------------------------") # Log this before curses init

    # Initial print statements should happen BEFORE curses.wrapper initializes the screen
    # So, move them outside main_simulation or handle them differently. For now, they will just print to console before UI starts.

    # --- Game World Setup ---
    # The initial print statements about game setup will now be routed to the UI log if possible,
    # or simply printed to console before curses UI starts.

    initial_setup_messages = [] # Collect messages to potentially pass to UI log

    initial_setup_messages.append("--- Initializing Game World & Event Manager ---")

    ticks_per_day = 10 # Game ticks per day
    # Note: stdscr.timeout(100) means roughly 10 UI frames/game ticks per second if game logic is fast.
    # If ticks_per_day is 10, then a game day would pass in about 1 second of real time.

    days_per_season = 10
    game_time_obj = Time(ticks_per_day=ticks_per_day)
    game_world = World(grid_size=(10, 10), game_time_ref=game_time_obj)
    event_manager = EventManager(world_ref=game_world)
    event_manager.load_event_definitions(EVENT_DEFINITIONS)

    # Clear previous test setups
    game_world.stockpiles.clear()
    game_world.resources.clear()
    game_world.buildings.clear()
    game_world.work_orders.clear()

    # Add a basic ToolShed and some tools for workers
    tool_shed = Stockpile(name="ToolShed", x=1, y=1, width=1, height=1, allowed_resources=["Stone Axe", "Stone Pickaxe"], total_capacity=10)
    game_world.add_stockpile(tool_shed)
    tool_shed.add_item("Stone Axe", 1)
    tool_shed.add_item("Stone Pickaxe", 1)
    game_world.ledger.update_stockpile_record(tool_shed.name, tool_shed.inventory, game_time_obj.current_day)
    print(f"Pre-stocked ToolShed with 1 Stone Axe and 1 Stone Pickaxe.")

    wood_stockpile_test = Stockpile(name="WoodStore", x=0, y=3, width=1, height=1, allowed_resources=["Wood"], total_capacity=50)
    game_world.add_stockpile(wood_stockpile_test)
    game_world.ledger.update_stockpile_record(wood_stockpile_test.name, wood_stockpile_test.inventory, game_time_obj.current_day)
    print(f"Added WoodStore stockpile.")

    stone_stockpile_test = Stockpile(name="StoneStore", x=1, y=3, width=1, height=1, allowed_resources=["Stone"], total_capacity=50)
    game_world.add_stockpile(stone_stockpile_test)
    game_world.ledger.update_stockpile_record(stone_stockpile_test.name, stone_stockpile_test.inventory, game_time_obj.current_day)
    print(f"Added StoneStore stockpile.")

    # General Store for consumables
    general_store = Stockpile(name="GeneralStore", x=2, y=3, width=1, height=1, allowed_resources=["FoodRation", "CleanWater", "Plant Fiber"], total_capacity=100)
    game_world.add_stockpile(general_store)
    general_store.add_item("FoodRation", 20)
    general_store.add_item("CleanWater", 20)
    general_store.add_item("Plant Fiber", 20) # Stock Plant Fiber
    game_world.ledger.update_stockpile_record(general_store.name, general_store.inventory, game_time_obj.current_day)
    initial_setup_messages.append(f"Added GeneralStore stockpile, stocked with Food, Water, and Plant Fiber.")


    # Add some Furniture beds for resting test
    from .furniture import Furniture # Ensure Furniture class is imported

    wooden_bed_bp = BLUEPRINTS.get("Wooden Bed")
    if wooden_bed_bp and wooden_bed_bp.get("type") == "Furniture":
        bed1_loc = (5,1)
        bed1 = Furniture(item_name="Wooden Bed",
                         display_name=wooden_bed_bp.get("description", "Wooden Bed"),
                         x=bed1_loc[0], y=bed1_loc[1],
                         functionality=wooden_bed_bp.get("functionality", {}),
                         size=wooden_bed_bp.get("size", (1,2)),
                         map_char=wooden_bed_bp.get("map_char", 'b'))
        game_world.add_furniture(bed1)
        initial_setup_messages.append(f"Placed {bed1.display_name} furniture at {bed1_loc}.")

        bed2_loc = (5,4) # Adjusted y to avoid overlap if hut is 2 tiles high
        bed2 = Furniture(item_name="Wooden Bed",
                         display_name=wooden_bed_bp.get("description", "Wooden Bed"),
                         x=bed2_loc[0], y=bed2_loc[1],
                         functionality=wooden_bed_bp.get("functionality", {}),
                         size=wooden_bed_bp.get("size", (1,2)),
                         map_char=wooden_bed_bp.get("map_char", 'b'))
        game_world.add_furniture(bed2)
        initial_setup_messages.append(f"Placed {bed2.display_name} furniture at {bed2_loc}.")


    # Setup for Event Testing (Now also Need Fulfillment Testing)
    print("\n--- Character Setup (Need Fulfillment & Event Test) ---")

    # Add some resources for gathering tasks to test yield events
    game_world.set_tile(0,0,"Forest"); game_world.add_resource("Wood", (0,0))
    game_world.set_tile(0,1,"Forest"); game_world.add_resource("Wood", (0,1))
    game_world.set_tile(1,0,"Rocks"); game_world.add_resource("Stone", (1,0))

    # Characters for Skill Progression Test
    event_test_chars = [] # Re-using this list name for convenience

    # Eva - Woodcutter, to test skill-up and tool break. Empathetic.
    char1_needs = {"Hunger": 80, "Thirst": 75, "Energy": 90, "Social": 60, "Comfort": 70, "Wood": 20}
    # Start Eva at Woodcutting level 4, close to level 5 for major skill up broadcast
    eva_skills = {"Woodcutting": {"level": 4, "experience": 500, "exp_to_next_level": char1._calculate_exp_for_level(4) if Character else 528}}
    char1 = Character(name="Eva", personality="Stoic", traits=["Empathetic"],
                      job="Woodcutter", x=2,y=2, skills=eva_skills,
                      needs=char1_needs)
    # Give Eva a nearly broken tool
    tool_shed.remove_item("Stone Axe", 1) # Remove the full durability one
    tool_shed.add_item("Stone Axe", 1) # Add a new one to grab
    char1.inventory["Stone Axe"] = 1 # Character needs to fetch it first to equip and use. This line is not needed if she fetches.
                                     # Instead, let's ensure she fetches it and then we'll modify its durability after fetching.
                                     # For simplicity in setup, let's give her one and set durability low.
    # We will set tool durability after she equips it. Or, create a custom low-dura tool.
    # For now, let's assume she'll grab one from ToolShed and it will break naturally or we can adjust durability later.
    # To make tool break more predictable for testing:
    # 1. Eva fetches a Stone Axe.
    # 2. After she equips it, we'll manually set its durability very low.
    # This requires a small change to the main loop or a delayed setup function.
    # For now, we'll rely on natural (but perhaps slow) tool breakage or assume manual adjustment during a hypothetical test run.

    game_world.add_character(char1)
    event_test_chars.append(char1)
    initial_setup_messages.append(f"  Added: {char1.name} (Job: {char1.job}, Woodcutting Lvl 4, Empathetic) at ({char1.x},{char1.y}). Will test skill-up & tool break.")

    # Liam - Now a Builder, to observe reactions. Add "Grumpy" to test negative tool break reaction.
    # Positioned at (2,1), Eva is at (2,2). Liam is 1 tile away.
    char2_needs = {"Hunger": 85, "Thirst": 70, "Energy": 95, "Social": 55, "Comfort": 65, "Stone": 5}
    char2 = Character(name="Liam", personality="Optimistic", traits=["Diligent", "Grumpy"], # Added Grumpy
                      job="Builder", x=2,y=1, skills={"Mining": 1, "Construction": 1},
                      needs=char2_needs)

    # Manager Character
    manager_char = Character(name="Bossman", personality="Demanding", traits=["Strict"], job="Manager", x=5,y=5, rank="Manager")
    game_world.add_character(manager_char)
    event_test_chars.append(manager_char)
    initial_setup_messages.append(f"  Added: {manager_char.name} (Job: {manager_char.job}) at ({manager_char.x},{manager_char.y})")

    # Assign Liam to Bossman and add to world
    char2.set_supervisor(manager_char.name)
    manager_char.add_subordinate(char2.name)
    game_world.add_character(char2)
    event_test_chars.append(char2)
    initial_setup_messages.append(f"  Added: {char2.name} (Job: {char2.job}, Supervisor: {char2.supervisor_name}, Skills: Mining L{char2.skills.get('Mining',{}).get('level',0)}, Construction L{char2.skills.get('Construction',{}).get('level',0)}) at ({char2.x},{char2.y})")

    # Crafty - Now a Carpenter, will craft a Wooden Bed.
    char3_needs = {"Hunger": 90, "Thirst": 80, "Energy": 85, "Social": 50, "Comfort": 60}
    # Give Crafty Carpentry skill
    crafty_skills = {"Stonemasonry": {"level": 0, "experience": 0}, "Carpentry": {"level": 1, "experience": 0}}
    char3 = Character(name="Crafty", personality="Inventive", traits=[],
                      job="Carpenter", x=4,y=2, skills=crafty_skills,
                      needs=char3_needs)
    char3.set_supervisor(manager_char.name)
    manager_char.add_subordinate(char3.name)
    game_world.add_character(char3)
    event_test_chars.append(char3)

    # Resources for Wooden Bed: {"Wood": 15, "Plant Fiber": 5}
    # Add Plant Fiber resource and stockpile if it doesn't exist. For now, pre-stock Crafty.
    # Assuming WoodStore can store Wood. We need a source or stockpile for Plant Fiber.
    # Let's create a simple plant fiber source tile and have a character gather it, or just give it to Crafty.
    # For simplicity of this test step, give directly to Crafty.
    char3.inventory["Wood"] = 20
    char3.inventory["Plant Fiber"] = 10
    initial_setup_messages.append(f"  Added: {char3.name} (Job: Carpenter, Supervisor: {char3.supervisor_name}, Carpentry Lvl 1) at ({char3.x},{char3.y}), pre-stocked for Wooden Bed.")

    # Initial Work Order for Crafty to make a Wooden Bed
    wooden_bed_bp_craft = BLUEPRINTS.get("Wooden Bed")
    if wooden_bed_bp_craft:
        bed_wo = WorkOrder(
            order_type="CraftItem",
            details={"item_name": "Wooden Bed", "quantity": 1, "required_resources": wooden_bed_bp_craft["required_resources"]},
            creation_day=1, priority=1
        )
        bed_wo.status = "Approved"
        bed_wo.assigned_to = char3.name
        game_world.add_work_order(bed_wo)
        char3.active_work_order_id = bed_wo.order_id # Set active WO
        char3.current_goal = "Execute Craft Order" # Set goal
        initial_setup_messages.append(f"  Assigned Craft WO for Wooden Bed to {char3.name}.")

    # Setup initial relationships for testing states
    if char1 and char2: # Eva and Liam
        char1.relationships[char2.name] = 60  # Friendly
        char2.relationships[char1.name] = 60  # Friendly
        initial_setup_messages.append(f"  Set Eva & Liam relationship to Friendly (60).")
    if char3 and manager_char: # Crafty and Bossman
        char3.relationships[manager_char.name] = -40 # Disliked
        manager_char.relationships[char3.name] = -40 # Disliked
        initial_setup_messages.append(f"  Set Crafty & Bossman relationship to Disliked (-40).")


    # Initial Build Order for Liam (Builder)
    hut_bp = STRUCTURE_BLUEPRINTS.get("wooden_hut")
    if hut_bp:
        build_site_loc = (6,1)
        # Ensure resources are available for the hut
        needed_wood_for_hut = hut_bp["required_resources"].get("Wood", 0)
        if wood_stockpile_test.inventory.get("Wood", 0) < needed_wood_for_hut:
             wood_stockpile_test.add_item("Wood", needed_wood_for_hut - wood_stockpile_test.inventory.get("Wood", 0) + 5) # Add enough + a bit more
        game_world.ledger.update_stockpile_record(wood_stockpile_test.name, wood_stockpile_test.inventory, game_time_obj.current_day)

        hut_build_wo = WorkOrder(
            order_type="BuildStructure",
            details={
                "structure_type": "wooden_hut",
                "location": build_site_loc,
                "required_resources": hut_bp["required_resources"],
                "size": hut_bp["size"],
                "build_time": hut_bp["build_time"]
            },
            creation_day=1, priority=1
        )
        hut_build_wo.status = "Approved" # Pre-approve for testing
        hut_build_wo.assigned_to = char2.name # Assign to Liam
        game_world.add_work_order(hut_build_wo)
        char2.active_build_order_id = hut_build_wo.order_id
        char2.current_goal = "Execute Build Order"
        initial_setup_messages.append(f"  Assigned Build WO for Wooden Hut at {build_site_loc} to {char2.name}.")

    initial_setup_messages.append("--- Simulation: Relationship & Need Fulfillment Test ---")
    max_simulation_days = 15 # Adjusted for skill progression
    last_season_change_day = game_time_obj.current_day
    running = True; current_total_ticks = 0

    # UI state variables
    selected_entity_details: Optional[Dict[str, Any]] = None
    cursor_y, cursor_x = 0, 0
    game_paused = False

    # Initial messages for UI log - these will be shown by the UI log window
    # The direct print() calls before this function are for pre-curses console output.
    game_world.add_event_log_message("--- Game Configuration ---")
    game_world.add_event_log_message(f"USE_LLM: {config.USE_LLM if hasattr(config, 'USE_LLM') else 'Not Set'}")
    # game_world.add_event_log_message("--------------------------") # Redundant with console
    game_world.add_event_log_message(f"ToolShed stocked.")
    game_world.add_event_log_message(f"WoodStore & StoneStore added.")
    game_world.add_event_log_message("--- Characters Initialized ---")
    for char_init_log in event_test_chars: # Use the list of test characters
        game_world.add_event_log_message(f"  {char_init_log.name} ({char_init_log.job}) at ({char_init_log.x},{char_init_log.y})")
    game_world.add_event_log_message("--- Simulation Starting ---")


    # Main simulation loop
    while running:
        # Input handling
        key = stdscr.getch()

        if key == ord('q'):
            running = False
            game_world.add_event_log_message("Quit command received. Shutting down.")
        elif key == ord('p'):
            game_paused = not game_paused
            game_world.add_event_log_message("SIMULATION " + ("PAUSED" if game_paused else "RESUMED"))
        elif not game_paused: # Only process game-altering input if not paused
            if key == curses.KEY_UP:
                cursor_y = max(0, cursor_y - 1)
            elif key == curses.KEY_DOWN:
                cursor_y = min(game_world.grid_size[0] - 1, cursor_y + 1)
            elif key == curses.KEY_LEFT:
                cursor_x = max(0, cursor_x - 1)
            elif key == curses.KEY_RIGHT:
                cursor_x = min(game_world.grid_size[1] - 1, cursor_x + 1)
            elif key == ord('\n') or key == curses.KEY_ENTER: # Select / Inspect
                chars_at_cursor = game_world.get_characters_at_location(cursor_x, cursor_y) # Note: world grid is (row,col) -> (y,x) but cursor is (x,y)
                if chars_at_cursor:
                    selected_entity_details = {"type": "character", "name": chars_at_cursor[0].name, "object": chars_at_cursor[0]}
                    game_world.add_event_log_message(f"Selected character: {chars_at_cursor[0].name}")
                else:
                    building_at_cursor = game_world.get_building_at(cursor_x, cursor_y)
                    if building_at_cursor:
                         selected_entity_details = {"type": "building", "name": building_at_cursor.display_name, "object": building_at_cursor}
                         game_world.add_event_log_message(f"Selected building: {building_at_cursor.display_name}")
                    else:
                        tile_info = game_world.get_tile(cursor_x,cursor_y)
                        resource_at_tile = None
                        for res_name, locs in game_world.resources.items():
                            if (cursor_x, cursor_y) in locs:
                                resource_at_tile = res_name
                                break
                        selected_entity_details = {"type": "tile", "x": cursor_x, "y": cursor_y, "tile_type": tile_info, "resource": resource_at_tile}
                        game_world.add_event_log_message(f"Selected tile ({cursor_x},{cursor_y}): {tile_info}" + (f" ({resource_at_tile})" if resource_at_tile else ""))

        # --- Game Logic Tick ---
        if not game_paused and running:
            new_day = game_time_obj.tick()
            current_total_ticks +=1

            event_manager.process_active_events()

            # Check if Crafty finished the bed, if so, create a PlaceFurniture WO for Liam
            # This is a simplified way to chain WOs for testing
            if bed_wo and bed_wo.status == "Completed" and char3.inventory.get("Wooden Bed", 0) > 0:
                # Check if a placement order already exists to avoid duplicates
                place_order_exists = any(wo.order_type == "PlaceFurniture" and wo.details.get("item_name") == "Wooden Bed" for wo in game_world.work_orders)
                if not place_order_exists:
                    target_place_loc = (4,4) # Example location
                    # Ensure Liam has the bed to place it (manual transfer for test)
                    if char3.inventory.get("Wooden Bed", 0) > 0:
                        char3.inventory["Wooden Bed"] -= 1
                        if char3.inventory["Wooden Bed"] == 0: del char3.inventory["Wooden Bed"]

                        char2.inventory["Wooden Bed"] = char2.inventory.get("Wooden Bed", 0) + 1
                        initial_setup_messages.append(f"  Manually moved Wooden Bed from Crafty to Liam for placement test.")

                        place_bed_wo = WorkOrder(
                            order_type="PlaceFurniture",
                            details={"item_name": "Wooden Bed", "target_location": target_place_loc},
                            creation_day=game_time_obj.current_day, priority=2
                        )
                        place_bed_wo.status = "Approved" # Auto-approve for testing
                        # No need to assign; Liam (Builder) should pick it up via decide_action
                        game_world.add_work_order(place_bed_wo)
                        initial_setup_messages.append(f"  Created PlaceFurniture WO for Wooden Bed at {target_place_loc}.")
                        # To prevent this block from running repeatedly after transfer
                        bed_wo = None # Nullify to stop re-triggering this specific WO creation logic

            for char_to_act in list(game_world.characters):
                if char_to_act not in game_world.characters: continue
                char_to_act.process_status_effects(game_world)
                char_to_act.decide_action(game_world)

            if new_day:
                game_world.add_event_log_message(f"*** NEW DAY: Day {game_time_obj.current_day}. Weather: {game_world.weather}, Season: {game_world.season} ***")
                event_manager.check_triggers()

                for char_daily_reset in game_world.characters:
                    # Basic Needs Decay
                    char_daily_reset.needs['Hunger'] = max(0, char_daily_reset.needs.get('Hunger', 100) - random.randint(10, 20))
                    char_daily_reset.needs['Thirst'] = max(0, char_daily_reset.needs.get('Thirst', 100) - random.randint(15, 25))
                    # Energy is primarily decayed by actions, but a small passive decay or cap could be added.
                    # For now, relying on _execute_rest to recover it.
                    char_daily_reset.needs['Comfort'] = max(0, char_daily_reset.needs.get('Comfort', 100) - random.randint(3, 7))

                    # Social Need Decay (existing)
                    if 'Social' in char_daily_reset.needs:
                        char_daily_reset.needs['Social'] = max(0, char_daily_reset.needs['Social'] - random.randint(3,7))

                    # Call character's own mood update logic
                    char_daily_reset._update_mood(game_world)

                    if char_daily_reset.current_goal in ["Wander", None, "Idle"] and \
                       not char_daily_reset.active_work_order_id and \
                       not char_daily_reset.active_build_order_id and \
                       char_daily_reset.job != "Unemployed":
                        char_daily_reset.current_goal = char_daily_reset.job_default_goal()

                if game_world.active_world_effects:
                    log_msg_world_effects = "Active World Effects:"
                    for key_eff, effect_info in game_world.active_world_effects.items():
                        expires_in_ticks = effect_info.get('expires_tick', 0) - current_total_ticks
                        log_msg_world_effects += f"\n    - {key_eff}: {effect_info.get('multiplier') or effect_info.get('bonus_details')} (expires ~{expires_in_ticks / ticks_per_day:.1f}d)"
                    game_world.add_event_log_message(log_msg_world_effects)

                # Log character skills daily for testing skill progression AND general status
                for char_status in event_test_chars:
                    if char_status in game_world.characters:
                        status_names = [s['name'] for s in char_status.status_effects]
                        skills_summary_list = []
                        for skill_name, data in char_status.skills.items():
                            skills_summary_list.append(f"{skill_name} L{data['level']}({data['experience']:.0f}/{data['exp_to_next_level']:.0f})")
                        skills_summary = ", ".join(skills_summary_list) if skills_summary_list else "None"

                        game_world.add_event_log_message(
                            f"  STATUS: {char_status.name} (Pos:({char_status.x},{char_status.y}), Goal='{char_status.current_goal}', "
                            f"Needs(H:{char_status.needs.get('Hunger',0)} T:{char_status.needs.get('Thirst',0)} E:{char_status.needs.get('Energy',0)} S:{char_status.needs.get('Social',0)} C:{char_status.needs.get('Comfort',0)}) Mood:{char_status.mood}, "
                            f"Statuses: {status_names}, Inv: {sum(char_status.inventory.values())}, Skills: [{skills_summary}])"
                        )

                if (game_time_obj.current_day - last_season_change_day) >= days_per_season:
                    game_world.advance_season()
                    last_season_change_day = game_time_obj.current_day

            if game_time_obj.current_day > max_simulation_days:
                game_world.add_event_log_message(f"Simulation reached max days ({max_simulation_days}).")
                running = False

        # --- UI Update ---
        # Pass cursor_x, cursor_y to draw_ui, and it will pass to draw_world_view
        draw_ui(game_world, selected_entity_details, cursor_x, cursor_y)

    # --- End of main simulation loop ---
    # Final state prints will go to console after curses ends.
    print(f"Final Time: {game_time_obj}")
    for char_final in event_test_chars:
        if char_final in game_world.characters:
            print(f"\n{char_final}") # Uses Character __str__
            print(f"  Final Needs: {char_final.needs}")
            print(f"  Status Effects: {[s['name'] for s in char_final.status_effects]}")
            print(f"  Inventory: {char_final.inventory}")
            print(f"  Recent Memories (last 10):")
            for mem in char_final.memory[-10:]:
                print(f"    - {mem}")

    print("\n--- World Event Log ---")
    for log_entry in game_world.event_log:
        print(log_entry)

if __name__ == "__main__":
    curses.wrapper(main_simulation)
