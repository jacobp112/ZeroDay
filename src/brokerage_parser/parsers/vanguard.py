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
        stmt_date = None
        period_start = None
        period_end = None

        # 1. Statement Date
        # "Statement date: January 31, 2023"
        stmt_match = self._find_pattern(r"Statement date:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if stmt_match:
            stmt_date = self._parse_date_flexible(stmt_match.group(1))

        # 2. Period
        # "For the period January 1, 2023, to January 31, 2023"
        # "Account activity from 01/01/2023 to 01/31/2023"

        # Try numeric range
        num_match = self._find_pattern(r"Account activity from\s*(\d{2}/\d{2}/\d{2,4})\s*to\s*(\d{2}/\d{2}/\d{2,4})")
        if num_match:
             period_start = self._parse_date_flexible(num_match.group(1))
             period_end = self._parse_date_flexible(num_match.group(2))
        else:
            # Text range
            # "For the period January 1, 2023, to January 31, 2023"
            text_match = self._find_pattern(r"(?:For the period|Account activity from)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}),?\s*(?:to|through)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
            if text_match:
                period_start = self._parse_date_flexible(text_match.group(1))
                period_end = self._parse_date_flexible(text_match.group(2))
            else:
                 # Single year case
                 range_match = self._find_pattern(r"(?:For the period|Account activity from)\s*([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}|[A-Za-z]+\s+\d{1,2}),?\s+(\d{4})")
                 if range_match:
                     start_part = range_match.group(1)
                     end_part = range_match.group(2)
                     year = range_match.group(3)

                     period_start = self._parse_date_flexible(f"{start_part} {year}")
                     if re.match(r"^\d+$", end_part):
                          month = start_part.split()[0]
                          period_end = self._parse_date_flexible(f"{month} {end_part} {year}")
                     else:
                         period_end = self._parse_date_flexible(f"{end_part} {year}")

        # Fallback
        if stmt_date and not period_start:
            return (stmt_date, stmt_date, stmt_date)

        if period_end and not stmt_date:
            stmt_date = period_end

        if stmt_date and period_start and period_end:
            return (stmt_date, period_start, period_end)

        return None

    def _parse_positions(self) -> List[Position]:
        positions = []
        headers = ["Investment Holdings", "Your Investments", "Fund Holdings", "Balances"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, r"^Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Example: Vanguard 500 Index Fund Admiral Shares VFIAX 100.000 $400.00 $40,000.00
        # Or just: Vanguard 500 Index Fund 100.000 ...

        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # Look for numerical values at end
                    market_value = self._parse_decimal(parts[-1])
                    if market_value is not None:
                        # Work backwards
                        # Price is usually -2 or -3
                        price = self._parse_decimal(parts[-2])
                        quantity = self._parse_decimal(parts[-3])

                        # Sometimes price is missing if it's just cash/sweep
                        if quantity is None and price is not None:
                            # Maybe parts[-3] failed but parts[-2] is actually quantity?
                            # Vanguard format varies.
                            pass

                        if quantity is not None and price is not None:
                            # Extract Name/Symbol
                            # Everything before the numbers
                            name_parts = parts[:-3]
                            full_name = " ".join(name_parts)

                            # Check if last part of name is a ticker symbol (3-5 CAPS)
                            symbol = full_name
                            possible_ticker = name_parts[-1] if name_parts else ""
                            if re.match(r"^[A-Z]{3,5}$", possible_ticker):
                                symbol = possible_ticker

                            positions.append(Position(
                                symbol=symbol,
                                quantity=quantity,
                                price=price,
                                market_value=market_value,
                                description=full_name
                            ))
                except:
                    continue
        return positions

    def _parse_transactions_from_tables(self) -> List[Transaction]:
        transactions = []
        tx_tables = self._get_tables_by_type("transactions")

        for table in tx_tables:
            start_row = 1
            header_row = [str(c).lower() for c in table[0]]

            # Column Mapping
            col_map = {
                "date": -1,
                "type": -1,
                "symbol": -1,
                "description": -1,
                "amount": -1
            }

            for idx, col_text in enumerate(header_row):
                if "date" in col_text and "trade" in col_text: col_map["date"] = idx
                elif "date" in col_text and col_map["date"] == -1: col_map["date"] = idx
                elif "type" in col_text or "transaction" in col_text: col_map["type"] = idx
                elif "symbol" in col_text: col_map["symbol"] = idx
                elif "description" in col_text or "name" in col_text or "investment" in col_text: col_map["description"] = idx
                elif "amount" in col_text or "principal" in col_text: col_map["amount"] = idx

            # Retry next row
            if col_map["date"] == -1 and len(table) > 1:
                header_row = [str(c).lower() for c in table[1]]
                for idx, col_text in enumerate(header_row):
                    if "date" in col_text and "trade" in col_text: col_map["date"] = idx
                    elif "date" in col_text and col_map["date"] == -1: col_map["date"] = idx
                    elif "type" in col_text or "transaction" in col_text: col_map["type"] = idx
                    elif "symbol" in col_text: col_map["symbol"] = idx
                    elif "description" in col_text or "name" in col_text or "investment" in col_text: col_map["description"] = idx
                    elif "amount" in col_text or "principal" in col_text: col_map["amount"] = idx
                start_row = 2

            # Fallback
            if col_map["date"] == -1:
                col_map["date"] = 0
                col_map["type"] = 1
                col_map["symbol"] = 2
                col_map["description"] = 3
                col_map["amount"] = -1

            for i in range(start_row, len(table)):
                row = table[i]
                if not row or len(row) < 3: continue

                # Date
                date_val = None
                date_str = str(row[col_map["date"]]).strip() if col_map["date"] < len(row) else ""
                date_val = self._parse_date(date_str, "%m/%d/%Y")
                if not date_val: date_val = self._parse_date(date_str, "%m/%d/%y")

                if not date_val: continue

                # Amount
                amount_idx = col_map["amount"]
                if amount_idx == -1: amount_idx = len(row) - 1

                amount_str = str(row[amount_idx]).strip() if amount_idx < len(row) else ""
                amount = self._parse_decimal(amount_str) or Decimal("0.0")

                # Description/Name
                desc_idx = col_map["description"]
                desc_str = str(row[desc_idx]) if desc_idx != -1 and desc_idx < len(row) else ""

                # Type from column or infer
                type_idx = col_map["type"]
                type_str = str(row[type_idx]).upper() if type_idx != -1 and type_idx < len(row) else ""

                full_desc = f"{type_str} {desc_str}".strip()

                # Determine Type
                tx_type = None
                combined = (type_str + " " + desc_str).upper()

                if "BUY" in combined or "PURCHASE" in combined or "REINVESTMENT" in combined:
                    tx_type = TransactionType.BUY
                elif "SELL" in combined or "REDEMPTION" in combined or "SALE" in combined:
                    tx_type = TransactionType.SELL
                elif "DIVIDEND" in combined:
                    tx_type = TransactionType.DIVIDEND
                elif "EXCHANGE IN" in combined:
                    tx_type = TransactionType.TRANSFER_IN
                elif "EXCHANGE OUT" in combined:
                    tx_type = TransactionType.TRANSFER_OUT

                if not tx_type: continue

                # Symbol
                symbol = "UNKNOWN"
                sym_idx = col_map["symbol"]
                if sym_idx != -1 and sym_idx < len(row):
                     val = str(row[sym_idx]).strip().upper()
                     if len(val) >= 3 and len(val) <= 5 and val.isalpha():
                         symbol = val

                if symbol == "UNKNOWN":
                    # Heuristic from name?
                    pass

                transactions.append(Transaction(
                    date=date_val,
                    type=tx_type,
                    description=full_desc,
                    amount=amount,
                    symbol=symbol
                ))
        return transactions

    def _parse_transactions(self) -> List[Transaction]:
        # 1. Try Table Extraction
        table_txs = self._parse_transactions_from_tables()
        if table_txs:
             return table_txs

        # 2. Fallback
        transactions = []
        headers = ["Transaction Summary", "Account Activity", "Activity Detail"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, r"^Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Date pattern
        date_pattern = r"(\d{2}/\d{2}/\d{2,4})"
        current_date = None

        for line in lines:
            # Check for date at start of line
            date_match = re.search(date_pattern, line)
            if date_match and line.strip().startswith(date_match.group(1)):
                parsed = self._parse_date(date_match.group(1), "%m/%d/%Y")
                if not parsed:
                    parsed = self._parse_date(date_match.group(1), "%m/%d/%y")
                if parsed:
                    current_date = parsed

            if current_date:
                upper_line = line.upper()
                # Skip header lines repeating date
                if "SETTLEMENT DATE" in upper_line:
                    continue

                tx_type = None
                description = line

                if "BUY" in upper_line or "PURCHASE" in upper_line:
                    tx_type = TransactionType.BUY
                elif "REINVESTMENT" in upper_line:
                     tx_type = TransactionType.BUY
                elif "SELL" in upper_line or "SALE" in upper_line or "REDEMPTION" in upper_line:
                     tx_type = TransactionType.SELL
                elif "DIVIDEND" in upper_line and "REINVESTMENT" not in upper_line:
                     tx_type = TransactionType.DIVIDEND
                elif "EXCHANGE IN" in upper_line:
                     tx_type = TransactionType.TRANSFER_IN
                elif "EXCHANGE OUT" in upper_line:
                     tx_type = TransactionType.TRANSFER_OUT

                if tx_type:
                    # Amount is usually the last number
                    parts = line.split()
                    amount = Decimal("0.0")
                    for part in reversed(parts):
                        val = self._parse_decimal(part)
                        if val is not None:
                            amount = val
                            break

                    # Symbol/Fund Name Extraction
                    # Vanguard places name after date usually, or at start if date was on prev line
                    # Logic: Remove date, remove keywords, what's left is often name?
                    # Simple MVP: Use full description as symbol if no obvious ticker

                    # Try to extract ticker if present in parens or at end of text block before numbers
                    # E.g. "Buy Vanguard 500 Index (VFIAX)"
                    symbol = "UNKNOWN"
                    ticker_match = re.search(r"\b([A-Z]{3,5})\b", line)
                    if ticker_match:
                         # verify it's not a keyword
                         candidate = ticker_match.group(1)
                         if candidate not in ["BUY", "SELL", "DATE", "CORP", "INC", "FUND"]:
                             symbol = candidate

                    if symbol == "UNKNOWN":
                        # Fallback to name extraction (simplified)
                        # Just take the first few words that aren't date or numbers
                        clean_parts = [p for p in parts if not re.match(r"[\d/.,$]+", p) and p.upper() not in ["BUY", "SELL", "PURCHASE", "REDEMPTION", "EXCHANGE", "IN", "OUT", "DIVIDEND", "REINVESTMENT"]]
                        if clean_parts:
                            # use first 3 words as symbol/name proxy
                            symbol = " ".join(clean_parts[:3])

                    transactions.append(Transaction(
                        date=current_date,
                        type=tx_type,
                        description=line.strip(),
                        amount=amount,
                        symbol=symbol
                    ))
        return transactions
