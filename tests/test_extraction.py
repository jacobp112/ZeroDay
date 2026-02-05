import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from brokerage_parser.extraction import extract_text

@pytest.fixture
def mock_pdf_path(tmp_path):
    f = tmp_path / "test.pdf"
    f.touch()
    return f

def test_extract_text_success(mock_pdf_path):
    """Test standard native text extraction via PyMuPDF (fitz)."""

    # Mock fitz.open
    with patch("brokerage_parser.extraction.fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Transaction Date: 2023-01-01\nBought AAPL 100 shares"

        # Make the doc iterable, yielding the page
        mock_doc.__iter__.return_value = [mock_page]
        mock_open.return_value = mock_doc

        result = extract_text(mock_pdf_path)

        assert 1 in result
        assert "Transaction Date" in result[1]
        mock_page.get_text.assert_called_once()
        mock_doc.close.assert_called_once()

def test_extract_text_low_content_warning(mock_pdf_path, caplog):
    """Test that a warning is logged when page content is low (potential scan)."""

    import logging

    with patch("brokerage_parser.extraction.fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        # Simulate very little text
        mock_page.get_text.return_value = "   Page number 1   "

        mock_doc.__iter__.return_value = [mock_page]
        mock_open.return_value = mock_doc

        with caplog.at_level(logging.WARNING):
            result = extract_text(mock_pdf_path)

        # Check that we still got the text
        assert 1 in result
        assert "Page number 1" in result[1]

        # Verify warning was logged
        assert "has only" in caplog.text
        assert "Attempting OCR" in caplog.text

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_text(Path("non_existent_file.pdf"))
