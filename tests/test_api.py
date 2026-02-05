"""
Tests for the ParseFin Enterprise API.

Tests cover:
- Successful PDF parsing
- Content-type validation
- Error handling for invalid files
- Health check endpoint
"""
import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from brokerage_parser.api import app, serialize_report, serialize_value


# Create test client
client = TestClient(app)


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerializeValue:
    """Test the serialize_value helper function."""

    def test_serialize_decimal(self):
        """Decimal should be serialized as string to preserve precision."""
        assert serialize_value(Decimal("123.456")) == "123.456"
        assert serialize_value(Decimal("0.00")) == "0.00"

    def test_serialize_date(self):
        """Date should be serialized as ISO format string."""
        assert serialize_value(date(2024, 1, 15)) == "2024-01-15"

    def test_serialize_none(self):
        """None should remain None."""
        assert serialize_value(None) is None

    def test_serialize_list(self):
        """Lists should be recursively serialized."""
        result = serialize_value([Decimal("1.0"), date(2024, 1, 1), "text"])
        assert result == ["1.0", "2024-01-01", "text"]

    def test_serialize_dict(self):
        """Dicts should be recursively serialized."""
        result = serialize_value({
            "amount": Decimal("100.50"),
            "date": date(2024, 6, 15),
        })
        assert result == {"amount": "100.50", "date": "2024-06-15"}

    def test_serialize_primitive(self):
        """Primitives should pass through unchanged."""
        assert serialize_value("hello") == "hello"
        assert serialize_value(42) == 42
        assert serialize_value(True) is True


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Test the health check endpoint."""

    def test_health_check_returns_ok(self):
        """Health check should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ParseFin Enterprise API"


# =============================================================================
# Parse Endpoint Tests
# =============================================================================

