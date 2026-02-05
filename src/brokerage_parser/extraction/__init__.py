from pathlib import Path
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import io
from dataclasses import dataclass

from brokerage_parser.models import BoundingBox, SourceReference, ExtractionMethod

# ... existing imports ...

# Configure logger
logger = logging.getLogger(__name__)

# Type definition for legacy tables
TableData = List[List[List[str]]]

# Optional OCR support
# ... (rest of file)
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    Image = None

@dataclass
class RichCell:
    text: str
    bbox: Optional[BoundingBox] = None

@dataclass
class RichTable:
    page_num: int
    rows: List[List[RichCell]]

    def to_plain(self) -> List[List[str]]:
        """Returns plain string representation for backward compatibility."""
        return [[cell.text for cell in row] for row in self.rows]

@dataclass
class RichPage:
    page_num: int
    full_text: str
    char_map: List[Optional[BoundingBox]]
    page_height: float
    page_width: float

    def get_source_for_span(self, start: int, end: int) -> Optional[SourceReference]:
        """
        Returns SourceReference for a span of text in the full_text.
        Computes the union of bboxes for valid characters in that range.
        """
        if start < 0 or end > len(self.char_map) or start >= end:
            return None

        span_bboxes = self.char_map[start:end]
        valid_bboxes = [b for b in span_bboxes if b is not None]

        if not valid_bboxes:
            # If we matched something but have no coords (e.g. newline chars, or inferred text)
            # return implicit low confidence source or None?
            # Requirement: "return the value with a null/empty source reference rather than failing"
            return SourceReference(
                bboxes=[],
                extraction_method=ExtractionMethod.INFERRED,
                confidence=0.0,
                raw_text=self.full_text[start:end]
            )

        # Merge bboxes
        # Simple union: min x0, min y0, max x1, max y1
        # But we might have multiple lines.
        # Ideally we return a list of block-bboxes (one per line/segment).
        # Heuristic: Group overlapping/nearby bboxes into lines?
        # For simplicity MVP: just return the list of ALL character bboxes?
        # Plan said: "List[BoundingBox]".
        # Optimization: Unions contiguous bboxes on the same line.

        merged_bboxes = self._merge_bboxes_by_line(valid_bboxes)

        return SourceReference(
            bboxes=merged_bboxes,
            extraction_method=ExtractionMethod.NATIVE_TEXT,
            confidence=1.0,
            raw_text=self.full_text[start:end]
        )

    def _merge_bboxes_by_line(self, bboxes: List[BoundingBox]) -> List[BoundingBox]:
        """Merge character bboxes into word/line chunks.
           Assumes PDF Coordinates (y=0 at bottom). Sorts Top-Down (descending Y)."""
        if not bboxes:
            return []

        # Group by vertical proximity.
        # For PDF coords, Top is high Y.
        # we want to process Top-to-Bottom, Left-to-Right.
        # Key: (-y1 (top), x0). Round y to group roughly.
        sorted_boxes = sorted(bboxes, key=lambda b: (round(-b.y1, 1), b.x0))

        merged = []
        current_box = sorted_boxes[0]

        for next_box in sorted_boxes[1:]:
            # Check Y-center proximity
            cy1 = (current_box.y0 + current_box.y1) / 2
            cy2 = (next_box.y0 + next_box.y1) / 2

            if abs(cy1 - cy2) < 5:
                current_box = BoundingBox(
                    page=current_box.page,
                    x0=min(current_box.x0, next_box.x0),
                    y0=min(current_box.y0, next_box.y0),
                    x1=max(current_box.x1, next_box.x1),
                    y1=max(current_box.y1, next_box.y1)
                )
            else:
                merged.append(current_box)
                current_box = next_box

        merged.append(current_box)
        return merged

