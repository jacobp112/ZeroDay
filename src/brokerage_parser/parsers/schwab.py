from typing import List, Optional
from datetime import date
from decimal import Decimal
from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import Transaction, Position, TransactionType, AccountSummary
import re

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
        # "For the period January 1 - January 31, 2023"

        # Try full start/end pattern first
        period_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*(?:to|-)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})")
        if period_match:
            period_start = self._parse_date_flexible(period_match.group(1))
            period_end = self._parse_date_flexible(period_match.group(2))
        else:
            # Try single year range: "January 1 - 31, 2023" or "January 1 - January 31, 2023" (if year at end)
            # This regex captures: Month DD (group 1) ... DD (group 2) ... YYYY (group 3)
            # Be careful not to match too aggressively.
            # "For the period January 1 - 31, 2023"
            range_match = self._find_pattern(r"(?:Statement Period:|For the period)\s*([A-Za-z]+\s+\d{1,2})\s*-\s*(\d{1,2}|[A-Za-z]+\s+\d{1,2}),?\s+(\d{4})")
            if range_match:
                start_part = range_match.group(1) # "January 1"
                end_part = range_match.group(2)   # "31" or "January 31"
                year = range_match.group(3)       # "2023"

                # reconstruct dates
                period_start = self._parse_date_flexible(f"{start_part} {year}")

                if re.match(r"^\d+$", end_part):
                     # just DD, need month from start
                     month = start_part.split()[0]
                     period_end = self._parse_date_flexible(f"{month} {end_part} {year}")
                else:
                    # Includes month
                    period_end = self._parse_date_flexible(f"{end_part} {year}")

        # Fallback Logic
        if stmt_date and not period_start:
            return (stmt_date, stmt_date, stmt_date)

        if period_end and not stmt_date:
            stmt_date = period_end

        if stmt_date and period_start and period_end:
            return (stmt_date, period_start, period_end)

        return None

    def _parse_positions(self) -> List[Position]:
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

        # Example: AAPL Apple Inc 100 $150.00 $15,000.00
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # Look for numerical values at end: Market Value, Price, Quantity?
                    # Or Quantity, Price, Market Value
                    # Schwab often puts Symbol first

                    market_value = self._parse_decimal(parts[-1])
                    if market_value is not None:
                        price = self._parse_decimal(parts[-2])
                        quantity = self._parse_decimal(parts[-3])

                        if quantity is not None and price is not None:
                            symbol = parts[0]
                            # Start description from index 1 up to -3
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
        tx_tables = self._get_tables_by_type("transactions")

        for table in tx_tables:
            # Assume header is row 0 or 1
            start_row = 1
            # Check for header row to map columns
            header_row = [str(c).lower() for c in table[0]]

            # Simple Column Mapping
            col_map = {
                "date": -1,
                "action": -1,
                "symbol": -1,
                "description": -1,
                "quantity": -1,
                "price": -1,
                "amount": -1
            }

            for idx, col_text in enumerate(header_row):
                if "date" in col_text: col_map["date"] = idx
                elif "action" in col_text: col_map["action"] = idx
                elif "symbol" in col_text: col_map["symbol"] = idx
                elif "description" in col_text: col_map["description"] = idx
                elif "quantity" in col_text or "shares" in col_text: col_map["quantity"] = idx
                elif "price" in col_text: col_map["price"] = idx
                elif "amount" in col_text or "total" in col_text: col_map["amount"] = idx

            # If map is empty or poor, try next row
            if col_map["date"] == -1 and len(table) > 1:
                header_row = [str(c).lower() for c in table[1]]
                for idx, col_text in enumerate(header_row):
                   if "date" in col_text: col_map["date"] = idx
                   elif "action" in col_text: col_map["action"] = idx
                   elif "symbol" in col_text: col_map["symbol"] = idx
                   elif "description" in col_text: col_map["description"] = idx
                   elif "quantity" in col_text or "shares" in col_text: col_map["quantity"] = idx
                   elif "price" in col_text: col_map["price"] = idx
                   elif "amount" in col_text or "total" in col_text: col_map["amount"] = idx
                start_row = 2

            # Fallback indices if still not found
            if col_map["date"] == -1:
                col_map["date"] = 0
                col_map["action"] = 1
                col_map["symbol"] = 2
                col_map["description"] = 3
                col_map["amount"] = -1 # look at last column

            for i in range(start_row, len(table)):
                row = table[i]
                if not row or len(row) < 3: continue

                # Date
                date_val = None
                date_str = str(row[col_map["date"]]).strip() if col_map["date"] < len(row) else ""

                # Try standard formats
                date_val = self._parse_date(date_str, "%m/%d/%Y")
                if not date_val:
                     date_val = self._parse_date(date_str, "%m/%d/%y")

                if not date_val:
                    continue # Not a valid transaction row (maybe subheader or footer)

                # Amount
                amount_idx = col_map["amount"]
                if amount_idx == -1:
                    amount_idx = len(row) - 1 # assume last

                amount_str = str(row[amount_idx]).strip() if amount_idx < len(row) else ""
                amount = self._parse_decimal(amount_str) or Decimal("0.0")

                # Action / Type
                action_idx = col_map["action"]
                action_str = str(row[action_idx]).upper() if action_idx != -1 and action_idx < len(row) else ""

                # Combine description if needed
                desc_idx = col_map["description"]
                desc_str = str(row[desc_idx]) if desc_idx != -1 and desc_idx < len(row) else ""

                full_desc = f"{action_str} {desc_str}".strip()

                # Determine Type
                tx_type = self._determine_transaction_type(full_desc, amount)
                if not tx_type:
                     continue

                # Symbol
                symbol = "UNKNOWN"
                sym_idx = col_map["symbol"]
                if sym_idx != -1 and sym_idx < len(row):
                     symbol = str(row[sym_idx]).strip().upper()

                if not symbol or symbol == "UNKNOWN":
                     # heuristics on description
                     pass # keep existing symbol logic if needed or accept UNKNOWN

                transactions.append(Transaction(
                    date=date_val,
                    type=tx_type,
                    description=full_desc,
                    amount=amount,
                    symbol=symbol
                ))

        return transactions

    def _determine_transaction_type(self, text: str, amount: Decimal) -> Optional[TransactionType]:
        text = text.upper()
        if "BUY" in text: return TransactionType.BUY
        if "SELL" in text: return TransactionType.SELL
        if "DIVIDEND" in text: return TransactionType.DIVIDEND
        if "INTEREST" in text: return TransactionType.INTEREST
        if "FEE" in text: return TransactionType.FEE
        if "TRANSFER" in text or "JOURNAL" in text or "WIRE" in text:
            return TransactionType.TRANSFER_OUT if amount < 0 else TransactionType.TRANSFER_IN
        return None # or TransactionType.BUY as default? Safer to return None if unclear

    def _parse_transactions(self) -> List[Transaction]:
        # 1. Try Table Extraction
        table_txs = self._parse_transactions_from_tables()
        if table_txs:
             return table_txs

        # 2. Fallback to Regex (Original Logic)
        transactions = []
        headers = ["Transaction Detail", "Investment Detail", "Account Activity"]
        lines = []
        for header in headers:
            found_lines = self._find_section(header, r"^Total")
            if found_lines:
                lines = found_lines
                break

        if not lines:
            return []

        # Simple regex for date MM/DD/YY or MM/DD/YYYY
        date_pattern = r"(\d{2}/\d{2}/\d{2,4})"
        current_date = None

        for line in lines:
            # Check for date at start of line
            date_match = re.search(date_pattern, line)
            if date_match and line.strip().startswith(date_match.group(1)):
                parsed = self._parse_date(date_match.group(1), "%m/%d/%y")
                if not parsed:
                    parsed = self._parse_date(date_match.group(1), "%m/%d/%Y")
                if parsed:
                    current_date = parsed

            if current_date:
                upper_line = line.upper()
                # Skip header lines repeating date
                if "SETTLEMENT DATE" in upper_line:
                   continue

                tx_type = None

                if "BUY" in upper_line or "BOUGHT" in upper_line:
                    tx_type = TransactionType.BUY
                elif "SELL" in upper_line or "SOLD" in upper_line:
                    tx_type = TransactionType.SELL
                elif "REINVEST" in upper_line:
                    tx_type = TransactionType.BUY
                elif "DIVIDEND" in upper_line:
                    tx_type = TransactionType.DIVIDEND
                elif "INTEREST" in upper_line:
                     tx_type = TransactionType.INTEREST
                elif "FEE" in upper_line:
                     tx_type = TransactionType.FEE
                elif "TRANSFER" in upper_line or "JOURNALED" in upper_line or "WIRE" in upper_line:
                     # Check direction keywords
                     if "IN" in upper_line:
                         tx_type = TransactionType.TRANSFER_IN
                     elif "OUT" in upper_line:
                         tx_type = TransactionType.TRANSFER_OUT
                     else:
                         # Fallback to amount check later, or default
                         tx_type = TransactionType.TRANSFER_IN # Default temporary

                if tx_type:
                    # Amount Logic
                    parts = line.split()
                    amount = Decimal("0.0")
                    for part in reversed(parts):
                        val = self._parse_decimal(part)
                        if val is not None:
                            amount = val
                            break

                    # Refine Transfer type using amount if not already determined by keywords
                    if (tx_type == TransactionType.TRANSFER_IN or tx_type == TransactionType.TRANSFER_OUT):
                         if "IN" not in upper_line and "OUT" not in upper_line:
                             if amount < 0:
                                 tx_type = TransactionType.TRANSFER_OUT
                             else:
                                 tx_type = TransactionType.TRANSFER_IN

                    # Symbol Extraction
                    symbol = "UNKNOWN"

                    # 1. Look for (TICKER)
                    paren_match = re.search(r"\(([A-Z]{1,5})\)", line)
                    if paren_match:
                        symbol = paren_match.group(1)
                    else:
                        # 2. Heuristic: Look for all-caps word that isn't a keyword
                        # Schwab often has: "Buy 100 Shares AAPL ..."
                        # Or "Dividend AAPL ..."
                        cleaned_parts = [p.strip() for p in parts]
                        for p in cleaned_parts:
                            if re.match(r"^[A-Z]{3,5}$", p) and p not in ["BUY", "SELL", "DATE", "CORP", "INC", "FUND", "CASH", "VISA", "WIRE", "FEES"]:
                                symbol = p
                                break

                    transactions.append(Transaction(
                        date=current_date,
                        type=tx_type,
                        description=line.strip(),
                        amount=amount,
                        symbol=symbol
                    ))

        return transactions
