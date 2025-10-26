
from typing import Optional, Tuple, Dict, Any
from . import config

class Crime:
    def __init__(self, world):
        self.world = world
        self.pending_crimes = []
        self.active_crimes = {}
        self.crime_history = []
        self._last_crime_id = 0
        self.cases = {}
        self._last_case_id = 0
        self._last_interview_id = 0
        self._interview_to_case_map = {}

    @property
    def pending_interviews(self):
        interviews = []
        for case in self.cases.values():
            if case.get("requires_interviews"):
                for interview_id, status in case.get("interview_plan", {}).items():
                    if status == "pending":
                        interviews.append({"id": interview_id, "case_id": case["case_id"], "witness": "Unknown"})
        return interviews

    def _next_crime_id(self) -> int:
        self._last_crime_id += 1
        return self._last_crime_id

    def _next_case_id(self) -> str:
        self._last_case_id += 1
        return f"case_{self._last_case_id}"

    def _next_interview_id(self) -> str:
        self._last_interview_id += 1
        return f"interview_{self._last_interview_id}"

    def investigate_disturbance(self, character):
        goal_params = character.current_goal.parameters if character.current_goal else {}
        crime_id = goal_params.get("crime_id") or character.active_crime_assignment
        if not crime_id:
            character.active_crime_assignment = None
            character.crime_investigation_focus = None
            character.current_goal = character.get_default_goal()
            return

        incident = self.world.get_crime_by_id(crime_id) if hasattr(self.world, "get_crime_by_id") else None
        if not incident or incident.get("status") == "resolved":
            character.active_crime_assignment = None
            character.crime_investigation_focus = None
            character.current_goal = character.get_default_goal()
            return

        suspect_name = incident.get("suspect")
        suspect = self.world.get_character_by_name(suspect_name) if suspect_name else None
        location_data = incident.get("location") or goal_params.get("location")
        location_coords: Optional[Tuple[int, int]] = None
        if isinstance(location_data, dict):
            coords = location_data.get("coords")
            if coords:
                location_coords = (coords[0], coords[1])
        if suspect:
            location_coords = (suspect.x, suspect.y)

        if location_coords and (character.x, character.y) != location_coords:
            character.move_towards(location_coords[0], location_coords[1], self.world)
            if suspect:
                character.add_memory(f"Closing in on {suspect_name} regarding case {crime_id}.")
            else:
                character.add_memory(
                    f"Investigating disturbance near {incident.get('location_label', 'the reported site')} for case {crime_id}."
                )
            return

        security_skill = character.skills.get("Security", {}).get("level", 0)
        success_chance = min(0.95, 0.45 + 0.08 * security_skill + (0.05 if suspect else 0.0))
        investigation_success = random.random() < success_chance

        if investigation_success and suspect:
            recovered_amount = 0
            stolen_resource = incident.get("resource")
            if stolen_resource:
                available = suspect.inventory.get(stolen_resource, 0)
                if available > 0:
                    recovered_amount = min(available, incident.get("amount", available))
                    suspect.inventory[stolen_resource] = available - recovered_amount
                    if suspect.inventory[stolen_resource] <= 0:
                        suspect.inventory.pop(stolen_resource, None)
                    target_stockpile = None
                    if isinstance(location_data, dict):
                        target_stockpile = self.world.get_stockpile_by_name(location_data.get("stockpile"))
                    if target_stockpile and target_stockpile.is_allowed(stolen_resource):
                        added, actual = target_stockpile.add_item(stolen_resource, recovered_amount)
                        if added:
                            recovered_amount = actual
                            if self.world.game_time:
                                self.world.economy.ledger.update_stockpile_record(
                                    target_stockpile.name,
                                    target_stockpile.inventory,
                                    self.world.game_time.current_day,
                                )
                    if recovered_amount > 0 and (not target_stockpile or not target_stockpile.is_allowed(stolen_resource)):
                        character.inventory[stolen_resource] = character.inventory.get(stolen_resource, 0) + recovered_amount

            suspect.update_reputation(-5, f"Apprehended for theft by {character.name}", self.world)
            suspect.update_mood_score(
                getattr(config, "MOOD_CHANGE_CAUGHT_STEALING", -15), "Apprehended for theft"
            )
            suspect.add_memory(f"Apprehended by {character.name} for theft case {crime_id}.")
            character.add_memory(f"Detained {suspect_name} and resolved case {crime_id}.")
            notes = (
                f"Suspect detained; recovered {recovered_amount} {incident.get('resource', 'goods')}"
                if recovered_amount
                else "Suspect detained"
            )
            evidence_strength = 0.6 + 0.1 * min(4, security_skill)
            if recovered_amount:
                evidence_strength += 0.15
            evidence_strength = min(1.0, evidence_strength)
            if hasattr(self.world, "resolve_crime_outcome"):
                self.world.resolve_crime_outcome(
                    crime_id,
                    "apprehended",
                    character.name,
                    caught=True,
                    notes=notes,
                    evidence_strength=evidence_strength,
                )
        elif investigation_success:
            character.add_memory(f"Secured the scene of case {crime_id}; suspect not present.")
            if hasattr(self.world, "resolve_crime_outcome"):
                self.world.resolve_crime_outcome(
                    crime_id,
                    "scene_secured",
                    character.name,
                    caught=False,
                    notes="Scene secured",
                    requeue=False,
                    evidence_strength=min(0.6, 0.35 + 0.05 * security_skill),
                )
        else:
            character.add_memory(f"Lost the trail for case {crime_id}; will revisit once new leads appear.")
            if hasattr(self.world, "resolve_crime_outcome"):
                self.world.resolve_crime_outcome(
                    crime_id,
                    "lost_trail",
                    character.name,
                    caught=False,
                    notes="Lead went cold",
                    requeue=True,
                    evidence_strength=0.1,
                )

        character.active_crime_assignment = None
        character.crime_investigation_focus = None
        character.current_goal = character.get_default_goal()

    def schedule_trial_for_crime(self, crime: dict, investigator: str, evidence_strength: float) -> dict:
        case_id = self._next_case_id()
        interview_id = self._next_interview_id()
        self._interview_to_case_map[interview_id] = case_id

        new_case = {
            "case_id": case_id,
            "evidence_strength": evidence_strength,
            "law_id": "law_1",
            "requires_interviews": True,
            "interview_plan": {interview_id: "pending"},
            "interview_statements": []
        }
        self.cases[case_id] = new_case
        return new_case

    def get_case_by_id(self, case_id: str) -> Optional[dict]:
        return self.cases.get(case_id)

    def _record_crime_history(self, incident: Dict[str, Any]) -> None:
        self.crime_history.append(incident)

    def get_case_by_assignment_id(self, assignment_id: str) -> Optional[dict]:
        case_id = self._interview_to_case_map.get(assignment_id)
        if case_id:
            return self.get_case_by_id(case_id)
        return None

    def assign_investigative_interview(self, investigator_name: str) -> Optional[dict]:
        for case in self.cases.values():
            if case.get("requires_interviews"):
                for interview_id, status in case.get("interview_plan", {}).items():
                    if status == "pending":
                        return {"id": interview_id}
        return None

    def record_interview_result(self, interview_id: str, investigator_name: str, evidence_boost: float, notes: str) -> bool:
        case = self.get_case_by_assignment_id(interview_id)
        if case:
            case["evidence_strength"] += evidence_boost
            case.setdefault("interview_statements", []).append(notes)
            if interview_id in case.get("interview_plan", {}):
                case["interview_plan"][interview_id] = "completed"
            self.world.add_event_log_message(f"Interview statement added to case {case['case_id']}: {notes}")
            return True
        return False

    def process_crime_daily(self):
        pass
