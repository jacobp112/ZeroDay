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

    def _parse_transactions(self) -> List[Transaction]:
        transactions = []
        # Fidelity section often "Activity", "Investment Activity", "Transaction History"
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
