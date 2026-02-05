
import pytest
from decimal import Decimal
from datetime import date
from brokerage_parser.models import ParsedStatement, Transaction, Position, AccountSummary, TransactionType

def create_statement(
    transactions=None,
    positions=None,
    account=None,
    period_start=date(2023, 1, 1),
    period_end=date(2023, 1, 31)
):
    return ParsedStatement(
        broker="TestBroker",
        period_start=period_start,
        period_end=period_end,
        transactions=transactions or [],
        positions=positions or [],
        account=account or AccountSummary(
            account_number="12345678",
            account_type="Individual",
            beginning_balance=Decimal("1000.00"),
            ending_balance=Decimal("1000.00")
        )
    )

def test_clean_validation():
    """Test that a mathematically perfect statement produces no warnings."""
    # Scenario:
    # Start: 1000.00
    # Deposit: +500.00
    # Buy: -200.00
    # End: 1300.00
    # Position: Value 1300.00 (Assuming all cash is in a position or we just track total value)
    # Wait, simple case: Cash account.
    # Start: 1000.00
    # Tx1: +500.00 (Deposit)
    # Tx2: -200.00 (Withdrawal)
    # Calc Change: +300.00
    # End: 1300.00
    # Positions: None (Empty) -> Asset check skipped if empty?
    # Logic in check 3: if self.account.ending_balance is not None and self.positions:

    # So let's test cash flow first
    account = AccountSummary(
        account_number="12345",
        account_type="Cash",
        beginning_balance=Decimal("1000.00"),
        ending_balance=Decimal("1300.00")
    )
    transactions = [
        Transaction(date(2023, 1, 15), TransactionType.TRANSFER_IN, "Deposit", Decimal("500.00")),
        Transaction(date(2023, 1, 20), TransactionType.TRANSFER_OUT, "Withdrawal", Decimal("-200.00")),
    ]

    stmt = create_statement(transactions=transactions, account=account)
    stmt.validate()

    assert len(stmt.integrity_warnings) == 0, f"Expected no warnings, got: {stmt.integrity_warnings}"

def test_orphaned_transaction():
    """Test that a transaction outside the period generates a warning."""
    transactions = [
        Transaction(date(2022, 12, 31), TransactionType.BUY, "Early Tx", Decimal("-10.00"))
    ]
    stmt = create_statement(transactions=transactions)
    stmt.validate()

    assert any("Orphaned transaction" in w for w in stmt.integrity_warnings)

def test_balance_mismatch():
    """Test mismatch between reported balance change and transaction sum."""
    # Start: 1000
    # End: 1100 (Change +100)
    # Tx: +50 (Sum +50)
    # Diff: 50 > 0.01
    account = AccountSummary(
        account_number="12345",
        account_type="Cash",
        beginning_balance=Decimal("1000.00"),
        ending_balance=Decimal("1100.00")
    )
    transactions = [
        Transaction(date(2023, 1, 15), TransactionType.DIVIDEND, "Div", Decimal("50.00"))
    ]
    stmt = create_statement(transactions=transactions, account=account)
    stmt.validate()

    assert any("Balance discrepancy" in w for w in stmt.integrity_warnings)

def test_asset_mismatch():
    """Test mismatch between ending balance and sum of positions."""
    # End Balance: 1000.00
    # Positions: 1 share @ 500.00 = 500.00
    # Diff: 500 > 1.0
    account = AccountSummary(
        account_number="12345",
        account_type="Margin",
        beginning_balance=Decimal("1000.00"),
        ending_balance=Decimal("1000.00")
    )
    positions = [
        Position("AAPL", "Apple", Decimal("1"), Decimal("500.00"), Decimal("500.00"))
    ]
    # No transactions to avoid balance discrepancy check noise (though they are independent checks)

    stmt = create_statement(positions=positions, account=account)
    stmt.validate()

    assert any("Asset discrepancy" in w for w in stmt.integrity_warnings)

def test_missing_metadata():
    """Test missing account number."""
    account = AccountSummary(
        account_number="Unknown",
        account_type="Cash",
        beginning_balance=Decimal("0"),
        ending_balance=Decimal("0")
    )
    stmt = create_statement(account=account)
    stmt.validate()
    assert any("Missing account number" in w for w in stmt.integrity_warnings)
