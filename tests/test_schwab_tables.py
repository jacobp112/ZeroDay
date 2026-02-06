import pytest
from brokerage_parser.parsers.schwab import SchwabParser, TransactionType
from brokerage_parser.models.domain import Transaction

def test_schwab_parse_transactions_from_tables():
    # Mock table data mimicking PyMuPDF output
    # Table 1: Activity
    # Headers: Date, Action, Symbol, Description, Quantity, Price, Fees, Amount
    table1 = [
        ["Date", "Action", "Symbol", "Description", "Quantity", "Price", "Fees", "Amount"],
        ["01/15/2023", "Buy", "AAPL", "Apple Inc", "10", "$150.00", "$0.00", "-$1500.00"],
        ["01/20/2023", "Dividend", "MSFT", "Microsoft Div", "", "", "", "$50.00"],
        ["02/01/2023", "Sell", "GOOGL", "Alphabet Inc", "5", "$100.00", "$0.01", "$500.00"]
    ]

    # Text is irrelevant for this test if table logic works
    parser = SchwabParser(text="dummy", tables=[table1])

    transactions = parser.parse().transactions

    assert len(transactions) == 3

    # Tx 1
    t1 = transactions[0]
    assert t1.date.strftime("%Y-%m-%d") == "2023-01-15"
    assert t1.type == TransactionType.BUY
    assert t1.symbol == "AAPL"
    assert t1.amount == -1500.00

    # Tx 2
    t2 = transactions[1]
    assert t2.type == TransactionType.DIVIDEND
    assert t2.symbol == "MSFT" # In header mode, we map symbol column
    assert t2.amount == 50.00

    # Tx 3
    t3 = transactions[2]
    assert t3.type == TransactionType.SELL
    assert t3.symbol == "GOOGL"
    assert t3.amount == 500.00

def test_schwab_parse_fallback():
    # Test that fallback still works when no tables
    text = """
    Transaction Detail
    01/01/23 Bought 100 AAPL @ 150.00 -15000.00
    """
    parser = SchwabParser(text=text, tables=[])
    transactions = parser.parse().transactions

    assert len(transactions) == 1
    assert transactions[0].symbol == "AAPL"
