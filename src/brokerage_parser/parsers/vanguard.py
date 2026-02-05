from typing import List, Optional
from datetime import date
from decimal import Decimal
from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import Transaction, Position, TransactionType
import re

class VanguardParser(Parser):
    def get_broker_name(self) -> str:
        return "Vanguard"

    def _parse_account_number(self) -> Optional[str]:
        match = self._find_pattern(r"Account Number\s*(\d+-\d+)")
        return match.group(1) if match else None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        return None

    def _parse_positions(self) -> List[Position]:
        return []

    def _parse_transactions(self) -> List[Transaction]:
        return []