def extract_tables(pdf_path: Path) -> Dict[int, List[RichTable]]:
    """
    Extracts tables with bounding box information using PyMuPDF.
    """
    # Need to access page height to flip coords.
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_tables = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            h = page.rect.height
            tables = page.find_tables()
            page_tables = []
            if tables:
                for table in tables:
                    rows = []
                    # Helper to flip
                    def to_bbox(rect):
                        if not rect: return None
                        # Flip Y
                        return BoundingBox(
                            page=page_num,
                            x0=rect.x0,
                            y0=h - rect.y1, # Bottom
                            x1=rect.x1,
                            y1=h - rect.y0  # Top
                        )

                    # Handle Header
                    header_cells = []
                    for i, name in enumerate(table.header.names):
                        rect = table.header.cells[i] if table.header.cells and i < len(table.header.cells) else None
                        header_cells.append(RichCell(text=str(name), bbox=to_bbox(rect)))
                    if header_cells:
                        rows.append(header_cells)

                    # Handle Rows
                    for row in table.rows:
                        row_cells = []
                        for i, cell_text in enumerate(row):
                            rect = row.cells[i] if row.cells and i < len(row.cells) else None
                            txt = str(cell_text) if cell_text is not None else ""
                            row_cells.append(RichCell(text=txt, bbox=to_bbox(rect)))
                        rows.append(row_cells)

                    page_tables.append(RichTable(page_num=page_num, rows=rows))

            if page_tables:
                extracted_tables[page_num] = page_tables
        doc.close()
        return extracted_tables
    except Exception as e:
        logger.error(f"Table extraction failed for {pdf_path}: {e}")
        return {}

