from dataclasses import dataclass, field, asdict
from decimal import Decimal
from datetime import date
from enum import Enum
from typing import List, Optional

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    FEE = "FEE"
    OTHER = "OTHER"

@dataclass
class Transaction:
    date: date
    type: TransactionType
    description: str
    amount: Decimal
    symbol: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None

    def to_dict(self):
        return {
            "date": self.date.isoformat(),
            "type": self.type.value,
            "description": self.description,
            "amount": str(self.amount),
            "symbol": self.symbol,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "price": str(self.price) if self.price is not None else None
        }

@dataclass
class Position:
    symbol: str
    description: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    cost_basis: Optional[Decimal] = None
    gain_loss: Optional[Decimal] = None

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "description": self.description,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "market_value": str(self.market_value),
            "cost_basis": str(self.cost_basis) if self.cost_basis is not None else None,
            "gain_loss": str(self.gain_loss) if self.gain_loss is not None else None
        }

@dataclass
class AccountSummary:
    account_number: str
    account_type: str
    beginning_balance: Optional[Decimal] = None
    ending_balance: Optional[Decimal] = None

    def to_dict(self):
        return {
            "account_number": self.account_number,
            "account_type": self.account_type,
            "beginning_balance": str(self.beginning_balance) if self.beginning_balance is not None else None,
            "ending_balance": str(self.ending_balance) if self.ending_balance is not None else None
        }

@dataclass
class ParsedStatement:
    broker: str
    account: Optional[AccountSummary] = None
    statement_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    positions: List[Position] = field(default_factory=list)
    transactions: List[Transaction] = field(default_factory=list)
    integrity_warnings: List[str] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)

    def validate(self) -> None:
        """
        Perform data integrity checks on the parsed statement.
        Populates self.integrity_warnings with any discrepancies found.
        """
        # 1. Orphaned Transactions
        if self.period_start and self.period_end:
            for tx in self.transactions:
                if tx.date < self.period_start or tx.date > self.period_end:
                    self.integrity_warnings.append(
                        f"Orphaned transaction: {tx.date} is outside period {self.period_start} - {self.period_end}"
                    )

        # 2. Cash Flow Reconciliation
        if self.account and self.account.beginning_balance is not None and self.account.ending_balance is not None:
            reported_change = self.account.ending_balance - self.account.beginning_balance
            calculated_change = sum(t.amount for t in self.transactions)

            # Use specific tolerance for floating point arithmetic if Decimals weren't used everywhere
            # But we are using Decimals, so we check for significant deviation
            diff = abs(reported_change - calculated_change)
            if diff > Decimal("0.01"):
                self.integrity_warnings.append(
                    f"Balance discrepancy: Reported change {reported_change} vs Calculated tx sum {calculated_change} (Diff: {diff})"
                )

        # 3. Asset Reconciliation
        if self.account and self.account.ending_balance is not None and self.positions:
            # Check if total position value matches ending balance
            # Note: valid only if account is purely positions or if we include cash in positions?
            # Typically ending_balance = cash + securities.
            # If positions include everything, this check works.
            # If positions are just securities, we need cash balance.
            # Assuming 'positions' might not include cash core position in some parsers.
            # But based on request: "Asset discrepancy: Ending Balance {ending} vs Sum of Positions {sum}"

            total_positions_value = sum(p.market_value for p in self.positions)
            diff = abs(total_positions_value - self.account.ending_balance)

            # Using 1.0 tolerance as requested for rounding/small cash diffs
            if diff > Decimal("1.0"):
                self.integrity_warnings.append(
                    f"Asset discrepancy: Ending Balance {self.account.ending_balance} vs Sum of Positions {total_positions_value} (Diff: {diff})"
                )

        # 4. Missing Metadata
        if self.account:
            if not self.account.account_number or self.account.account_number == "Unknown":
                self.integrity_warnings.append("Missing account number")

    def to_dict(self):
        return {
            "broker": self.broker,
            "account": self.account.to_dict() if self.account else None,
            "statement_date": self.statement_date.isoformat() if self.statement_date else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "positions": [p.to_dict() for p in self.positions],
            "transactions": [t.to_dict() for t in self.transactions],
            "integrity_warnings": self.integrity_warnings,
            "parse_errors": self.parse_errors
        }
