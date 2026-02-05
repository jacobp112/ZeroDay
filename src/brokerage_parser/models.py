from datetime import date
from decimal import Decimal
from enum import Enum
import hashlib
import re
from typing import List, Optional

from dataclasses import dataclass, field, asdict

class TaxWrapper(Enum):
    GIA = "GIA"                       # General Investment Account
    ISA = "ISA"                       # Individual Savings Account
    JISA = "JISA"                     # Junior ISA
    LISA = "LISA"                     # Lifetime ISA
    SIPP = "SIPP"                     # Self-Invested Personal Pension
    SSAS = "SSAS"                     # Small Self-Administered Scheme
    OFFSHORE_BOND = "OFFSHORE_BOND"   # Offshore investment bond
    ONSHORE_BOND = "ONSHORE_BOND"     # Onshore investment bond
    UNKNOWN = "UNKNOWN"

class CorporateActionType(Enum):
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    MERGER = "MERGER"
    SPIN_OFF = "SPIN_OFF"
    RETURN_OF_CAPITAL = "RETURN_OF_CAPITAL"
    SCRIP_DIVIDEND = "SCRIP_DIVIDEND"
    TENDER_OFFER = "TENDER_OFFER"
    NAME_CHANGE = "NAME_CHANGE"

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    FEE = "FEE"
    OTHER = "OTHER"

def validate_isin(isin: str) -> bool:
    """ISIN: 12 chars, first 2 are country code (letters), last is check digit."""
    # TODO: Implement full checksum validation
    if not isin:
        return False
    return bool(re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', isin))

def validate_sedol(sedol: str) -> bool:
    """SEDOL: 7 alphanumeric characters."""
    # TODO: Implement full checksum validation
    if not sedol:
        return False
    return bool(re.match(r'^[B-Z0-9]{6}\d$', sedol)) # Basic regex for SEDOL characters

def validate_currency(currency: str) -> bool:
    """ISO 4217: 3 uppercase letters."""
    if not currency:
        return False
    return bool(re.match(r'^[A-Z]{3}$', currency))


def generate_transaction_id(tx: 'Transaction') -> str:
    """Generate deterministic ID from transaction fields."""
    # Hash components: date, type, symbol, amount, quantity, price, description
    components = [
        tx.date.isoformat(),
        tx.type.value,
        tx.symbol or "",
        str(tx.amount),
        str(tx.quantity) if tx.quantity else "",
        str(tx.price) if tx.price else "",
        tx.description
    ]
    raw_id = "|".join(components)
    return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()

@dataclass
class Transaction:
    date: date
    type: TransactionType
    description: str
    amount: Decimal
    symbol: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    # UK Extensions
    isin: Optional[str] = None
    sedol: Optional[str] = None
    currency: str = "GBP"
    fx_rate: Optional[Decimal] = None
    gbp_amount: Optional[Decimal] = None
    settlement_date: Optional[date] = None
    trade_date: Optional[date] = None
    transaction_id: Optional[str] = None

    def to_dict(self):
        base_dict = {
            "date": self.date.isoformat(),
            "type": self.type.value,
            "description": self.description,
            "amount": str(self.amount),
            "symbol": self.symbol,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "price": str(self.price) if self.price is not None else None
        }

        # Extensions - only add if set/different from default
        if self.isin: base_dict["isin"] = self.isin
        if self.sedol: base_dict["sedol"] = self.sedol
        if self.currency != "GBP": base_dict["currency"] = self.currency
        if self.fx_rate is not None: base_dict["fx_rate"] = str(self.fx_rate)
        if self.gbp_amount is not None: base_dict["gbp_amount"] = str(self.gbp_amount)
        if self.settlement_date: base_dict["settlement_date"] = self.settlement_date.isoformat()
        if self.trade_date: base_dict["trade_date"] = self.trade_date.isoformat()
        if self.transaction_id: base_dict["transaction_id"] = self.transaction_id

        return base_dict

@dataclass
class Position:
    symbol: str
    description: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    cost_basis: Optional[Decimal] = None
    gain_loss: Optional[Decimal] = None
    # UK Extensions
    isin: Optional[str] = None
    sedol: Optional[str] = None
    currency: str = "GBP"
    gbp_market_value: Optional[Decimal] = None
    cost_basis_gbp: Optional[Decimal] = None
    unrealised_gain_gbp: Optional[Decimal] = None

    def to_dict(self):
        base_dict = {
            "symbol": self.symbol,
            "description": self.description,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "market_value": str(self.market_value),
            "cost_basis": str(self.cost_basis) if self.cost_basis is not None else None,
            "gain_loss": str(self.gain_loss) if self.gain_loss is not None else None
        }

        if self.isin: base_dict["isin"] = self.isin
        if self.sedol: base_dict["sedol"] = self.sedol
        if self.currency != "GBP": base_dict["currency"] = self.currency
        if self.gbp_market_value is not None: base_dict["gbp_market_value"] = str(self.gbp_market_value)
        if self.cost_basis_gbp is not None: base_dict["cost_basis_gbp"] = str(self.cost_basis_gbp)
        if self.unrealised_gain_gbp is not None: base_dict["unrealised_gain_gbp"] = str(self.unrealised_gain_gbp)

        return base_dict

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
class CorporateAction:
    date: date
    type: CorporateActionType
    source_isin: str
    description: str
    target_isin: Optional[str] = None
    ratio_from: Decimal = Decimal("1")
    ratio_to: Decimal = Decimal("1")
    cash_component_gbp: Optional[Decimal] = None

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "type": self.type.value,
            "source_isin": self.source_isin,
            "description": self.description,
            "target_isin": self.target_isin,
            "ratio_from": str(self.ratio_from),
            "ratio_to": str(self.ratio_to),
            "cash_component_gbp": str(self.cash_component_gbp) if self.cash_component_gbp is not None else None
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
    # UK Extensions
    tax_wrapper: TaxWrapper = TaxWrapper.UNKNOWN
    currency: str = "GBP"
    custodian: Optional[str] = None
    corporate_actions: List[CorporateAction] = field(default_factory=list)

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
        base_dict = {
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

        if self.tax_wrapper != TaxWrapper.UNKNOWN: base_dict["tax_wrapper"] = self.tax_wrapper.value
        if self.currency != "GBP": base_dict["currency"] = self.currency
        if self.custodian: base_dict["custodian"] = self.custodian
        if self.corporate_actions: base_dict["corporate_actions"] = [c.to_dict() for c in self.corporate_actions]

        return base_dict

@dataclass
class TaxLot:
    id: str
    isin: str
    acquisition_date: date
    quantity: Decimal
    cost_gbp: Decimal
    cost_per_share_gbp: Decimal
    source_transaction_id: Optional[str] = None
    is_section_104: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "isin": self.isin,
            "acquisition_date": self.acquisition_date.isoformat(),
            "quantity": str(self.quantity),
            "cost_gbp": str(self.cost_gbp),
            "cost_per_share_gbp": str(self.cost_per_share_gbp),
            "source_transaction_id": self.source_transaction_id,
            "is_section_104": self.is_section_104
        }
