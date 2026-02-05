import pytest
from decimal import Decimal
from datetime import date

from brokerage_parser.parsers.generic import GenericParser
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import TransactionType


class TestGenericParser:
    """Tests for the GenericParser class."""

    def test_get_broker_name(self):
        """Test that the broker name is 'Generic'."""
        parser = GenericParser("", [])
        assert parser.get_broker_name() == "Generic"

    def test_parse_transactions_with_standard_headers(self):
        """Test parsing transaction table with standard column headers."""
        # Mock table with standard headers
        mock_table = [
            ["Date", "Type", "Symbol", "Quantity", "Amount"],
            ["01/15/2024", "Buy", "AAPL", "10", "$1,500.00"],
            ["01/20/2024", "Sell", "GOOGL", "5", "$2,500.00"],
            ["02/01/2024", "Dividend", "MSFT", "", "$50.00"],
        ]

        parser = GenericParser("", [mock_table])
        transactions = parser._parse_transactions()

        assert len(transactions) == 3

        # Check first transaction
        assert transactions[0].date == date(2024, 1, 15)
        assert transactions[0].type == TransactionType.BUY
        assert transactions[0].symbol == "AAPL"
        assert transactions[0].quantity == Decimal("10")
        assert transactions[0].amount == Decimal("1500.00")

        # Check second transaction
        assert transactions[1].date == date(2024, 1, 20)
        assert transactions[1].type == TransactionType.SELL
        assert transactions[1].symbol == "GOOGL"
        assert transactions[1].quantity == Decimal("5")
        assert transactions[1].amount == Decimal("2500.00")

    def test_parse_transactions_with_alternative_headers(self):
        """Test parsing with alternative column names like 'Trade Date' and 'Action'."""
        mock_table = [
            ["Trade Date", "Action", "Ticker", "Shares", "Total"],
            ["02/10/2024", "Purchase", "TSLA", "3", "$750.00"],
        ]

        parser = GenericParser("", [mock_table])
        transactions = parser._parse_transactions()

        assert len(transactions) == 1
        assert transactions[0].date == date(2024, 2, 10)
        assert transactions[0].type == TransactionType.BUY  # "Purchase" maps to BUY
        assert transactions[0].symbol == "TSLA"
        assert transactions[0].quantity == Decimal("3")
        assert transactions[0].amount == Decimal("750.00")

    def test_parse_transactions_missing_required_columns(self):
        """Test that tables without Date+Amount are skipped gracefully."""
        # Table missing Amount column
        mock_table = [
            ["Date", "Type", "Symbol"],
            ["01/15/2024", "Buy", "AAPL"],
        ]

        parser = GenericParser("", [mock_table])
        transactions = parser._parse_transactions()

        # Should return empty, not crash
        assert len(transactions) == 0

    def test_parse_positions_with_standard_headers(self):
        """Test parsing positions table with standard headers."""
        mock_table = [
            ["Symbol", "Quantity", "Value"],
            ["AAPL", "100", "$15,000.00"],
            ["GOOGL", "50", "$7,500.00"],
        ]

        parser = GenericParser("", [mock_table])
        positions = parser._parse_positions()

        assert len(positions) == 2
        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == Decimal("100")
        assert positions[0].market_value == Decimal("15000.00")

    def test_parse_positions_with_alternative_headers(self):
        """Test parsing positions with alternative column names."""
        mock_table = [
            ["Security", "Shares", "Market Value"],
            ["Microsoft Corp", "200", "$50,000.00"],
        ]

        parser = GenericParser("", [mock_table])
        positions = parser._parse_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "Microsoft Corp"
        assert positions[0].quantity == Decimal("200")
        assert positions[0].market_value == Decimal("50000.00")

    def test_parse_positions_missing_required_columns(self):
        """Test that position tables without required columns are skipped."""
        # Missing Value column
        mock_table = [
            ["Symbol", "Quantity"],
            ["AAPL", "100"],
        ]

        parser = GenericParser("", [mock_table])
        positions = parser._parse_positions()

        assert len(positions) == 0

    def test_non_standard_headers_returns_empty(self):
        """Test that completely non-standard headers result in empty lists, not crash."""
        mock_table = [
            ["Column1", "Column2", "Column3"],
            ["ValueA", "ValueB", "ValueC"],
        ]

        parser = GenericParser("", [mock_table])
        transactions = parser._parse_transactions()
        positions = parser._parse_positions()

        assert transactions == []
        assert positions == []

    def test_empty_tables_returns_empty(self):
        """Test that empty tables are handled gracefully."""
        parser = GenericParser("", [])
        transactions = parser._parse_transactions()
        positions = parser._parse_positions()

        assert transactions == []
        assert positions == []

    def test_full_parse_with_mixed_tables(self):
        """Test full parse() method with both transaction and position tables."""
        tx_table = [
            ["Date", "Activity", "Symbol", "Amount"],
            ["03/01/2024", "Buy", "VTI", "$5,000.00"],
        ]
        pos_table = [
            ["Symbol", "Quantity", "Value"],
            ["VTI", "50", "$10,000.00"],
        ]

        parser = GenericParser("", [tx_table, pos_table])
        statement = parser.parse()

        assert statement.broker == "Generic"
        assert len(statement.transactions) == 1
        assert len(statement.positions) == 1


class TestGetParserFactory:
    """Tests for the parser factory with GenericParser integration."""

    def test_unknown_broker_with_tables_returns_generic_parser(self):
        """Test that unknown broker with tables returns GenericParser."""
        mock_tables = [
            [["Date", "Type", "Amount"], ["01/01/2024", "Buy", "$100"]]
        ]
        parser = get_parser("unknown", "some text", tables=mock_tables)

        assert parser is not None
        assert parser.get_broker_name() == "Generic"

    def test_unknown_broker_without_tables_returns_none(self):
        """Test that unknown broker without tables returns None."""
        parser = get_parser("unknown", "some text", tables=None)
        assert parser is None

        parser = get_parser("unknown", "some text", tables=[])
        assert parser is None

    def test_known_broker_still_returns_correct_parser(self):
        """Test that known brokers still get their specific parsers."""
        parser = get_parser("schwab", "some text", tables=[])
        assert parser is not None
        assert parser.get_broker_name() == "Schwab"

        parser = get_parser("fidelity", "some text", tables=[])
        assert parser is not None
        assert parser.get_broker_name() == "Fidelity"

        parser = get_parser("vanguard", "some text", tables=[])
        assert parser is not None
        assert parser.get_broker_name() == "Vanguard"
