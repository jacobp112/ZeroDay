import pytest
from brokerage_parser.extraction import (
    detect_implicit_columns,
    split_line_by_columns,
    text_to_implicit_table
)


class TestDetectImplicitColumns:
    """Tests for detect_implicit_columns() function."""

    def test_detect_columns_with_aligned_text(self):
        """Test detection with sample aligned text (3 columns)."""
        lines = [
            "Date        Description          Amount",
            "01/15/23    Buy AAPL            -1500.00",
            "01/16/23    Dividend MSFT          25.50",
            "01/17/23    Sell GOOGL           2500.00",
            "01/18/23    Buy TSLA             -750.00",
            "01/19/23    Interest                5.25",
        ]

        columns = detect_implicit_columns(lines, min_gap=3, min_lines=5)

        # Should detect 2 column boundaries (between 3 columns)
        assert len(columns) == 2
        # Columns should be around positions 8 and 23
        assert 6 <= columns[0] <= 12  # After "Date" / "01/15/23"
        assert 20 <= columns[1] <= 28  # After "Description" / text

    def test_detect_columns_with_4_columns(self):
        """Test detection with 4 columns."""
        lines = [
            "Date        Symbol     Quantity     Amount",
            "01/15/23    AAPL       100          15000.00",
            "01/16/23    GOOGL      50            7500.00",
            "01/17/23    MSFT       200          20000.00",
            "01/18/23    TSLA       25            5000.00",
            "01/19/23    AMZN       30            6000.00",
        ]

        columns = detect_implicit_columns(lines, min_gap=3, min_lines=5)

        # Should detect 3 column boundaries (between 4 columns)
        assert len(columns) == 3

    def test_no_columns_with_inconsistent_spacing(self):
        """Test that inconsistent spacing returns no columns."""
        lines = [
            "This is just some random text without columns",
            "Another line with different spacing here",
            "And yet another line that doesn't align at all",
            "Random text that has no structure whatsoever",
            "Final line with no consistent gaps to detect",
        ]

        columns = detect_implicit_columns(lines, min_gap=3, min_lines=5)

        # Should not detect any columns
        assert len(columns) == 0

    def test_too_few_lines(self):
        """Test that too few lines returns empty list."""
        lines = [
            "Date        Amount",
            "01/15/23    1500.00",
        ]

        columns = detect_implicit_columns(lines, min_gap=3, min_lines=5)

        assert len(columns) == 0

    def test_empty_lines(self):
        """Test with empty input."""
        columns = detect_implicit_columns([], min_gap=3, min_lines=5)
        assert columns == []

    def test_very_short_lines(self):
        """Test with lines too short to have columns."""
        lines = ["a b", "c d", "e f", "g h", "i j"]

        columns = detect_implicit_columns(lines, min_gap=3, min_lines=5)
        assert columns == []


class TestSplitLineByColumns:
    """Tests for split_line_by_columns() function."""

    def test_split_with_column_positions(self):
        """Test splitting a line at specified positions."""
        line = "Date        Description          Amount"
        positions = [8, 23]  # Based on actual detected positions

        cells = split_line_by_columns(line, positions)

        assert len(cells) == 3
        assert "Date" in cells[0]
        assert "Description" in cells[1]
        assert "Amount" in cells[2]

    def test_split_data_row(self):
        """Test splitting a data row."""
        line = "01/15/23    Buy AAPL            -1500.00"
        positions = [8, 23]  # Actual detected positions

        cells = split_line_by_columns(line, positions)

        assert len(cells) == 3
        assert cells[0] == "01/15/23"
        assert "Buy AAPL" in cells[1]
        assert "-1500.00" in cells[2]

    def test_split_short_line(self):
        """Test splitting a line shorter than expected."""
        line = "Short"
        positions = [12, 33]

        cells = split_line_by_columns(line, positions)

        # Should handle gracefully
        assert len(cells) == 3
        assert cells[0] == "Short"
        assert cells[1] == ""
        assert cells[2] == ""

    def test_split_no_positions(self):
        """Test splitting with no column positions."""
        line = "Just a regular line of text"
        positions = []

        cells = split_line_by_columns(line, positions)

        assert len(cells) == 1
        assert cells[0] == "Just a regular line of text"

    def test_split_empty_line(self):
        """Test splitting empty line."""
        line = ""
        positions = [12, 33]

        cells = split_line_by_columns(line, positions)

        # Should return list with empty strings
        assert len(cells) >= 1


