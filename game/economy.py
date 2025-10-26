# game/economy.py
from __future__ import annotations
import math
import random
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .ledger import Ledger
from .work_order import WorkOrder
from .data import BLUEPRINTS, MARKET_PRICES, JOB_TASK_DEFINITIONS
from . import config

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class Economy:
    def __init__(self, world: World):
        self.world = world
        self.ledger: Ledger = Ledger()
        self.work_orders: List[WorkOrder] = []
        self.businesses: Dict[str, Dict[str, Any]] = {}
        self._business_counter: int = 0
        self.latest_wealth_snapshot: Dict[str, Any] = {}
        self._last_wealth_tension_day: Optional[int] = None
        self.resource_collection_directives: Dict[str, Dict[str, Any]] = {}
        self.treasury_coins: int = getattr(config, "STARTING_TREASURY_COINS", 0)
        self.pending_wages: List[Dict[str, Any]] = []
        self.todays_wages_paid: int = 0
        self.todays_wages_owed: int = 0
        self.last_daily_economic_report: Dict[str, Any] = {}
        self.today_surplus_sales: List[Dict[str, Any]] = []

        self.base_market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_prices: Dict[str, int] = MARKET_PRICES.copy()
        self.market_price_multipliers: Dict[str, float] = {
            item_name: 1.0 for item_name in self.base_market_prices.keys()
        }
        self.work_shift_definitions: Dict[str, Dict[str, Any]] = config.WORK_SHIFT_DEFINITIONS.copy()
        self.work_shift_backlog: Dict[str, float] = {
            key: 0.0 for key in self.work_shift_definitions
        }
        self.latest_workforce_report: Dict[str, Any] = {}
        self._last_workforce_update_day: Optional[int] = None
        self.work_logistics_history: List[Dict[str, Any]] = []
        self.market_location: Tuple[int, int] = (
            self.world.grid_size[0] // 2,
            self.world.grid_size[1] // 2,
        )

    def dissolve_business(self, business_id: str, reason: str):
        """Dissolves a business, removing it from the economy."""
        business = self.businesses.pop(business_id, None)
        if business:
            self.world.add_event_log_message(f"Business {business.get('name')} has been dissolved. Reason: {reason}.")

    def transfer_business_ownership(self, business_id: str, new_owner: 'Character'):
        """Transfers ownership of a business to a new character."""
        business = self.businesses.get(business_id)
        if business and new_owner:
            old_owner_name = business['owner']
            business['owner'] = new_owner.name
            new_owner.businesses_owned.append(business_id)
            old_owner = self.world.get_character_by_name(old_owner_name)
            if old_owner:
                old_owner.businesses_owned.remove(business_id)
            self.world.add_event_log_message(f"Ownership of {business.get('name')} transferred to {new_owner.name}.")

    def add_work_order(self, work_order: WorkOrder):
        if work_order not in self.work_orders:
            self.work_orders.append(work_order)

    def get_pending_work_orders(self) -> List[WorkOrder]:
        pending = [wo for wo in self.work_orders if wo.status == "Pending"]
        pending.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return pending

    def get_approved_craft_orders(self) -> List[WorkOrder]:
        approved = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "CraftItem" and wo.assigned_to is None
        ]
        approved.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved

    def get_approved_build_orders(self) -> List[WorkOrder]:
        approved_build = [
            wo for wo in self.work_orders
            if wo.status == "Approved" and wo.order_type == "BuildStructure" and wo.assigned_to is None
        ]
        approved_build.sort(key=lambda wo: (wo.priority, wo.creation_day))
        return approved_build

    def get_work_order_by_id(self, order_id: str) -> Optional[WorkOrder]:
        for wo in self.work_orders:
            if wo.order_id == order_id:
                return wo
        return None

    def get_total_resource_quantity(self, resource_name: str) -> int:
        return self.ledger.get_total_resource_count(resource_name)

    def _next_business_id(self) -> str:
        self._business_counter += 1
        return f"biz_{self._business_counter}"

    def launch_business(
        self,
        owner: 'Character',
        template: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if owner is None:
            return None

        templates = list(getattr(config, "BUSINESS_TEMPLATES", []))
        if template is None:
            if not templates:
                return None
            template = random.choice(templates)

        startup_cost = int(template.get("startup_cost", getattr(config, "BUSINESS_STARTUP_COST", 0)))
        if owner.money < startup_cost:
            return None

        owner.money -= startup_cost
        business_id = self._next_business_id()
        display_name = template.get("display_name", template.get("key", "Enterprise"))
        business_name = f"{owner.name}'s {display_name}"
        base_capital = int(template.get("base_capital", startup_cost))
        revenue_range = template.get("revenue_range") or getattr(config, "BUSINESS_DAILY_REVENUE_RANGE", (4, 9))
        business = {
            "id": business_id,
            "name": business_name,
            "owner": owner.name,
            "industry": template.get("industry", "general"),
            "capital": base_capital,
            "revenue_range": tuple(revenue_range),
            "status": "active",
            "founded_day": self.world.game_time.current_day if self.world.game_time else 0,
            "employees": [],
            "cash_reserve": 0,
            "history": [],
            "inventory": {},
        }
        self.businesses[business_id] = business

        owner.assign_business_role(business_id, "owner")
        owner.add_memory(f"Invested {startup_cost} coins to establish {business_name}.")
        owner.record_life_event(
            self.world,
            "business_founded",
            f"Founded {business_name} in the {business['industry']} trade.",
            tags=["business"],
            significance=3,
            details={"business_id": business_id, "industry": business["industry"]},
        )
        owner.update_mood_score(getattr(config, "MOOD_CHANGE_STARTED_PROJECT", 5), f"Founded {business_name}")
        owner.update_reputation(getattr(config, "BUSINESS_REPUTATION_BONUS", 0), f"Founded {business_name}", self.world)

        self.world.add_event_log_message(f"{owner.name} establishes {business_name} ({business['industry']}).")
        self.world.add_notable_event(
            "BusinessFounded",
            {
                "summary": f"{owner.name} opened {business_name}.",
                "owner": owner.name,
                "industry": business["industry"],
                "business_id": business_id,
            },
        )

        max_employees = getattr(config, "BUSINESS_MAX_EMPLOYEES", 0)
        if max_employees > 0:
            candidate_pool: List['Character'] = []
            for character in self.world.characters:
                if character.name == owner.name:
                    continue
                if getattr(character, "retired", False):
                    continue
                if business_id in getattr(character, "business_roles", {}):
                    continue
                if character.job in {"Unemployed", "Laborer", "Apprentice", None}:
                    candidate_pool.append(character)
            random.shuffle(candidate_pool)
            for candidate in candidate_pool:
                if len(business["employees"]) >= max_employees:
                    break
                business["employees"].append(candidate.name)
                candidate.assign_business_role(business_id, "employee")
                candidate.add_memory(f"Hired to work at {business_name}.")
                candidate.record_life_event(
                    self.world,
                    "business_employment",
                    f"Began working at {business_name}.",
                    tags=["business", "employment"],
                    significance=2,
                    details={"business_id": business_id, "role": "employee"},
                )

        return business

    def _handle_character_departure_from_business(
        self,
        business_id: str,
        character_name: str,
        owner_departure: bool = False,
    ) -> None:
        business = self.businesses.get(business_id)
        if not business:
            return

        if owner_departure:
            self._close_business(business, f"owner {character_name} departed")
            return

        if character_name in business.get("employees", []):
            business["employees"] = [name for name in business["employees"] if name != character_name]
            employee = self.world.get_character_by_name(character_name)
            if employee:
                employee.leave_business_role(business_id, f"Left employment at {business['name']}.")

    def _restock_business_inputs(
        self,
        business: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        inventory: Dict[str, int] = business.setdefault("inventory", {})
        restock_days = max(1, int(profile.get("restock_days", 1) or 1))
        procurement_multiplier = max(
            0.0, float(profile.get("procurement_cost_multiplier", 0.0) or 0.0)
        )

        restocked: Dict[str, int] = {}
        shortages: Dict[str, int] = {}
        total_cost = 0

        for resource_name, per_cycle in profile.get("inputs", {}).items():
            required_per_cycle = int(math.ceil(per_cycle)) if per_cycle else 0
            if required_per_cycle <= 0:
                continue
            target_quantity = required_per_cycle * restock_days
            current_quantity = int(inventory.get(resource_name, 0))
            needed = max(0, target_quantity - current_quantity)
            if needed <= 0:
                continue

            taken = self.world._withdraw_from_stockpiles(resource_name, needed)
            if taken > 0:
                inventory[resource_name] = current_quantity + taken
                restocked[resource_name] = restocked.get(resource_name, 0) + taken
                unit_price = self.get_market_price(resource_name)
                total_cost += int(round(unit_price * procurement_multiplier * taken))
            shortage = needed - taken
            if shortage > 0:
                shortages[resource_name] = shortage

        return {
            "restocked": restocked,
            "shortages": shortages,
            "procurement_cost": total_cost,
        }

    def _run_business_industry_cycle(
        self,
        business: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        inventory: Dict[str, int] = business.setdefault("inventory", {})
        report: Dict[str, Any] = {
            "restocked": {},
            "shortages": {},
            "inputs_consumed": {},
            "outputs_created": {},
            "notes": [],
            "procurement_cost": 0,
            "sale_value": 0,
            "cycles": 0,
            "supply_ratio": 0.0,
            "efficiency_multiplier": float(profile.get("base_efficiency", 1.0)),
        }

        restock_report = self._restock_business_inputs(business, profile)
        report["restocked"] = restock_report.get("restocked", {})
        report["shortages"] = dict(restock_report.get("shortages", {}))
        report["procurement_cost"] = restock_report.get("procurement_cost", 0)

        active_employees: List['Character'] = []
        for employee_name in business.get("employees", []):
            employee = self.world.get_character_by_name(employee_name)
            if not employee or getattr(employee, "retired", False):
                continue
            active_employees.append(employee)

        available_cycles = max(0.0, float(profile.get("base_cycles", 1.0)))
        available_cycles += len(active_employees) * float(profile.get("per_employee_cycles", 0.0))

        owner = self.world.get_character_by_name(business.get("owner", ""))
        participants: List['Character'] = []
        if owner and not getattr(owner, "retired", False):
            participants.append(owner)
        participants.extend(active_employees)

        skill_weights = profile.get("skill_weights", {})
        raw_skill = 0.0
        for character in participants:
            skills = getattr(character, "skills", {})
            for skill_name, weight in skill_weights.items():
                if weight <= 0:
                    continue
                skill_entry = skills.get(skill_name, 0)
                if isinstance(skill_entry, dict):
                    skill_level = skill_entry.get("level", 0)
                else:
                    skill_level = skill_entry
                raw_skill += float(skill_level) * float(weight)

        skill_target = max(1.0, float(profile.get("skill_target", 8.0)))
        normalized_skill = raw_skill / skill_target
        available_cycles += normalized_skill * float(profile.get("skill_cycle_bonus", 0.0))

        max_cycles = int(round(available_cycles))
        if available_cycles > 0 and max_cycles == 0:
            max_cycles = 1
        if max_cycles < 0:
            max_cycles = 0

        inputs: Dict[str, int] = {}
        inventory_levels: Dict[str, int] = {}
        for resource_name, amount in profile.get("inputs", {}).items():
            required = int(math.ceil(amount)) if amount else 0
            if required <= 0:
                continue
            inputs[resource_name] = required
            inventory_levels[resource_name] = int(inventory.get(resource_name, 0))

        if inputs:
            cycle_limits: List[int] = []
            for resource_name, required in inputs.items():
                available = inventory_levels.get(resource_name, 0)
                if required <= 0:
                    continue
                cycle_limits.append(available // required)
            max_cycles_by_inventory = min(cycle_limits) if cycle_limits else 0
        else:
            max_cycles_by_inventory = max_cycles

        cycles = min(max_cycles, max_cycles_by_inventory)
        supply_ratio = 0.0 if max_cycles <= 0 else cycles / max(1, max_cycles)
        report["cycles"] = cycles
        report["supply_ratio"] = supply_ratio

        base_efficiency = float(profile.get("base_efficiency", 1.0))
        supply_weight = float(profile.get("supply_weight", 0.0))
        skill_weight = float(profile.get("skill_weight", 0.0))
        efficiency = base_efficiency + (supply_ratio * supply_weight) + (max(0.0, normalized_skill) * skill_weight)
        floor = float(profile.get("efficiency_floor", 0.0))
        ceiling = float(profile.get("efficiency_ceiling", 2.0))
        report["efficiency_multiplier"] = max(floor, min(ceiling, efficiency))

        if cycles <= 0:
            if max_cycles == 0:
                report["notes"].append("No staffed shifts to run production.")
            elif inputs:
                lacking: List[tuple[str, int]] = []
                for resource_name, required in inputs.items():
                    available = inventory_levels.get(resource_name, 0)
                    if available < required:
                        deficit = required - available
                        lacking.append((resource_name, deficit))
                        report["shortages"][resource_name] = max(
                            report["shortages"].get(resource_name, 0), deficit
                        )
                if lacking:
                    formatted = ", ".join(f"{amount} {resource}" for resource, amount in lacking)
                    report["notes"].append(f"Awaiting inputs: {formatted}")
            return report

        consumed: Dict[str, int] = {}
        for resource_name, required in inputs.items():
            if required <= 0:
                continue
            total_needed = required * cycles
            if total_needed <= 0:
                continue
            current_quantity = inventory.get(resource_name, 0)
            new_quantity = max(0, current_quantity - total_needed)
            inventory[resource_name] = new_quantity
            if new_quantity == 0:
                inventory.pop(resource_name, None)
            consumed[resource_name] = total_needed
        if consumed:
            report["inputs_consumed"] = consumed

        sale_value = float(profile.get("sale_value_per_cycle", 0)) * cycles
        sale_multiplier = float(profile.get("sale_value_multiplier", 0.0))
        outputs_created: Dict[str, int] = {}
        deposited: Dict[str, int] = {}

        for resource_name, amount in profile.get("outputs", {}).items():
            output_per_cycle = int(math.ceil(amount)) if amount else 0
            if output_per_cycle <= 0:
                continue
            produced = output_per_cycle * cycles
            if produced <= 0:
                continue
            outputs_created[resource_name] = produced
            unit_price = self.get_market_price(resource_name)
            if sale_multiplier:
                sale_value += int(round(unit_price * sale_multiplier * produced))
            if profile.get("store_outputs"):
                inventory[resource_name] = inventory.get(resource_name, 0) + produced
            if profile.get("deposit_outputs"):
                deposit_result = self.world._deposit_work_output(resource_name, produced)
                delivered = deposit_result.get("delivered", 0)
                if delivered:
                    deposited[resource_name] = deposited.get(resource_name, 0) + delivered
                overflow = deposit_result.get("overflow", 0)
                if overflow:
                    report.setdefault("overflow", {})[resource_name] = overflow

        if outputs_created:
            report["outputs_created"] = outputs_created
        if deposited:
            report["deposited"] = deposited

        report["sale_value"] = int(round(sale_value))

        if report["shortages"]:
            formatted = ", ".join(
                f"{amount} {resource}" for resource, amount in report["shortages"].items()
            )
            report["notes"].append(f"Short on {formatted} for future orders.")

        return report

    def _close_business(self, business: Dict[str, Any], reason: str) -> None:
        if business.get("status") == "closed":
            return

        business["status"] = "closed"
        business["closed_day"] = self.world.game_time.current_day if self.world.game_time else 0
        owner = self.world.get_character_by_name(business.get("owner", ""))
        if owner:
            owner.handle_business_closure(business["id"], self.world, f"{business['name']} closed ({reason}).")
        for employee_name in list(business.get("employees", [])):
            employee = self.world.get_character_by_name(employee_name)
            if employee:
                employee.handle_business_closure(business["id"], self.world, f"{business['name']} closed ({reason}).")
        business["employees"] = []
        business["cash_reserve"] = 0
        self.world.add_event_log_message(f"{business['name']} closed: {reason}.")
        self.world.add_notable_event(
            "BusinessClosed",
            {
                "summary": f"{business['name']} closed due to {reason}.",
                "business_id": business.get("id"),
                "owner": business.get("owner"),
                "reason": reason,
            },
        )

    def _update_businesses(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.businesses:
            report["business_events"] = events
            return events

        revenue_variance = getattr(config, "BUSINESS_REVENUE_VARIANCE", 0.0)
        retention = getattr(config, "BUSINESS_CAPITAL_RETENTION", 0.5)
        base_cost = getattr(config, "BUSINESS_BASE_OPERATING_COST", 2)
        wage = getattr(config, "BUSINESS_EMPLOYEE_WAGE", 3)
        owner_draw_limit = getattr(config, "BUSINESS_OWNER_DRAW", 0)
        capital_factor = getattr(config, "BUSINESS_CAPITAL_PROFIT_FACTOR", 0.0)
        failure_threshold = getattr(config, "BUSINESS_FAILURE_THRESHOLD", -15)
        recovery_bonus = getattr(config, "BUSINESS_RECOVERY_BONUS", 0.0)
        reputation_bonus = getattr(config, "BUSINESS_REPUTATION_BONUS", 0)
        industry_profiles = getattr(config, "BUSINESS_INDUSTRY_PROFILES", {})

        supply_alerts: List[Dict[str, Any]] = report.setdefault("business_supply_alerts", [])
        ledgers: List[Dict[str, Any]] = report.setdefault("business_ledgers", [])

        for business_id, business in list(self.businesses.items()):
            if business.get("status") != "active":
                continue

            revenue_range = business.get("revenue_range") or getattr(
                config, "BUSINESS_DAILY_REVENUE_RANGE", (4, 9)
            )
            revenue_low, revenue_high = revenue_range
            if revenue_low > revenue_high:
                revenue_low, revenue_high = revenue_high, revenue_low

            base_gross = random.randint(int(revenue_low), int(revenue_high))
            base_gross += int(business.get("capital", 0) * capital_factor)
            if revenue_variance:
                base_gross = max(
                    0, int(base_gross * random.uniform(1 - revenue_variance, 1 + revenue_variance))
                )

            profile = industry_profiles.get(business.get("industry"))
            industry_report: Optional[Dict[str, Any]] = None
            gross = base_gross
            procurement_cost = 0
            if profile:
                industry_report = self._run_business_industry_cycle(business, profile)
                procurement_cost = int(industry_report.get("procurement_cost", 0))
                efficiency_multiplier = float(industry_report.get("efficiency_multiplier", 1.0) or 0.0)
                gross = max(0, int(round(gross * efficiency_multiplier)))
                gross += int(industry_report.get("sale_value", 0))
            else:
                business.pop("inventory", None)

            payroll_total = 0
            paid_workers: List[str] = []
            for employee_name in list(business.get("employees", [])):
                employee = self.world.get_character_by_name(employee_name)
                if not employee or getattr(employee, "retired", False):
                    continue
                employee.receive_income(wage, f"work at {business['name']}")
                payroll_total += wage
                paid_workers.append(employee.name)

            expenses = base_cost + payroll_total + procurement_cost
            owner_draw = 0
            owner = self.world.get_character_by_name(business.get("owner", ""))
            if owner and gross > expenses and owner_draw_limit > 0:
                available_profit = gross - expenses
                owner_draw = min(owner_draw_limit, available_profit)
                if owner_draw > 0:
                    owner.receive_income(owner_draw, f"profits from {business['name']}")
                    expenses += owner_draw

            net_profit = gross - expenses
            if net_profit >= 0:
                retained = int(net_profit * retention)
                bonus = int(gross * recovery_bonus)
                business["capital"] = business.get("capital", 0) + retained + bonus
            else:
                business["capital"] = business.get("capital", 0) + net_profit
            business["cash_reserve"] = max(0, business.get("cash_reserve", 0) + net_profit)

            if industry_report:
                business["last_industry_report"] = dict(industry_report)
            elif "last_industry_report" in business:
                del business["last_industry_report"]

            if owner and net_profit > 0 and reputation_bonus:
                owner.update_reputation(reputation_bonus, f"Profitable day at {business['name']}", self.world)

            history_entry = {
                "day": self.world.game_time.current_day if self.world.game_time else -1,
                "gross": gross,
                "net": net_profit,
                "payroll": payroll_total,
                "owner_draw": owner_draw,
                "procurement": procurement_cost,
            }
            if industry_report:
                history_entry["supply_ratio"] = industry_report.get("supply_ratio")
                history_entry["cycles"] = industry_report.get("cycles")
            business.setdefault("history", []).append(history_entry)
            business["history"] = business["history"][-14:]

            if industry_report and industry_report.get("shortages"):
                shortages = {
                    resource: amount
                    for resource, amount in industry_report.get("shortages", {}).items()
                    if amount > 0
                }
                if shortages:
                    supply_alerts.append(
                        {
                            "id": business_id,
                            "name": business.get("name"),
                            "industry": business.get("industry"),
                            "shortages": shortages,
                        }
                    )

            ledger_entry: Dict[str, Any] = {
                "id": business_id,
                "name": business.get("name"),
                "industry": business.get("industry"),
                "gross": gross,
                "net": net_profit,
                "payroll": payroll_total,
                "procurement": procurement_cost,
            }
            if industry_report:
                ledger_entry["supply_ratio"] = industry_report.get("supply_ratio")
                ledger_entry["notes"] = list(industry_report.get("notes", []))
                ledger_entry["outputs"] = dict(industry_report.get("outputs_created", {}))
            ledgers.append(ledger_entry)

            if business.get("capital", 0) <= failure_threshold:
                self._close_business(business, "insolvency")
                events.append(
                    {
                        "id": business_id,
                        "name": business.get("name"),
                        "status": "closed",
                        "net": net_profit,
                        "reason": "insolvency",
                    }
                )
                continue

            event_payload: Dict[str, Any] = {
                "id": business_id,
                "name": business.get("name"),
                "gross": gross,
                "net": net_profit,
                "payroll": payroll_total,
                "owner_draw": owner_draw,
                "status": "active",
                "employees_paid": paid_workers,
                "industry": business.get("industry"),
            }
            if industry_report:
                event_payload["industry_report"] = industry_report
            events.append(event_payload)

        report["business_events"] = events
        return events

    def _update_character_wealth(self, report: Dict[str, Any]) -> Dict[str, Any]:
        wealth_events: List[Dict[str, Any]] = []
        wealth_entries: List[Dict[str, Any]] = []
        for character in self.world.characters:
            if not hasattr(character, "evaluate_daily_wealth"):
                continue
            updates = character.evaluate_daily_wealth(self.world)
            net = updates.get("net_worth", getattr(character, "net_worth", character.money))
            wealth_entries.append(
                {
                    "name": character.name,
                    "net_worth": net,
                    "status": getattr(character, "wealth_status", "modest"),
                }
            )
            event_payload = {k: v for k, v in updates.items() if k not in {"net_worth", "previous_net_worth"}}
            if event_payload:
                wealth_events.append({"character": character.name, **event_payload})

        wealth_entries.sort(key=lambda entry: entry["net_worth"])
        richest = sorted(wealth_entries, key=lambda entry: entry["net_worth"], reverse=True)[:3]
        poorest = wealth_entries[:3]

        snapshot = {
            "entries": wealth_entries,
            "richest": richest,
            "poorest": poorest,
        }
        self.latest_wealth_snapshot = snapshot
        report["wealth_snapshot"] = snapshot
        if wealth_events:
            report["wealth_events"] = wealth_events
        return snapshot

    def _evaluate_wealth_tensions(
        self,
        report: Dict[str, Any],
        wealth_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.world.game_time:
            return
        if wealth_data is None:
            wealth_data = self.latest_wealth_snapshot
        if not wealth_data:
            return

        today = self.world.game_time.current_day
        if self._last_wealth_tension_day == today:
            return
        threshold = getattr(config, "WEALTH_JEALOUSY_THRESHOLD", 0)
        if threshold <= 0:
            return

        richest = wealth_data.get("richest", [])
        jealousy_records: List[Dict[str, Any]] = []
        for character in self.world.characters:
            if not hasattr(character, "net_worth"):
                continue
            target_name = None
            gap_value = 0
            for entry in richest:
                if entry["name"] == character.name:
                    continue
                diff = entry["net_worth"] - getattr(character, "net_worth", character.money)
                if diff > gap_value:
                    gap_value = diff
                    target_name = entry["name"]
            if target_name and gap_value >= threshold:
                if character._last_jealousy_day == today:
                    continue
                character._last_jealousy_day = today
                character.add_memory(
                    f"Jealous of {target_name}'s fortune (gap {gap_value} coins)."
                )
                character.update_mood_score(
                    getattr(config, "WEALTH_JEALOUSY_MOOD_PENALTY", -3),
                    f"Jealous of {target_name}'s wealth",
                )
                character.modify_relationship(
                    target_name,
                    getattr(config, "WEALTH_JEALOUSY_RELATIONSHIP_HIT", -2),
                    self.world,
                    reason="Envious of their wealth",
                )
                jealousy_records.append(
                    {"character": character.name, "target": target_name, "gap": gap_value}
                )

        if jealousy_records:
            report.setdefault("wealth_tensions", []).extend(jealousy_records)
            self._last_wealth_tension_day = today

    def _settle_wage_backlog(self) -> int:
        if not self.pending_wages or self.treasury_coins <= 0:
            return 0
        paid_total = 0
        remaining_debts: List[Dict[str, Any]] = []
        for debt in self.pending_wages:
            amount_due = debt.get("amount_due", 0)
            if amount_due <= 0:
                continue
            character = self.world.get_character_by_name(debt.get("character", ""))
            if not character:
                continue
            payment = min(amount_due, self.treasury_coins)
            if payment <= 0:
                remaining_debts.append(debt)
                continue
            self.treasury_coins -= payment
            character.money += payment
            paid_total += payment
            amount_due -= payment
            character.add_memory(f"Received {payment} coin{'s' if payment != 1 else ''} in back pay for {debt.get('reason', 'work')}.")
            character.update_mood_score(config.MOOD_CHANGE_GOT_PAID, "Received back pay")
            if amount_due > 0:
                debt["amount_due"] = amount_due
                remaining_debts.append(debt)
            else:
                self.world.add_event_log_message(f"Cleared wage arrears for {character.name}'s {debt.get('reason', 'duties')}.")
        self.pending_wages = remaining_debts
        self.todays_wages_paid += paid_total
        return paid_total

    def process_payment(self, character: 'Character', amount: int, reason: str) -> Tuple[int, int]:
        if amount <= 0:
            return 0, 0
        paid = min(amount, self.treasury_coins)
        if paid > 0:
            self.treasury_coins -= paid
            character.money += paid
            self.todays_wages_paid += paid
        owed = amount - paid
        if owed > 0:
            self.todays_wages_owed += owed
            debt_record = {
                "character": character.name,
                "amount_due": owed,
                "reason": reason,
                "day_incurred": self.world.game_time.current_day if self.world.game_time else -1,
            }
            self.pending_wages.append(debt_record)
            self.world.add_event_log_message(
                f"Treasury short {owed} coins for {character.name}'s {reason}. Added to wage arrears."
            )
        return paid, owed

    def identify_resource_pressures(self) -> List[Dict[str, Any]]:
        """Returns resource pressure descriptors sorted by severity."""
        pressures: List[Dict[str, Any]] = []
        resources_to_check = [
            "Wood",
            "Stone",
            "Iron Ore",
            "Lumber",
            "Furniture",
            "Herbs",
            "Food",
            "Water",
        ]
        for resource in resources_to_check:
            quantity = self.world.get_total_resource_quantity(resource)
            low_threshold = getattr(config, "MAYOR_RESOURCE_LOW_THRESHOLD", 20)
            high_threshold = getattr(config, "MAYOR_RESOURCE_HIGH_THRESHOLD", 150)
            if quantity < low_threshold:
                severity = low_threshold - quantity
                pressures.append({
                    "resource": resource,
                    "status": "shortage",
                    "quantity": quantity,
                    "threshold": low_threshold,
                    "severity": severity,
                })
            elif quantity > high_threshold:
                severity = quantity - high_threshold
                pressures.append({
                    "resource": resource,
                    "status": "surplus",
                    "quantity": quantity,
                    "threshold": high_threshold,
                    "severity": severity,
                })
        pressures.sort(key=lambda entry: entry.get("severity", 0), reverse=True)
        return pressures

    def _handle_surplus_trade(self, resource_name: str, severity: int) -> Optional[Dict[str, Any]]:
        sale_cap = getattr(config, "MAX_SURPLUS_SALE_PER_DAY", 0)
        if sale_cap <= 0 or severity <= 0:
            return None
        if any(trade.get("resource") == resource_name for trade in self.today_surplus_sales):
            return None

        quantity_to_sell = min(severity, sale_cap)
        withdrawn = self.world._withdraw_from_stockpiles(resource_name, quantity_to_sell)
        if withdrawn <= 0:
            return None

        unit_price = self.get_market_price(resource_name)
        revenue = unit_price * withdrawn
        self.treasury_coins += revenue
        trade_details = {
            "resource": resource_name,
            "quantity": withdrawn,
            "unit_price": unit_price,
            "revenue": revenue,
            "day": self.world.game_time.current_day if self.world.game_time else -1,
        }
        self.today_surplus_sales.append(trade_details)
        self.world.add_event_log_message(
            f"Converted surplus {withdrawn} {resource_name} into {revenue} coins at the market."
        )
        self.world.add_notable_event(
            "SurplusTrade",
            {
                "summary": f"Sold {withdrawn} {resource_name} for {revenue} coins.",
                "resource": resource_name,
                "revenue": revenue,
            },
        )
        return trade_details

    def _spawn_conversion_work_order(self, resource_name: str, severity: int) -> Optional[WorkOrder]:
        if not self.world.game_time or severity <= 0:
            return None

        conversion_map = {
            "Wood": {"item_name": "Arrow Bundle", "quantity_factor": 1},
            "Herbs": {"item_name": "Bandages", "quantity_factor": 1},
        }
        recipe = conversion_map.get(resource_name)
        if not recipe:
            return None

        target_item = recipe["item_name"]
        existing = [
            wo for wo in self.work_orders
            if wo.details.get("item_name") == target_item and wo.status in {"Pending", "Approved", "InProgress"}
        ]
        if existing:
            return None

        blueprint = BLUEPRINTS.get(target_item)
        if not blueprint or "required_resources" not in blueprint:
            return None

        quantity = max(1, severity // 5 * recipe.get("quantity_factor", 1))
        required_resources = {
            res: qty * quantity for res, qty in blueprint["required_resources"].items()
        }
        details = {
            "item_name": target_item,
            "quantity": quantity,
            "required_resources": required_resources,
        }
        work_order = WorkOrder(
            order_type="CraftItem",
            details=details,
            priority=3,
            creation_day=self.world.game_time.current_day,
        )
        self.add_work_order(work_order)
        self.world.add_event_log_message(
            f"Economic council schedules crafting of {quantity} {target_item} to soak {resource_name} surplus."
        )
        return work_order

    def set_resource_collection_directive(
        self,
        resource_name: str,
        per_trip_quota: int,
        duration_days: int,
        reason: str,
        originator: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.world.game_time:
            raise ValueError("Cannot set resource directive without game time reference.")

        directive = {
            "resource": resource_name,
            "per_trip_quota": max(1, per_trip_quota),
            "set_day": self.world.game_time.current_day,
            "expires_day": self.world.game_time.current_day + max(1, duration_days),
            "reason": reason,
            "originator": originator,
            "last_reminded_day": None,
        }
        self.resource_collection_directives[resource_name] = directive
        summary = f"Resource directive for {resource_name}: gather at least {directive['per_trip_quota']} per trip"
        if originator:
            summary += f" (ordered by {originator})"
        self.world.add_event_log_message(summary)
        self.world.add_notable_event(
            "ResourceDirective",
            {
                "summary": summary,
                "resource": resource_name,
                "originator": originator,
            },
        )
        return directive

    def get_resource_directive(self, resource_name: str) -> Optional[Dict[str, Any]]:
        directive = self.resource_collection_directives.get(resource_name)
        if not directive or not self.world.game_time:
            return directive
        if directive["expires_day"] < self.world.game_time.current_day:
            # Expired directive
            del self.resource_collection_directives[resource_name]
            return None
        return directive

    def expire_resource_directives(self):
        if not self.world.game_time:
            return
        expired: List[str] = []
        for resource_name, directive in list(self.resource_collection_directives.items()):
            if directive["expires_day"] < self.world.game_time.current_day:
                expired.append(resource_name)
                del self.resource_collection_directives[resource_name]
        if expired:
            self.world.add_event_log_message(f"Resource directives concluded for: {expired}")

    def manage_economy(self):
        if not self.world.game_time:
            return
        pressures = self.identify_resource_pressures()
        for pressure in pressures:
            resource = pressure["resource"]
            if pressure["status"] == "shortage":
                if resource in self.resource_collection_directives:
                    continue
                severity = pressure["severity"]
                per_trip_quota = max(4, min(15, severity + 3))
                duration_days = 5
                self.set_resource_collection_directive(
                    resource,
                    per_trip_quota,
                    duration_days,
                    reason="Automated economic response to shortage",
                    originator="Economic Council",
                )
            elif pressure["status"] == "surplus":
                severity = pressure.get("severity", 0)
                self._handle_surplus_trade(resource, severity)
                self._spawn_conversion_work_order(resource, severity)

    def process_daily_economy(self, report: Dict[str, Any]):
        if not self.world.game_time:
            return

        family_events = []
        previous_wages_paid = self.todays_wages_paid
        previous_wages_owed = self.todays_wages_owed
        self.todays_wages_paid = 0
        self.todays_wages_owed = 0

        report.update({
            "day": self.world.game_time.current_day,
            "tax_collected": 0,
            "food_consumed": 0,
            "food_deficit": 0,
            "water_consumed": 0,
            "water_deficit": 0,
            "wages_paid": previous_wages_paid,
            "wages_owed": previous_wages_owed,
            "arrears": sum(debt.get("amount_due", 0) for debt in self.pending_wages),
            "arrears_paid": 0,
            "crime_events": [],
            "treasury": self.treasury_coins,
            "surplus_trades": list(self.today_surplus_sales),
            "pending_crimes": len(self.world.crime.pending_crimes),
            "environment": self.world.environment_effect_snapshot,
        })

        tax_income = getattr(config, "DAILY_BASE_TAX_INCOME", 0)
        if tax_income:
            self.treasury_coins += tax_income
            report["tax_collected"] = tax_income

        report["arrears_paid"] = self._settle_wage_backlog()
        report["treasury"] = self.treasury_coins
        report["arrears"] = sum(debt.get("amount_due", 0) for debt in self.pending_wages)

        business_events = self._update_businesses(report)
        wealth_snapshot = self._update_character_wealth(report)
        self._evaluate_wealth_tensions(report, wealth_snapshot)

        # Process personal pursuits and add them to the report
        personal_pursuits_events = self.world.process_personal_pursuits_daily()
        if personal_pursuits_events:
            report["personal_pursuits"] = personal_pursuits_events

        summary = (
            f"Economic summary — Treasury {self.treasury_coins}c "
            f"(tax +{report['tax_collected']}c, wages paid {report['wages_paid']}c, arrears settled {report['arrears_paid']}c)."
            f" Outstanding arrears {report['arrears']}c, food deficit {report['food_deficit']} rations,"
            f" water deficit {report['water_deficit']} casks."
        )
        self.world.add_event_log_message(summary)
        for business_event in business_events:
            if business_event.get("status") == "closed":
                self.world.add_event_log_message(
                    f"Business closed: {business_event.get('name')} ({business_event.get('reason', 'closure')})."
                )
            else:
                net = business_event.get("net", 0)
                self.world.add_event_log_message(
                    f"{business_event.get('name')} netted {net} coin{'s' if net != 1 else ''} after payroll."
                )
                industry_report = business_event.get("industry_report") or {}
                notes = industry_report.get("notes") or []
                for note in notes:
                    self.world.add_event_log_message(f"{business_event.get('name')}: {note}")
                outputs_created = industry_report.get("outputs_created") or {}
                if outputs_created:
                    output_summary = ", ".join(
                        f"{amount} {resource}"
                        for resource, amount in outputs_created.items()
                        if amount
                    )
                    if output_summary:
                        self.world.add_event_log_message(
                            f"{business_event.get('name')} produced {output_summary}."
                        )
        for crime_event in report.get("crime_events", []):
            self.world.add_event_log_message(f"Security report: {crime_event['description']}.")

        if report["surplus_trades"]:
            trade_summaries = ", ".join(
                f"{trade['quantity']} {trade['resource']} (+{trade['revenue']}c)"
                for trade in report["surplus_trades"]
            )
            self.world.add_event_log_message(f"Trade ledger: {trade_summaries} exported to market.")

        for wealth_event in report.get("wealth_events", []):
            if "business_started" in wealth_event:
                started = wealth_event["business_started"]
                self.world.add_event_log_message(
                    f"{wealth_event['character']} opened {started.get('name')} ({started.get('industry')})."
                )
            if "retired" in wealth_event:
                retired = wealth_event["retired"]
                self.world.add_event_log_message(
                    f"{wealth_event['character']} retires from {retired.get('former_job')} with {retired.get('net_worth')} coins saved."
                )
            if "nobility" in wealth_event:
                nobility = wealth_event["nobility"]
                self.world.add_event_log_message(
                    f"{wealth_event['character']} earns the title {nobility.get('title')} through amassed wealth."
                )
        if report.get("wealth_tensions"):
            for tension in report["wealth_tensions"]:
                self.world.add_event_log_message(
                    f"Jealousy simmers: {tension['character']} eyes {tension['target']}'s fortune (gap {tension['gap']}c)."
                )
        if family_events:
            for event in family_events:
                event_type = event.get("type")
                if event_type == "union":
                    partners = event.get("partners", [])
                    if partners:
                        self.world.add_event_log_message(
                            f"Union celebrated: {' & '.join(partners)}."
                        )
                elif event_type == "new_child":
                    parents = event.get("parents", [])
                    child = event.get("child")
                    if len(parents) == 2 and child:
                        self.world.add_event_log_message(
                            f"{parents[0]} and {parents[1]} welcome {child}."
                        )

        self.last_daily_economic_report = report
        self.today_surplus_sales = []

    def get_market_price(self, item_name: str) -> int:
        return self.market_prices.get(item_name, self.base_market_prices.get(item_name, 0))

    def _process_work_crew(self, key: str, definition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        crew_report = {
            "key": key,
            "title": definition.get("title"),
            "workers": [],
            "output_produced": {},
            "inputs_consumed": {},
            "backlog_cleared": 0,
            "new_backlog": 0,
            "shortages": [],
            "gathered": 0,
            "delivered": 0,
            "backlog": 0,
            "notes": [],
        }

        worker_jobs = definition.get("jobs", [])
        workers = [
            char for char in self.world.characters if char.job and char.job.title in worker_jobs
        ]
        crew_report["workers"] = [worker.name for worker in workers]

        if not workers:
            crew_report["notes"].append("No workers assigned to this shift.")
            return crew_report

        # Calculate base yield
        total_skill = 0
        for worker in workers:
            skill_name = definition.get("skill")
            if skill_name:
                skill_entry = worker.skills.get(skill_name, {})
                total_skill += skill_entry.get("level", 0) if isinstance(skill_entry, dict) else skill_entry

        shift_ticks = definition.get("shift_ticks", 1)
        base_yield = len(workers) * shift_ticks
        skill_bonus = total_skill * definition.get("skill_yield_bonus", 0.1)
        potential_yield = base_yield * (1 + skill_bonus)

        inputs = definition.get("inputs", {})
        output_resource = definition.get("resource")
        output_amount = 0

        if inputs:
            # Manufacturing
            shortages = {
                res: req - sum(sp.inventory.get(res, 0) for sp in self.world.stockpiles)
                for res, req in inputs.items()
                if sum(sp.inventory.get(res, 0) for sp in self.world.stockpiles) < req
            }

            if shortages:
                crew_report["notes"].append(f"Awaiting inputs: {', '.join(shortages.keys())}")
                crew_report["shortages"] = [
                    {"resource": res, "needed": inputs[res], "available": sum(sp.inventory.get(res, 0) for sp in self.world.stockpiles)}
                    for res in shortages
                ]
                return crew_report

            # This part is simplified as the detailed logic above handles the checks.
            # The original logic for calculating cycles can now proceed with the assumption
            # that enough materials are available for at least one cycle.
            cycle_limits = [
                sum(sp.inventory.get(res, 0) for sp in self.world.stockpiles) // req
                for res, req in inputs.items() if req > 0
            ]
            potential_material_cycles = min(cycle_limits) if cycle_limits else int(potential_yield)
            num_cycles = min(int(potential_yield), potential_material_cycles)

            # Step 2: Withdraw all resources for the calculated cycles
            inputs_consumed = {}
            all_materials_withdrawn = True
            for resource, required in inputs.items():
                consumed_amount = required * num_cycles
                withdrawn_amount = self.world._withdraw_from_stockpiles(resource, consumed_amount)
                inputs_consumed[resource] = withdrawn_amount
                if withdrawn_amount < consumed_amount:
                    all_materials_withdrawn = False
                    crew_report["notes"].append(f"Failed to withdraw sufficient {resource}. Halting production.")
                    # In a more complex sim, we'd return partially withdrawn materials.
                    # For now, we halt and the materials are effectively lost for this cycle.
                    break

            crew_report["inputs_consumed"] = inputs_consumed
            crew_report["gathered"] = num_cycles

            if all_materials_withdrawn and output_resource:
                # Step 3: Calculate output based on successful cycles
                output_per_cycle = definition.get("output_per_cycle", 1)
                output_amount = num_cycles * output_per_cycle
                crew_report["output_produced"] = {output_resource: output_amount}
        else:
            # Gathering
            output_amount = int(potential_yield)
            crew_report["gathered"] = output_amount
            if output_resource:
                crew_report["output_produced"] = {output_resource: output_amount}

        current_backlog = self.world.work_shift_backlog.get(key, 0.0)
        total_to_deliver = output_amount + current_backlog

        hauler_jobs = definition.get("hauler_jobs", [])
        haulers = [char for char in self.world.characters if char.job and char.job.title in hauler_jobs]
        hauler_capacity = definition.get("hauler_capacity", 5)
        total_carry_capacity = len(haulers) * hauler_capacity

        delivered_this_shift = int(min(total_to_deliver, total_carry_capacity))

        if delivered_this_shift > 0 and output_resource:
            deposit_results = self.world._deposit_work_output(output_resource, delivered_this_shift)
            actually_delivered = deposit_results.get("delivered", 0)
            crew_report["delivered"] = actually_delivered

            new_backlog = total_to_deliver - actually_delivered
            self.work_shift_backlog[key] = new_backlog
            crew_report["backlog"] = new_backlog
            crew_report["backlog_cleared"] = current_backlog - max(0, new_backlog - output_amount)

        return crew_report

    def process_workforce_daily(self, daily_report: Dict[str, Any]) -> Dict[str, Any]:
        if not self.world.game_time:
            return {}

        today = self.world.game_time.current_day
        if self._last_workforce_update_day == today:
            return self.latest_workforce_report

        report: Dict[str, Any] = {
            "day": today,
            "crews": [],
            "backlog_cleared": 0,
            "new_backlog": 0,
            "shortages": [],
            "alerts": [],
            "gathered_total": 0,
            "delivered_total": 0,
            "backlog_total": 0,
        }

        # Process crews in order, allowing upstream production to feed downstream
        work_shift_definitions = self.world.get_work_shift_definitions()

        # Topological sort for work crews

        # 1. Build Adjacency List & In-Degree Count
        adj: Dict[str, List[str]] = {key: [] for key in work_shift_definitions}
        in_degree: Dict[str, int] = {key: 0 for key in work_shift_definitions}

        # Map resource outputs to the crews that produce them
        resource_producers: Dict[str, str] = {}
        for key, definition in work_shift_definitions.items():
            if definition.get("resource"):
                resource_producers[definition["resource"]] = key

        for key, definition in work_shift_definitions.items():
            inputs = definition.get("inputs", {})
            for resource in inputs:
                if resource in resource_producers:
                    producer_key = resource_producers[resource]
                    if producer_key != key:
                        adj[producer_key].append(key)
                        in_degree[key] += 1

        # 2. Initialize Queue with Source Nodes (in-degree == 0)
        queue = [key for key, degree in in_degree.items() if degree == 0]
        sorted_keys = []

        # 3. Process Queue
        while queue:
            current_key = queue.pop(0)
            sorted_keys.append(current_key)

            for neighbor_key in adj.get(current_key, []):
                in_degree[neighbor_key] -= 1
                if in_degree[neighbor_key] == 0:
                    queue.append(neighbor_key)

        # Check for cycles (e.g., A needs B, B needs A)
        if len(sorted_keys) != len(work_shift_definitions):
            # Fallback or error for cyclical dependencies
            report["alerts"].append("Cyclical dependency detected in workforce definitions. Processing order may be incorrect.")
            # Simple sort as a fallback
            sorted_keys = sorted(
                work_shift_definitions.keys(),
                key=lambda k: 0 if not work_shift_definitions[k].get("inputs") else 1
            )


        for key in sorted_keys:
            definition = work_shift_definitions[key]
            crew_report = self._process_work_crew(key, definition)
            if crew_report:
                report["crews"].append(crew_report)
                if crew_report.get("shortages"):
                    report["shortages"].extend(crew_report["shortages"])
                    for shortage in crew_report.get("shortages", []):
                        alert_msg = (
                            f"Workforce alert for {crew_report.get('title', key)}: "
                            f"stalled pending {shortage.get('resource')}."
                        )
                        if alert_msg not in report["alerts"]:
                            report["alerts"].append(alert_msg)

        # Summarize totals
        for crew_report in report["crews"]:
            report["gathered_total"] += crew_report.get("gathered", 0)
            report["delivered_total"] += crew_report.get("delivered", 0)
            report["backlog_total"] += crew_report.get("backlog", 0)
            report["backlog_cleared"] += crew_report.get("backlog_cleared", 0)
            report["new_backlog"] += crew_report.get("new_backlog", 0)

        self.latest_workforce_report = report
        self._last_workforce_update_day = today
        daily_report["workforce"] = report
        return report

    def get_workforce_snapshot(self) -> Dict[str, Any]:
        return self.latest_workforce_report.copy()

    def _withdraw_from_stockpiles(self, resource_name: str, needed: int) -> int:
        return self.world._withdraw_from_stockpiles(resource_name, needed)
