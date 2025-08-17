from __future__ import annotations
import random
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from game.world import World
    from game.character import Character
    from game.time import Time

class ElectionManager:
    """
    Manages elections in the game world.
    """
    def __init__(self, world: World):
        self.world = world

    def hold_election(self):
        """
        Handles the logic for holding an election.
        """
        if not self.world.game_time or not hasattr(self.world.game_time, 'days_until_election'):
            self.world.add_event_log_message("Election handling called but game_time or election timer is not properly set up.")
            return

        self.world.add_event_log_message(f"--- ELECTION DAY (Day {self.world.game_time.current_day}) ---")

        # Identify candidates: e.g., Nobles or high Leadership
        candidates: List[Character] = []
        for char in self.world.characters:
            is_noble_lord = hasattr(char, 'rank') and char.rank == "Noble Lord"
            leadership_skill = 0
            if hasattr(char, 'skills') and char.skills and "Leadership" in char.skills and isinstance(char.skills["Leadership"], dict):
                leadership_skill = char.skills["Leadership"].get("level",0)

            if is_noble_lord or leadership_skill >= 3: # Min leadership 3 for candidacy
                if char.job != "Mayor":
                    candidates.append(char)

        current_mayor: Optional[Character] = None
        for char in self.world.characters:
            if char.job == "Mayor":
                current_mayor = char
                break

        if not candidates and not current_mayor:
            self.world.add_event_log_message("No eligible candidates found for Mayor. Election postponed.")
            self.world.game_time.days_until_election = self.world.game_time.days_until_election // 2 # Postpone for a shorter period
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
            self.world.game_time.days_until_election = self.world.game_time.ELECTION_CYCLE_DAYS
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
            if current_mayor.name in winner.subordinates_names:
                 winner.remove_subordinate(current_mayor.name)

        winner.job = "Mayor"
        winner.rank = "Noble Lord"
        winner.current_goal = winner.job_default_goal()
        winner.appointed_by = None

        if winner.supervisor_name:
            old_supervisor = self.world.get_character_by_name(winner.supervisor_name)
            if old_supervisor and winner.name in old_supervisor.subordinates_names:
                old_supervisor.remove_subordinate(winner.name)
            winner.supervisor_name = None
        if winner.appointed_by : winner.appointed_by = None

        self.world.game_time.days_until_election = self.world.game_time.ELECTION_CYCLE_DAYS
