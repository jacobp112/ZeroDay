"""Tests for optional OCR support in extraction module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestOCRTrigger:
    """Test that OCR is triggered when native text extraction yields little text."""

    @patch('brokerage_parser.extraction.fitz')
    def test_ocr_triggered_on_low_text_content(self, mock_fitz):
        """Verify _attempt_ocr is called when page has < 50 chars."""
        # Import after patching
        from brokerage_parser import extraction

        # Mock the page
        mock_page = MagicMock()
        mock_page.get_text.return_value = "short"  # Only 5 chars

        # Mock the document
        mock_doc = MagicMock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extraction, '_attempt_ocr', return_value="") as mock_ocr:
            with patch.object(Path, 'exists', return_value=True):
                extraction.extract_text(Path("dummy.pdf"))

        # OCR should have been attempted
        mock_ocr.assert_called_once()

    @patch('brokerage_parser.extraction.fitz')
    def test_ocr_not_triggered_on_sufficient_text(self, mock_fitz):
        """Verify _attempt_ocr is NOT called when page has >= 50 chars."""
        from brokerage_parser import extraction

        # Mock the page with enough text
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 100  # 100 chars - sufficient

        # Mock the document
        mock_doc = MagicMock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extraction, '_attempt_ocr', return_value="OCR text") as mock_ocr:
            with patch.object(Path, 'exists', return_value=True):
                extraction.extract_text(Path("dummy.pdf"))

        # OCR should NOT have been called
        mock_ocr.assert_not_called()


class TestOCRSuccess:
    """Test successful OCR extraction."""

    def test_attempt_ocr_returns_text_when_available(self):
        """Test _attempt_ocr returns OCR text when pytesseract works."""
        from brokerage_parser import extraction

        # Skip if OCR not available
        if not extraction.OCR_AVAILABLE:
            pytest.skip("pytesseract not installed")

        # Mock a page
        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Fake PNG
        mock_page.get_pixmap.return_value = mock_pixmap

        # Mock pytesseract
        with patch.object(extraction.pytesseract, 'image_to_string', return_value="Scanned Transaction Data"):
            with patch.object(extraction.Image, 'open') as mock_image_open:
                mock_image_open.return_value = MagicMock()
                result = extraction._attempt_ocr(mock_page)

        assert result == "Scanned Transaction Data"

    @patch('brokerage_parser.extraction.fitz')
    def test_ocr_text_used_when_better_than_native(self, mock_fitz):
        """Test that OCR text replaces native text when it has more content."""
        from brokerage_parser import extraction

        if not extraction.OCR_AVAILABLE:
            pytest.skip("pytesseract not installed")

        # Mock the page with very little native text
        mock_page = MagicMock()
        mock_page.get_text.return_value = "x"  # Only 1 char

        # Mock the document
        mock_doc = MagicMock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
        mock_doc.__enter__ = Mock(return_value=mock_doc)
        mock_doc.__exit__ = Mock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        # Mock OCR to return meaningful text
        with patch.object(extraction, '_attempt_ocr', return_value="Scanned Transaction Data From OCR"):
            with patch.object(Path, 'exists', return_value=True):
                result = extraction.extract_text(Path("dummy.pdf"))

        # Should use OCR text since it's longer
        assert "Scanned Transaction Data From OCR" in result[1]


class TestMissingDependency:
    """Test graceful handling when OCR dependencies are missing."""

    def test_attempt_ocr_returns_empty_when_not_available(self):
        """Test _attempt_ocr returns empty string when pytesseract not installed."""
        from brokerage_parser import extraction

        # Save original value
        original_available = extraction.OCR_AVAILABLE

        try:
            # Simulate OCR not available
            extraction.OCR_AVAILABLE = False

            mock_page = MagicMock()
            result = extraction._attempt_ocr(mock_page)

            assert result == ""
        finally:
            # Restore
            extraction.OCR_AVAILABLE = original_available

    def test_attempt_ocr_handles_tesseract_not_found(self):
        """Test _attempt_ocr handles TesseractNotFoundError gracefully."""
        from brokerage_parser import extraction

        if not extraction.OCR_AVAILABLE:
            pytest.skip("pytesseract not installed")

        # Mock a page
        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        mock_page.get_pixmap.return_value = mock_pixmap

        # Mock pytesseract to raise TesseractNotFoundError
        with patch.object(extraction.pytesseract, 'image_to_string') as mock_ocr:
            mock_ocr.side_effect = extraction.pytesseract.TesseractNotFoundError()
            with patch.object(extraction.Image, 'open') as mock_image_open:
                mock_image_open.return_value = MagicMock()
                result = extraction._attempt_ocr(mock_page)

        # Should return empty string, not crash
        assert result == ""

    @patch('brokerage_parser.extraction.fitz')
    def test_extract_text_continues_without_ocr(self, mock_fitz):
        """Test extract_text works even when OCR is unavailable."""
        from brokerage_parser import extraction

        # Save original value
        original_available = extraction.OCR_AVAILABLE

        try:
            # Simulate OCR not available
            extraction.OCR_AVAILABLE = False

            # Mock the page with minimal text
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Hello"

            # Mock the document
            mock_doc = MagicMock()
            mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
            mock_doc.__enter__ = Mock(return_value=mock_doc)
            mock_doc.__exit__ = Mock(return_value=False)
            mock_fitz.open.return_value = mock_doc

            with patch.object(Path, 'exists', return_value=True):
                # Should not crash
                result = extraction.extract_text(Path("dummy.pdf"))

            # Should return the native text
            assert result[1] == "Hello"
        finally:
            # Restore
            extraction.OCR_AVAILABLE = original_available
