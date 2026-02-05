from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import date, datetime
import re
from typing import List, Optional, Pattern
from brokerage_parser.models import ParsedStatement, Transaction, Position, AccountSummary

from brokerage_parser.extraction import TableData

class Parser(ABC):
    def __init__(self, text: str, tables: Optional[List[TableData]] = None):
        self.text = text
        self.lines = text.split('\n')
        # tables is List[TableData], where TableData is List[List[List[str]]] (List of Tables on a page)
        # So tables passed here is a list of page-level table sets?
        # Or should we flatten it?
        # The extraction returns Dict[int, TableData].
        # Orchestrator will likely pass values() or a flat list.
        # Let's verify what orchestrator will pass.
        # Orchestrator calls process_statement, which calls extraction.
        # Let's assume orchestrator passes a flattened list of tables or the raw dict.
        # The user said: "tables: Optional[List[List[List[str]]]]" (which matches TableData alias) in one place
        # But TableData alias I defined is List of Tables.
        # So "tables" arg here should probably be the full collection.
        # Let's align with the user request: "tables: Optional[List[List[List[str]]]] = None"
        # Wait, the user's alias TableData = List[List[List[str]]] represents ONE page's tables.
        # So passing a List[TableData] would be List[List[List[List[str]]]].
        # Let's simplify. We just want a flat list of ALL tables found in the document, regardless of page?
        # Or preserved by page? Preserving by page is better for context but flat is easier for "find the transaction table".
        # User said: "tables: Optional[List[List[List[str]]]] = None" in the user request.
        # That implies a flat list of tables. Each item is a Table (List[List[str]]).
        # So let's flatten in orchestrator.
        self.tables = tables or []

    def _identify_table_type(self, table: List[List[str]]) -> str:
        """
        Identifies the type of table based on header keywords.
        Returns: "transactions", "positions", or "unknown"
        """
        if not table:
            return "unknown"

        # Check first few rows for headers (headers might be row 0, 1, or 2)
        for i in range(min(5, len(table))):
            row = [str(cell).lower().strip() for cell in table[i]]
            row_text = " ".join(row)

            # Keywords for Transactions
            if "date" in row_text and ("activity" in row_text or "description" in row_text or "transaction" in row_text):
                 return "transactions"

            # Keywords for Positions
            if ("symbol" in row_text or "security" in row_text) and ("quantity" in row_text or "shares" in row_text) and ("value" in row_text or "amount" in row_text):
                 return "positions"

        return "unknown"

    def _get_tables_by_type(self, table_type: str) -> List[List[List[str]]]:
        """Returns all tables matching the given type."""
        return [t for t in self.tables if self._identify_table_type(t) == table_type]

    def parse(self) -> ParsedStatement:
        """Main parsing method."""
        acc_num = self._parse_account_number() or "Unknown"
        # We default type to "Brokerage" for now as we don't parse it yet
        account_summary = AccountSummary(account_number=acc_num, account_type="Brokerage")

        statement = ParsedStatement(
            broker=self.get_broker_name(),
            account=account_summary
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

    def _parse_date_flexible(self, value: str) -> Optional[date]:
        """Tries to parse a date string using multiple common formats."""
        if not value:
            return None

        # Clean up the string: remove commas, extra spaces, normalize dashes if any remain
        clean_val = value.replace(",", " ").replace("-", " ").strip()
        # Collapse multiple spaces
        clean_val = re.sub(r'\s+', ' ', clean_val)

        formats = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%B %d %Y",  # January 31 2023 (commas removed)
            "%b %d %Y",  # Jan 31 2023
        ]

        for fmt in formats:
            try:
                return datetime.strptime(clean_val, fmt).date()
            except ValueError:
                continue

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
             end_idx = end_match.start()

        section_text = remaining_text[:end_idx]
        return [line.strip() for line in section_text.split('\n') if line.strip()]
