import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Using dataclasses for clear, structured data containers

@dataclass
class CharacterData:
    name: str
    personality: str
    traits: List[str]
    skills: Dict[str, int]
    job: Optional[str] = "Unemployed"
    rank: Optional[str] = "Worker"
    x: Optional[int] = None
    y: Optional[int] = None
    needs: Dict[str, int] = field(default_factory=dict)
    family_members: List[str] = field(default_factory=list)

@dataclass
class StockpileData:
    name: str
    x: int
    y: int
    width: int
    height: int
    allowed_resources: List[str]
    initial_inventory: Dict[str, int] = field(default_factory=dict)
    total_capacity: int = 100

@dataclass
class BuildingData:
    structure_type: str
    location: List[int] # Expecting [x, y]
    display_name: Optional[str] = None # Optional, can be derived from type

@dataclass
class Scenario:
    name: str
    description: str
    starting_characters: List[CharacterData] = field(default_factory=list)
    starting_stockpiles: List[StockpileData] = field(default_factory=list)
    starting_buildings: List[BuildingData] = field(default_factory=list)
    # Could add starting date, season, etc. here later

class ScenarioLoader:
    """Loads scenario data from a JSON file."""

    @staticmethod
    def load_from_file(filepath: str) -> Scenario:
        """
        Reads a JSON file and parses it into a Scenario object.
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Reconstruct the data into our dataclasses for type safety and clarity
            characters = [CharacterData(**char_data) for char_data in data.get("starting_characters", [])]
            stockpiles = [StockpileData(**sp_data) for sp_data in data.get("starting_stockpiles", [])]
            buildings = [BuildingData(**b_data) for b_data in data.get("starting_buildings", [])]

            return Scenario(
                name=data.get("name", "Unnamed Scenario"),
                description=data.get("description", ""),
                starting_characters=characters,
                starting_stockpiles=stockpiles,
                starting_buildings=buildings
            )
        except FileNotFoundError:
            print(f"Error: Scenario file not found at {filepath}")
            raise
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {filepath}")
            raise
        except TypeError as e:
            # This can happen if the JSON structure doesn't match the dataclass fields
            print(f"Error: Mismatch between JSON structure and Scenario dataclasses in {filepath}. Details: {e}")
            raise
