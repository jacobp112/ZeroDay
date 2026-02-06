from typing import List, Optional, Dict, Tuple
from datetime import date
from decimal import Decimal
from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import TransactionType
from brokerage_parser.models.domain import Transaction, Position, AccountSummary
import re
import logging

logger = logging.getLogger(__name__)

from brokerage_parser.llm.client import LLMClient
from brokerage_parser.extraction.spatial import find_value_in_region, find_text_in_page, top_right_region
from brokerage_parser.models import ExtractionMethod
from brokerage_parser.models.domain import SourceReference, ParsedStatement
from brokerage_parser.extraction import RichPage, RichTable, TableData
from brokerage_parser.config import settings



class SchwabParser(Parser):
    def get_broker_name(self) -> str:
        return "Schwab"

    def __init__(self, text: str, tables: Optional[List[TableData]] = None, rich_text_map: Optional[Dict[int, RichPage]] = None, rich_tables: Optional[List[RichTable]] = None):
        super().__init__(text, tables, rich_text_map, rich_tables)
        self.field_sources: Dict[str, SourceReference] = {}
        self.llm_client = LLMClient()

    def parse(self) -> ParsedStatement:
        statement = super().parse()
        if self.field_sources:
            if statement.source_map is None:
                statement.source_map = {}
            statement.source_map.update(self.field_sources)
        return statement

    def _extract_account_number_regex(self) -> Tuple[Optional[str], Optional[SourceReference]]:
        # Tier 1: Regex
        match = self._find_pattern(r"Account Number:?\s*([\d-]+)")
        if match:
            # Track source
            val, source = self._track_field(match.group(1), match, 1)
            # Ensure method is native_text
            if source: source.extraction_method = ExtractionMethod.NATIVE_TEXT
            return val, source
        return None, None

    def _extract_account_number_spatial(self) -> Tuple[Optional[str], Optional[SourceReference]]:
        # Tier 2: Spatial (Top-Right)
        if not self.rich_text_map:
            return None, None

        page1 = self.rich_text_map.get(1)
        if not page1:
            return None, None

        # Pattern: strict digits/dashes, maybe 8-12 chars?
        # Schwab accounts usually 8 digits or 4-4. "[\d-]+" is broad.
        # Let's search for \d{4}-\d{4} or \d{8}
        pattern = r"\b\d{4}-?\d{4}\b"

        # Only look in top-right
        source = find_value_in_region(page1, lambda b: top_right_region(b, page1.page_height, page1.page_width), pattern)

        if source:
            source.extraction_method = ExtractionMethod.VISUAL_HEURISTIC
            return source.raw_text, source
        return None, None

    def _extract_account_number_llm(self) -> Tuple[Optional[str], Optional[SourceReference]]:
        # Tier 3: LLM Fallback
        if not self.llm_client.enabled or not self.rich_text_map:
            return None, None

        page1 = self.rich_text_map.get(1)
        if not page1:
            return None, None

        # Full Page Context
        prompt = f"""
        Extract the brokerage Account Number from the following text.
        Return ONLY the account number as a string. If not found, return null.

        Text:
        {page1.full_text}
        """

        val = self.llm_client.complete(prompt, json_schema={"type": "object", "properties": {"account_number": {"type": "string"}}})

        # Parse JSON if LLM returned JSON string (the client tries to return content string,
        # but if we asked for JSON mode, it might be '{"account_number": "123"}' )
        if not val: return None, None

        # Simple cleanup if it returned raw JSON string
        clean_val = val
        if "{" in val and "account_number" in val:
             try:
                 import json
                 j = json.loads(val)
                 clean_val = j.get("account_number")
             except:
                 pass

        if not clean_val or clean_val.lower() == "null" or clean_val.lower() == "none":
            return None, None

        # Reverse Lookup
        # Search for the extracted string in the page
        source = find_text_in_page(page1, clean_val)

        if source:
            source.extraction_method = ExtractionMethod.LLM_FALLBACK
            source.confidence = 0.9 # High confidence if found in text
            return clean_val, source
        else:
            # "Ghost Data" - return page-level source
            # Create a source pointing to the whole page?
            # Or just empty bboxes with Amber confidence
            return clean_val, SourceReference(
                bboxes=[], # Could add page rect if needed
                extraction_method=ExtractionMethod.LLM_FALLBACK,
                confidence=0.7, # Amber
                raw_text=clean_val
            )

    def _parse_account_number(self) -> Optional[str]:
        # Tier 1
        val, src = self._extract_account_number_regex()
        if val:
            if src: self.field_sources["account_number"] = src
            return val

        # Tier 2
        val, src = self._extract_account_number_spatial()
        if val:
            if src: self.field_sources["account_number"] = src
            return val

        # Tier 3
        val, src = self._extract_account_number_llm()
        if val:
            if src: self.field_sources["account_number"] = src
            return val

        return None


    def _extract_dates_llm(self) -> Optional[tuple[date, date, date]]:
        if not self.llm_client.enabled or not self.rich_text_map:
            return None

        page1 = self.rich_text_map.get(1)
        if not page1:
            return None

        prompt = f"""
        Extract the Statement Date, Period Start Date, and Period End Date from the text.
        Return JSON with keys: "statement_date", "period_start", "period_end".
        Format dates as YYYY-MM-DD. If not found, use null.

        Text:
        {page1.full_text}
        """

        val = self.llm_client.complete(prompt, json_schema={
            "type": "object",
            "properties": {
                "statement_date": {"type": "string", "format": "date"},
                "period_start": {"type": "string", "format": "date"},
                "period_end": {"type": "string", "format": "date"}
            }
        })

        if not val: return None

        try:
            import json
            j = json.loads(val)
            s_date = self._parse_date(j.get("statement_date"), "%Y-%m-%d")
            p_start = self._parse_date(j.get("period_start"), "%Y-%m-%d")
            p_end = self._parse_date(j.get("period_end"), "%Y-%m-%d")

            if s_date or p_start or p_end:
                # Reverse Lookup and Source Tracking using find_text_in_page requires original format?
                # LLM normalized it to YYYY-MM-DD. We can't easily reverse lookup the EXACT string if it changed format.
                # Heuristic: Tag whole page as source (Amber).
                # Or ask LLM to return "extracted_text" snippet?
                # For now, use Amber page-level source.

                def create_source(field_name):
                    return SourceReference(
                        bboxes=[],
                        extraction_method=ExtractionMethod.LLM_FALLBACK,
                        confidence=0.7,
                        raw_text=str(j.get(field_name))
                    )

                if s_date: self.field_sources["statement_date"] = create_source("statement_date")
                if p_start: self.field_sources["period_start"] = create_source("period_start")
                if p_end: self.field_sources["period_end"] = create_source("period_end")

                # Fill gaps
                if s_date and not p_end: p_end = s_date
                if p_end and not s_date: s_date = p_end

                return (s_date, p_start, p_end)
        except:
            pass
        return None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        stmt_date = None
        period_start = None
        period_end = None

        # Tier 1: Regex
        # 1. Search for Statement Date
        stmt_match = self._find_pattern(r"(?:Statement Date:|As of)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if stmt_match:
            d_str = stmt_match.group(1)
            stmt_date = self._parse_date_flexible(d_str)
            if stmt_date:
                _, src = self._track_field(stmt_date, stmt_match, 1)
                if src: self.field_sources["statement_date"] = src

        # 2. Search for Period
        period_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*(?:to|through|-)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if period_match:
            p1 = period_match.group(1)
            p2 = period_match.group(2)
            period_start = self._parse_date_flexible(p1)
            period_end = self._parse_date_flexible(p2)

            if period_start:
                _, src = self._track_field(period_start, period_match, 1)
                if src: self.field_sources["period_start"] = src
            if period_end:
                 _, src = self._track_field(period_end, period_match, 2)
                 if src: self.field_sources["period_end"] = src
        else:
            # Range match logic (Simplified for brevity, keeping orig logic structure)
            range_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}|[A-Za-z]+\s+\d{1,2}),?\s+(\d{4})")
            if range_match:
                 # Reconstruct is hard to track individually without careful span math.
                 # Will skip detailed source tracking for this sub-case for MVP or track whole match.
                 # Tracking whole match for both:
                 _, src = self._track_field(None, range_match, 0)

                 start_part = range_match.group(1)
                 end_part = range_match.group(2)
                 year = range_match.group(3)
                 period_start = self._parse_date_flexible(f"{start_part} {year}")

                 if re.match(r"^\d+$", end_part):
                     month = start_part.split()[0]
                     period_end = self._parse_date_flexible(f"{month} {end_part} {year}")
                 else:
                     period_end = self._parse_date_flexible(f"{end_part} {year}")

                 if src:
                     self.field_sources["period_start"] = src
                     self.field_sources["period_end"] = src

        # Fallback Logic
        if stmt_date and not period_start:
             pass # logic handled below
        if period_end and not stmt_date:
            stmt_date = period_end
            if "period_end" in self.field_sources:
                 self.field_sources["statement_date"] = self.field_sources["period_end"]

        if stmt_date and period_start and period_end:
            return (stmt_date, period_start, period_end)

        # Tier 3: LLM
        if not stmt_date and not period_start:
             llm_dates = self._extract_dates_llm()
             if llm_dates:
                 return llm_dates

        # Return partials if found
        if stmt_date:
             # partial
             return (stmt_date, period_start, period_end)

        return None


    def _parse_positions_from_tables(self) -> List[Position]:
        positions = []
        if not self.tables:
            return []

        for table in self.tables:
            if not table: continue
            headers = [str(h).lower() for h in table[0]]

            # Heuristic for Position table
            if "symbol" not in headers or ("quantity" not in headers and "shares" not in headers):
                continue

            try:
                idx_symbol = headers.index("symbol")
                idx_qty = headers.index("quantity") if "quantity" in headers else headers.index("shares")
                idx_price = headers.index("price") if "price" in headers else -1
                idx_mv = headers.index("market value") if "market value" in headers else -1
                if idx_mv == -1 and "amount" in headers: idx_mv = headers.index("amount")
                if idx_mv == -1 and "value" in headers: idx_mv = headers.index("value")
                if idx_mv == -1 and "current value" in headers: idx_mv = headers.index("current value")
                idx_desc = headers.index("description") if "description" in headers else -1
            except ValueError:
                continue

            for row in table[1:]:
                if len(row) <= max(idx_symbol, idx_qty): continue

                try:
                    qty = self._parse_decimal(row[idx_qty])
                    if qty is None: continue

                    symbol = str(row[idx_symbol])
                    if symbol.lower() in ["total", "account", "subtotal"]: continue

                    price = self._parse_decimal(row[idx_price]) if idx_price >= 0 else Decimal(0)
                    market_value = self._parse_decimal(row[idx_mv]) if idx_mv >= 0 else Decimal(0)
                    desc = str(row[idx_desc]) if idx_desc >= 0 else ""

                    positions.append(Position(
                        symbol=symbol,
                        description=desc,
                        quantity=qty,
                        price=price,
                        market_value=market_value
                    ))
                except Exception:
                    continue

        return positions

    def _parse_positions(self) -> List[Position]:
        # Try table parsing first
        table_pos = self._parse_positions_from_tables()
        if table_pos:
            return table_pos

        # Basic position parsing (can be enhanced later if needed, focusing on Transactions for MVP)
        positions = []
        headers = ["Account Holdings", "Portfolio Summary", "Investment Summary", "Positions"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, r"^Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Example: AAPL Apple Inc 100 150.00 15000.00
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    market_value = self._parse_decimal(parts[-1])
                    if market_value is not None:
                        price = self._parse_decimal(parts[-2])
                        quantity = self._parse_decimal(parts[-3])

                        if quantity is not None and price is not None:
                            symbol = parts[0]
                            description = " ".join(parts[1:-3])

                            if symbol.lower() not in ["symbol", "total", "account", "subtotal"]:
                                positions.append(Position(
                                    symbol=symbol,
                                    quantity=quantity,
                                    price=price,
                                    market_value=market_value,
                                    description=description
                                ))
                except:
                    continue
        return positions

    def _parse_transactions_from_tables(self) -> List[Transaction]:
        transactions = []
        if not self.tables:
            return []

        for table in self.tables:
            # Check headers in first row
            if not table: continue
            headers = [str(h).lower() for h in table[0]]

            # Simple heuristic for identifying Activity/Transaction tables
            if "date" not in headers or "amount" not in headers:
                continue

            try:
                idx_date = headers.index("date")
                idx_action = headers.index("action") if "action" in headers else -1
                idx_amount = headers.index("amount")
                idx_symbol = headers.index("symbol") if "symbol" in headers else -1
                idx_desc = headers.index("description") if "description" in headers else -1
                idx_qty = headers.index("quantity") if "quantity" in headers else -1
                idx_price = headers.index("price") if "price" in headers else -1
            except ValueError:
                continue

            for row in table[1:]:
                # Ensure row has enough columns
                if len(row) <= max(idx_date, idx_amount): continue

                try:
                    # Clean date string if needed, existing _parse_date handles formats
                    date_val = self._parse_date(row[idx_date])
                    if not date_val: continue

                    amount = self._parse_decimal(row[idx_amount])
                    if amount is None: continue

                    action_str = str(row[idx_action]).upper() if idx_action >= 0 else "UNKNOWN"
                    symbol = str(row[idx_symbol]) if idx_symbol >= 0 else None
                    desc = str(row[idx_desc]) if idx_desc >= 0 else ""
                    qty = self._parse_decimal(row[idx_qty]) if idx_qty >= 0 else None
                    price = self._parse_decimal(row[idx_price]) if idx_price >= 0 else None

                    # Map Type
                    tx_type = TransactionType.OTHER
                    if "BUY" in action_str: tx_type = TransactionType.BUY
                    elif "SELL" in action_str: tx_type = TransactionType.SELL
                    elif "DIVIDEND" in action_str: tx_type = TransactionType.DIVIDEND
                    elif "INTEREST" in action_str: tx_type = TransactionType.INTEREST
                    elif "FEE" in action_str: tx_type = TransactionType.FEE

                    transactions.append(Transaction(
                        date=date_val,
                        type=tx_type,
                        description=desc,
                        amount=amount,
                        symbol=symbol,
                        quantity=qty,
                        price=price
                    ))
                except Exception:
                    continue

        return transactions

    def _parse_transactions(self) -> List[Transaction]:
        # Try table parsing first
        table_txs = self._parse_transactions_from_tables()
        if table_txs:
            return table_txs

        transactions = []

        # Priority list of headers to look for
        headers = ["Transaction Detail", "Activity Detail", "Investment Detail", "Account Activity"]

        # Find section range in self.text
        section_start = -1
        section_end = -1
        found_header = None

        for header in headers:
            start_match = self._find_pattern(header)
            if start_match:
                section_start = start_match.start() # Or end? Usually text follows header.
                # Actually _find_section finds lines AFTER the header match.
                # Let's align with _find_section logic: start at match start or end?
                # _find_section: start_idx = self.text.find(start_match.group(0)) ... remaining = text[start_idx:]
                # It includes the header line in the remaining text?
                # No, split('\n') and filter.

                # Let's locate the exact text block.
                section_start = start_match.start()

                # Find end
                remaining_text = self.text[section_start:]
                end_match = self._find_pattern(r"^(Total|Investment Detail|Account Holdings)", remaining_text)
                if end_match:
                    section_end = section_start + end_match.start()
                else:
                    section_end = len(self.text)

                found_header = header
                break

        if section_start == -1:
            logger.warning("No transaction section found.")
            return []

        # Get the section text raw
        section_raw = self.text[section_start:section_end]

        # Iterate matches in this section

        # Regex Patterns
        # A. Trade
        pat_trade = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<action>Bought|Buy|Sold|Sell|Reinvestment)\s+(?:(?P<symbol_pre>[A-Z]{1,5})\s+)?(?P<quantity>[\d,.]+)\s+(?:Shares?\s+)?(?:(?P<symbol_post>[A-Z]{1,5})\s+)?(?:@\s*(?P<price>[\d,.]+)\s+)?(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE | re.MULTILINE
        )
        # B. Dividend
        pat_div = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<action>Qualified Dividend|Cash Dividend|Dividend Received)\s+(?P<symbol>[A-Z]{1,5})?\s*(?P<description>.*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE | re.MULTILINE
        )
        # C. Fees/Interest
        pat_fee_int = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<description>(?:Bank Interest|Margin Interest|Service Fee|Wire Fee).*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE | re.MULTILINE
        )
        # D. Transfers
        pat_transfer = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<description>(?:Wire Transfer|MoneyLink Transfer|Journal(?:ed)?|Transfer)\s*(?:In|Out|From|To)?.*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE | re.MULTILINE
        )

        # Helper to process a regex match iteration
        # We need to find ALL matches in expected chronological order or line by line.
        # "Raw line" iteration is safer to preserve "Description appending" logic.

        # We will split section_raw by newline but keep tracking offset
        lines = section_raw.split('\n')
        current_offset = section_start

        last_tx = None

        for line in lines:
            line_len = len(line)
            stripped = line.strip()

            # Calculate strip offset
            leading_spaces = len(line) - len(line.lstrip())
            line_start_global = current_offset + leading_spaces

            # Update offset for next loop (line + newline)
            current_offset += line_len + 1

            if not stripped: continue

            # Check for date at start
            # We match strictly on the stripped line
            pat_date_start = re.compile(r"^(\d{2}/\d{2}/\d{2,4})")
            date_match = pat_date_start.match(stripped)

            if date_match:
                # Parse Date
                date_str = date_match.group(1)
                date_val = self._parse_date(date_str, "%m/%d/%y") or self._parse_date(date_str, "%m/%d/%Y")

                # Capture Source for Date
                date_span = date_match.span(1) # span in stripped line
                # Global span
                d_start = line_start_global + date_span[0]
                d_end = line_start_global + date_span[1]
                date_source = self._get_source_for_range(d_start, d_end)

                if not date_val:
                    continue

                tx = None
                source_map = {}
                if date_source:
                    source_map["date"] = date_source

                # 1. Trade
                m_trade = pat_trade.search(stripped)
                if m_trade:
                    action = m_trade.group("action").upper()
                    if "BUY" in action or "BOUGHT" in action or "REINVEST" in action:
                        tx_type = TransactionType.BUY
                    else:
                        tx_type = TransactionType.SELL

                    # Symbol
                    sym_grp = "symbol_pre" if m_trade.group("symbol_pre") else "symbol_post"
                    symbol = m_trade.group(sym_grp)
                    if symbol:
                        val, src = self._track_field(symbol, m_trade, m_trade.re.groupindex[sym_grp])
                        # _track_field expects a match object and group index?
                        # No, _track_field(value_obj, match, match_group_index).
                        # But `m_trade` search was on `stripped`. `match.span` is local to stripped.
                        # `_track_field` assumes global match if used naively??
                        # Wait, `_track_field` implementation uses `match.span()`.
                        # If I pass `m_trade`, it gives local span (0, 10).
                        # `_track_field` calls `_get_source_for_range(0, 10)`.
                        # This is WRONG. It needs global offset.
                        # I must manually calculate global offsets here.

                        s_span = m_trade.span(sym_grp)
                        s_global_start = line_start_global + s_span[0]
                        s_global_end = line_start_global + s_span[1]
                        source_map["symbol"] = self._get_source_for_range(s_global_start, s_global_end)

                    # Quantity
                    qty_str = m_trade.group("quantity")
                    quantity = self._parse_decimal(qty_str)
                    if qty_str:
                         q_span = m_trade.span("quantity")
                         source_map["quantity"] = self._get_source_for_range(line_start_global + q_span[0], line_start_global + q_span[1])

                    # Price
                    price_str = m_trade.group("price")
                    price = self._parse_decimal(price_str)
                    if price_str:
                        p_span = m_trade.span("price")
                        source_map["price"] = self._get_source_for_range(line_start_global + p_span[0], line_start_global + p_span[1])

                    # Amount
                    amt_str = m_trade.group("amount")
                    amount = self._parse_decimal(amt_str)
                    if amt_str:
                        a_span = m_trade.span("amount")
                        source_map["amount"] = self._get_source_for_range(line_start_global + a_span[0], line_start_global + a_span[1])

                    tx = Transaction(
                        date=date_val,
                        type=tx_type,
                        description=stripped,
                        amount=amount,
                        symbol=symbol,
                        quantity=quantity,
                        price=price,
                        source_map=source_map
                    )

                # 2. Dividend
                if not tx:
                    m_div = pat_div.search(stripped)
                    if m_div:
                        symbol = m_div.group("symbol")
                        # desc_part = m_div.group("description") # usage not shown in orig code
                        amount = self._parse_decimal(m_div.group("amount"))

                        if symbol:
                            span = m_div.span("symbol")
                            source_map["symbol"] = self._get_source_for_range(line_start_global + span[0], line_start_global + span[1])

                        if m_div.group("amount"):
                            span = m_div.span("amount")
                            source_map["amount"] = self._get_source_for_range(line_start_global + span[0], line_start_global + span[1])

                        tx = Transaction(
                            date=date_val,
                            type=TransactionType.DIVIDEND,
                            description=stripped,
                            amount=amount,
                            symbol=symbol,
                            source_map=source_map
                        )

                # 3. Fees
                if not tx:
                    m_fee = pat_fee_int.search(stripped)
                    if m_fee:
                        desc = m_fee.group("description")
                        amount = self._parse_decimal(m_fee.group("amount"))
                        tx_type = TransactionType.INTEREST if "INTEREST" in desc.upper() else TransactionType.FEE

                        if m_fee.group("amount"):
                            span = m_fee.span("amount")
                            source_map["amount"] = self._get_source_for_range(line_start_global + span[0], line_start_global + span[1])

                        tx = Transaction(
                            date=date_val,
                            type=tx_type,
                            description=stripped,
                            amount=amount,
                            source_map=source_map
                        )

                # 4. Transfers
                if not tx:
                    m_trans = pat_transfer.search(stripped)
                    if m_trans:
                        desc = m_trans.group("description")
                        amount = self._parse_decimal(m_trans.group("amount"))
                        is_out = (amount and amount < 0) or "OUT" in desc.upper() or "TO" in desc.upper()
                        tx_type = TransactionType.TRANSFER_OUT if is_out else TransactionType.TRANSFER_IN

                        if m_trans.group("amount"):
                            span = m_trans.span("amount")
                            source_map["amount"] = self._get_source_for_range(line_start_global + span[0], line_start_global + span[1])

                        tx = Transaction(
                            date=date_val,
                            type=tx_type,
                            description=stripped,
                            amount=amount,
                            source_map=source_map
                        )

                if tx:
                    transactions.append(tx)
                    last_tx = tx
                else:
                    logger.warning(f"Unmatched transaction line: {stripped}")

            else:
                 # Wrapped description
                if last_tx:
                    last_tx.description += " " + stripped
                    # We could loosely track source for full description but it's complex (multi-line).
                    # MVP: Transaction Description source is usually the first line or not strictly tracked (as it's derived).
                    # If we need it, we'd add to the source_map['description'] list of bboxes.
                    pass
                else:
                    pass

        return transactions