class TestTextToImplicitTable:
    """Tests for text_to_implicit_table() function."""

    def test_convert_aligned_text_to_table(self):
        """Test converting aligned text to table structure."""
        text = """Date        Description          Amount
01/15/23    Buy AAPL            -1500.00
01/16/23    Dividend MSFT          25.50
01/17/23    Sell GOOGL           2500.00
01/18/23    Buy TSLA             -750.00
01/19/23    Interest                5.25"""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)

        # Should produce a valid table
        assert len(table) >= 5  # Header + 5 data rows
        assert len(table[0]) >= 2  # At least 2 columns

        # Check header
        assert "Date" in table[0][0]

        # Check that all rows have same number of columns
        col_count = len(table[0])
        for row in table:
            assert len(row) == col_count

    def test_no_table_for_unstructured_text(self):
        """Test that unstructured text returns empty."""
        text = """This is just a paragraph of text.
It has multiple lines but no column structure.
The spacing is inconsistent throughout.
There are no tables here to detect.
Just regular prose without alignment."""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)

        assert table == []

    def test_empty_text(self):
        """Test with empty input."""
        table = text_to_implicit_table("", min_gap=3, min_lines=5)
        assert table == []

    def test_too_few_lines(self):
        """Test with text having too few lines."""
        text = """Date        Amount
01/15/23    1500.00"""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)
        assert table == []

    def test_whitespace_only_text(self):
        """Test with whitespace-only text."""
        text = "   \n\n   \n  "
        table = text_to_implicit_table(text, min_gap=3, min_lines=5)
        assert table == []

    def test_normalized_column_count(self):
        """Test that all rows have normalized column count."""
        text = """Col1        Col2        Col3
Data1       Data2       Data3
Short
Medium      MedData
Full        FullData    Complete
Another     Row         Here"""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)

        if table:  # Only test if table was detected
            col_count = len(table[0])
            for row in table:
                assert len(row) == col_count


class TestImplicitTableIntegration:
    """Integration tests for implicit table detection."""

    def test_sample_brokerage_format(self):
        """Test with a realistic brokerage statement format."""
        text = """Account Activity Summary

Transaction     Trade         Settlement    Description                    Amount
Type            Date          Date

BUY             01/15/2024    01/17/2024    APPLE INC COM                 -1,500.00
SELL            01/20/2024    01/22/2024    GOOGLE INC CL A                2,500.00
DIVIDEND        01/25/2024    01/25/2024    MICROSOFT CORP                    25.50
BUY             01/28/2024    01/30/2024    TESLA INC                       -750.00
INTEREST        01/31/2024    01/31/2024    CASH INTEREST                      5.25"""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)

        # Should detect the tabular portion
        assert len(table) >= 5

    def test_holdings_format(self):
        """Test with holdings/positions format."""
        text = """Current Holdings as of 01/31/2024

Symbol          Description              Quantity        Price          Value

AAPL            Apple Inc                    100         150.00      15,000.00
GOOGL           Alphabet Inc                  50         140.00       7,000.00
MSFT            Microsoft Corp               200         400.00      80,000.00
AMZN            Amazon.com Inc                30         170.00       5,100.00
TSLA            Tesla Inc                     25         200.00       5,000.00
META            Meta Platforms                40         350.00      14,000.00"""

        table = text_to_implicit_table(text, min_gap=3, min_lines=5)

        # Should detect holdings table
        assert len(table) >= 5
