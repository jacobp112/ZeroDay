from typing import List, Optional
from datetime import date
from decimal import Decimal
from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import Transaction, Position, TransactionType
import re

class FidelityParser(Parser):
    def get_broker_name(self) -> str:
        return "Fidelity"

    def _parse_account_number(self) -> Optional[str]:
        # Fidelity often has "Account Number X12-345678"
        match = self._find_pattern(r"Account Number\s*([A-Z\d-]+)")
        return match.group(1) if match else None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        return None

    def _parse_positions(self) -> List[Position]:
        return []

    def _parse_transactions(self) -> List[Transaction]:
        transactions = []
        # Fidelity section often "Activity"
        return transactions
