from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional

class MatchType(Enum):
    SAME_DAY = "SAME_DAY"
    BED_AND_BREAKFAST = "BED_AND_BREAKFAST" # 30-day rule
    SECTION_104 = "SECTION_104"   # Pool
    CORPORATE_ACTION = "CORPORATE_ACTION" # Stock splits, etc.

@dataclass
class MatchEvent:
    sell_transaction_id: str
    match_type: MatchType
    quantity: Decimal
    proceeds: Decimal          # Pro-rated proceeds from the sell transaction
    allowable_cost: Decimal    # The matched cost (from specific buy or pool average)
    gain_gbp: Decimal

    # If matched to a specific buy (Same Day or BnB), this is set.
    # If matched to Pool, this is None.
    buy_transaction_id: Optional[str] = None

    date: Optional[str] = None # Sell date for reporting context

    def to_dict(self):
        return {
            "sell_transaction_id": self.sell_transaction_id,
            "buy_transaction_id": self.buy_transaction_id,
            "match_type": self.match_type.value,
            "quantity": str(self.quantity),
            "proceeds": str(self.proceeds),
            "allowable_cost": str(self.allowable_cost),
            "gain_gbp": str(self.gain_gbp),
            "date": self.date
        }

@dataclass
class CGTReport:
    tax_year: str
    total_gains: Decimal = Decimal("0.00")
    total_losses: Decimal = Decimal("0.00")
    net_gain: Decimal = Decimal("0.00")
    match_events: List[MatchEvent] = field(default_factory=list)

    def add_event(self, event: MatchEvent):
        self.match_events.append(event)
        if event.gain_gbp > 0:
            self.total_gains += event.gain_gbp
        else:
            self.total_losses += event.gain_gbp # This will be negative

        self.net_gain += event.gain_gbp

    def to_dict(self):
        return {
            "tax_year": self.tax_year,
            "total_gains": str(self.total_gains),
            "total_losses": str(self.total_losses),
            "net_gain": str(self.net_gain),
            "match_events": [e.to_dict() for e in self.match_events]
        }
