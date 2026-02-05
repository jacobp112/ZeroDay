from decimal import Decimal
import pytest
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import TransactionType

# Mock Text Data
SCHWAB_TEXT = """
Charles Schwab & Co., Inc.
Statement Date: January 31, 2023
Statement Period: January 1, 2023 to January 31, 2023
Account Number: 1234-5678

Transaction Detail
01/01/23    Buy 10 Shares AAPL @ 150.00                    -1500.00
01/15/23    Sell 5 Shares MSFT                             750.00
01/20/23    Cash Dividend AAPL                             10.50
01/25/23    Reinvestment AAPL 0.07 Shares @ 150.00         -10.50
02/01/23    Bank Interest                                  0.45
02/05/23    Service Fee                                    -25.00
02/10/23    Journaled In (Cash)                            5000.00
02/15/23    Wire Transfer Out                              -1000.00

Account Holdings
AAPL Apple Inc 100 150.00 15000.00
MSFT Microsoft Corp 50 300.00 15000.00
Total
"""

FIDELITY_TEXT = """
Fidelity Investments
Statement Date: 01/31/2023
Account Activity for 01/01/2023 - 01/31/2023
Account Number X12-345678

Activity
02/01/23    YOU BOUGHT GOOGL 10 Shares @ 100.00      -1000.00
02/05/23    YOU SOLD MSFT 5 Shares @ 200.00          1000.00
02/10/23    DIVIDEND RECEIVED AAPL                   50.00
02/15/23    REINVESTMENT AAPL 0.5 Shares @ 100.00    -50.00

Holdings
GOOGL Alphabet Inc 10 100.00 1000.00
AAPL Apple Inc 50 150.00 7500.00
Total
"""

VANGUARD_TEXT = """
The Vanguard Group
Statement date: January 31, 2023
For the period January 1, 2023, to January 31, 2023
Account Number 9876-54321

Activity Detail
03/01/23    Buy Vanguard 500 Index Fund Admiral Shares VFIAX    -3000.00
03/05/23    Redemption Vanguard Total Bond Market VBTLX         1000.00
03/10/23    Dividend Received VFIAX                             45.50
03/10/23    Dividend Reinvestment VFIAX                         -45.50
03/15/23    Exchange Out Vanguard Growth Index VIGAX            -5000.00
03/15/23    Exchange In Vanguard Value Index VIVAX              5000.00

Investment Holdings
Vanguard 500 Index Fund Admiral Shares VFIAX 100.000 400.00 40000.00
Vanguard Total Bond Market Index Fund VBTLX 500.000 10.00 5000.00
Total
"""

def test_schwab_parser_account():
    parser = get_parser("schwab", SCHWAB_TEXT)
    assert parser is not None
    assert parser.get_broker_name() == "Schwab"

    statement = parser.parse()
    assert statement.broker == "Schwab"
    assert statement.account is not None
    assert statement.account.account_number == "1234-5678"

def test_schwab_parser_transactions():
    parser = get_parser("schwab", SCHWAB_TEXT)
    statement = parser.parse()

    assert len(statement.transactions) >= 1
    tx = statement.transactions[0]

    assert tx.type == TransactionType.BUY
    assert tx.date.year == 2023
    assert tx.date.month == 1
    assert tx.date.day == 1

def test_fidelity_parser_identification():
    parser = get_parser("fidelity", FIDELITY_TEXT)
    assert parser is not None
    assert parser.get_broker_name() == "Fidelity"

    statement = parser.parse()
    assert statement.account is not None
    assert statement.account.account_number == "X12-345678"

def test_vanguard_parser_identification():
    parser = get_parser("vanguard", VANGUARD_TEXT)
    assert parser is not None
    assert parser.get_broker_name() == "Vanguard"

    statement = parser.parse()
    assert statement.account is not None
    assert statement.account.account_number == "9876-54321"

def test_factory_invalid():
    parser = get_parser("webull", "some text")
    assert parser is None

