from typing import List, Optional, Dict, Any
from datetime import date
import re
from decimal import Decimal
import logging

from brokerage_parser.parsers.base import Parser
from brokerage_parser.models import TransactionType
from brokerage_parser.models.domain import Transaction, Position

logger = logging.getLogger(__name__)

class GenericParser(Parser):
    def get_broker_name(self) -> str:
        return "Generic"

    def _parse_account_number(self) -> Optional[str]:
        return None

    def _parse_statement_dates(self) -> Optional[tuple[date, date, date]]:
        return None

    def _identify_table_type(self, table: List[List[str]]) -> str:
        """
        Override base class with more flexible table type detection.
        Returns: "transactions", "positions", or "unknown"
        """
        if not table:
            return "unknown"

        # Transaction-related keywords (more flexible than base class)
        tx_date_keywords = ["date", "trade date", "settlement date"]
        tx_type_keywords = ["action", "type", "transaction", "activity", "description"]
        tx_amount_keywords = ["amount", "total", "value", "price", "net amount"]

        # Position-related keywords (more flexible than base class)
        pos_symbol_keywords = ["symbol", "ticker", "security", "asset", "holding"]
        pos_qty_keywords = ["quantity", "shares", "units", "held"]
        pos_value_keywords = ["value", "market value", "amount", "current value"]

        for i in range(min(5, len(table))):
            row = [str(cell).lower().strip() for cell in table[i]]
            row_text = " ".join(row)

            # For transactions: date + (type OR amount)
            has_date = any(k in row_text for k in tx_date_keywords)
            has_type = any(k in row_text for k in tx_type_keywords)
            has_amount = any(k in row_text for k in tx_amount_keywords)

            if has_date and (has_type or has_amount):
                return "transactions"

            # For positions: symbol + quantity + value
            has_symbol = any(k in row_text for k in pos_symbol_keywords)
            has_qty = any(k in row_text for k in pos_qty_keywords)
            has_value = any(k in row_text for k in pos_value_keywords)

            if has_symbol and has_qty and has_value:
                return "positions"

        return "unknown"

    def _find_header_row(self, table: List[List[str]], keywords: List[str]) -> int:
        """Finds the row index that contains at least one of the keywords."""
        for i, row in enumerate(table[:5]):  # Check first 5 rows
            row_text = " ".join([str(c).lower() for c in row])
            if any(k.lower() in row_text for k in keywords):
                return i
        return -1

    def _map_columns(self, header_row: List[str], column_keywords: Dict[str, List[str]]) -> Dict[str, int]:
        """Maps column names to indices based on keywords."""
        mapping = {}
        header_text_map = {idx: str(col).lower().strip() for idx, col in enumerate(header_row)}

        for col_name, keywords in column_keywords.items():
            for idx, text in header_text_map.items():
                if any(k.lower() == text for k in keywords) or any(k.lower() in text for k in keywords):
                    # Prefer exact match or contains? "Trade Date" contains "Date".
                    # Let's try simple contains first.
                    if col_name not in mapping:
                        mapping[col_name] = idx
                    # If we find "Trade Date" and we already have "Date", we might want "Trade Date".
                    # But for now first match is generic approach.

        return mapping

    def _map_transaction_type(self, type_str: str) -> TransactionType:
        """Maps a transaction type string to a TransactionType enum."""
        type_lower = type_str.lower().strip()

        type_mapping = {
            "buy": TransactionType.BUY,
            "purchase": TransactionType.BUY,
            "bought": TransactionType.BUY,
            "sell": TransactionType.SELL,
            "sold": TransactionType.SELL,
            "dividend": TransactionType.DIVIDEND,
            "div": TransactionType.DIVIDEND,
            "interest": TransactionType.INTEREST,
            "transfer in": TransactionType.TRANSFER_IN,
            "deposit": TransactionType.TRANSFER_IN,
            "transfer out": TransactionType.TRANSFER_OUT,
            "withdrawal": TransactionType.TRANSFER_OUT,
            "fee": TransactionType.FEE,
        }

        for key, tx_type in type_mapping.items():
            if key in type_lower:
                return tx_type

        return TransactionType.OTHER

    def _parse_transactions(self) -> List[Transaction]:
        transactions = []

        # Keywords to define transaction columns
        col_definitions = {
            "date": ["Date", "Trade Date", "Settlement Date"],
            "type": ["Action", "Type", "Transaction", "Activity"],
            "symbol": ["Symbol", "Ticker", "Security", "Description"], # Description is fallback for text
            "amount": ["Amount", "Total", "Value", "Price", "Net Amount"],
            "quantity": ["Quantity", "Shares", "Units"]
        }

        for table in self.tables:
            # Use base class identification or just try to map?
            # Requirement: "Use _identify_table_type() to find transaction tables"
            if self._identify_table_type(table) != "transactions":
                continue

            # Re-find header row
            # We look for "date" keyword as anchor
            header_idx = self._find_header_row(table, col_definitions["date"])
            if header_idx == -1:
                continue

            header_row = table[header_idx]
            mapping = self._map_columns(header_row, col_definitions)

            # Check required columns: Date + Amount
            if "date" not in mapping or "amount" not in mapping:
                logger.warning(f"GenericParser: Skipping transaction table, missing date/amount. Found: {list(mapping.keys())}")
                continue

            # Iterate rows
            for row in table[header_idx+1:]:
                if len(row) <= max(mapping.values()):
                    continue

                try:
                    date_val = self._parse_date_flexible(row[mapping["date"]])
                    amount_val = self._parse_decimal(row[mapping["amount"]])

                    if not date_val: # Date is mandatory
                        continue

                    description = ""
                    # If we only have "type" column, use it. If we have symbol, use it.
                    # Or try to get description from other columns?
                    # For generic, let's keep it simple.

                    tx_type_str = row[mapping["type"]].strip() if "type" in mapping else "Unknown"
                    tx_type = self._map_transaction_type(tx_type_str)
                    symbol = row[mapping["symbol"]].strip() if "symbol" in mapping else None
                    quantity = self._parse_decimal(row[mapping["quantity"]]) if "quantity" in mapping else None

                    # Build description from available info
                    description = f"{tx_type_str} {symbol or ''}".strip()

                    txn = Transaction(
                        date=date_val,
                        type=tx_type,
                        description=description,
                        amount=amount_val or Decimal("0"),
                        symbol=symbol,
                        quantity=quantity
                    )
                    transactions.append(txn)
                except Exception as e:
                    # Generic parser shouldn't crash on row error
                    continue

        return transactions

    def _parse_positions(self) -> List[Position]:
        positions = []

        col_definitions = {
            "symbol": ["Symbol", "Ticker", "Security", "Asset"],
            "quantity": ["Quantity", "Shares", "Units", "Held"],
            "value": ["Value", "Market Value", "Amount", "Current Value"]
        }

        for table in self.tables:
             if self._identify_table_type(table) != "positions":
                 continue

             header_idx = self._find_header_row(table, col_definitions["symbol"])
             if header_idx == -1:
                 continue

             header_row = table[header_idx]
             mapping = self._map_columns(header_row, col_definitions)

             # Required: Symbol + Quantity + Value
             if not all(k in mapping for k in ["symbol", "quantity", "value"]):
                 logger.warning(f"GenericParser: Skipping positions table, missing columns. Found: {list(mapping.keys())}")
                 continue

             for row in table[header_idx+1:]:
                 if len(row) <= max(mapping.values()):
                     continue

                 try:
                     symbol_val = row[mapping["symbol"]].strip()
                     qty_val = self._parse_decimal(row[mapping["quantity"]])
                     val_val = self._parse_decimal(row[mapping["value"]])

                     if not symbol_val:
                         continue

                     pos = Position(
                         symbol=symbol_val,
                         description=symbol_val,  # Use symbol as description if not available
                         quantity=qty_val or Decimal("0"),
                         price=Decimal("0"),  # Price not typically available in generic tables
                         market_value=val_val or Decimal("0")
                     )
                     positions.append(pos)
                 except:
                     continue

        return positions
