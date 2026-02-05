import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from decimal import Decimal
from brokerage_parser.models import BoundingBox, SourceReference, ExtractionMethod
from brokerage_parser.extraction import RichPage
from brokerage_parser.parsers.schwab import SchwabParser

@pytest.fixture
def mock_rich_text_map():
    # Construct a simple "hello world" style rich page
    # Added '@' for regex matching
    text = "01/01/23 Buy AAPL 10 @ 150.00 -1500.00"

    # Create synthetic bboxes
    bboxes = []
    x = 0
    y = 100
    for char in text:
        # Space handling: assume logic assigns bbox to space too
        box = BoundingBox(page=1, x0=x, y0=y, x1=x+10, y1=y+10)
        bboxes.append(box)
        x += 10

    return {
        1: RichPage(
            page_num=1,
            full_text=text,
            char_map=bboxes,
            page_height=800,
            page_width=600
        )
    }

def test_rich_page_get_source_for_span(mock_rich_text_map):
    page = mock_rich_text_map[1]
    text = page.full_text

    # Dynamic index finding
    start_idx = text.find("Buy")
    print(f"DEBUG: 'Buy' found at index {start_idx} in '{text}'")

    assert start_idx != -1
    end_idx = start_idx + 3

    source = page.get_source_for_span(start_idx, end_idx)
    assert source is not None
    assert len(source.bboxes) == 1
    assert source.raw_text == "Buy"
    assert source.extraction_method == ExtractionMethod.NATIVE_TEXT

    # Check bbox coords
    # x0 should be start_idx * 10
    expected_x0 = start_idx * 10
    bbox = source.bboxes[0]

    assert bbox.x0 == expected_x0, f"Expected x0={expected_x0} (idx {start_idx}), got {bbox.x0}"
    assert bbox.x1 == expected_x0 + 30 # 3 chars * 10 width
    assert bbox.y0 == 100

def test_schwab_parser_source_tracking(mock_rich_text_map):
    text = mock_rich_text_map[1].full_text

    header = "Transaction Detail\n"
    # Note: text already has @
    full_text = header + text

    # Bboxes for header
    header_bboxes = [None] * len(header)
    full_bboxes = header_bboxes + mock_rich_text_map[1].char_map

    rich_page = RichPage(
        page_num=1,
        full_text=full_text,
        char_map=full_bboxes,
        page_height=800,
        page_width=600
    )

    parser = SchwabParser(text=full_text, tables=[], rich_text_map={1: rich_page})

    txs = parser._parse_transactions()

    assert len(txs) == 1, f"Expected 1 transaction, got {len(txs)}"
    tx = txs[0]

    assert tx.symbol == "AAPL"
    assert tx.amount == Decimal("-1500.00")

    assert tx.source_map is not None

    # Symbol "AAPL"
    orig_sym_idx = text.find("AAPL")
    expected_x0 = orig_sym_idx * 10

    src_sym = tx.source_map.get("symbol")
    assert src_sym is not None, "Symbol source missing"
    assert src_sym.raw_text == "AAPL"
    assert src_sym.bboxes[0].x0 == expected_x0, f"Expected sym x0={expected_x0}, got {src_sym.bboxes[0].x0}"

    # Price
    # "150.00"
    src_price = tx.source_map.get("price")
    assert src_price is not None
    assert src_price.raw_text == "150.00"

    orig_price_idx = text.find("150.00")
    expected_price_x0 = orig_price_idx * 10
    assert src_price.bboxes[0].x0 == expected_price_x0

    # Amount "-1500.00"
    src_amt = tx.source_map.get("amount")
    assert src_amt is not None
    assert src_amt.raw_text == "-1500.00"

def test_merge_bboxes_by_line_ordering():
    """Verify that merging logic respects PDF coordinate system (handling Top-Down reading order)."""
    # PDF Coords: Y=0 is bottom. Higher Y is top.
    # Line 1 (Top): y=700-710
    # Line 2 (Bottom): y=680-690

    line1_char1 = BoundingBox(1, 10, 700, 20, 710)
    line1_char2 = BoundingBox(1, 20, 700, 30, 710)

    line2_char1 = BoundingBox(1, 10, 680, 20, 690)

    # Unsorted input
    bboxes = [line2_char1, line1_char2, line1_char1]

    page = RichPage(1, "dummy", [], 800, 600)
    merged = page._merge_bboxes_by_line(bboxes)

    # Expect 2 merged boxes.
    # Order should be Line 1 then Line 2?
    # _merge_bboxes_by_line sorts by -y1.
    # Line 1 y1=710. -710.
    # Line 2 y1=690. -690.
    # -710 < -690. So Line 1 comes first.

    assert len(merged) == 2
    assert merged[0].y0 == 700 # Line 1
    assert merged[1].y0 == 680 # Line 2

def test_rich_table_structure():
    from brokerage_parser.extraction import RichTable, RichCell

    cell1 = RichCell("Header", BoundingBox(1, 10, 700, 50, 720))
    cell2 = RichCell("Value", BoundingBox(1, 10, 680, 50, 700))

    table = RichTable(1, [[cell1], [cell2]])

    # Test conversion
    plain = table.to_plain()
    assert plain == [["Header"], ["Value"]]
