"""Tests for position extraction from structured table data."""
import pytest
from decimal import Decimal
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser


class TestSchwabPositionsFromTables:
    """Test Schwab position extraction from table data."""

    def test_parse_positions_from_tables_basic(self):
        """Test basic position extraction with standard Schwab table format."""
        # Mock table data with standard headers
        tables = [[
            ["Symbol", "Description", "Quantity", "Price", "Market Value"],
            ["AAPL", "Apple Inc", "100", "$150.00", "$15,000.00"],
            ["MSFT", "Microsoft Corp", "50", "$300.00", "$15,000.00"],
            ["GOOGL", "Alphabet Inc", "25", "$2,000.00", "$50,000.00"],
        ]]

        parser = SchwabParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 3
        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == Decimal("100")
        assert positions[0].price == Decimal("150.00")
        assert positions[0].market_value == Decimal("15000.00")

        assert positions[1].symbol == "MSFT"
        assert positions[2].symbol == "GOOGL"

    def test_parse_positions_skips_header_rows(self):
        """Test that header/footer rows are skipped."""
        tables = [[
            ["Symbol", "Description", "Shares", "Price", "Value"],
            ["Total", "Total Value", "", "", "$80,000.00"],
            ["AAPL", "Apple Inc", "100", "$150.00", "$15,000.00"],
        ]]

        parser = SchwabParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"

    def test_parse_positions_falls_back_to_regex(self):
        """Test that _parse_positions falls back to regex when no table data."""
        parser = SchwabParser("Sample text with no holdings section", [])
        positions = parser._parse_positions()

        assert len(positions) == 0  # No data to parse


class TestFidelityPositionsFromTables:
    """Test Fidelity position extraction from table data."""

    def test_parse_positions_from_tables_basic(self):
        """Test basic position extraction with standard Fidelity table format."""
        tables = [[
            ["Symbol", "Name", "Shares", "Price", "Current Value"],
            ["VTI", "Vanguard Total Stock Market ETF", "200", "$220.50", "$44,100.00"],
            ["BND", "Vanguard Total Bond Market ETF", "150", "$80.00", "$12,000.00"],
        ]]

        parser = FidelityParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 2
        assert positions[0].symbol == "VTI"
        assert positions[0].description == "Vanguard Total Stock Market ETF"
        assert positions[0].quantity == Decimal("200")
        assert positions[0].price == Decimal("220.50")
        assert positions[0].market_value == Decimal("44100.00")

    def test_parse_positions_extracts_symbol_from_description(self):
        """Test symbol extraction when Symbol column is missing."""
        tables = [[
            ["Security", "Shares", "Price", "Value"],
            ["Apple Inc AAPL", "100", "$150.00", "$15,000.00"],
        ]]

        parser = FidelityParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        # Should extract AAPL from description
        assert positions[0].symbol == "AAPL"

    def test_parse_positions_with_header_on_row_1(self):
        """Test position extraction when header is on row 1 instead of row 0."""
        tables = [[
            ["Your Holdings Summary", "", "", "", ""],
            ["Symbol", "Security", "Shares", "Price", "Value"],
            ["TSLA", "Tesla Inc", "30", "$250.00", "$7,500.00"],
        ]]

        parser = FidelityParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        assert positions[0].symbol == "TSLA"


