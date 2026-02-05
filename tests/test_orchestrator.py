import pytest
from unittest.mock import patch, MagicMock
from brokerage_parser.orchestrator import process_statement
from brokerage_parser.models import ParsedStatement

@patch("brokerage_parser.orchestrator.extract_text")
@patch("brokerage_parser.orchestrator.detect_broker")
@patch("brokerage_parser.orchestrator.get_parser")
def test_process_statement_success(mock_get_parser, mock_detect, mock_extract, tmp_path):
    # Setup Mocks
    mock_pdf = tmp_path / "dummy.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Schwab Header\nTransaction Detail\n..."}
    mock_detect.return_value = ("schwab", 0.9)

    mock_parser_instance = MagicMock()
    mock_statement = ParsedStatement(broker="Schwab", account_number="123")
    mock_parser_instance.parse.return_value = mock_statement
    mock_get_parser.return_value = mock_parser_instance

    # Execute
    result = process_statement(str(mock_pdf))

    # Verify
    assert result.broker == "Schwab"
    assert result.account_number == "123"
    mock_extract.assert_called_once()
    mock_detect.assert_called_once()
    mock_get_parser.assert_called_once()
    mock_parser_instance.parse.assert_called_once()


@patch("brokerage_parser.orchestrator.extract_text")
@patch("brokerage_parser.orchestrator.detect_broker")
def test_process_statement_unknown_broker(mock_detect, mock_extract, tmp_path):
    mock_pdf = tmp_path / "unknown.pdf"
    mock_pdf.touch()

    mock_extract.return_value = {1: "Unknown content"}
    mock_detect.return_value = ("unknown", 0.0)

    result = process_statement(str(mock_pdf))

    assert result.broker == "Unknown"
    assert "Could not detect broker." in result.parse_errors

def test_process_statement_file_not_found():
    with pytest.raises(ValueError):
        process_statement("non_existent.pdf")
