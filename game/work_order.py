# game/work_order.py
from typing import Dict, Optional, Any
import uuid # For unique IDs

class WorkOrder:
    def __init__(self, order_type: str, details: Dict[str, Any],
                 priority: int = 1, creation_day: int = 0):
        self.order_id: str = f"wo_{uuid.uuid4().hex[:8]}" # Unique ID
        self.order_type: str = order_type  # e.g., "CraftItem", "BuildStructure"
        self.details: Dict[str, Any] = details
        # For "CraftItem": {"item_name": "Wooden Chair", "quantity": 5, "required_resources": {"Wood": 25}}
        # For "BuildStructure": {"structure_type": "small_workshop", "location": (x,y), "required_resources": {...}, "size": (w,h), "build_time": B_T}

        self.priority: int = priority
        self.status: str = "Pending"  # Pending, Approved, Denied, InProgress, Completed, Cancelled
        self.creation_day: int = creation_day

        self.approved_by: Optional[str] = None
        self.approval_day: Optional[int] = None
        self.denied_by: Optional[str] = None
        self.denial_reason: Optional[str] = None
        self.assigned_to: Optional[str] = None # For later when workers pick up tasks
        # self.completion_day: Optional[int] = None # For tracking when it's done

    def __str__(self):
        detail_summary = self.details.get('item_name', self.details.get('structure_type', 'Unknown Detail'))
        if 'quantity' in self.details: detail_summary += f" (Qty: {self.details['quantity']})"

        return (f"WorkOrder(ID: {self.order_id}, Type: {self.order_type}, Detail: {detail_summary}, "
                f"Status: {self.status}, Prio: {self.priority}, Created: Day {self.creation_day}, "
                f"ReqRes: {self.details.get('required_resources', {})}, Assigned: {self.assigned_to})")
