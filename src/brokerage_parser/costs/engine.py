import re
from typing import List
from decimal import Decimal
from brokerage_parser.models import TransactionType
from brokerage_parser.models.domain import Transaction
from brokerage_parser.costs.models import CostReport, CostItem, CostCategory

class CostAnalysisEngine:
    """
    Analyzes transactions to extract and categorize explicit costs according to MiFID II.
    Aggregates Service Costs, Transaction Costs, and Ancillary Costs.
    """

    # Compiled regex patterns for performance
    # Order matters: check Specific Transaction Taxes first, then Management, then Ancillary
    PATTERN_TRANSACTION_COST = re.compile(r"(?i)\b(stamp duty|sdrt|commission|brokerage|ptm levy)\b")
    PATTERN_SERVICE_COST = re.compile(r"(?i)\b(management|mgmt|advisory|custody|service fee|ongoing charge|account fee)\b")
    PATTERN_ANCILLARY_COST = re.compile(r"(?i)\b(wire|transfer|fx|payment|interest charged)\b") # 'interest' might be tricky, usually income, but 'interest charged' is cost

    def analyze(self, transactions: List[Transaction]) -> CostReport:
        report = CostReport()

        for tx in transactions:
            # FILTER 1: Strict Negative Amount Check
            # Costs are outflows. Positive amounts are deposits/income and can never be costs.
            # Convert to GBP if available, otherwise use raw amount (assuming GBP for now or simple sum)
            # Use gbp_amount if present for normalization, else amount
            amount = tx.gbp_amount if tx.gbp_amount is not None else tx.amount

            if amount >= 0:
                continue

            # Check Description Pattern
            description = tx.description
            category = None

            if self.PATTERN_TRANSACTION_COST.search(description):
                category = CostCategory.TRANSACTION_COST
            elif self.PATTERN_SERVICE_COST.search(description):
                category = CostCategory.SERVICE_COST
            elif self.PATTERN_ANCILLARY_COST.search(description):
                category = CostCategory.ANCILLARY_COST

            # Additional Check: If it's explicitly typed as FEE, default to Service if no other match?
            # Or keeps it uncategorized?
            # Requirement says "Iterate through all transactions... If description contains..."
            # Let's stick to regex matches to be safe against misclassified "FEE" types that might be something else.
            # But if type is FEE and no regex match? Often miscellaneous charges.
            # For now, we strictly follow the regex requirement.

            if category:
                # Create Cost Item
                # usage: absolute value of the negative amount
                cost_value = abs(amount)

                item = CostItem(
                    date=tx.date,
                    description=tx.description,
                    amount_gbp=cost_value,
                    category=category
                )
                report.add_item(item)

        return report
