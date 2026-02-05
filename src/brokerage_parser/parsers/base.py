from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import date, datetime
import re
from typing import List, Optional, Pattern, Dict, Tuple, Any, Union
import logging
from brokerage_parser.models import ParsedStatement, Transaction, Position, AccountSummary, SourceReference, ExtractionMethod, BoundingBox
from brokerage_parser.extraction import TableData, RichPage, RichTable

logger = logging.getLogger(__name__)

# Type alias for legacy tables
TableData = List[List[str]]

class Parser(ABC):
    def __init__(self, text: str, tables: Optional[List[TableData]] = None, rich_text_map: Optional[Dict[int, RichPage]] = None, rich_tables: Optional[List[RichTable]] = None):
        self.text = text
        self.tables = tables or []
        self.rich_text_map = rich_text_map or {}
        self.rich_tables = rich_tables or []

        # Let's build a global offset map if rich_text is provided.
        self.global_offset_map = [] # List[(start, end, page_num, local_start)]
        self._build_offset_map()

    def _build_offset_map(self):
        """Builds a mapping from global text offsets to specific pages and local offsets."""
        current_offset = 0
        if not self.rich_text_map:
            return

        sorted_pages = sorted(self.rich_text_map.keys())
        for page_num in sorted_pages:
            rich_page = self.rich_text_map[page_num]
            page_len = len(rich_page.full_text)

            # Record the range for this page in the global text
            # Assuming self.text is exactly "\n".join(pages)
            # We must verify if self.text matches exactly or if we need to reconstruct it?
            # Orchestrator usually does text = "\n".join(extract_text(...).values())
            # so it should align, plus the joining newlines.

            self.global_offset_map.append({
                "global_start": current_offset,
                "global_end": current_offset + page_len,
                "page_num": page_num,
                "local_start": 0 # offset within the page
            })

            current_offset += page_len + 1 # +1 for the newline used in join

    def _get_source_for_range(self, start_idx: int, end_idx: int) -> Optional[SourceReference]:
        """
        Finds the source reference for a global text range.
        Handles ranges that might span pages (unlikely for single field, but possible).
        """
        if not self.rich_text_map:
            return None

        # Find which page(s) this range covers
        # Most fields are within a single page.

        sources = []
        raw_texts = []

        for mapping in self.global_offset_map:
            # Check overlap
            # Range: [start_idx, end_idx)
            # Map:   [g_start, g_end)

            overlap_start = max(start_idx, mapping["global_start"])
            overlap_end = min(end_idx, mapping["global_end"])

            if overlap_start < overlap_end:
                # We have overlap on this page
                page_num = mapping["page_num"]
                # Convert global to local
                local_start = overlap_start - mapping["global_start"]
                local_end = overlap_end - mapping["global_start"]

                rich_page = self.rich_text_map.get(page_num)
                if rich_page:
                    ref = rich_page.get_source_for_span(local_start, local_end)
                    if ref:
                        sources.append(ref)
                        if ref.raw_text:
                            raw_texts.append(ref.raw_text)

        if not sources:
            return None

        if len(sources) == 1:
            return sources[0]

        # Merge multi-page sources (rare)
        all_bboxes = []
        for s in sources:
            all_bboxes.extend(s.bboxes)

        return SourceReference(
            bboxes=all_bboxes,
            extraction_method=sources[0].extraction_method, # Assuming same method
            confidence=min(s.confidence for s in sources),
            raw_text="".join(raw_texts)
        )

    def _track_field(self, value_obj: Any, match: Optional[re.Match], match_group: int = 0) -> Tuple[Any, Optional[SourceReference]]:
        """
        Helper to extract source for a regex match and return (value, source_ref).
        If value is just the text, we return it. If it's converted (Decimal), passed as value_obj.
        """
        if not match or not self.rich_text_map:
            return value_obj, None

        start, end = match.span(match_group)
        source = self._get_source_for_range(start, end)
        return value_obj, source

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

