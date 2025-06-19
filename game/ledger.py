# game/ledger.py
from typing import Dict, Optional, Tuple, List # Added List

class Ledger:
    def __init__(self):
        # Structure: {resource_name: {stockpile_name: count}}
        self.records: Dict[str, Dict[str, int]] = {}
        # Structure: {stockpile_name: update_timestamp_day}
        self.stockpile_last_updated_day: Dict[str, int] = {}

    def update_stockpile_record(self, stockpile_name: str,
                                stockpile_inventory: Dict[str, int],
                                current_day: int):
        # Clear previous records for this stockpile from all resource lists
        for resource_type in list(self.records.keys()): # Iterate over a copy of keys
            if stockpile_name in self.records[resource_type]:
                del self.records[resource_type][stockpile_name]
            if not self.records[resource_type]: # If no stockpiles left for this resource type
                del self.records[resource_type]

        # Add new records based on current stockpile inventory
        for resource_name, count in stockpile_inventory.items():
            if count > 0: # Only record if there's something
                if resource_name not in self.records:
                    self.records[resource_name] = {}
                self.records[resource_name][stockpile_name] = count

        self.stockpile_last_updated_day[stockpile_name] = current_day
        # print(f"Ledger: Updated {stockpile_name} on day {current_day}. Current records: {self.records}")


    def get_total_resource_count(self, resource_name: str) -> int:
        if resource_name not in self.records:
            return 0
        return sum(self.records[resource_name].values())

    def get_resource_count_in_stockpile(self, resource_name: str, stockpile_name: str) -> int:
        return self.records.get(resource_name, {}).get(stockpile_name, 0)

    def get_stockpile_last_update_day(self, stockpile_name: str) -> Optional[int]:
        return self.stockpile_last_updated_day.get(stockpile_name)

    def __str__(self):
        summary = ["Ledger Records:"]
        if not self.records and not self.stockpile_last_updated_day: # Check both as empty records might still have timestamps if all items removed
            summary.append("  No records and no stockpiles tracked.")
            return "\n".join(summary)

        # Collect all known stockpile names from timestamps to display even if currently empty
        all_tracked_stockpiles = set(self.stockpile_last_updated_day.keys())

        sorted_resources = sorted(self.records.keys())

        for resource in sorted_resources:
            summary.append(f"  Resource: {resource}")
            stockpiles_data = self.records[resource]
            sorted_stockpiles = sorted(stockpiles_data.keys())
            for sp_name in sorted_stockpiles:
                count = stockpiles_data[sp_name]
                update_day = self.stockpile_last_updated_day.get(sp_name, "N/A")
                summary.append(f"    - {sp_name}: {count} (Updated Day: {update_day})")
            # Note stockpiles that allow this resource but currently have 0 (not in records[resource])
            # This part can be complex; for now, the __str__ focuses on what *is* recorded.

        # List stockpiles that are tracked (have timestamps) but currently hold no recorded resources
        empty_but_tracked_stockpiles = []
        for sp_name in all_tracked_stockpiles:
            found_in_records = False
            for resource_data in self.records.values():
                if sp_name in resource_data:
                    found_in_records = True
                    break
            if not found_in_records:
                update_day = self.stockpile_last_updated_day.get(sp_name, "N/A")
                empty_but_tracked_stockpiles.append(f"    - {sp_name}: EMPTY (Updated Day: {update_day})")

        if empty_but_tracked_stockpiles:
            if not self.records: # If all are empty
                 summary.append("  All tracked stockpiles are currently empty.")
            else: # Some have items, some are empty
                 summary.append("  Other Tracked Stockpiles (currently empty of recorded resources):")
            for line in sorted(empty_but_tracked_stockpiles):
                summary.append(line)

        return "\n".join(summary)
