from __future__ import annotations
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Protocol

class EventType(Enum):
    """Defines the different types of events in the game."""
    # Add more event types here as the system grows
    RUMOR_CREATED = auto()
    CHARACTER_HIRED = auto()
    CHARACTER_FIRED = auto()
    BUILDING_COMPLETED = auto()
    # etc.

class Event:
    """Represents an event that has occurred in the game."""
    def __init__(self, event_type: EventType, data: Dict[str, Any]):
        self.type = event_type
        self.data = data

    def __str__(self):
        return f"Event(type={self.type.name}, data={self.data})"

class EventListener(Protocol):
    """A protocol for any class that can handle events."""
    def handle_event(self, event: Event):
        """Processes an event received from the event bus."""
        ...

# A type alias for a callable function that can handle an event
HandlerFunction = Callable[[Event], None]

class EventBus:
    """A simple event bus for dispatching events to listeners."""
    def __init__(self):
        self.listeners: Dict[EventType, List[HandlerFunction]] = {}

    def subscribe(self, event_type: EventType, handler: HandlerFunction):
        """
        Subscribes a handler function to a specific event type.

        Args:
            event_type: The type of event to listen for.
            handler: The function to call when the event is posted.
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(handler)
        print(f"DEBUG: Handler {handler.__name__} subscribed to {event_type.name}")

    def post(self, event: Event):
        """
        Posts an event to all subscribed listeners.

        Args:
            event: The event to dispatch.
        """
        if event.type in self.listeners:
            # print(f"DEBUG: Posting event {event.type.name} to {len(self.listeners[event.type])} listener(s).")
            for handler in self.listeners[event.type]:
                handler(event)
        # else:
            # print(f"DEBUG: Event {event.type.name} posted, but no listeners.")
