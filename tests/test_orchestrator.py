import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from brokerage_parser.orchestrator import process_statement
from brokerage_parser.models import ParsedStatement
from brokerage_parser.reporting.models import ClientReport

@patch("brokerage_parser.orchestrator.extract_text_with_layout")
@patch("brokerage_parser.orchestrator.detect_broker")
@patch("brokerage_parser.orchestrator.get_parser")
def test_process_statement_success(mock_get_parser, mock_detect, mock_extract, tmp_path):
    # Setup Mocks
    mock_pdf = tmp_path / "dummy.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Schwab Header\nTransaction Detail\n..."}
    mock_detect.return_value = ("schwab", 0.9)

    mock_parser_instance = MagicMock()
    # Mock ParsedStatement with AccountSummary
    mock_account = MagicMock()
    mock_account.account_number = "123"
    mock_account.beginning_balance = Decimal("100.00")
    mock_account.ending_balance = Decimal("100.00")

    mock_statement = ParsedStatement(broker="Schwab", account=mock_account)
    mock_parser_instance.parse.return_value = mock_statement
    mock_get_parser.return_value = mock_parser_instance

    # Execute
    result = process_statement(str(mock_pdf))

    # Verify - result is now ClientReport
    assert isinstance(result, ClientReport)
    assert result.source_statement.broker == "Schwab"
    assert result.metadata.account_number == "123"
    mock_extract.assert_called_once()
    mock_detect.assert_called_once()
    mock_get_parser.assert_called_once()
    mock_parser_instance.parse.assert_called_once()


@patch("brokerage_parser.orchestrator.extract_text_with_layout")
@patch("brokerage_parser.orchestrator.detect_broker")
def test_process_statement_unknown_broker(mock_detect, mock_extract, tmp_path):
    mock_pdf = tmp_path / "unknown.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Unknown content"}
    mock_detect.return_value = ("unknown", 0.0)

    result = process_statement(str(mock_pdf))

    # Should return a ClientReport with errors in source_statement
    assert isinstance(result, ClientReport)
    assert result.source_statement.broker == "Unknown"
    assert "Could not detect broker and no usable tables found." in result.source_statement.parse_errors

def test_process_statement_file_not_found():
    with pytest.raises(ValueError):
        process_statement("non_existent.pdf")
