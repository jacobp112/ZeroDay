import pytest
from decimal import Decimal
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser
from brokerage_parser.models import TransactionType

class TestBaseUtilities:
    """Tests for utility methods in the base Parser class."""

    def setup_method(self):
        # Instantiate a concrete parser to access base methods
        self.parser = SchwabParser("dummy")

    @pytest.mark.parametrize("input_val, expected", [
        ("100.00", Decimal("100.00")),
        ("$100.00", Decimal("100.00")),
        ("-100.00", Decimal("-100.00")),
        ("($100.00)", Decimal("-100.00")),
        ("$  1,500.00", Decimal("1500.00")),
        ("1,234.56", Decimal("1234.56")),
    ])
    def test_parse_decimal_valid(self, input_val, expected):
        assert self.parser._parse_decimal(input_val) == expected

    @pytest.mark.parametrize("bad_input", ["", None, "$", "abc", "N/A", "12.34.56"])
    def test_parse_decimal_invalid(self, bad_input):
        assert self.parser._parse_decimal(bad_input) is None

    @pytest.mark.parametrize("date_str", ["", "invalid", "13/45/99", "2023-01-15"])
    def test_parse_date_invalid(self, date_str):
        assert self.parser._parse_date(date_str) is None

class TestEmptyInput:
    """Tests handling of empty or minimal inputs."""

    @pytest.mark.parametrize("parser_cls", [SchwabParser, FidelityParser, VanguardParser])
    def test_empty_string(self, parser_cls):
        parser = parser_cls("")
        statement = parser.parse()
        assert statement.positions == []
        assert statement.transactions == []
        # Should default to Unknown/Brokerage if parsing fails but shouldn't crash
        assert statement.account.account_number == "Unknown" or statement.account.account_number is None

    def test_whitespace_only(self):
        parser = SchwabParser("   \n   \t   ")
        statement = parser.parse()
        assert statement.transactions == []

class TestMalformedDates:
    """Tests parsing logic when dates are malformed."""

    def test_invalid_date_format_in_transaction(self):
        text = """
        Transaction Detail
        99/99/2023    Buy AAPL 10 Shares    -1500.00
        Jan 01 2023   Sell MSFT 5 Shares     750.00
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        # Should gracefully skip these lines or fail to create transactions
        # Currently our logic requires a valid date to create a tx
        assert len(statement.transactions) == 0

class TestMalformedAmounts:
    """Tests parsing logic when amounts are malformed."""

    def test_missing_or_bad_amounts(self):
        text = """
        Transaction Detail
        01/01/23    Buy AAPL 10 Shares    $N/A
        01/02/23    Sell MSFT 5 Shares
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        assert len(statement.transactions) == 0

class TestMissingSections:
    """Tests handling of missing sections."""

    def test_no_transaction_section(self):
        text = """
        Account Holdings
        AAPL 100 150.00 15000.00
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        assert statement.transactions == []
        assert len(statement.positions) == 1

    def test_no_holdings_section(self):
        text = """
        Transaction Detail
        01/01/23 Buy AAPL 1 Share -100.00
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        assert statement.positions == []
        assert len(statement.transactions) == 1

class TestPartialData:
    """Tests transactions with missing fields."""

    def test_transaction_no_symbol(self):
        # "Buy" but no clear symbol
        text = """
        Transaction Detail
        01/01/23    Buy Something Weird    -100.00
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        # Invalid input (no quantity) should result in no transaction being parsed
        assert len(statement.transactions) == 0

class TestSpecialCharacters:
    """Tests inputs with special characters and formatting."""

    def test_extra_spaces_and_unicode_in_description(self):
        text = """
        Transaction Detail
        01/01/23    Buy   Vanguard® 500 Index   (VFIAX)  10 Shares -500.00
        Total
        """
        parser = SchwabParser(text)
        statement = parser.parse()
        # Regex is strict and fails on complexities like unicode or unusual spacing/parens without perfect match
        assert len(statement.transactions) == 0

class TestBoundaryConditions:
    """Stress tests and boundaries."""

    def test_large_input_stress_test(self):
        # Generate 100 transactions
        lines = ["Transaction Detail"]
        for i in range(100):
            # Use valid symbol format ABC
            lines.append(f"01/01/23    Buy ABC 10 @ 10.00    -100.00")
        lines.append("Total")

        text = "\n".join(lines)
        parser = SchwabParser(text)
        statement = parser.parse()

        assert len(statement.transactions) == 100
        assert statement.transactions[99].symbol == "ABC"
