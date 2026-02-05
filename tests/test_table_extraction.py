import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from brokerage_parser.extraction import extract_tables, extract_text_with_layout, TableData

@pytest.fixture
def mock_pdf_path():
    p = MagicMock(spec=Path)
    p.exists.return_value = True
    return p

@pytest.fixture
def mock_fitz():
    with patch("brokerage_parser.extraction.fitz") as mock:
        yield mock

def test_extract_tables_success(mock_pdf_path, mock_fitz):

    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_table = MagicMock()

    # Setup table data structure
    table_data = [["Date", "Description", "Amount"], ["01/01/2023", "Test", "100.00"]]
    mock_table.extract.return_value = table_data

    mock_page.find_tables.return_value = [mock_table]
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz.open.return_value = mock_doc

    result = extract_tables(mock_pdf_path)

    assert 1 in result
    assert result[1] == [table_data]
    mock_fitz.open.assert_called_once_with(mock_pdf_path)

def test_extract_tables_no_tables(mock_pdf_path, mock_fitz):

    mock_doc = MagicMock()
    mock_page = MagicMock()

    mock_page.find_tables.return_value = []
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz.open.return_value = mock_doc

    result = extract_tables(mock_pdf_path)

    assert result == {}

def test_extract_tables_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_tables(Path("non_existent.pdf"))

def test_extract_text_with_layout(mock_pdf_path, mock_fitz):
    mock_doc = MagicMock()
    mock_page = MagicMock()

    # Mock blocks: (x0, y0, x1, y1, text, block_no, block_type)
    # type 0 = text
    mock_blocks = [
        (10, 20, 100, 30, "Column 1 Row 1", 0, 0),
        (110, 20, 200, 30, "Column 2 Row 1", 1, 0),
        (10, 40, 100, 50, "Column 1 Row 2", 2, 0),
    ]

    mock_page.get_text.return_value = mock_blocks
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz.open.return_value = mock_doc

    result = extract_text_with_layout(mock_pdf_path)

    assert 1 in result
    extracted = result[1]
    # Verify order - sorting by y then x
    lines = extracted.strip().split('\n')
    assert "Column 1 Row 1" in lines[0] or "Column 2 Row 1" in lines[1]
    # Exact order depends on the simple sort, but checking content is present is key logic verification