def test_fidelity_parser_transactions():
    parser = get_parser("fidelity", FIDELITY_TEXT)
    statement = parser.parse()

    assert len(statement.transactions) == 4

    # Check BUY
    tx1 = statement.transactions[0]
    assert tx1.type == TransactionType.BUY
    assert tx1.symbol == "GOOGL"
    assert tx1.amount == Decimal("-1000.00")
    assert tx1.date.day == 1

    # Check SELL
    tx2 = statement.transactions[1]
    assert tx2.type == TransactionType.SELL
    assert tx2.symbol == "MSFT"
    assert tx2.amount == Decimal("1000.00")

    # Check DIVIDEND
    tx3 = statement.transactions[2]
    assert tx3.type == TransactionType.DIVIDEND
    assert tx3.symbol == "AAPL"
    assert tx3.amount == Decimal("50.00")

    # Check REINVESTMENT (Mapped to BUY)
    tx4 = statement.transactions[3]
    assert tx4.type == TransactionType.BUY
    assert tx4.symbol == "AAPL"
    # Note: Logic picks up last number, which is -50.00.
    # Just verifying it picks up something numeric
    assert tx4.amount == Decimal("-50.00")

    # Check Positions
    assert len(statement.positions) == 2
    pos1 = statement.positions[0]
    assert pos1.symbol == "GOOGL"
    assert pos1.quantity == Decimal("10")
    assert pos1.price == Decimal("100.00")
    assert pos1.market_value == Decimal("1000.00")

def test_vanguard_parser_transactions():
    parser = get_parser("vanguard", VANGUARD_TEXT)
    statement = parser.parse()

    assert len(statement.transactions) == 6

    # 1. Buy
    tx1 = statement.transactions[0]
    assert tx1.type == TransactionType.BUY
    assert "VFIAX" in tx1.description or tx1.symbol == "VFIAX"
    assert tx1.amount == Decimal("-3000.00")

    # 2. Redemption (Sell)
    tx2 = statement.transactions[1]
    assert tx2.type == TransactionType.SELL
    assert "VBTLX" in tx2.description or tx2.symbol == "VBTLX"
    assert tx2.amount == Decimal("1000.00")

    # 3. Dividend
    tx3 = statement.transactions[2]
    assert tx3.type == TransactionType.DIVIDEND
    assert tx3.amount == Decimal("45.50")

    # 4. Reinvestment (Mapped to Buy)
    tx4 = statement.transactions[3]
    assert tx4.type == TransactionType.BUY
    assert tx4.amount == Decimal("-45.50")

    # 5. Exchange Out (Transfer Out)
    tx5 = statement.transactions[4]
    assert tx5.type == TransactionType.TRANSFER_OUT
    assert tx5.amount == Decimal("-5000.00")

    # 6. Exchange In (Transfer In)
    tx6 = statement.transactions[5]
    assert tx6.type == TransactionType.TRANSFER_IN
    assert tx6.amount == Decimal("5000.00")

    # Positions
    assert len(statement.positions) == 2
    pos1 = statement.positions[0]
    # Check if logic picked up VFIAX as symbol (last part of name)
    assert pos1.symbol == "VFIAX"
    assert pos1.quantity == Decimal("100.000")
    assert pos1.market_value == Decimal("40000.00")
    assert "Vanguard 500 Index Fund Admiral Shares" in pos1.description