def extract_rich_text(pdf_path: Path) -> Dict[int, RichPage]:
    """
    Extracts text preserving structure and coordinate mapping.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    rich_pages = {}

    try:
        doc = fitz.open(pdf_path)

        for page_num, page in enumerate(doc, start=1):
            page_w = page.rect.width
            page_h = page.rect.height

            full_text_accum = []
            char_map_accum = []

            blocks = page.get_text("dict")["blocks"]
            text_blocks = [b for b in blocks if b["type"] == 0]
            # Block sort order should match reading order (top-down, left-right)
            # Default is usually okay, but we can verify.
            # Fitz uses Y-down.
            text_blocks.sort(key=lambda b: (round(b["bbox"][1]), b["bbox"][0]))

            for block in text_blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span["text"]

                        # Span BBox in Fitz Coords (Top-Left Origin)
                        # b[0]=x0, b[1]=y0(top), b[2]=x1, b[3]=y1(bottom)
                        raw_bbox = span["bbox"]

                        # Flip Y for PDF output
                        # y0_new (bottom) = h - y1_raw
                        # y1_new (top) = h - y0_raw
                        # x stays same
                        span_bbox = BoundingBox(
                            page=page_num,
                            x0=raw_bbox[0],
                            y0=page_h - raw_bbox[3],
                            x1=raw_bbox[2],
                            y1=page_h - raw_bbox[1]
                        )

                        for char in span_text:
                            full_text_accum.append(char)
                            char_map_accum.append(span_bbox)

                    full_text_accum.append("\n")
                    char_map_accum.append(None)

            full_text = "".join(full_text_accum)

            rich_pages[page_num] = RichPage(
                page_num=page_num,
                full_text=full_text,
                char_map=char_map_accum,
                page_height=page_h,
                page_width=page_w
            )

        doc.close()
        return rich_pages

    except Exception as e:
        logger.error(f"Rich text extraction failed: {e}")
        return {}

# Re-implement extract_text_with_layout to potentially use RichPage logic if we unify?
# For now, keep separate to avoid breaking existing flows during refactor.
def extract_text_with_layout(pdf_path: Path) -> Dict[int, str]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    extracted_text = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("blocks")
            text_blocks = [b for b in blocks if b[6] == 0]
            text_blocks.sort(key=lambda b: (round(b[1]), b[0]))
            full_page_text = ""
            for b in text_blocks:
                full_page_text += b[4] + "\n"
            extracted_text[page_num] = full_page_text
        doc.close()
        return extracted_text
    except Exception as e:
        logger.error(f"Layout text extraction failed for {pdf_path}: {e}")
        return {}

def extract_text(pdf_path: Path) -> Dict[int, str]:
    # (Original native extraction logic + OCR fallback)
    # ... (Keep existing implementation for brevity unless changing)
    # Since I'm using replace_file_content, I need to provide full file or careful chunks.
    # The prompt asked to "EndLine: 381", so I must provide the full file content or what replaces it.
    # I will paste the original `extract_text` and following functions.

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    extracted_data = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            stripped_text = text.strip()
            char_count = len(stripped_text)
            if char_count < 50:
                logger.warning(f"Page {page_num} has only {char_count} chars. Attempting OCR...")
                ocr_text = _attempt_ocr(page)
                if ocr_text and len(ocr_text.strip()) > char_count:
                    text = ocr_text
                    logger.info(f"Page {page_num}: Using OCR text ({len(ocr_text.strip())} chars)")
            extracted_data[page_num] = text
        doc.close()
        return extracted_data
    except Exception as e:
        raise Exception(f"Failed to extract text from {pdf_path}: {str(e)}")

def _attempt_ocr(page) -> str:
    if not OCR_AVAILABLE:
        return ""
    try:
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        text = pytesseract.image_to_string(image)
        return text
    except Exception:
        return ""

def detect_implicit_columns(lines: List[str], min_gap: int = 3, min_lines: int = 5) -> List[int]:
    # (Same as before)
    if not lines or len(lines) < min_lines: return []
    valid_lines = [line for line in lines if len(line.strip()) > 10]
    if len(valid_lines) < min_lines: return []
    max_len = max(len(line) for line in valid_lines)
    if max_len < 20: return []
    space_counts = [0] * max_len
    for line in valid_lines:
        padded = line.ljust(max_len)
        for i, char in enumerate(padded):
            if char == ' ': space_counts[i] += 1
    threshold = len(valid_lines) * 0.7
    gap_regions = []
    in_gap = False
    gap_start = 0
    for i, count in enumerate(space_counts):
        if count >= threshold:
            if not in_gap:
                gap_start = i
                in_gap = True
        else:
            if in_gap:
                gap_end = i
                if gap_end - gap_start >= min_gap: gap_regions.append((gap_start, gap_end))
                in_gap = False
    column_boundaries = []
    for start, end in gap_regions:
        if start > 0 and end < max_len - 2:
            column_boundaries.append(start)
    return column_boundaries

def split_line_by_columns(line: str, column_positions: List[int]) -> List[str]:
    # (Same as before)
    if not column_positions: return [line.strip()] if line.strip() else []
    cells = []
    prev_pos = 0
    for pos in column_positions:
        if pos <= len(line):
            cells.append(line[prev_pos:pos].strip())
            prev_pos = pos
        else:
            cells.append(line[prev_pos:].strip() if prev_pos < len(line) else "")
            prev_pos = len(line)
    if prev_pos < len(line): cells.append(line[prev_pos:].strip())
    else: cells.append("")
    return cells

def split_line_by_columns_rich(line_text: str, line_bboxes: List[Optional[BoundingBox]], column_positions: List[int]) -> List[RichCell]:
    """
    Split a line into cells, preserving bbox info for each cell.
    line_bboxes should match line_text length.
    """
    if not column_positions:
        # One single cell
        valid_bboxes = [b for b in line_bboxes if b]
        # Union bboxes
        union_box = None
        if valid_bboxes:
            # simple union
            union_box = BoundingBox(
                page=valid_bboxes[0].page,
                x0=min(b.x0 for b in valid_bboxes),
                y0=min(b.y0 for b in valid_bboxes),
                x1=max(b.x1 for b in valid_bboxes),
                y1=max(b.y1 for b in valid_bboxes)
            )
        return [RichCell(text=line_text.strip(), bbox=union_box)]

    cells = []
    prev_pos = 0

    # We append a sentinel to handle the last segment easily
    positions = column_positions + [len(line_text)]

    for pos in positions:
        # Clamp
        pos = min(pos, len(line_text))

        # Segment
        seg_text = line_text[prev_pos:pos]
        seg_bboxes = line_bboxes[prev_pos:pos]

        # Trim whitespace?
        # If we trim text, we should trim bboxes too.
        stripped_text = seg_text.strip()

        if not stripped_text:
             cells.append(RichCell(text="", bbox=None))
        else:
            # Find start/end index of stripped text within seg_text
            start_offset = seg_text.find(stripped_text)
            end_offset = start_offset + len(stripped_text)

            # Extract relevant bboxes
            sub_bboxes = seg_bboxes[start_offset:end_offset]
            valid_sub = [b for b in sub_bboxes if b]

            union_box = None
            if valid_sub:
                union_box = BoundingBox(
                    page=valid_sub[0].page,
                    x0=min(b.x0 for b in valid_sub),
                    y0=min(b.y0 for b in valid_sub),
                    x1=max(b.x1 for b in valid_sub),
                    y1=max(b.y1 for b in valid_sub)
                )
            cells.append(RichCell(text=stripped_text, bbox=union_box))

        prev_pos = pos

    return cells

def text_to_implicit_table(text_obj: Union[str, RichPage], min_gap: int = 3, min_lines: int = 5) -> Union[List[List[str]], List[List[RichCell]]]:
    """
    Convert text (or RichPage) to table using implicit column detection.

    If inputs str -> Returns List[List[str]] (Top-level table)
    If inputs RichPage -> Returns List[List[RichCell]] (RichTable rows)
    """
    if isinstance(text_obj, str):
        return _text_to_implicit_table_str(text_obj, min_gap, min_lines)

    elif isinstance(text_obj, RichPage):
        # Rich logic
        full_text = text_obj.full_text
        char_map = text_obj.char_map

        # We need to process lines from full_text but map back to indices to get slices of char_map
        lines_with_indices = [] # Tuple(start, end, text)

        current_idx = 0
        raw_lines = full_text.split('\n')

        valid_lines_texts = []

        for line in raw_lines:
            length = len(line)
            # Line span: current_idx to current_idx + length
            # Note: newline char is at current_idx + length?
            # split('\n') consumes the separator.
            # So full_text[current_idx + length] should be '\n' (unless last line).

            if line.strip():
                lines_with_indices.append((current_idx, current_idx + length, line))
                valid_lines_texts.append(line)

            current_idx += length + 1

        if len(lines_with_indices) < min_lines:
            return []

        column_positions = detect_implicit_columns(valid_lines_texts, min_gap, min_lines)
        if not column_positions:
            return []

        rich_table = []
        for start, end, line_text in lines_with_indices:
            line_bboxes = char_map[start:end]
            row_cells = split_line_by_columns_rich(line_text, line_bboxes, column_positions)
            if any(c.text for c in row_cells):
                rich_table.append(row_cells)

        # Normalize
        if not rich_table: return []
        max_cols = max(len(row) for row in rich_table)
        for row in rich_table:
            while len(row) < max_cols:
                row.append(RichCell(text="", bbox=None))

        return rich_table

    return []

def _text_to_implicit_table_str(text: str, min_gap: int, min_lines: int) -> List[List[str]]:
    # Simple reimplementation of old logic
    if not text.strip(): return []
    lines = text.split('\n')
    valid = [l for l in lines if l.strip()]
    if len(valid) < min_lines: return []
    cols = detect_implicit_columns(valid, min_gap, min_lines)
    if not cols: return []

    table = []
    for line in valid:
        # Split inline
        cells = []
        prev = 0
        positions = cols + [len(line)]
        for pos in positions:
            pos = min(pos, len(line))
            cells.append(line[prev:pos].strip())
            prev = pos
        if any(cells): table.append(cells)

    if not table: return []
    max_c = max(len(r) for r in table)
    for r in table:
        while len(r) < max_c: r.append("")
    return table
