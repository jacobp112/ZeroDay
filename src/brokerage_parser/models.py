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
    account_number: str
    statement_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    positions: List[Position] = field(default_factory=list)
    transactions: List[Transaction] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "broker": self.broker,
            "account_number": self.account_number,
            "statement_date": self.statement_date.isoformat() if self.statement_date else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "positions": [p.to_dict() for p in self.positions],
            "transactions": [t.to_dict() for t in self.transactions],
            "parse_errors": self.parse_errors
        }
