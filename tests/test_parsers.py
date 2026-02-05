from decimal import Decimal
import pytest
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import TransactionType

# Mock Text Data
SCHWAB_TEXT = """
Charles Schwab & Co., Inc.
Account Number: 1234-5678

Transaction Detail
01/01/23    Buy AAPL 10 Shares @ 150.00    -1500.00
01/15/23    Sell MSFT 5 Shares             750.00
Total
"""

FIDELITY_TEXT = """
Fidelity Investments
Account Number X12-345678

Activity
02/01/23    YOU BOUGHT GOOGL
"""

VANGUARD_TEXT = """
The Vanguard Group
Account Number 9876-54321
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