class TestVanguardPositionsFromTables:
    """Test Vanguard position extraction from table data."""

    def test_parse_positions_from_tables_basic(self):
        """Test basic position extraction with Vanguard table format."""
        tables = [[
            ["Symbol", "Investment", "Shares", "NAV", "Value"],
            ["", "Vanguard 500 Index Fund Admiral Shares VFIAX", "100", "$400.00", "$40,000.00"],
            ["", "Vanguard Total Bond Market Index Fund VBTLX", "200", "$10.50", "$2,100.00"],
        ]]

        parser = VanguardParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 2
        # Should extract ticker from end of description
        assert positions[0].symbol == "VFIAX"
        assert positions[0].quantity == Decimal("100")
        assert positions[0].price == Decimal("400.00")
        assert positions[0].market_value == Decimal("40000.00")

        assert positions[1].symbol == "VBTLX"

    def test_vanguard_ticker_extraction_from_description(self):
        """Test Vanguard-specific ticker extraction from description."""
        tables = [[
            ["Symbol", "Fund Name", "Shares", "Price", "Value"],
            ["", "Vanguard 500 Index Fund Admiral Shares VFIAX", "100", "$400.00", "$40,000.00"],
        ]]

        parser = VanguardParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        # VFIAX should be extracted from the end of the description
        assert positions[0].symbol == "VFIAX"
        assert "Vanguard 500" in positions[0].description

    def test_vanguard_skips_common_words(self):
        """Test that common words like FUND, INDEX are not used as symbols."""
        tables = [[
            ["Symbol", "Investment", "Shares", "Price", "Value"],
            ["", "Vanguard Real Estate Index Fund", "50", "$100.00", "$5,000.00"],
        ]]

        parser = VanguardParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        # Should NOT use "FUND" or "INDEX" as symbol
        # Should fall back to first few words since no valid ticker found
        assert positions[0].symbol != "FUND"
        assert positions[0].symbol != "INDEX"

    def test_vanguard_with_explicit_symbol_column(self):
        """Test extraction when Symbol column is present."""
        tables = [[
            ["Symbol", "Investment", "Shares", "Price", "Value"],
            ["VFIAX", "Vanguard 500 Index Fund", "100", "$400.00", "$40,000.00"],
        ]]

        parser = VanguardParser("Sample text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        assert positions[0].symbol == "VFIAX"


class TestTableExtractionFallback:
    """Test that table extraction is tried first, with regex fallback."""

    def test_schwab_uses_tables_when_available(self):
        """Verify Schwab uses table data when available."""
        tables = [[
            ["Symbol", "Description", "Quantity", "Price", "Market Value"],
            ["AAPL", "Apple Inc", "100", "$150.00", "$15,000.00"],
        ]]

        # Text that would NOT match regex patterns
        parser = SchwabParser("Random text with no position data", tables)
        positions = parser._parse_positions()

        # Should get position from tables
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"

    def test_fidelity_uses_tables_when_available(self):
        """Verify Fidelity uses table data when available."""
        tables = [[
            ["Symbol", "Name", "Quantity", "Price", "Value"],
            ["MSFT", "Microsoft", "50", "$300.00", "$15,000.00"],
        ]]

        parser = FidelityParser("Random text", tables)
        positions = parser._parse_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "MSFT"

    def test_vanguard_uses_tables_when_available(self):
        """Verify Vanguard uses table data when available."""
        tables = [[
            ["Symbol", "Investment", "Shares", "Price", "Value"],
            ["", "Vanguard Total Stock Market ETF VTI", "75", "$220.00", "$16,500.00"],
        ]]

        parser = VanguardParser("Random text", tables)
        positions = parser._parse_positions()

        assert len(positions) == 1
        # Should extract VTI from end
        assert positions[0].symbol == "VTI"


class TestEdgeCases:
    """Test edge cases in position table parsing."""

    def test_empty_table(self):
        """Test handling of empty tables."""
        tables = [[]]

        parser = SchwabParser("text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 0

    def test_single_row_table(self):
        """Test handling of table with only header row."""
        tables = [[
            ["Symbol", "Description", "Quantity", "Price", "Value"],
        ]]

        parser = SchwabParser("text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 0

    def test_malformed_numeric_values(self):
        """Test handling of malformed numeric values."""
        tables = [[
            ["Symbol", "Description", "Quantity", "Price", "Market Value"],
            ["AAPL", "Apple Inc", "invalid", "$150.00", "$15,000.00"],
        ]]

        parser = SchwabParser("text", tables)
        positions = parser._parse_positions_from_tables()

        # Should still parse with quantity=0
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("0")
        assert positions[0].market_value == Decimal("15000.00")

    def test_missing_price_column(self):
        """Test handling when price column is missing."""
        tables = [[
            ["Symbol", "Name", "Shares", "Value"],
            ["AAPL", "Apple Inc", "100", "$15,000.00"],
        ]]

        parser = FidelityParser("text", tables)
        positions = parser._parse_positions_from_tables()

        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        assert positions[0].price == Decimal("0")  # Default when missing
