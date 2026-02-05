import pytest
from decimal import Decimal
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import TransactionType

# Mock Data from Implementation Plan (with fractional share fix)
SCHWAB_ROBUST_TEXT = """
Charles Schwab & Co., Inc.
Statement Period: January 1, 2023 through January 31, 2023

Transaction Detail
01/05/23    Bought 100 Shares NVDA @ 205.50               -20,550.00
            Sweep to Money Market
01/10/23    Sold 50 Shares AMD @ 85.25                    4,262.50
01/15/23    Qualified Dividend AAPL                       150.25
01/20/23    Wire Transfer Out                             -5,000.00
            To: External Bank Acct ending 1234
01/25/23    Bank Interest                                 4.12
01/28/23    Bought 0.523 Shares VOO @ 380.25              -198.87
01/29/23    Service Fee                                   -15.00
01/30/23    Wire Transfer In                              10,000.00
01/31/23    Margin Interest                               -12.50
Total                                                     -21,344.50
"""

def test_schwab_robust_parsing():
    parser = get_parser("schwab", SCHWAB_ROBUST_TEXT)
    statement = parser.parse()

    transactions = statement.transactions
    assert len(transactions) == 9

    # 1. Buy NVDA
    tx1 = transactions[0]
    assert tx1.type == TransactionType.BUY
    assert tx1.symbol == "NVDA"
    assert tx1.quantity == Decimal("100")
    assert tx1.price == Decimal("205.50")
    assert tx1.amount == Decimal("-20550.00")
    assert "Sweep to Money Market" in tx1.description

    # 2. Sell AMD
    tx2 = transactions[1]
    assert tx2.type == TransactionType.SELL
    assert tx2.symbol == "AMD"
    assert tx2.quantity == Decimal("50")
    assert tx2.amount == Decimal("4262.50")

    # 3. Dividend AAPL
    tx3 = transactions[2]
    assert tx3.type == TransactionType.DIVIDEND
    assert tx3.symbol == "AAPL"
    assert tx3.amount == Decimal("150.25")

    # 4. Wire Transfer Out
    tx4 = transactions[3]
    assert tx4.type == TransactionType.TRANSFER_OUT
    assert tx4.amount == Decimal("-5000.00")
    assert "To: External Bank" in tx4.description

    # 5. Bank Interest
    tx5 = transactions[4]
    assert tx5.type == TransactionType.INTEREST
    assert tx5.amount == Decimal("4.12")

    # 6. Buy VOO (Fractional)
    tx6 = transactions[5]
    assert tx6.type == TransactionType.BUY
    assert tx6.symbol == "VOO"
    assert tx6.quantity == Decimal("0.523")
    assert tx6.amount == Decimal("-198.87")

    # 7. Service Fee
    tx7 = transactions[6]
    assert tx7.type == TransactionType.FEE
    assert tx7.amount == Decimal("-15.00")

    # 8. Wire Transfer In
    tx8 = transactions[7]
    assert tx8.type == TransactionType.TRANSFER_IN
    assert tx8.amount == Decimal("10000.00")

    # 9. Margin Interest
    tx9 = transactions[8]
    assert tx9.type == TransactionType.INTEREST # Or FEE? Usually interest is Interest type
    # User requirement listed Interest type for "margin interest"
    assert tx9.amount == Decimal("-12.50")
