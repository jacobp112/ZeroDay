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
        # Example: "Statement Period: January 1, 2023 to January 31, 2023"
        # This is a placeholder standard pattern
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

    def _parse_transactions(self) -> List[Transaction]:
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
