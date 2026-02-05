"""
Tests for the CLI module.

Tests batch processing, output handling, and Rich UI components.
"""
import pytest
import subprocess
import sys
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from brokerage_parser.cli import (
    find_pdf_files,
    process_single_file,
    process_batch,
    main,
)
from brokerage_parser.models import ParsedStatement


class TestFindPdfFiles:
    """Tests for find_pdf_files function."""

    def test_find_single_pdf_file(self, tmp_path):
        """Single PDF file returns list with that file."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        result = find_pdf_files(pdf_file)

        assert len(result) == 1
        assert result[0] == pdf_file

    def test_find_non_pdf_file_returns_empty(self, tmp_path):
        """Non-PDF file returns empty list."""
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        result = find_pdf_files(txt_file)

        assert len(result) == 0

    def test_find_pdfs_in_directory(self, tmp_path):
        """Directory returns all PDF files."""
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()
        (tmp_path / "c.txt").touch()  # Should be ignored

        result = find_pdf_files(tmp_path)

        assert len(result) == 2
        assert all(f.suffix == ".pdf" for f in result)

    def test_find_pdfs_sorted(self, tmp_path):
        """PDF files are returned in sorted order."""
        (tmp_path / "z.pdf").touch()
        (tmp_path / "a.pdf").touch()
        (tmp_path / "m.pdf").touch()

        result = find_pdf_files(tmp_path)

        assert [f.name for f in result] == ["a.pdf", "m.pdf", "z.pdf"]

    def test_empty_directory(self, tmp_path):
        """Empty directory returns empty list."""
        result = find_pdf_files(tmp_path)

        assert len(result) == 0

    def test_nonexistent_path(self, tmp_path):
        """Non-existent path returns empty list."""
        result = find_pdf_files(tmp_path / "nonexistent")

        assert len(result) == 0


class TestProcessSingleFile:
    """Tests for process_single_file function."""

    @patch("brokerage_parser.cli.process_statement")
    def test_successful_processing(self, mock_process, tmp_path):
        """Successful file processing returns correct result dict."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        from brokerage_parser.models import AccountSummary
        mock_statement = ParsedStatement(
            broker="Schwab",
            account=AccountSummary(account_number="1234", account_type="Individual"),
            statement_date="2024-01-15",
        )
        mock_process.return_value = mock_statement

        result = process_single_file(pdf_file, None, "json", show_spinner=False)

        assert result["status"] == "Success"
        assert result["broker"] == "Schwab"
        assert result["account"] == "1234"
        assert result["file"] == "test.pdf"

    @patch("brokerage_parser.cli.process_statement")
    def test_failed_processing(self, mock_process, tmp_path):
        """Failed processing returns Failed status with error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_process.side_effect = Exception("Parse error")

        result = process_single_file(pdf_file, None, "json", show_spinner=False)

        assert result["status"] == "Failed"
        assert result["error"] == "Parse error"

    @patch("brokerage_parser.cli.process_statement")
    def test_output_saved_to_file(self, mock_process, tmp_path):
        """Output is saved when output_path is provided."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        output_file = tmp_path / "output.json"

        mock_statement = ParsedStatement(broker="Fidelity")
        # Ensure to_dict is NOT mocked on the instance if we want to test save_output's real behavior,
        # OR mock it to return something predictable.
        mock_process.return_value = mock_statement

        process_single_file(pdf_file, output_file, "json", show_spinner=False)

        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content["broker"] == "Fidelity"


class TestProcessBatch:
    """Tests for process_batch function."""

    @patch("brokerage_parser.cli.process_statement")
    def test_batch_processes_all_files(self, mock_process, tmp_path):
        """Batch mode processes all files and returns results."""
        pdf_files = []
        for name in ["a.pdf", "b.pdf", "c.pdf"]:
            f = tmp_path / name
            f.touch()
            pdf_files.append(f)

        mock_statement = ParsedStatement(broker="Schwab")
        mock_process.return_value = mock_statement

        results = process_batch(pdf_files, None, "json")

        assert len(results) == 3
        assert mock_process.call_count == 3

    @patch("brokerage_parser.cli.process_statement")
    def test_batch_saves_to_output_dir(self, mock_process, tmp_path):
        """Batch mode saves files to output directory."""
        pdf_files = [tmp_path / "test.pdf"]
        pdf_files[0].touch()
        output_dir = tmp_path / "output"

        mock_statement = ParsedStatement(broker="Vanguard")
        mock_statement.to_dict = MagicMock(return_value={"broker": "Vanguard"})
        mock_process.return_value = mock_statement

        process_batch(pdf_files, output_dir, "json")

        assert (output_dir / "test.json").exists()


class TestCLIIntegration:
    """Integration tests for CLI using subprocess."""

    def test_help_command(self):
        """Help command shows usage information."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        output = result.stdout or ""
        assert "Brokerage Statement Parser" in output or "🏦" in output or "brokerage-parser" in output

    def test_parse_help(self):
        """Parse subcommand help shows options."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", "parse", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "--output" in result.stdout
        assert "--format" in result.stdout

    def test_nonexistent_file_error(self, tmp_path):
        """Non-existent file path returns error."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", "parse", str(tmp_path / "fake.pdf")],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 1

    def test_empty_directory_warning(self, tmp_path):
        """Directory with no PDFs shows warning."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", "parse", str(tmp_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 1
