from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .building import Workplace


class Job:
    """Represents a character's job."""

    def __init__(self, title: str, workplace: "Workplace", salary: int):
        self.title = title
        self.workplace = workplace
        self.salary = salary

    def to_dict(self):
        return {
            "title": self.title,
            "workplace": self.workplace.display_name if self.workplace else "Unknown",
            "salary": self.salary,
        }
