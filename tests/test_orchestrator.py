import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from brokerage_parser.orchestrator import process_statement
from brokerage_parser.models import ParsedStatement

@patch("brokerage_parser.orchestrator.extract_rich_text")
@patch("brokerage_parser.orchestrator.extract_tables")
@patch("brokerage_parser.orchestrator.extract_text_with_layout")
@patch("brokerage_parser.orchestrator.detect_broker")
@patch("brokerage_parser.orchestrator.get_parser")
def test_process_statement_success(mock_get_parser, mock_detect, mock_extract, mock_tables, mock_rich_text, tmp_path):
    # Setup Mocks
    mock_pdf = tmp_path / "dummy.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Schwab Header\nTransaction Detail\n..."}
    mock_tables.return_value = {1: []}  # Empty tables
    mock_rich_text.return_value = {}
    mock_detect.return_value = ("schwab", 0.9)

    mock_parser_instance = MagicMock()
    # Mock ParsedStatement with AccountSummary
    mock_account = MagicMock()
    mock_account.account_number = "123"
    mock_account.beginning_balance = Decimal("100.00")
    mock_account.ending_balance = Decimal("100.00")

    mock_statement = ParsedStatement(broker="Schwab", account=mock_account)
    mock_parser_instance.parse.return_value = mock_statement

    # get_parser returns a CLASS, which is then instantiated.
    # So we need a mock class that returns mock_parser_instance when called
    mock_parser_class = MagicMock(return_value=mock_parser_instance)
    mock_get_parser.return_value = mock_parser_class

    # Execute
    result = process_statement(str(mock_pdf))

    # Verify - result is ParsedStatement
    assert isinstance(result, ParsedStatement)
    assert result.broker == "Schwab"
    mock_extract.assert_called_once()
    mock_detect.assert_called_once()
    mock_get_parser.assert_called_once()
    mock_parser_instance.parse.assert_called_once()


@patch("brokerage_parser.orchestrator.extract_rich_text")
@patch("brokerage_parser.orchestrator.extract_tables")
@patch("brokerage_parser.orchestrator.extract_text_with_layout")
@patch("brokerage_parser.orchestrator.detect_broker")
@patch("brokerage_parser.orchestrator.get_parser")
def test_process_statement_unknown_broker(mock_get_parser, mock_detect, mock_extract, mock_tables, mock_rich_text, tmp_path):
    mock_pdf = tmp_path / "unknown.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Unknown content"}
    mock_tables.return_value = {1: []}
    mock_rich_text.return_value = {}
    mock_detect.return_value = ("unknown", 0.0)

    # For unknown broker, get_parser returns GenericParser class
    mock_parser_instance = MagicMock()
    mock_statement = ParsedStatement(broker="Unknown")
    mock_statement.parse_errors = ["Could not detect broker and no usable tables found."]
    mock_parser_instance.parse.return_value = mock_statement

    # get_parser returns a CLASS, which is then instantiated
    mock_parser_class = MagicMock(return_value=mock_parser_instance)
    mock_get_parser.return_value = mock_parser_class

    result = process_statement(str(mock_pdf))

    # Should return a ParsedStatement with parse_errors
    assert isinstance(result, ParsedStatement)
    assert result.broker == "Unknown"

def test_process_statement_file_not_found():
    with pytest.raises(FileNotFoundError):
        process_statement("non_existent.pdf")
