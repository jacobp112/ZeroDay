from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import date, datetime
import re
from typing import List, Optional, Pattern
from brokerage_parser.models import ParsedStatement, Transaction, Position, AccountSummary

class Parser(ABC):
    def __init__(self, text: str):
        self.text = text
        self.lines = text.split('\n')

    def parse(self) -> ParsedStatement:
        """Main parsing method."""
        statement = ParsedStatement(
            broker=self.get_broker_name(),
            account_number=self._parse_account_number() or "Unknown"
        )

        dates = self._parse_statement_dates()
        if dates:
            statement.statement_date = dates[0]
            statement.period_start = dates[1]
            statement.period_end = dates[2]

        statement.positions = self._parse_positions()
        statement.transactions = self._parse_transactions()

        return statement

    @abstractmethod
    def get_broker_name(self) -> str:
        pass

    @abstractmethod
    def _parse_account_number(self) -> Optional[str]:
        pass

    @abstractmethod
    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        """Returns (statement_date, period_start, period_end)"""
        pass

    @abstractmethod
    def _parse_positions(self) -> List[Position]:
        pass

    @abstractmethod
    def _parse_transactions(self) -> List[Transaction]:
        pass

    # Utility Methods
    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        if not value:
            return None
        # Remove '$', ',' and handle parentheses for negative
        clean_val = value.replace('$', '').replace(',', '').strip()
        if '(' in clean_val and ')' in clean_val:
            clean_val = '-' + clean_val.replace('(', '').replace(')', '')

        try:
            return Decimal(clean_val)
        except:
            return None

    def _parse_date(self, value: str, fmt: str = "%m/%d/%Y") -> Optional[date]:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except:
            return None

    def _find_pattern(self, pattern: str, text: Optional[str] = None) -> Optional[re.Match]:
        """Finds the first match of a regex pattern."""
        search_text = text if text else self.text
        return re.search(pattern, search_text, re.IGNORECASE | re.MULTILINE)

    def _find_section(self, start_pattern: str, end_pattern: str) -> List[str]:
        """Extracts lines between two patterns."""
        start_match = self._find_pattern(start_pattern)
        if not start_match:
            return []

        start_idx = self.text.find(start_match.group(0))
        remaining_text = self.text[start_idx:]

        end_match = self._find_pattern(end_pattern, remaining_text)
        if not end_match:
             # If end pattern not found, take reasonably large chunk or rest of text
             end_idx = len(remaining_text)
        else:
             end_idx = remaining_text.find(end_match.group(0))

        section_text = remaining_text[:end_idx]
        return [line.strip() for line in section_text.split('\n') if line.strip()]
