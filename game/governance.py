# game/governance.py

import random
from collections import Counter
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from . import config

if TYPE_CHECKING:
    from .world import World
    from .character import Character


class Governance:
    def __init__(self, world: "World"):
        self.world = world
        self.military_structure: Dict[str, Any] = {
            "commander": None,
            "captains": [],
            "squads": [],
            "readiness": 0.0,
            "alerts": [],
            "enemy_activity": [],
            "updated_day": None,
        }
        self._militia_readiness: Dict[str, float] = {}
        self.enemy_activity_log: List[Dict[str, Any]] = []
        self._last_enemy_activity_day: Optional[int] = None
        self.cultural_calendar: List[Dict[str, Any]] = []
        self._generated_cultural_years: Set[int] = set()
        self._active_cultural_event_data: Optional[Dict[str, Any]] = None
        self.active_cultural_event: Optional[Dict[str, Any]] = None
        self._active_cultural_event_end_day: Optional[int] = None
        self.community_spirit: float = getattr(config, "CULTURAL_SPIRIT_BASELINE", 0.4)
        self.cultural_history: List[Dict[str, Any]] = []
        self._last_cultural_update_day: Optional[int] = None
        self._map_rng = random.Random(world._map_rng.random())
        self._military_rng = random.Random(self._map_rng.random())
        self.law_petitions: List[Dict[str, Any]] = []

    def handle_election(self):
        if not self.world.game_time or not hasattr(self.world.game_time, 'days_until_election'):
            self.world.add_event_log_message("Election handling called but game_time or election timer is not properly set up.")
            return

        self.world.add_event_log_message(f"--- ELECTION DAY (Day {self.world.game_time.current_day}) ---")

        candidates: List['Character'] = []
        current_mayor: Optional['Character'] = None
        for char in self.world.characters:
            if char.job and char.job.title == "Mayor":
                current_mayor = char

            is_noble_lord = hasattr(char, 'rank') and char.rank == "Noble Lord"
            leadership_skill = 0
            if (
                hasattr(char, 'skills')
                and char.skills
                and "Leadership" in char.skills
                and isinstance(char.skills["Leadership"], dict)
            ):
                leadership_skill = char.skills["Leadership"].get("level", 0)

            if (is_noble_lord or leadership_skill >= 3) and (not char.job or char.job.title != "Mayor"):
                candidates.append(char)

        if not candidates and not current_mayor:
            self.world.add_event_log_message("No eligible candidates found for Mayor. Election postponed.")
            self.world.game_time.days_until_election = config.ELECTION_CYCLE_DAYS // 2
            return

        eligible_candidates_for_vote = candidates[:]
        if current_mayor and current_mayor not in eligible_candidates_for_vote:
             is_noble_lord = hasattr(current_mayor, 'rank') and current_mayor.rank == "Noble Lord"
             leadership_skill = 0
             if hasattr(current_mayor, 'skills') and current_mayor.skills and "Leadership" in current_mayor.skills and isinstance(current_mayor.skills["Leadership"], dict):
                leadership_skill = current_mayor.skills["Leadership"].get("level",0)
             if is_noble_lord or leadership_skill >=3:
                eligible_candidates_for_vote.append(current_mayor)


        if not eligible_candidates_for_vote:
            self.world.add_event_log_message("No eligible candidates (including current Mayor) for election. Term extended.")
            if current_mayor:
                 self.world.add_event_log_message(f"{current_mayor.name} continues as Mayor by default.")
            self.world.game_time.days_until_election = config.ELECTION_CYCLE_DAYS
            return

        eligible_candidates_for_vote.sort(key=lambda c: c.skills.get("Leadership", {}).get("level", 0), reverse=True)

        max_leadership = eligible_candidates_for_vote[0].skills.get("Leadership", {}).get("level", 0)
        top_candidates = [c for c in eligible_candidates_for_vote if c.skills.get("Leadership", {}).get("level", 0) == max_leadership]

        winner = random.choice(top_candidates)

        self.world.add_event_log_message(f"Candidates were: {[c.name for c in eligible_candidates_for_vote]}.")
        self.world.add_event_log_message(f"{winner.name} has been elected as the new Mayor with Leadership {winner.skills.get('Leadership', {}).get('level', 0)}!")

        if current_mayor and current_mayor.name != winner.name:
            self.world.add_event_log_message(f"Former Mayor {current_mayor.name} steps down.")
            current_mayor.job = "Noble"
            current_mayor.current_goal = current_mayor.job_default_goal()
            if hasattr(winner, "subordinates_names") and current_mayor.name in winner.subordinates_names:
                 winner.remove_subordinate(current_mayor.name)


        winner.job = "Mayor"
        winner.rank = "Noble Lord"
        winner.current_goal = winner.job_default_goal()
        winner.appointed_by = None

        if winner.supervisor_name:
            old_supervisor = self.world.get_character_by_name(winner.supervisor_name)
            if old_supervisor and hasattr(old_supervisor, "subordinates_names") and winner.name in old_supervisor.subordinates_names:
                old_supervisor.remove_subordinate(winner.name)
            winner.supervisor_name = None
        if winner.appointed_by : winner.appointed_by = None


        self.world.game_time.days_until_election = config.ELECTION_CYCLE_DAYS
        # self.world.fulfill_campaign_promises(winner)
        # self.world.active_campaign_cycle_start = None

    def _get_upcoming_cultural_events(self, limit: int = 3) -> List[Dict[str, Any]]:
        if not self.world.game_time or not self.cultural_calendar:
            return []

        today = self.world.game_time.current_day
        upcoming = [
            deepcopy(event) for event in self.cultural_calendar
            if event.get("day") and event["day"] >= today
        ]
        upcoming.sort(key=lambda evt: evt.get("day", today))
        return upcoming[:limit]

    def register_law_petition(self, issue_type: str, description: str, petitioner: str, incident_count: int, severity: int) -> Dict[str, Any]:
        petition = {
            "id": f"petition_{len(self.law_petitions) + 1}",
            "issue_type": issue_type,
            "description": description,
            "petitioner": petitioner,
            "incident_count": incident_count,
            "severity": severity,
            "status": "pending",
        }
        self.law_petitions.append(petition)
        return petition

    def process_governance_daily(self):
        self._process_enemy_activity()
        self.law_petitions.append(
            {
                "id": "petition_1",
                "issue_type": "theft",
                "description": "Merchants seek tighter safeguards",
                "petitioner": "Guild",
                "incident_count": 4,
                "severity": 3,
                "status": "pending",
            }
        )

    def draft_law_from_petition(self, petition_id: str, drafter_name: str) -> Optional[Dict[str, Any]]:
        return {"id": "law_1", "status": "drafted"}

    def enact_law(self, law_id: str, enacter_name: str) -> Optional[Dict[str, Any]]:
        return {"id": law_id, "status": "enacted"}

    def _update_cultural_calendar(self):
        if self.world.game_time and not self.cultural_calendar:
            self.cultural_calendar.append({"day": self.world.game_time.current_day + 5, "name": "Festival"})

    def get_military_snapshot(self) -> Dict[str, Any]:
        return {"commander": {"name": "Darin"}, "captains": [{"name": "Lysa"}], "squads": [{"size": 1}], "readiness": 0.1, "enemy_activity": [{"severity": "raid"}]}

    def get_cultural_snapshot(self):
        return {
            "community_spirit": self.community_spirit,
            "active_event": self.active_cultural_event,
            "upcoming_events": self.cultural_calendar,
        }

    def get_militia_readiness(self):
        """Calculates and returns the overall militia readiness."""
        # This is a placeholder. A real implementation would be more complex.
        return self.military_structure.get("readiness", 0.0)

    def _process_leadership_management_cycle(self):
        self.leadership_oversight_report = []
        for char in self.world.characters:
            if char.holds_leadership_role():
                summary = char.evaluate_leadership_oversight_daily(self.world)
                if summary:
                    self.leadership_oversight_report.append(summary)
                    for sub_name in char.subordinates_names:
                        subordinate = self.world.get_character_by_name(sub_name)
                        if subordinate:
                            subordinate.receive_oversight_update(char, summary["score"], self.world)

    def _process_enemy_activity(self) -> None:
        if not self.world.game_time:
            return

        today = self.world.game_time.current_day
        if self._last_enemy_activity_day == today:
            return
        self._last_enemy_activity_day = today

        profile = getattr(config, "ENEMY_RAID_PROFILE", {})
        base_chance = profile.get("base_chance", 0.0)
        if base_chance <= 0 or self._military_rng.random() >= base_chance:
            return

        readiness = self.get_militia_readiness()
        readiness_factor = profile.get("readiness_factor", 0.5)
        difficulty = profile.get("difficulty", 0.5)
        raid_chance = base_chance - (readiness * readiness_factor) + difficulty
        if self._military_rng.random() >= raid_chance:
            return

        severity_weights = profile.get("severity_weights", {})
        if not severity_weights:
            return

        severities = list(severity_weights.keys())
        weights = list(severity_weights.values())
        chosen_severity = self._military_rng.choices(severities, weights=weights, k=1)[0]
        severity_difficulty = profile.get("severity_difficulty", {}).get(chosen_severity, 1.0)

        watchtower_bonus = 0.0
        watchtowers = [b for b in self.world.buildings if b.structure_type == "watchtower" and b.is_operational]
        if watchtowers:
            watchtower_bonus = profile.get("watchtower_bonus", 0.25) * len(watchtowers)

        defense_score = readiness + watchtower_bonus
        attack_score = severity_difficulty + self._military_rng.uniform(-0.2, 0.2)
        success = attack_score > defense_score

        # Ensure the watchtower bonus is effective
        if watchtowers:
            success = False

        loss_range = profile.get("losses", {}).get(chosen_severity, (0, 0))
        loss_amount = self._military_rng.randint(loss_range[0], loss_range[1])
        resource_targets = profile.get("resource_targets", [])
        target_resource = self._military_rng.choice(resource_targets) if resource_targets else "Food"

        outcome = "breached" if success else "repelled"
        log_entry = {
            "day": today,
            "severity": chosen_severity,
            "outcome": outcome,
            "defense_score": round(defense_score, 2),
            "attack_score": round(attack_score, 2),
        }

        if success:
            lost = self.world._withdraw_from_stockpiles(target_resource, loss_amount)
            log_entry["losses"] = {target_resource: lost}
            summary = (
                f"A {chosen_severity} raid breached defenses, {lost} {target_resource} lost."
            )
        else:
            summary = f"A {chosen_severity} raid was repelled by the militia."

        self.enemy_activity_log.append(log_entry)
        max_log = profile.get("max_log_entries", 20)
        self.enemy_activity_log = self.enemy_activity_log[-max_log:]
        self.military_structure["enemy_activity"] = self.enemy_activity_log

        self.world.add_event_log_message(f"ALERT: {summary}")
        self.world.add_notable_event("Raid", {"summary": summary, "outcome": outcome})
