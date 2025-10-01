# Simulation Systems Overview

This document summarizes the systemic layers that drive the Living World settlement, focusing on recent additions that deepen day-to-day activity.

## Day and Night Phases
- Phase schedules are configurable via `DAY_PHASE_CONFIG` with behaviour tweaks under `PHASE_BEHAVIOR_TWEAKS`.
- `Time.get_phase()` exposes the active phase, while `World.update_day_phase()` records transitions and shares the snapshot with the UI.
- Characters adjust their goals based on phase traits (meal focus, job urgency, quiet hours) when `_apply_phase_behavior` runs during decision making.

## Weather Events and Environment Effects
- Severe weather pulls definitions from `WEATHER_EVENT_DEFINITIONS`, applies world effects, and recalculates travel speed, yields, and price multipliers.
- `World.daily_environment_tick()` evaluates event lifecycles, clearing expired effects and logging narrative hooks.
- Citizens duck for shelter if `_should_seek_weather_shelter()` signals danger, ensuring storms visibly reshape activity.

## Resource Nodes
- Each resource node now tracks durability, depletion, and regrowth progress.
- Harvest executors flag when `World.deplete_resource_node()` exhausts a node, allowing the map tile to update immediately.
- `_advance_resource_regrowth()` steadily restores depleted nodes so long-term stewardship matters.

## Population Churn
- `World.evaluate_population_dynamics()` reviews economic surplus, housing, and morale to schedule births, invite migrants, or record departures.
- Demographic registries capture arrivals for UI summaries while new citizens inherit traits and needs from archetype pools.

These systems feed directly into the `/game_state` payload for the HUD overlays, enabling the command interface to highlight phase shifts, weather hazards, resource pressure, and demographic changes in real time.
