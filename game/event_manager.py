# game/event_manager.py
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Callable
import random
import json
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .world import World
    from .character import Character

# Using a simple dict for event definitions for now, loaded from events_data.py
# If events become more complex, could use dataclasses for definitions too.

@dataclass
class ActiveEvent:
    event_id: str
    description: str
    message_template: str # Original message template for logging
    effects: List[Dict[str, Any]]
    duration_ticks: int # Remaining duration in game ticks
    start_tick: int
    one_time: bool = False
    triggered_for_targets: Optional[List[str]] = None # e.g., character names for targeted events
    # Store any specific state for this instance of the event, e.g. which resource is boosted
    instance_data: Dict[str, Any] = field(default_factory=dict)


class EventManager:
    def __init__(self, world_ref: 'World'):
        self.world_ref = world_ref # Reference to the game world
        self.event_definitions: Dict[str, Dict[str, Any]] = {}
        self.active_events: List[ActiveEvent] = []
        self.triggered_one_time_events: set[str] = set() # Track IDs of one-time events that have occurred

    def load_event_definitions(self, event_data: Dict[str, Dict[str, Any]]):
        """Loads event definitions directly from a dictionary (e.g., events_data.EVENT_DEFINITIONS)."""
        self.event_definitions = event_data
        print(f"EventManager: Loaded {len(self.event_definitions)} event definitions.")

    def _check_individual_trigger(self, event_id: str, event_def: Dict[str, Any]) -> bool:
        """Checks trigger for a single event definition."""
        trigger_cfg = event_def.get("trigger")
        if not trigger_cfg:
            return False

        trigger_type = trigger_cfg.get("type")

        if event_def.get("one_time", False) and event_id in self.triggered_one_time_events:
            return False # Don't re-trigger one-time events

        if trigger_type == "random_daily":
            chance = trigger_cfg.get("chance", 0.01)
            if random.random() < chance:
                return True
        elif trigger_type == "random_daily_target_character":
            # This type of trigger means the event *could* happen for any character.
            # The actual targeting will occur when the event is instantiated.
            # The chance here is just for the event type to be considered.
            # We'll handle per-character roll during instantiation or effect application.
            # For now, let's assume if this trigger type is chosen, we'll try to apply it to one random char.
             return True # The check_triggers will handle the per-character roll
        # Add more trigger types: world_state (e.g., low_food), specific_day, etc.

        return False

    def _instantiate_event(self, event_id: str, event_def: Dict[str, Any], target_character: Optional['Character'] = None) -> Optional[ActiveEvent]:
        """Creates an ActiveEvent instance from an event definition."""
        current_tick = self.world_ref.game_time.current_total_ticks
        duration_days = event_def.get("duration_days", 0)
        duration_ticks = duration_days * self.world_ref.game_time.ticks_per_day

        message_template = event_def.get("message", event_def.get("description", "An event occurred!"))

        instance_data = {} # For event-specific dynamic data

        # Handle character-targeted event messages
        final_message = message_template
        triggered_targets_names = []
        if "{character_name}" in message_template:
            if target_character:
                final_message = message_template.replace("{character_name}", target_character.name)
                triggered_targets_names.append(target_character.name)
                instance_data["target_character_name"] = target_character.name # Store for effect application
            else: # Needs a character but none provided (e.g. global event that *could* target)
                 # This case should ideally be handled by the trigger providing a target
                print(f"Warning: Event '{event_id}' has character in message but no target provided during instantiation.")
                return None # Cannot properly instantiate

        active_event_instance = ActiveEvent(
            event_id=event_id,
            description=event_def.get("description", "Unknown event"),
            message_template=final_message, # Use the processed message
            effects=event_def.get("effects", []),
            duration_ticks=duration_ticks,
            start_tick=current_tick,
            one_time=event_def.get("one_time", False),
            triggered_for_targets=triggered_targets_names if triggered_targets_names else None,
            instance_data=instance_data
        )
        return active_event_instance

    def check_triggers(self):
        """
        Checks all event definitions and triggers them if conditions are met.
        This method should be called once per day.
        """
        for event_id, event_def in self.event_definitions.items():
            if self._check_individual_trigger(event_id, event_def):
                trigger_cfg = event_def.get("trigger", {})

                if trigger_cfg.get("type") == "random_daily_target_character":
                    # For events that target a character, roll for each character
                    chance_per_char = trigger_cfg.get("chance_per_char", 0.01)
                    for char_obj in self.world_ref.characters:
                        if random.random() < chance_per_char:
                            instance = self._instantiate_event(event_id, event_def, target_character=char_obj)
                            if instance:
                                self.active_events.append(instance)
                                self.world_ref.add_event_log_message(instance.message_template) # Log the processed message
                                print(f"EVENT TRIGGERED: {instance.description} for {char_obj.name}")
                                self.world_ref.apply_event_effects(instance) # Apply initial effects
                                if instance.one_time:
                                    self.triggered_one_time_events.add(event_id)
                            break # Typically, such an event might only hit one char per day even if multiple roll true
                else: # For global events or other types not needing per-character iteration here
                    instance = self._instantiate_event(event_id, event_def)
                    if instance:
                        self.active_events.append(instance)
                        self.world_ref.add_event_log_message(instance.message_template)
                        print(f"EVENT TRIGGERED: {instance.description}")
                        self.world_ref.apply_event_effects(instance) # Apply initial effects
                        if instance.one_time:
                            self.triggered_one_time_events.add(event_id)

    def process_active_events(self):
        """Processes ongoing effects of active events and handles expiration."""
        current_tick = self.world_ref.game_time.current_total_ticks
        events_to_remove = []
        for event_instance in self.active_events:
            event_instance.duration_ticks -= 1 # Assuming process_active_events is called once per tick

            # Apply any per-tick effects if defined for the event type
            # For now, most effects are applied on trigger or managed by status effects on characters/world flags
            # Example: A continuous drain effect
            # for effect_def in event_instance.effects:
            #    if effect_def.get("apply_per_tick"):
            #        self.world_ref.apply_event_effects(event_instance, effect_def) # Pass specific effect

            if event_instance.duration_ticks <= 0:
                events_to_remove.append(event_instance)
                self.world_ref.add_event_log_message(f"Event '{event_instance.description}' has ended.")
                print(f"EVENT ENDED: {event_instance.description}")
                # Apply expiration effects if any (e.g., remove temporary world modifiers)
                self.world_ref.expire_event_effects(event_instance)

        for expired_event in events_to_remove:
            self.active_events.remove(expired_event)

    def get_active_event_modifiers(self, effect_type: str, target_key: Optional[str] = None) -> List[Any]:
        """
        Collects modifiers from all active events relevant to a specific effect type and target.
        Example: Get all "modify_resource_yield" multipliers for "Wood".
        """
        modifiers = []
        for event_instance in self.active_events:
            for effect in event_instance.effects:
                if effect.get("type") == effect_type:
                    if target_key: # If the effect is specific (e.g. to a resource type)
                        # Check if the effect's target_key matches (e.g., effect["resource_type"] == "Wood")
                        # This needs a flexible way to match keys, e.g. effect.get("resource_type") or effect.get("item_type")
                        # For now, let's assume a common key like "applies_to" or check specific known keys
                        if effect.get("resource_type") == target_key or \
                           effect.get("item_type") == target_key or \
                           effect.get("skill_used") == target_key:
                            modifiers.append(effect) # Return the whole effect dict for the caller to parse
                    else: # Global effect of this type
                        modifiers.append(effect)
        return modifiers

    def is_event_active(self, event_id_or_type: str, target_character_name: Optional[str] = None) -> bool:
        """Checks if an event (by ID or a general type from its effects) is active, optionally for a specific character."""
        for event_instance in self.active_events:
            if event_instance.event_id == event_id_or_type:
                if target_character_name:
                    if event_instance.triggered_for_targets and target_character_name in event_instance.triggered_for_targets:
                        return True
                else: # Not checking for a specific character target
                    return True
            # Check if any effect type matches event_id_or_type (e.g. "minor_illness")
            for effect in event_instance.effects:
                if effect.get("type") == event_id_or_type or effect.get("status_name") == event_id_or_type : # crude check
                    if target_character_name:
                         if event_instance.triggered_for_targets and target_character_name in event_instance.triggered_for_targets:
                            return True
                    else:
                        return True
        return False
