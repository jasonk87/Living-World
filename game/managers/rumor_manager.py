from __future__ import annotations
from typing import TYPE_CHECKING
from ..rumor import Rumor
from ..events import Event, EventType, EventBus

if TYPE_CHECKING:
    from ..world import World


class RumorManager:
    """Manages rumors in the world by listening to events."""
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        # Subscribe to the event for creating rumors
        event_bus.subscribe(EventType.RUMOR_CREATED, self.handle_rumor_created)

    def handle_rumor_created(self, event: Event):
        """
        Event handler for when a rumor is created.
        Adds the new rumor to the world.
        """
        rumor = event.data.get("rumor")
        if isinstance(rumor, Rumor):
            self.world.rumors.append(rumor)
            # Log that a new rumor is circulating
            log_message = f"New Rumor Circulating: {rumor.subject_char_id} - {rumor.content_key} (Strength: {rumor.initial_strength})"
            self.world.add_event_log_message(log_message)
            print(f"DEBUG: RumorManager handled RUMOR_CREATED event: {log_message}")
        else:
            print(f"ERROR: RumorManager received invalid data for RUMOR_CREATED event: {event.data}")

    def update_rumors_daily(self):
        """Updates all rumors, decaying their lifespan and removing expired ones."""
        if not self.world.rumors:
            return

        original_rumor_count = len(self.world.rumors)
        # Iterate over a copy of the list as we may modify it
        for rumor in list(self.world.rumors):
            rumor.lifespan_days -= 1
            if rumor.lifespan_days <= 0:
                self.world.rumors.remove(rumor)
                # Optional: Log the expiration of a rumor
                # self.world.add_event_log_message(f"A rumor has expired: {rumor.content}")

        expired_count = original_rumor_count - len(self.world.rumors)
        if expired_count > 0:
            self.world.add_event_log_message(f"Expired {expired_count} rumor(s).")
