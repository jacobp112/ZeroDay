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
    process_batch_plain,
    configure_settings,
    start_frontend,
    GLOBAL_SETTINGS
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
        output = result.stdout or result.stderr
        assert "No PDF files found" in output

class TestCLIFeatures:
    """Tests for new CLI features (Settings, Frontend, Export)."""

    def test_settings_configuration(self):
        """Verify configure_settings updates GLOBAL_SETTINGS."""
        # Mock Confirm.ask and Prompt.ask
        # Sequence:
        # 1. Confirm "Include Sources?" -> True
        # 2. Prompt "Select Format" -> "3" (Markdown)
        with patch('rich.prompt.Confirm.ask', side_effect=[True]), \
             patch('rich.prompt.Prompt.ask', side_effect=["3"]):

            configure_settings()

            assert GLOBAL_SETTINGS["include_sources"] is True
            assert GLOBAL_SETTINGS["output_format"] == "markdown"

    @patch('subprocess.run')
    def test_start_frontend(self, mock_run):
        """Verify start_frontend calls npm run dev."""
        # Mock directory existence check
        with patch('pathlib.Path.exists', return_value=True):
            start_frontend()

            assert mock_run.called
            args, kwargs = mock_run.call_args
            # On Windows it might be npm.cmd, on others npm
            cmd_list = args[0]
            assert "npm" in cmd_list[0] or "npm.cmd" in cmd_list[0]
            assert "run" in cmd_list[1]
            assert "dev" in cmd_list[2]

    @patch('brokerage_parser.export.to_markdown')
    @patch('brokerage_parser.cli.process_wrapper')
    def test_markdown_export_execution(self, mock_process, mock_md_export, tmp_path):
        """Verify process_batch_plain calls to_markdown when format is markdown."""
        # Setup mock statement
        mock_stmt = MagicMock(spec=ParsedStatement)
        # Attribute access on mock needs to be explicit for some properties if used
        mock_stmt.broker = "TestBroker"
        mock_stmt.account = "1234"
        mock_stmt.transactions = []
        mock_stmt.parse_errors = []
        mock_process.return_value = mock_stmt

        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        # Run process_batch_plain with markdown format
        # Signature: process_batch_plain(pdf_files, args, include_sources, output_format, output_dir)
        process_batch_plain(
            [pdf_file],
            MagicMock(),
            include_sources=False,
            output_format="markdown",
            output_dir=str(tmp_path / "out")
        )

        assert mock_md_export.called
        # Check arguments passed to to_markdown
        args, _ = mock_md_export.call_args
        assert args[0] == mock_stmt
        assert str(args[1]).endswith(".md")

    @patch('brokerage_parser.cli.start_frontend')
    @patch('brokerage_parser.cli.process_batch')
    def test_run_demo_mode(self, mock_process_batch, mock_start_frontend):
        """Verify run_demo_mode prompts for input and handles Frontend handoff."""
        from brokerage_parser.cli import run_demo_mode

        # Setup mock results with a failure to trigger the handoff prompt
        mock_process_batch.return_value = [
            {"status": "Success"},
            {"status": "Partial"} # Trigger warning
        ]

        # Mock Sequence:
        # 1. IntPrompt.ask -> 3 (files)
        # 2. IntPrompt.ask -> 10 (txns)
        # 3. Confirm.ask -> True (Launch Frontend?)
        # 4. input() -> "" (Press Enter)
        with patch('rich.prompt.IntPrompt.ask', side_effect=[3, 10]), \
             patch('rich.prompt.Confirm.ask', side_effect=[True]), \
             patch('builtins.input', return_value=""):

            run_demo_mode()

            # Verify batch processing called
            assert mock_process_batch.called

            # Verify frontend launch called with a URL
            assert mock_start_frontend.called
            call_args = mock_start_frontend.call_args
            assert call_args.kwargs.get('url') is not None
            assert "doc_id=" in call_args.kwargs['url']
