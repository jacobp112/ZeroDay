from typing import List, Optional
from datetime import date
from decimal import Decimal
from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import Transaction, Position, TransactionType, AccountSummary
import re
import logging

logger = logging.getLogger(__name__)

class SchwabParser(Parser):
    def get_broker_name(self) -> str:
        return "Schwab"

    def _parse_account_number(self) -> Optional[str]:
        # Example pattern: "Account Number: 1234-5678"
        match = self._find_pattern(r"Account Number:?\s*([\d-]+)")
        return match.group(1) if match else None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        stmt_date = None
        period_start = None
        period_end = None

        # 1. Search for Statement Date
        # "Statement Date: January 31, 2023" or "As of January 31, 2023"
        stmt_match = self._find_pattern(r"(?:Statement Date:|As of)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if stmt_match:
            stmt_date = self._parse_date_flexible(stmt_match.group(1))

        # 2. Search for Period
        # "Statement Period: January 1, 2023 to January 31, 2023"
        # "For the period January 1 through January 31, 2023"

        # Try full start/end pattern first
        period_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*(?:to|through|-)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if period_match:
            period_start = self._parse_date_flexible(period_match.group(1))
            period_end = self._parse_date_flexible(period_match.group(2))
        else:
            # Try single year range: "January 1 - 31, 2023"
            range_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}|[A-Za-z]+\s+\d{1,2}),?\s+(\d{4})")
            if range_match:
                start_part = range_match.group(1) # "January 1"
                end_part = range_match.group(2)   # "31" or "January 31"
                year = range_match.group(3)       # "2023"

                period_start = self._parse_date_flexible(f"{start_part} {year}")

                if re.match(r"^\d+$", end_part):
                     # just DD, need month from start
                     month = start_part.split()[0]
                     period_end = self._parse_date_flexible(f"{month} {end_part} {year}")
                else:
                    period_end = self._parse_date_flexible(f"{end_part} {year}")

        # Fallback Logic
        if stmt_date and not period_start:
            return (stmt_date, stmt_date, stmt_date)

        if period_end and not stmt_date:
            stmt_date = period_end

        if stmt_date and period_start and period_end:
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
        lines = []

        # Find the first matching section
        for header in headers:
            # Look for section ending with "Total" or next header like "Investment Detail"
            found_lines = self._find_section(header, r"^(Total|Investment Detail|Account Holdings)")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            logger.warning("No transaction section found.")
            return []

        current_date = None
        current_description_buffer = [] # To handle multi-line descriptions if needed

        # Regex Patterns

        # A. Trade (Buy/Sell/Reinvest)
        # Matches: "Bought 100 Shares AAPL @ 150.00 -15000.00"
        # Matches: "Sell 5 Shares MSFT 750.00" (implied price or missing)
        # Matches: "Reinvestment AAPL 0.07 Shares @ 150.00 -10.50"
        pat_trade = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<action>Bought|Buy|Sold|Sell|Reinvestment)\s+(?:(?P<symbol_pre>[A-Z]{1,5})\s+)?(?P<quantity>[\d,.]+)\s+(?:Shares?\s+)?(?:(?P<symbol_post>[A-Z]{1,5})\s+)?(?:@\s*(?P<price>[\d,.]+)\s+)?(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE
        )
        # Note on symbol placement: "Buy 10 Shares AAPL" (symbol post) vs "Reinvestment AAPL 0.07 Shares" (symbol pre)

        # B. Dividend: 01/15/23 Qualified Dividend AAPL 150.25
        # Symbol might be implicit or in description
        pat_div = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<action>Qualified Dividend|Cash Dividend|Dividend Received)\s+(?P<symbol>[A-Z]{1,5})?\s*(?P<description>.*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE
        )

        # C. Fees/Interest: 01/25/23 Bank Interest 4.12
        pat_fee_int = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<description>(?:Bank Interest|Margin Interest|Service Fee|Wire Fee).*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE
        )

        # D. Transfers: 01/20/23 Wire Transfer Out -5,000.00
        # Added "Journaled" support
        pat_transfer = re.compile(
            r"^(?P<date>\d{2}/\d{2}/\d{2,4})\s+(?P<description>(?:Wire Transfer|MoneyLink Transfer|Journal(?:ed)?|Transfer)\s*(?:In|Out|From|To)?.*?)\s+(?P<amount>-?[\d,]+\.\d{2}|\([\d,]+\.\d{2}\))",
            re.IGNORECASE
        )

        # Helper date pattern for line start check
        pat_date_start = re.compile(r"^(\d{2}/\d{2}/\d{2,4})")

        last_tx = None # Keep track of last transaction to append description lines

        for line in lines:
            line = line.strip()
            if not line: continue

            # Check if line starts with a date -> New Transaction
            date_match = pat_date_start.match(line)

            if date_match:
                # Parse Date
                date_str = date_match.group(1)
                date_val = self._parse_date(date_str, "%m/%d/%y") or self._parse_date(date_str, "%m/%d/%Y")

                if not date_val:
                    logger.warning(f"Invalid date format in line: {line}")
                    continue

                tx = None

                # Try Matching Patterns

                # 1. Trade (Buy/Sell/Reinvest)
                m_trade = pat_trade.search(line)
                if m_trade:
                    action = m_trade.group("action").upper()
                    if "BUY" in action or "BOUGHT" in action or "REINVEST" in action:
                        tx_type = TransactionType.BUY
                    else:
                        tx_type = TransactionType.SELL

                    symbol = m_trade.group("symbol_pre") or m_trade.group("symbol_post")
                    quantity = self._parse_decimal(m_trade.group("quantity"))
                    price = self._parse_decimal(m_trade.group("price"))
                    amount = self._parse_decimal(m_trade.group("amount"))

                    tx = Transaction(
                        date=date_val,
                        type=tx_type,
                        description=line,
                        amount=amount,
                        symbol=symbol,
                        quantity=quantity,
                        price=price
                    )

                # 2. Dividend
                if not tx:
                    m_div = pat_div.search(line)
                    if m_div:
                        symbol = m_div.group("symbol")
                        desc_part = m_div.group("description")
                        amount = self._parse_decimal(m_div.group("amount"))

                        # If symbol not captured directly, look in description or fallback
                        if not symbol:
                            # Try finding ticker in description if missing
                            # Simple heuristic: look for last word if it's ALL CAPS?
                            # Or just leave None if ambiguous.
                            # For "Qualified Dividend AAPL", regex catches AAPL as symbol.
                            pass

                        tx = Transaction(
                            date=date_val,
                            type=TransactionType.DIVIDEND,
                            description=line,
                            amount=amount,
                            symbol=symbol
                        )

                # 3. Fees / Interest
                if not tx:
                    m_fee = pat_fee_int.search(line)
                    if m_fee:
                        desc = m_fee.group("description")
                        amount = self._parse_decimal(m_fee.group("amount"))

                        tx_type = TransactionType.INTEREST if "INTEREST" in desc.upper() else TransactionType.FEE

                        tx = Transaction(
                            date=date_val,
                            type=tx_type,
                            description=line,
                            amount=amount
                        )

                # 4. Transfers
                if not tx:
                    m_trans = pat_transfer.search(line)
                    if m_trans:
                        desc = m_trans.group("description")
                        amount = self._parse_decimal(m_trans.group("amount"))

                        # Classification
                        is_out = (amount and amount < 0) or "OUT" in desc.upper() or "TO" in desc.upper()
                        tx_type = TransactionType.TRANSFER_OUT if is_out else TransactionType.TRANSFER_IN

                        tx = Transaction(
                            date=date_val,
                            type=tx_type,
                            description=line,
                            amount=amount
                        )

                if tx:
                    transactions.append(tx)
                    last_tx = tx
                else:
                    logger.warning(f"Unmatched transaction line: {line}")

            else:
                # Line does NOT start with date -> Wrapped Description or Junk
                if last_tx:
                    # Append to previous description
                    last_tx.description += " " + line
                else:
                    # Ignore junk lines before first transaction
                    pass

        return transactions
