import sys
import os
import threading
import time as py_time

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from game.game_manager import Game
from game.server import run_server

def simulation_thread_func(game: Game):
    """The main loop for the simulation thread."""
    print("Simulation thread started.")
    while game.simulation_running:
        if not game.game_paused:
            game.tick()

        current_sleep_duration = game.base_tick_sleep_duration
        if game.simulation_speed_multiplier > 0:
            current_sleep_duration /= game.simulation_speed_multiplier

        py_time.sleep(max(0.01, current_sleep_duration))

    print("Simulation thread finished.")
    # Print final report after simulation stops
    final_report = game.get_final_report()
    print(final_report)

def main():
    """
    Initializes the game, starts the simulation and server threads,
    and handles graceful shutdown.
    """
    game = Game()

    # Start simulation thread
    sim_thread = threading.Thread(target=simulation_thread_func, args=(game,), daemon=True)
    sim_thread.start()

    # Start server thread
    # The server runs in its own thread so it doesn't block the main thread.
    server_thread = threading.Thread(target=run_server, args=(game,), daemon=True)
    server_thread.start()

    print("Game simulation running in background. Access UI at http://localhost:8000/")
    print("Press Ctrl+C to stop server and simulation.")

    try:
        # Keep the main thread alive to catch KeyboardInterrupt
        while sim_thread.is_alive():
            sim_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nCtrl+C received. Shutting down...")
    finally:
        game.simulation_running = False
        if sim_thread.is_alive():
            sim_thread.join()
        # The server thread is a daemon, so it will exit when the main thread exits.

    print("Exited gracefully.")

if __name__ == "__main__":
    main()
