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
        # Fidelity "Account Number X12-345678" or similar
        # Tightened regex to avoid matching random text
        match = self._find_pattern(r"Account Number\s*([A-Z\d-]{8,})")
        return match.group(1) if match else None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        stmt_date = None
        period_start = None
        period_end = None

        # 1. Statement Date
        # "Statement Date: 01/31/2023" or "January 31, 2023"
        stmt_match = self._find_pattern(r"Statement Date:?\s*(\d{2}/\d{2}/\d{2,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if stmt_match:
            stmt_date = self._parse_date_flexible(stmt_match.group(1))

        # 2. Period
        # "Account Activity for 01/01/2023 - 01/31/2023"
        # "Period: January 1, 2023 through January 31, 2023"

        # Numeric range 01/01/2023 - 01/31/2023
        num_range_match = self._find_pattern(r"(?:Account Activity for|Period:)\s*(\d{2}/\d{2}/\d{2,4})\s*-\s*(\d{2}/\d{2}/\d{2,4})")
        if num_range_match:
             period_start = self._parse_date_flexible(num_range_match.group(1))
             period_end = self._parse_date_flexible(num_range_match.group(2))
        else:
            # Text range "January 1 ... January 31 ..."
            # Reuse logic similar to Schwab if needed, or specific Fidelity text patterns
            text_range_match = self._find_pattern(r"(?:Period:)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*(?:through|-|to)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
            if text_range_match:
                period_start = self._parse_date_flexible(text_range_match.group(1))
                period_end = self._parse_date_flexible(text_range_match.group(2))
            else:
                 # Single year case? "January 1 - 31, 2023"
                 range_match = self._find_pattern(r"(?:Period:)\s*([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}|[A-Za-z]+\s+\d{1,2}),?\s+(\d{4})")
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
        # Try common Fidelity position headers
        headers = ["Holdings", "Your Account Summary", "Core Account"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, "Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Simple position parsing strategy: look for lines with Symbol, Qty, Price, Value
        # Example: AAPL 100 150.00 15000.00
        # Or: CASH ...

        for line in lines:
            parts = line.split()
            # Heuristic: Valid position lines usually have a symbol and at least 3 numbers (Qty, Price, Value)
            # This is a simplification for the MVP
            if len(parts) >= 4:
                try:
                    # Assume last 3 are numbers
                    value = self._parse_decimal(parts[-1])
                    price = self._parse_decimal(parts[-2])
                    qty = self._parse_decimal(parts[-3])

                    if value is not None and price is not None and qty is not None:
                        # Symbol is usually the first item, or first few if description is long
                        symbol = parts[0]
                        # Filter out common headers/junk
                        if symbol.lower() not in ["symbol", "total", "subtotal", "account"]:
                            positions.append(Position(
                                symbol=symbol,
                                quantity=qty,
                                price=price,
                                market_value=value,
                                description=" ".join(parts[1:-3])
                            ))
                except:
                    continue

        return positions

    def _parse_transactions_from_tables(self) -> List[Transaction]:
        transactions = []
        tx_tables = self._get_tables_by_type("transactions")

        for table in tx_tables:
            # Assume header is row 0 or 1
            start_row = 1
            header_row = [str(c).lower() for c in table[0]]

            # Column Mapping
            col_map = {
                "date": -1,
                "action": -1,
                "symbol": -1,
                "description": -1,
                "amount": -1
            }

            for idx, col_text in enumerate(header_row):
                if "date" in col_text: col_map["date"] = idx
                elif "action" in col_text or "type" in col_text: col_map["action"] = idx
                elif "symbol" in col_text: col_map["symbol"] = idx
                elif "description" in col_text: col_map["description"] = idx
                elif "amount" in col_text: col_map["amount"] = idx

            # If map is poor, try next row
            if col_map["date"] == -1 and len(table) > 1:
                header_row = [str(c).lower() for c in table[1]]
                for idx, col_text in enumerate(header_row):
                   if "date" in col_text: col_map["date"] = idx
                   elif "action" in col_text or "type" in col_text: col_map["action"] = idx
                   elif "symbol" in col_text: col_map["symbol"] = idx
                   elif "description" in col_text: col_map["description"] = idx
                   elif "amount" in col_text: col_map["amount"] = idx
                start_row = 2

            # Fallback
            if col_map["date"] == -1:
                col_map["date"] = 0
                col_map["action"] = 1
                col_map["symbol"] = 2
                col_map["description"] = 3
                col_map["amount"] = -1

            for i in range(start_row, len(table)):
                row = table[i]
                if not row or len(row) < 3: continue

                # Date
                date_val = None
                # Fidelity dates are clean usually
                date_str = str(row[col_map["date"]]).strip() if col_map["date"] < len(row) else ""
                date_val = self._parse_date(date_str, "%m/%d/%Y")
                if not date_val: date_val = self._parse_date(date_str, "%m/%d/%y")

                if not date_val: continue

                # Amount
                amount_idx = col_map["amount"]
                if amount_idx == -1: amount_idx = len(row) - 1

                amount_str = str(row[amount_idx]).strip() if amount_idx < len(row) else ""
                amount = self._parse_decimal(amount_str) or Decimal("0.0")

                # Action/Desc
                action_idx = col_map["action"]
                action_str = str(row[action_idx]).upper() if action_idx != -1 and action_idx < len(row) else ""

                desc_idx = col_map["description"]
                desc_str = str(row[desc_idx]) if desc_idx != -1 and desc_idx < len(row) else ""

                full_desc = f"{action_str} {desc_str}".strip()

                # Type mapping
                tx_type = None
                if "BOUGHT" in action_str or "BUY" in action_str or "REINVESTMENT" in action_str:
                    tx_type = TransactionType.BUY
                elif "SOLD" in action_str or "SELL" in action_str:
                    tx_type = TransactionType.SELL
                elif "DIVIDEND" in action_str:
                    tx_type = TransactionType.DIVIDEND
                elif "INTEREST" in action_str:
                    tx_type = TransactionType.INTEREST
                else:
                    # Fallback to description check
                    if "DIVIDEND" in desc_str.upper(): tx_type = TransactionType.DIVIDEND
                    elif "FEE" in desc_str.upper(): tx_type = TransactionType.FEE

                if not tx_type: continue

                # Symbol
                symbol = "UNKNOWN"
                sym_idx = col_map["symbol"]
                if sym_idx != -1 and sym_idx < len(row):
                     symbol = str(row[sym_idx]).strip().upper()

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
        headers = ["Activity", "Investment Activity", "Transaction History"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, "Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Regex for date MM/DD/YY or MM/DD/YYYY
        date_pattern = r"(\d{2}/\d{2}/\d{2,4})"

        current_date = None

        for line in lines:
            date_match = re.search(date_pattern, line)
            if date_match:
                parsed_date = self._parse_date(date_match.group(1), "%m/%d/%y")
                if not parsed_date:
                     parsed_date = self._parse_date(date_match.group(1), "%m/%d/%Y")

                if parsed_date:
                    current_date = parsed_date

            if current_date:
                upper_line = line.upper()
                tx_type = None

                if "YOU BOUGHT" in upper_line:
                    tx_type = TransactionType.BUY
                elif "YOU SOLD" in upper_line:
                    tx_type = TransactionType.SELL
                elif "DIVIDEND RECEIVED" in upper_line:
                    tx_type = TransactionType.DIVIDEND
                elif "REINVESTMENT" in upper_line:
                    # User requested mapping Reinvestment to BUY
                    tx_type = TransactionType.BUY

                if tx_type:
                    symbol = "UNKNOWN"
                    parts = line.split()
                    upper_parts = [p.upper() for p in parts]

                    try:
                        if tx_type == TransactionType.BUY and "BOUGHT" in upper_parts:
                            idx = upper_parts.index("BOUGHT")
                            if idx + 1 < len(parts):
                                symbol = parts[idx + 1]
                        elif tx_type == TransactionType.SELL and "SOLD" in upper_parts:
                            idx = upper_parts.index("SOLD")
                            if idx + 1 < len(parts):
                                symbol = parts[idx + 1]
                        elif tx_type == TransactionType.DIVIDEND and "RECEIVED" in upper_parts:
                            idx = upper_parts.index("RECEIVED")
                            if idx + 1 < len(parts):
                                symbol = parts[idx + 1]
                        elif tx_type == TransactionType.BUY and "REINVESTMENT" in upper_parts:
                             idx = upper_parts.index("REINVESTMENT")
                             if idx + 1 < len(parts):
                                symbol = parts[idx + 1]
                    except ValueError:
                        pass

                    # Extract Amount - Look for numbers
                    amount = Decimal("0.0")
                    for part in reversed(parts):
                        d = self._parse_decimal(part)
                        if d is not None:
                            amount = d
                            break

                    if symbol != "UNKNOWN":
                        transactions.append(Transaction(
                            date=current_date,
                            type=tx_type,
                            description=line.strip(),
                            amount=amount,
                            symbol=symbol
                        ))
        return transactions