def test_schwab_parser_full():
    parser = get_parser("schwab", SCHWAB_TEXT)
    statement = parser.parse()

    assert len(statement.transactions) == 8

    # 1. Buy
    tx1 = statement.transactions[0]
    assert tx1.type == TransactionType.BUY
    assert tx1.symbol == "AAPL"
    assert tx1.amount == Decimal("-1500.00")

    # 2. Sell
    tx2 = statement.transactions[1]
    assert tx2.type == TransactionType.SELL
    assert tx2.symbol == "MSFT"
    assert tx2.amount == Decimal("750.00")

    # 3. Dividend
    tx3 = statement.transactions[2]
    assert tx3.type == TransactionType.DIVIDEND
    assert tx3.symbol == "AAPL"
    assert tx3.amount == Decimal("10.50")

    # 4. Reinvestment (Mapped to Buy)
    tx4 = statement.transactions[3]
    assert tx4.type == TransactionType.BUY
    assert tx4.symbol == "AAPL"
    assert tx4.amount == Decimal("-10.50")

    # 5. Interest
    tx5 = statement.transactions[4]
    assert tx5.type == TransactionType.INTEREST
    assert tx5.amount == Decimal("0.45")

    # 6. Fee
    tx6 = statement.transactions[5]
    assert tx6.type == TransactionType.FEE
    assert tx6.amount == Decimal("-25.00")

    # 7. Transfer In
    tx7 = statement.transactions[6]
    assert tx7.type == TransactionType.TRANSFER_IN
    assert tx7.amount == Decimal("5000.00")

    # 8. Transfer Out
    tx8 = statement.transactions[7]
    assert tx8.type == TransactionType.TRANSFER_OUT
    assert tx8.amount == Decimal("-1000.00")

    # Positions
    assert len(statement.positions) == 2
    pos1 = statement.positions[0]
    assert pos1.symbol == "AAPL"
    assert pos1.quantity == Decimal("100")
    assert pos1.price == Decimal("150.00")
    assert pos1.market_value == Decimal("15000.00")

def test_schwab_statement_dates():
    parser = get_parser("schwab", SCHWAB_TEXT)
    dates = parser._parse_statement_dates()
    assert dates is not None
    stmt_date, start, end = dates

    assert stmt_date.year == 2023
    assert stmt_date.month == 1
    assert stmt_date.day == 31

    assert start.day == 1
    assert end.day == 31

def test_fidelity_statement_dates():
    parser = get_parser("fidelity", FIDELITY_TEXT)
    dates = parser._parse_statement_dates()
    assert dates is not None
    stmt_date, start, end = dates

    assert stmt_date.year == 2023
    assert stmt_date.month == 1
    assert stmt_date.day == 31

    assert start.day == 1
    assert end.day == 31

def test_vanguard_statement_dates():
    parser = get_parser("vanguard", VANGUARD_TEXT)
    dates = parser._parse_statement_dates()
    assert dates is not None
    stmt_date, start, end = dates

    assert stmt_date.year == 2023
    assert stmt_date.month == 1
    assert stmt_date.day == 31

    assert start.day == 1
    assert end.day == 31

def test_statement_dates_none():
    # Test text with no dates
    text = """
    Some Broker
    Account Number: 123
    No dates here
    """
    # Schwab
    parser = get_parser("schwab", text)
    assert parser._parse_statement_dates() is None

    # Fidelity
    parser = get_parser("fidelity", text)
    assert parser._parse_statement_dates() is None

    # Vanguard
    parser = get_parser("vanguard", text)
    assert parser._parse_statement_dates() is None

def test_schwab_single_year_range():
    text = """
    Charles Schwab
    Statement Date: January 31, 2023
    Statement Period: January 1 - 31, 2023
    Account Number: 123
    """
    parser = get_parser("schwab", text)
    dates = parser._parse_statement_dates()
    assert dates is not None
    stmt_date, start, end = dates

    assert start.month == 1
    assert start.day == 1
    assert start.year == 2023

    assert end.month == 1 # inferred month
    assert end.day == 31
    assert end.year == 2023

def test_range_fallback_logic():
    # Only Period found, no statement date
    text = """
    Charles Schwab
    Statement Period: January 1, 2023 to January 31, 2023
    """
    parser = get_parser("schwab", text)
    dates = parser._parse_statement_dates()
    assert dates is not None
    stmt_date, start, end = dates

    # Logic: use period_end as statement_date
    assert stmt_date == end
    assert stmt_date.day == 31
