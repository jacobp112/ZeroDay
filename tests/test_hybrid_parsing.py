import unittest
from unittest.mock import MagicMock, patch
from datetime import date
from decimal import Decimal
import os

from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.extraction import RichPage, BoundingBox
from brokerage_parser.models import ExtractionMethod
from brokerage_parser.models.domain import SourceReference

class TestHybridParsing(unittest.TestCase):

    def setUp(self):
        # Create a mock RichPage
        self.mock_bbox = BoundingBox(1, 10, 10, 20, 20)
        self.mock_page_h = 100
        self.mock_page_w = 100

        self.rich_page = RichPage(
            page_num=1,
            full_text="Some text",
            char_map=[None] * 9, # Length of "Some text"
            page_height=self.mock_page_h,
            page_width=self.mock_page_w
        )
        self.rich_map = {1: self.rich_page}

    def test_tier1_regex_account_number(self):
        text = "Account Number: 1234-5678"
        parser = SchwabParser(text=text, rich_text_map=self.rich_map)

        statement = parser.parse()
        self.assertEqual(statement.account.account_number, "1234-5678")

    def test_tier2_spatial_account_number(self):
        # Setup: Text does NOT contain "Account Number:" label.
        # But RichPage has the number in Top Right.

        text = "Header\nSome unexpected text"

        # Create a RichPage with the number in top right
        # Top Right: x > 50, y > 80 (since h=100)
        # "1234-5678"
        acct_num = "1234-5678"
        full_text = f"Header\n{acct_num}\nBody"

        # BBoxes for acct_num needs to be in top right
        chars = []
        bboxes = []

        # Header
        for c in "Header\n":
            chars.append(c)
            bboxes.append(BoundingBox(1, 0, 0, 10, 10)) # Bottom Left

        # Acct Num (Top Right)
        for c in acct_num:
            chars.append(c)
            bboxes.append(BoundingBox(1, 60, 90, 80, 95)) # x=60-80, y=90-95 (Top Right)

        # Body
        for c in "\nBody":
            chars.append(c)
            bboxes.append(BoundingBox(1, 0, 0, 10, 10))

        rich_page = RichPage(
            page_num=1,
            full_text=full_text,
            char_map=bboxes,
            page_height=100,
            page_width=100
        )

        parser = SchwabParser(text=full_text, rich_text_map={1: rich_page})

        # Ensure regex fails
        self.assertIsNone(parser._find_pattern(r"Account Number:"))

        # Run Parse
        statement = parser.parse()

        self.assertEqual(statement.account.account_number, "1234-5678")
        self.assertIn("account_number", statement.source_map)
        self.assertEqual(statement.source_map["account_number"].extraction_method, ExtractionMethod.VISUAL_HEURISTIC)

    @patch("brokerage_parser.llm.client.LLMClient.complete")
    def test_tier3_llm_account_number(self, mock_complete):
        # Setup: No label, No spatial match.
        text = "Just some messy text with the number hidden 9999-8888 somewhere."

        # Mock LLM response
        mock_complete.return_value = '{"account_number": "9999-8888"}'

        rich_page = RichPage(1, text, [None]*len(text), 100, 100)
        parser = SchwabParser(text=text, rich_text_map={1: rich_page})
        parser.llm_client.enabled = True

        statement = parser.parse()

        self.assertEqual(statement.account.account_number, "9999-8888")
        self.assertIn("account_number", statement.source_map)
        self.assertEqual(statement.source_map["account_number"].extraction_method, ExtractionMethod.LLM_FALLBACK)
        # Check confidence (reverse lookup worked)
        self.assertEqual(statement.source_map["account_number"].confidence, 0.9)

if __name__ == '__main__':
    unittest.main()
