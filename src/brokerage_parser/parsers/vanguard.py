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

    def _parse_transactions(self) -> List[Transaction]:
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