class TestParseEndpoint:
    """Test the POST /v1/parse endpoint."""

    def test_rejects_non_pdf_content_type(self):
        """Should reject files that are not PDFs."""
        # Create a fake text file
        fake_file = io.BytesIO(b"This is not a PDF")

        response = client.post(
            "/v1/parse",
            files={"file": ("test.txt", fake_file, "text/plain")}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_content_type"
        assert "text/plain" in data["detail"]["message"]

    def test_rejects_image_content_type(self):
        """Should reject image files."""
        fake_file = io.BytesIO(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes

        response = client.post(
            "/v1/parse",
            files={"file": ("test.png", fake_file, "image/png")}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_content_type"

    @patch("brokerage_parser.api.orchestrator.process_statement")
    def test_successful_parse_returns_json(self, mock_process):
        """Should return serialized report on successful parse."""
        from dataclasses import dataclass

        # Create a minimal mock report
        @dataclass
        class MockMetadata:
            client_name: str = "Test Client"
            report_date: date = date(2024, 1, 15)
            reporting_period_start: date = None
            reporting_period_end: date = None
            broker_name: str = "Schwab"
            account_number: str = "123456"

        @dataclass
        class MockPortfolioSummary:
            total_value_gbp: Decimal = Decimal("10000.00")
            cash_value_gbp: Decimal = Decimal("1000.00")
            investments_value_gbp: Decimal = Decimal("9000.00")
            currency: str = "GBP"

        @dataclass
        class MockCostReport:
            total_fees_gbp: Decimal = Decimal("50.00")

        @dataclass
        class MockTaxPack:
            tax_wrapper: str = "GIA"
            allowance_status: dict = None
            cgt_report: dict = None
            cost_report: MockCostReport = None

        @dataclass
        class MockParsedStatement:
            broker: str = "Schwab"

        @dataclass
        class MockReport:
            metadata: MockMetadata = None
            portfolio_summary: MockPortfolioSummary = None
            tax_pack: MockTaxPack = None
            holdings: list = None
            source_statement: MockParsedStatement = None

        mock_report = MockReport(
            metadata=MockMetadata(),
            portfolio_summary=MockPortfolioSummary(),
            tax_pack=MockTaxPack(
                allowance_status={},
                cost_report=MockCostReport()
            ),
            holdings=[],
            source_statement=MockParsedStatement(),
        )
        mock_process.return_value = mock_report

        # Create a fake PDF (just needs correct content-type)
        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")

        response = client.post(
            "/v1/parse",
            files={"file": ("statement.pdf", fake_pdf, "application/pdf")}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "metadata" in data
        assert "portfolio_summary" in data
        assert data["metadata"]["broker_name"] == "Schwab"
        assert data["portfolio_summary"]["total_value_gbp"] == "10000.00"

    @patch("brokerage_parser.api.orchestrator.process_statement")
    def test_value_error_returns_400(self, mock_process):
        """ValueError from orchestrator should return 400."""
        mock_process.side_effect = ValueError("File not found: test.pdf")

        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")

        response = client.post(
            "/v1/parse",
            files={"file": ("statement.pdf", fake_pdf, "application/pdf")}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "validation_error"
        assert "File not found" in data["detail"]["message"]

    @patch("brokerage_parser.api.orchestrator.process_statement")
    def test_generic_exception_returns_500(self, mock_process):
        """Generic exceptions should return 500."""
        mock_process.side_effect = RuntimeError("Unexpected internal error")

        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")

        response = client.post(
            "/v1/parse",
            files={"file": ("statement.pdf", fake_pdf, "application/pdf")}
        )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "processing_error"
        assert "Unexpected internal error" in data["detail"]["message"]

    @patch("brokerage_parser.api.orchestrator.process_statement")
    def test_temp_file_cleanup_on_success(self, mock_process):
        """Temp file should be cleaned up after successful processing."""
        from dataclasses import dataclass

        @dataclass
        class MinimalReport:
            data: str = "test"

        mock_process.return_value = MinimalReport()

        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")

        # Track temp files created
        created_temps = []
        original_named_temp = __import__('tempfile').NamedTemporaryFile

        def tracking_temp(*args, **kwargs):
            temp = original_named_temp(*args, **kwargs)
            created_temps.append(temp.name)
            return temp

        with patch('tempfile.NamedTemporaryFile', tracking_temp):
            response = client.post(
                "/v1/parse",
                files={"file": ("statement.pdf", fake_pdf, "application/pdf")}
            )

        # Verify temp file was cleaned up
        for temp_path in created_temps:
            assert not os.path.exists(temp_path), f"Temp file was not cleaned up: {temp_path}"

    @patch("brokerage_parser.api.orchestrator.process_statement")
    def test_temp_file_cleanup_on_error(self, mock_process):
        """Temp file should be cleaned up even when processing fails."""
        mock_process.side_effect = RuntimeError("Processing failed")

        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")

        created_temps = []
        original_named_temp = __import__('tempfile').NamedTemporaryFile

        def tracking_temp(*args, **kwargs):
            temp = original_named_temp(*args, **kwargs)
            created_temps.append(temp.name)
            return temp

        with patch('tempfile.NamedTemporaryFile', tracking_temp):
            response = client.post(
                "/v1/parse",
                files={"file": ("statement.pdf", fake_pdf, "application/pdf")}
            )

        assert response.status_code == 500

        # Verify temp file was still cleaned up
        for temp_path in created_temps:
            assert not os.path.exists(temp_path), f"Temp file was not cleaned up: {temp_path}"


# =============================================================================
# Integration Test with Real Sample (if available)
# =============================================================================

class TestIntegration:
    """Integration tests using real sample files."""

    @pytest.fixture
    def sample_pdf_path(self):
        """Get path to a sample PDF if it exists."""
        samples_dir = Path(__file__).parent.parent / "samples"
        if samples_dir.exists():
            pdfs = list(samples_dir.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
        return None

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "samples").exists(),
        reason="No samples directory available"
    )
    def test_parse_real_sample_if_available(self, sample_pdf_path):
        """Integration test with real PDF if samples exist."""
        if sample_pdf_path is None:
            pytest.skip("No sample PDFs available")

        with open(sample_pdf_path, "rb") as f:
            response = client.post(
                "/v1/parse",
                files={"file": (sample_pdf_path.name, f, "application/pdf")}
            )

        # Should either succeed or return a structured error
        assert response.status_code in [200, 400, 500]
        data = response.json()

        if response.status_code == 200:
            # Verify basic structure
            assert "metadata" in data or "data" in data
