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
        # argparse help usually contains "usage:"
        assert "usage:" in output
        assert "--output" in output
        assert "--format" in output

    def test_nonexistent_file_error(self, tmp_path):
        """Non-existent file path returns error (only printed to stdout with Rich)."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        # No 'parse' subcommand
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", str(tmp_path / "fake.pdf")],
            capture_output=True,
            text=True,
            env=env,
        )

        # The new CLI prints error and returns (default exit code 0 unless sys.exit called with error)
        # Checking cli.py: `if not path.exists(): ... return`
        # So return code is 0, but error message is printed.

        output = result.stdout or result.stderr
        assert "Error" in output or "not found" in output

    def test_empty_directory_warning(self, tmp_path):
        """Directory with no PDFs shows warning."""
        env = {"PYTHONPATH": "src", "PYTHONUTF8": "1", **dict(os.environ)}
        result = subprocess.run(
            [sys.executable, "-m", "brokerage_parser.cli", str(tmp_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        output = result.stdout or result.stderr
        assert "No PDF files found" in output
