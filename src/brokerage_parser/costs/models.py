from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List
from datetime import date

class CostCategory(Enum):
    SERVICE_COST = "SERVICE_COST"           # Management fees, Custody fees
    TRANSACTION_COST = "TRANSACTION_COST"   # Stamp Duty, SDRT, Commission, PTM Levy
    PRODUCT_COST = "PRODUCT_COST"           # OCF/TER (Placeholder for now)
    ANCILLARY_COST = "ANCILLARY_COST"       # Wire, Transfer, FX fees

@dataclass
class CostItem:
    date: date
    description: str
    amount_gbp: Decimal # Always positive for reporting
    category: CostCategory

@dataclass
class CostReport:
    total_service_costs: Decimal = Decimal("0.00")
    total_transaction_costs: Decimal = Decimal("0.00")
    total_product_costs: Decimal = Decimal("0.00")
    total_ancillary_costs: Decimal = Decimal("0.00")
    total_costs: Decimal = Decimal("0.00")

    items: List[CostItem] = field(default_factory=list)

    def add_item(self, item: CostItem):
        self.items.append(item)
        if item.category == CostCategory.SERVICE_COST:
            self.total_service_costs += item.amount_gbp
        elif item.category == CostCategory.TRANSACTION_COST:
            self.total_transaction_costs += item.amount_gbp
        elif item.category == CostCategory.PRODUCT_COST:
            self.total_product_costs += item.amount_gbp
        elif item.category == CostCategory.ANCILLARY_COST:
            self.total_ancillary_costs += item.amount_gbp

        self.total_costs += item.amount_gbp

    def to_dict(self):
        return {
            "total_service_costs": str(self.total_service_costs),
            "total_transaction_costs": str(self.total_transaction_costs),
            "total_product_costs": str(self.total_product_costs),
            "total_ancillary_costs": str(self.total_ancillary_costs),
            "total_costs": str(self.total_costs),
            "items": [
                {
                    "date": i.date.isoformat(),
                    "description": i.description,
                    "amount_gbp": str(i.amount_gbp),
                    "category": i.category.value
                } for i in self.items
            ]
        }
