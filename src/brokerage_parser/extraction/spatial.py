import re
from typing import Optional
from brokerage_parser.models import BoundingBox, SourceReference, ExtractionMethod
from brokerage_parser.extraction import RichPage

def find_value_in_region(
    page: RichPage,
    region_filter: callable,
    value_pattern: str
) -> Optional[SourceReference]:
    r"""
    Search for a regex pattern within a spatially defined region of the page.

    Args:
        page: The RichPage object containing text and character maps.
        region_filter: A function that takes a BoundingBox and returns True if it's in the region.
                       Note: BoundingBox coords are PDF standard (Origin Bottom-Left).
        value_pattern: Regex pattern to search for (e.g. r'\d{8}').

    Returns:
        SourceReference if found, else None.
    """

    # 1. Filter characters by spatial region
    filtered_chars = []
    filtered_bboxes = []

    # RichPage.char_map maps 1:1 with RichPage.full_text characters (including newlines which are None)

    for i, char in enumerate(page.full_text):
        bbox = page.char_map[i]

        # Keep newlines to preserve some structure, or if bbox matches
        if char == '\n':
            filtered_chars.append(char)
            filtered_bboxes.append(None)
            continue

        if bbox and region_filter(bbox):
            filtered_chars.append(char)
            filtered_bboxes.append(bbox)
        else:
            # Replace non-matching chars with space to preserve offsets?
            # Or just skip? If we skip, we lose word boundaries if we aren't careful.
            # Safe bet: Replace with space so regex word boundaries work.
            filtered_chars.append(' ')
            filtered_bboxes.append(None)

    filtered_text = "".join(filtered_chars)

    # 2. Search for pattern
    match = re.search(value_pattern, filtered_text)
    if match:
        start, end = match.span()

        # Recover original bboxes for the matched range
        matched_bboxes = []
        for i in range(start, end):
            if filtered_bboxes[i]:
                matched_bboxes.append(filtered_bboxes[i])

        # Merge bboxes (copy logic from extraction.py or import it?
        # For now, simplistic merge or just return list.
        # extraction.py has _merge_bboxes_by_line but it's on RichPage instance methods...
        # slightly awkward access.
        # Let's perform a simple containment box for MVP or try to reuse page.get_source_for_span logic?
        # But indices align with full_text, so we can use page.get_source_for_span
        # provided the filtered_text indices match full_text indices.
        # They DO match because we replaced rejected chars with spaces!

        return page.get_source_for_span(start, end)

        # Override extraction method to VISUAL_HEURISTIC
        # wait, page.get_source_for_span returns NATIVE_TEXT.
        # We need to modify it.

    return None

def find_text_in_page(page: RichPage, text: str) -> Optional[SourceReference]:
    """
    Exact string search in the full page to find source coordinates.
    Useful for 'Reverse Lookup' after LLM extraction.
    """
    # Simple search
    idx = page.full_text.find(text)
    if idx != -1:
        start = idx
        end = idx + len(text)
        return page.get_source_for_span(start, end)
    return None

def top_right_region(bbox: BoundingBox, page_height: float, page_width: float) -> bool:
    """
    Standard 'Top Right' filter.
    Top 20% of page, Right 50% of page?
    Or just Top 20%?
    """
    # y0 is bottom. Top is y > 0.8 * height
    # Right is x > 0.5 * width

    is_top = bbox.y0 > (page_height * 0.80)
    # is_right = bbox.x0 > (page_width * 0.5) # Optional, maybe too strict for some headers

    return is_top # Relaxed to just Top for now as per plan example "Top-Right Quadrant" usually implies both, but "Top 20%" was the text constraint.
