import random
from collections import deque
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Iterable, Tuple, Deque, Union
from copy import deepcopy
from . import config
from .rumor import Rumor

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class Health:
    def __init__(self, character: 'Character'):
        self.character = character
        self.is_sick: bool = False
        self.sickness_severity: int = 0
        self.is_injured: bool = False
        self.injury_severity: int = 0
        self.is_deceased: bool = False

        health_defaults = getattr(config, "HEALTH_PROFILE_DEFAULTS", {})
        base_vitality = float(health_defaults.get("base_vitality", 72))
        vitality_variance = float(health_defaults.get("vitality_variance", 6))
        base_immunity = float(health_defaults.get("base_immunity", 0.6))
        immunity_variance = float(health_defaults.get("immunity_variance", 0.1))
        base_stress = float(health_defaults.get("base_stress", 0.2))

        vitality = max(
            getattr(config, "HEALTH_VITALITY_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_VITALITY_CEILING", 100.0),
                base_vitality + random.uniform(-vitality_variance, vitality_variance),
            ),
        )
        immunity = max(
            getattr(config, "HEALTH_IMMUNITY_FLOOR", 0.05),
            min(
                getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                base_immunity + random.uniform(-immunity_variance, immunity_variance),
            ),
        )
        stress = max(
            getattr(config, "HEALTH_STRESS_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_STRESS_CEILING", 1.0),
                base_stress + random.uniform(-0.05, 0.05),
            ),
        )

        self.health_profile: Dict[str, Any] = {
            "vitality": vitality,
            "immune_resilience": immunity,
            "stress": stress,
            "chronic_conditions": [],
            "recent_events": deque(maxlen=getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10)),
            "condition_history": [],
            "last_checkup_day": None,
            "last_checkup_note_day": None,
        }
        self.health_profile["vitality_band"] = self._classify_vitality(vitality)
        self.health_profile["stress_band"] = self._classify_stress(stress)
        self.health_profile["immunity_band"] = self._classify_immunity(immunity)

    @staticmethod
    def _classify_vitality(value: float) -> str:
        if value >= 85:
            return "robust"
        if value >= 70:
            return "steady"
        if value >= 50:
            return "strained"
        if value >= 30:
            return "frail"
        return "critical"

    @staticmethod
    def _classify_stress(value: float) -> str:
        if value <= 0.18:
            return "calm"
        if value <= 0.32:
            return "steady"
        if value <= 0.55:
            return "tense"
        if value <= 0.75:
            return "strained"
        return "overwhelmed"

    @staticmethod
    def _classify_immunity(value: float) -> str:
        if value >= 0.78:
            return "resilient"
        if value >= 0.6:
            return "steady"
        if value >= 0.45:
            return "susceptible"
        return "fragile"

    def get_health_snapshot(self) -> Dict[str, Any]:
        profile = getattr(self, "health_profile", None)
        if not profile:
            return {}

        snapshot: Dict[str, Any] = {
            "is_sick": self.is_sick,
            "sickness_severity": self.sickness_severity,
            "is_injured": self.is_injured,
            "injury_severity": self.injury_severity,
            "vitality": round(float(profile.get("vitality", 0.0)), 1),
            "immune_resilience": round(float(profile.get("immune_resilience", 0.0)), 3),
            "stress": round(float(profile.get("stress", 0.0)), 3),
            "vitality_band": profile.get("vitality_band"),
            "stress_band": profile.get("stress_band"),
            "immunity_band": profile.get("immunity_band"),
            "last_checkup_day": profile.get("last_checkup_day"),
        }

        events = profile.get("recent_events", [])
        if isinstance(events, deque):
            events_iterable = list(events)
        else:
            events_iterable = list(events)
        snapshot["recent_events"] = [deepcopy(evt) for evt in events_iterable[-getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10):]]

        condition_history = profile.get("condition_history", [])
        snapshot["condition_history"] = [deepcopy(evt) for evt in condition_history[-12:]]
        snapshot["chronic_conditions"] = [deepcopy(entry) for entry in profile.get("chronic_conditions", [])]
        snapshot["active_conditions"] = [deepcopy(entry) for entry in profile.get("active_conditions", [])]

        return snapshot

    def to_dict(self) -> Dict[str, Any]:
        return self.get_health_snapshot()

    def get_health_summary(self) -> Dict[str, Any]:
        """Returns a simplified health summary for UI purposes."""
        profile = getattr(self, "health_profile", {})
        return {
            "vitality": round(float(profile.get("vitality", 0.0)), 1),
            "is_sick": self.is_sick,
            "is_injured": self.is_injured,
        }

    def record_health_event(
        self,
        world: Optional['World'],
        event_type: str,
        summary: str,
        *,
        severity: Optional[float] = None,
        delta: Optional[float] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        profile = getattr(self, "health_profile", None)
        if profile is None:
            return {}

        event_day = None
        if world and world.game_time:
            event_day = world.game_time.current_day

        record = {
            "day": event_day,
            "type": event_type,
            "summary": summary,
        }
        if severity is not None:
            record["severity"] = round(float(severity), 2)
        if delta is not None:
            record["delta"] = round(float(delta), 2)
        if tags:
            record["tags"] = [str(tag) for tag in tags if tag]

        significance = 1
        if event_type in {"fell_ill", "injured", "recovered"}:
            significance = 2

        self.character.add_memory(summary)

        life_event_logged = False
        life_event_error: Optional[str] = None
        try:
            self.character.record_life_event(
                world,
                f"health_{event_type}",
                summary,
                tags=["health"] + list(record.get("tags", [])),
                significance=significance,
            )
            life_event_logged = True
        except Exception as exc:  # noqa: BLE001
            life_event_error = f"{exc.__class__.__name__}: {exc}"
            if world and hasattr(world, "add_event_log_message"):
                world.add_event_log_message(
                    f"Failed to log health life event '{event_type}' for {self.character.name}: {life_event_error}"
                )

        record["life_event_logged"] = life_event_logged
        if life_event_error:
            record["life_event_error"] = life_event_error

        events_deque = profile.setdefault(
            "recent_events",
            deque(maxlen=getattr(config, "HEALTH_RECENT_EVENT_LIMIT", 10)),
        )
        events_deque.append(record)

        history = profile.setdefault("condition_history", [])
        history.append(dict(record))
        if len(history) > 48:
            del history[:-48]

        return dict(record)

    def evaluate_daily_health(self, world: Optional['World']) -> List[Dict[str, Any]]:
        profile = getattr(self, "health_profile", None)
        if profile is None:
            return []

        events: List[Dict[str, Any]] = []
        need_thresholds = getattr(config, "HEALTH_NEED_THRESHOLDS", {})
        need_margin = getattr(config, "HEALTH_NEED_RECOVERY_MARGIN", 15)
        vitality_weights = getattr(config, "HEALTH_VITALITY_NEED_WEIGHTS", {})
        stress_need_weight = getattr(config, "HEALTH_STRESS_NEED_WEIGHT", 0.1)
        stress_recovery = getattr(config, "HEALTH_STRESS_RECOVERY_RATE", 0.05)
        vitality_recovery_bonus = getattr(config, "HEALTH_VITALITY_RECOVERY_BONUS", 2.0)

        vitality = float(profile.get("vitality", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_vitality", 70)))
        stress = float(profile.get("stress", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_stress", 0.2)))
        immunity = float(profile.get("immune_resilience", getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_immunity", 0.6)))

        vitality_delta = 0.0
        stress_delta = 0.0

        for need, threshold in need_thresholds.items():
            current_value = self.character.needs.get(need, threshold)
            if current_value < threshold:
                deficit = (threshold - current_value) / 100.0
                vitality_delta -= deficit * vitality_weights.get(need, 5.0)
                stress_delta += deficit * stress_need_weight
            elif current_value >= threshold + need_margin:
                recovery_factor = (current_value - threshold) / 100.0
                vitality_delta += recovery_factor * vitality_recovery_bonus
                stress_delta -= stress_recovery

        if self.is_sick and self.sickness_severity > 0:
            vitality_delta -= 1.0 + 0.18 * float(self.sickness_severity)
            stress_delta += 0.04 * float(self.sickness_severity)
        if self.is_injured and self.injury_severity > 0:
            vitality_delta -= 0.8 + 0.12 * float(self.injury_severity)
            stress_delta += 0.035 * float(self.injury_severity)

        vitality = max(
            getattr(config, "HEALTH_VITALITY_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_VITALITY_CEILING", 100.0),
                vitality + vitality_delta,
            ),
        )
        stress = max(
            getattr(config, "HEALTH_STRESS_FLOOR", 0.0),
            min(
                getattr(config, "HEALTH_STRESS_CEILING", 1.0),
                stress + stress_delta,
            ),
        )

        immunity += (vitality - getattr(config, "HEALTH_PROFILE_DEFAULTS", {}).get("base_vitality", 70)) / 100.0 * getattr(config, "HEALTH_IMMUNITY_VITALITY_WEIGHT", 0.32)
        immunity -= stress * getattr(config, "HEALTH_IMMUNITY_STRESS_WEIGHT", 0.45)
        if not self.is_sick and not self.is_injured and vitality_delta > 0:
            immunity += 0.02
        immunity = max(
            getattr(config, "HEALTH_IMMUNITY_FLOOR", 0.05),
            min(
                getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                immunity,
            ),
        )

        profile["vitality"] = vitality
        profile["stress"] = stress
        profile["immune_resilience"] = immunity
        profile["immunity_band"] = self._classify_immunity(immunity)

        if world and world.game_time:
            profile["last_evaluated_day"] = world.game_time.current_day

        previous_band = profile.get("vitality_band")
        new_band = self._classify_vitality(vitality)
        if previous_band and new_band != previous_band:
            change = vitality - profile.get("previous_vitality", vitality)
            events.append(
                self.record_health_event(
                    world,
                    "vitality_shift",
                    f"Vitality is now {new_band} ({vitality:.0f}).",
                    delta=change,
                    tags=["vitality"],
                )
            )
        profile["vitality_band"] = new_band
        profile["previous_vitality"] = vitality

        previous_stress_band = profile.get("stress_band")
        new_stress_band = self._classify_stress(stress)
        if previous_stress_band and new_stress_band != previous_stress_band:
            events.append(
                self.record_health_event(
                    world,
                    "stress_shift",
                    f"Stress level is now {new_stress_band} ({stress:.2f}).",
                    severity=stress,
                    tags=["stress"],
                )
            )
        profile["stress_band"] = new_stress_band

        sickness_model = getattr(config, "HEALTH_SICKNESS_MODEL", {})
        injury_model = getattr(config, "HEALTH_INJURY_MODEL", {})

        # Sickness progression or onset
        if not self.is_sick:
            exposure_bonus = 0.0
            if world:
                for other in world.get_nearby_characters(self.character, radius=sickness_model.get("exposure_radius", 1)):
                    if getattr(other, "is_sick", False):
                        exposure_bonus += sickness_model.get("exposure_bonus", 0.05)
            vitality_factor = max(0.0, (sickness_model.get("worsen_threshold", 40) - vitality) / 100.0)
            immunity_factor = max(0.0, 1.0 - immunity)
            sickness_chance = (
                sickness_model.get("base_chance", 0.01)
                + vitality_factor * sickness_model.get("vitality_weight", 0.2)
                + immunity_factor * sickness_model.get("immunity_weight", 0.3)
                + exposure_bonus
            )
            sickness_chance = min(0.95, max(0.0, sickness_chance))
            if random.random() < sickness_chance:
                severity_range = sickness_model.get("severity_range", (1.0, 3.0))
                severity = max(0.5, random.uniform(*severity_range))
                self.is_sick = True
                self.sickness_severity = round(max(float(self.sickness_severity), severity), 1)
                event = self.record_health_event(
                    world,
                    "fell_ill",
                    f"Fell ill (severity {self.sickness_severity:.1f}).",
                    severity=self.sickness_severity,
                    tags=["illness"],
                )
                events.append(event)
                if world:
                    world.add_event_log_message(f"{self.character.name} has fallen ill (severity {self.sickness_severity:.1f}).")
                    world.add_notable_event(
                        "CharacterSickness",
                        {
                            "summary": f"{self.character.name} has fallen ill.",
                            "character": self.character.name,
                            "severity": self.sickness_severity,
                        },
                    )
                    if world.game_time:
                        new_rumor = Rumor(
                            subject_char_id=self.character.name,
                            content_key="has_fallen_ill_negative",
                            initial_strength=config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT,
                            creation_day=world.game_time.current_day,
                            is_positive=False,
                            original_source_char_id=self.character.name,
                        )
                        world.add_rumor(new_rumor)
                        self.character.known_rumor_ids.add(new_rumor.rumor_id)
        else:
            worsen_threshold = sickness_model.get("worsen_threshold", 40)
            worsen_chance = sickness_model.get("worsen_chance", 0.2)
            if vitality < worsen_threshold and random.random() < worsen_chance:
                increase = random.choice([0.5, 1.0])
                self.sickness_severity = round(min(10.0, self.sickness_severity + increase), 1)
                events.append(
                    self.record_health_event(
                        world,
                        "sickness_worsened",
                        f"Illness worsened to severity {self.sickness_severity:.1f}.",
                        severity=self.sickness_severity,
                        tags=["illness", "worsened"],
                    )
                )
            else:
                recovery = sickness_model.get("recovery_rate", 0.8)
                if vitality >= sickness_model.get("recovery_vitality", 70):
                    recovery += 0.6
                recovery += max(0.0, immunity - 0.55) * sickness_model.get("recovery_immunity_bonus", 0.05) * 5
                previous_severity = self.sickness_severity
                self.sickness_severity = round(max(0.0, self.sickness_severity - recovery), 1)
                if self.sickness_severity <= 0:
                    self.is_sick = False
                    self.sickness_severity = 0
                    events.append(
                        self.record_health_event(
                            world,
                            "recovered",
                            "Recovered from illness.",
                            tags=["illness", "recovery"],
                        )
                    )
                    immunity = min(
                        getattr(config, "HEALTH_IMMUNITY_CEILING", 0.95),
                        immunity + sickness_model.get("recovery_immunity_bonus", 0.05),
                    )
                    profile["immune_resilience"] = immunity
                    profile["immunity_band"] = self._classify_immunity(immunity)
                    if world:
                        world.add_event_log_message(f"{self.character.name} has recovered from illness.")
                elif previous_severity - self.sickness_severity >= 1.5:
                    events.append(
                        self.record_health_event(
                            world,
                            "sickness_improved",
                            f"Illness eased to severity {self.sickness_severity:.1f}.",
                            severity=self.sickness_severity,
                            tags=["illness", "improving"],
                        )
                    )

        # Injury progression or onset
        if not self.is_injured:
            job_title = self.character.job.title if self.character.job else "Unemployed"
            job_modifier = injury_model.get("job_risk", {}).get(job_title, 0.0)
            vitality_penalty = max(0.0, (injury_model.get("worsen_threshold", 45) - vitality) / 100.0) * injury_model.get("vitality_weight", 0.01)
            injury_chance = min(0.9, max(0.0, injury_model.get("base_chance", 0.0015) + job_modifier + vitality_penalty))
            if random.random() < injury_chance:
                severity_range = injury_model.get("severity_range", (1.0, 4.0))
                injury_severity = max(0.5, random.uniform(*severity_range))
                self.is_injured = True
                self.injury_severity = round(max(float(self.injury_severity), injury_severity), 1)
                event = self.record_health_event(
                    world,
                    "injured",
                    f"Sustained an injury (severity {self.injury_severity:.1f}).",
                    severity=self.injury_severity,
                    tags=["injury"],
                )
                events.append(event)
                if world:
                    world.add_event_log_message(f"{self.character.name} has been injured (severity {self.injury_severity:.1f}).")
                    world.add_notable_event(
                        "CharacterInjury",
                        {
                            "summary": f"{self.character.name} has been injured.",
                            "character": self.character.name,
                            "severity": self.injury_severity,
                        },
                    )
                    if world.game_time:
                        new_rumor = Rumor(
                            subject_char_id=self.character.name,
                            content_key="has_been_injured_negative",
                            initial_strength=config.RUMOR_INITIAL_STRENGTH_SMALL_EVENT,
                            creation_day=world.game_time.current_day,
                            is_positive=False,
                            original_source_char_id=self.character.name,
                        )
                        world.add_rumor(new_rumor)
                        self.character.known_rumor_ids.add(new_rumor.rumor_id)
        else:
            worsen_threshold = injury_model.get("worsen_threshold", 45)
            worsen_chance = injury_model.get("worsen_chance", 0.15)
            if vitality < worsen_threshold and random.random() < worsen_chance:
                increase = random.choice([0.5, 1.0])
                self.injury_severity = round(min(10.0, self.injury_severity + increase), 1)
                events.append(
                    self.record_health_event(
                        world,
                        "injury_worsened",
                        f"Injury worsened to severity {self.injury_severity:.1f}.",
                        severity=self.injury_severity,
                        tags=["injury", "worsened"],
                    )
                )
            else:
                recovery = injury_model.get("recovery_rate", 0.7)
                if vitality >= injury_model.get("recovery_vitality", 65):
                    recovery += 0.4
                previous_severity = self.injury_severity
                self.injury_severity = round(max(0.0, self.injury_severity - recovery), 1)
                if self.injury_severity <= 0:
                    self.is_injured = False
                    self.injury_severity = 0
                    events.append(
                        self.record_health_event(
                            world,
                            "injury_healed",
                            "Recovered from injury.",
                            tags=["injury", "recovery"],
                        )
                    )
                elif previous_severity - self.injury_severity >= 1.5:
                    events.append(
                        self.record_health_event(
                            world,
                            "injury_improved",
                            f"Injury eased to severity {self.injury_severity:.1f}.",
                            severity=self.injury_severity,
                            tags=["injury", "improving"],
                        )
                    )

        active_conditions: List[Dict[str, Any]] = []
        if self.is_sick and self.sickness_severity > 0:
            active_conditions.append({
                "type": "illness",
                "severity": self.sickness_severity,
                "status": "active",
            })
        if self.is_injured and self.injury_severity > 0:
            active_conditions.append({
                "type": "injury",
                "severity": self.injury_severity,
                "status": "active",
            })
        chronic_conditions = profile.get("chronic_conditions", [])
        profile["active_conditions"] = active_conditions + [deepcopy(cond) for cond in chronic_conditions]

        if (self.is_sick or self.is_injured) and world and world.game_time:
            note_day = profile.get("last_checkup_note_day")
            if note_day is None or world.game_time.current_day - note_day >= 3:
                events.append(
                    self.record_health_event(
                        world,
                        "checkup_due",
                        "Needs a clinic follow-up soon.",
                        tags=["medical"],
                    )
                )
                profile["last_checkup_note_day"] = world.game_time.current_day

        return [event for event in events if event]
