# Living World Simulation

This repository powers a prototype settlement simulation with a lightweight web
UI. The backend simulation and HTTP server run entirely from Python and serve
static assets from the `ui/` directory.

## Getting Started

1. Install the project dependencies (a standard Python 3.11 environment is
   sufficient; no external services are required).
2. Start the simulation and bundled web server:

   ```bash
   python -m game
   ```

   The command starts the simulation loop and serves the UI on
   [http://localhost:5000](http://localhost:5000). The script automatically
   warms the index page so you should immediately see the UI load once the
   server is up.
3. Visit the UI in a browser to observe the world state tick forward in real
   time. The event log and overlays provide additional detail on ongoing
   systems such as the legal process and the healthcare triage pipeline.

To stop the simulation press <kbd>Ctrl</kbd> + <kbd>C</kbd> in the terminal.

## Systems Spotlight

The simulation advances several structured loops each day. Recent highlights
include:

- **Workforce logistics:** configurable work crews for logging, quarrying, and
  farming now estimate daily production, coordinate haulers, and push gathered
  goods into available stockpiles while tracking backlogs when storage or
  carry-capacity runs short.
- **Training grounds:** apprenticeship programs queue under-skilled citizens,
  select instructors, and report active sessions alongside waitlists to the UI.
- **Civic services:** the legal system, healthcare triage, and housing reviews
  all report their status through the API so that the HUD can surface key
  pressures without digging into logs.
