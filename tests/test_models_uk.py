from datetime import date
from decimal import Decimal
import pytest
from brokerage_parser.models import TransactionType
from brokerage_parser.models.domain import (
    Transaction, Position, ParsedStatement,
    TaxWrapper, CorporateAction, CorporateActionType, TaxLot,
    validate_isin, validate_sedol, validate_currency, generate_transaction_id
)

# 1. Enum Tests
def test_tax_wrapper_enums():
    assert TaxWrapper.ISA.value == "ISA"
    assert TaxWrapper.SIPP.value == "SIPP"
    assert TaxWrapper.GIA.value == "GIA"
    assert TaxWrapper.UNKNOWN.value == "UNKNOWN"

def test_corporate_action_type_enums():
    assert CorporateActionType.STOCK_SPLIT.value == "STOCK_SPLIT"
    assert CorporateActionType.MERGER.value == "MERGER"

# 2. Validation Tests
def test_validate_isin():
    assert validate_isin("US0378331005") is True  # Valid format
    assert validate_isin("GB0002374006") is True  # Valid format
    assert validate_isin("INVALID") is False      # Length/Format mismatch
    assert validate_isin("US037833100") is False  # Too short
    assert validate_isin(None) is False

def test_validate_sedol():
    assert validate_sedol("0263494") is True      # Valid format
    assert validate_sedol("B0SWJX5") is True      # Valid format
    assert validate_sedol("0000001") is True      # Valid regex (ignore checksum for now)
    assert validate_sedol("INVALID") is False     # Invalid format (ends in letter)
    assert validate_sedol("TOO_LONG_STRING") is False
    assert validate_sedol(None) is False

def test_validate_currency():
    assert validate_currency("GBP") is True
    assert validate_currency("USD") is True
    assert validate_currency("gbp") is False      # Case sensitive
    assert validate_currency("US") is False       # Too short
    assert validate_currency(None) is False

# 3. Transaction Extensions Tests
def test_transaction_backward_compatibility():
    # Create old-style transaction
    tx = Transaction(
        date=date(2023, 1, 1),
        type=TransactionType.BUY,
        description="Buy AAPL",
        amount=Decimal("-150.00"),
        symbol="AAPL",
        quantity=Decimal("1"),
        price=Decimal("150.00")
    )

    # Check default values for new fields
    assert tx.currency == "GBP"
    assert tx.isin is None
    assert tx.sedol is None
    assert tx.fx_rate is None

    # Check to_dict does NOT include new fields (except defaults if strict, but our rule is
    # "Extensions - only add if set/different from default")
    d = tx.to_dict()
    assert "isin" not in d
    assert "sedol" not in d
    assert "currency" not in d # Default is GBP, so not included
    assert "transaction_id" not in d
    assert d["amount"] == "-150.00"

def test_transaction_uk_extensions():
    tx = Transaction(
        date=date(2023, 1, 1),
        type=TransactionType.BUY,
        description="Buy VUSA",
        amount=Decimal("-100.00"),
        symbol="VUSA",
        transaction_id="tx_123",
        isin="IE00B3XXRP09",
        sedol="B3XXRP0",
        currency="USD",
        fx_rate=Decimal("1.25"),
        gbp_amount=Decimal("-80.00")
    )

    assert tx.currency == "USD"
    assert tx.isin == "IE00B3XXRP09"

    d = tx.to_dict()
    assert d["isin"] == "IE00B3XXRP09"
    assert d["sedol"] == "B3XXRP0"
    assert d["currency"] == "USD" # Non-default, should be included
    assert d["fx_rate"] == "1.25"
    assert d["gbp_amount"] == "-80.00"
    assert d["transaction_id"] == "tx_123"

def test_generate_transaction_id():
    tx1 = Transaction(
        date=date(2023, 1, 1),
        type=TransactionType.BUY,
        description="Buy AAPL",
        amount=Decimal("-150.00"),
        symbol="AAPL",
        quantity=Decimal("1"),
        price=Decimal("150.00")
    )

    id1 = generate_transaction_id(tx1)

    # Same transaction should generate same ID
    tx2 = Transaction(
        date=date(2023, 1, 1),
        type=TransactionType.BUY,
        description="Buy AAPL",
        amount=Decimal("-150.00"),
        symbol="AAPL",
        quantity=Decimal("1"),
        price=Decimal("150.00")
    )
    id2 = generate_transaction_id(tx2)

    assert id1 == id2
    assert len(id1) == 64 # SHA256 hex digest length

    # Different transaction
    tx3 = Transaction(
        date=date(2023, 1, 2), # Different date
        type=TransactionType.BUY,
        description="Buy AAPL",
        amount=Decimal("-150.00"),
        symbol="AAPL",
        quantity=Decimal("1"),
        price=Decimal("150.00")
    )
    id3 = generate_transaction_id(tx3)
    assert id1 != id3

# 4. Position Extensions Tests
def test_position_backward_compatibility():
    pos = Position(
        symbol="AAPL",
        description="Apple Inc",
        quantity=Decimal("10"),
        price=Decimal("150.00"),
        market_value=Decimal("1500.00")
    )

    assert pos.currency == "GBP"
    d = pos.to_dict()
    assert "isin" not in d
    assert "currency" not in d

def test_position_uk_extensions():
    pos = Position(
        symbol="VUSA",
        description="Vanguard S&P 500",
        quantity=Decimal("10"),
        price=Decimal("50.00"),
        market_value=Decimal("500.00"),
        isin="IE00B3XXRP09",
        currency="USD",
        gbp_market_value=Decimal("400.00")
    )

    d = pos.to_dict()
    assert d["isin"] == "IE00B3XXRP09"
    assert d["currency"] == "USD"
    assert d["gbp_market_value"] == "400.00"

# 5. ParsedStatement Extensions Tests
def test_parsed_statement_extensions():
    stmt = ParsedStatement(broker="TestBroker")

    # Defaults
    assert stmt.tax_wrapper == TaxWrapper.UNKNOWN
    assert stmt.currency == "GBP"
    assert stmt.corporate_actions == []

    d = stmt.to_dict()
    assert "tax_wrapper" not in d
    assert "currency" not in d
    assert "corporate_actions" not in d

    # With Extensions
    ca = CorporateAction(
        date=date(2023, 1, 1),
        type=CorporateActionType.STOCK_SPLIT,
        source_isin="US123",
        description="Split",
        ratio_from=Decimal("1"),
        ratio_to=Decimal("2")
    )

    stmt.tax_wrapper = TaxWrapper.ISA
    stmt.currency = "USD"
    stmt.custodian = "Pershing"
    stmt.corporate_actions = [ca]

    d = stmt.to_dict()
    assert d["tax_wrapper"] == "ISA"
    assert d["currency"] == "USD"
    assert d["custodian"] == "Pershing"
    assert len(d["corporate_actions"]) == 1
    assert d["corporate_actions"][0]["type"] == "STOCK_SPLIT"

# 6. TaxLot Tests
def test_tax_lot_model():
    lot = TaxLot(
        id="lot_1",
        isin="GB123",
        acquisition_date=date(2023, 1, 1),
        quantity=Decimal("100"),
        cost_gbp=Decimal("1000.00"),
        cost_per_share_gbp=Decimal("10.00"),
        source_transaction_id="tx_1",
        is_section_104=True
    )

    d = lot.to_dict()
    assert d["id"] == "lot_1"
    assert d["isin"] == "GB123"
    assert d["cost_gbp"] == "1000.00"
    assert d["is_section_104"] is True
