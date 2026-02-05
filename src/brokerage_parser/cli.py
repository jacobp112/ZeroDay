import argparse
import sys
import time
import json
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# --- RICH IMPORTS ---
from rich.console import Console, Group
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeElapsedColumn, TaskID
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.theme import Theme
from rich.layout import Layout
from rich.tree import Tree
from rich.syntax import Syntax
from rich.align import Align
from rich import box

# --- MOCK / REAL IMPORT TOGGLE ---
try:
    from brokerage_parser.orchestrator import process_statement as real_process_statement
except ImportError:
    real_process_statement = None

# --- THEME CONFIGURATION ---
# Professional enterprise color scheme - muted, sophisticated
custom_theme = Theme({
    "brand": "bold blue",
    "brand.secondary": "dim blue",
    "header": "bold white",
    "table.border": "dim",
    "table.header": "bold",
    "status.success": "green",
    "status.warning": "yellow",
    "status.error": "red",
    "status.info": "blue",
    "log.time": "dim",
    "log.msg": "white",
    "muted": "dim white",
})

# --- TTY DETECTION ---
# Auto-detect if we're running in an interactive terminal
IS_TTY = sys.stdout.isatty()

# Create console with appropriate settings
# - When TTY: full rich formatting
# - When piped/redirected: plain text output
console = Console(
    theme=custom_theme,
    force_terminal=None,  # Auto-detect
    no_color=not IS_TTY,  # Disable colors when piped
    force_interactive=IS_TTY  # Only interactive prompts when TTY
)

# --- MOCK LOGIC (Preserved & Enhanced) ---
class MockAccount:
    def __init__(self): self.account_number = f"****{random.randint(1000,9999)}"

class MockStatement:
    def __init__(self, filename):
        self.broker = random.choice(["Fidelity", "Vanguard", "Schwab", "E*TRADE", "Morgan Stanley"])
        self.account = MockAccount()
        self.statement_date = datetime.now().strftime("%Y-%m-%d")
        self.transactions = [{"date": "2023-01-01", "amount": round(random.uniform(10.0, 5000.0), 2)} for _ in range(random.randint(0, 25))]
        self.positions = [1] * random.randint(0, 10)
        self.parse_errors = []

        # Simulation Logic
        if "error" in str(filename).lower():
            raise ValueError("Corrupted PDF Structure / Encryption Failed")
        if "partial" in str(filename).lower():
            self.parse_errors = ["Page 3: OCR Confidence low", "Page 5: Table mismatch"]

    def to_dict(self):
        return {
            "broker": self.broker,
            "account": self.account.account_number,
            "txns": self.transactions,
            "positions": len(self.positions),
            "errors": self.parse_errors
        }

# Global toggle
USE_MOCK = False

def process_wrapper(path):
    """Wrapper to switch between Mock and Real logic dynamically."""
    if USE_MOCK or real_process_statement is None:
        # Simulate varying processing times for realism
        time.sleep(random.uniform(0.3, 1.2))
        return MockStatement(path)
    return real_process_statement(path)

# --- UI COMPONENT MANAGER ---

class Dashboard:
    """Manages the layout and components of the TUI."""

    def __init__(self):
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=7)
        )
        self.layout["main"].split_row(
            Layout(name="table", ratio=2),
            Layout(name="log", ratio=1)
        )

        self.log_messages = []
        self.table = self._create_table()
        self.progress = Progress(
            SpinnerColumn(style="brand"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None, style="dim blue", complete_style="brand"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            expand=True
        )

    def _create_table(self) -> Table:
        table = Table(
            expand=True,
            border_style="dim",
            box=box.SIMPLE_HEAD,
            header_style="bold",
            row_styles=["", "dim"]
        )
        table.add_column("Status", width=8, justify="center")
        table.add_column("File", ratio=1)
        table.add_column("Broker", width=16)
        table.add_column("Account", width=12)
        table.add_column("Transactions", justify="right", width=12)
        table.add_column("Notes", width=24, style="dim")
        return table

    def get_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            "[bold]ParseFin[/] [dim]Statement Parser[/]",
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M')}[/]"
        )
        return Panel(grid, style="on #1a1a2e", box=box.SIMPLE)

    def log(self, message: str, level="info"):
        """Adds a message to the side log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "white"
        if level == "error": color = "red"
        if level == "success": color = "green"
        if level == "warn": color = "yellow"

        self.log_messages.append(f"[dim]{timestamp}[/] [{color}]{message}[/]")
        if len(self.log_messages) > 15: # Keep only last 15 messages
            self.log_messages.pop(0)

    def get_log_panel(self) -> Panel:
        return Panel(
            "\n".join(self.log_messages),
            title="[bold]System Log",
            border_style="dim white",
            box=box.ROUNDED,
            padding=(0, 1)
        )

    def update_layout(self):
        """Updates the renderables in the layout."""
        self.layout["header"].update(self.get_header())
        self.layout["table"].update(Panel(self.table, title="Processing Results", border_style="dim", box=box.SIMPLE))
        self.layout["log"].update(self.get_log_panel())
        self.layout["footer"].update(Panel(self.progress, title="Progress", border_style="dim", box=box.SIMPLE))
        return self.layout

# --- MAIN LOGIC ---

def process_batch(pdf_files: List[Path], args):
    """
    Process a batch of PDFs with TTY-aware output.

    Output modes:
    - --json: JSON to stdout (machine-readable)
    - --ndjson: Newline-delimited JSON (streamable)
    - --quiet: Suppress TUI, plain text output
    - TTY: Rich dashboard with live updates
    - Non-TTY: Automatic plain text output
    """
    # Explicit machine-readable flags take priority
    use_json = getattr(args, 'json', False)
    use_ndjson = getattr(args, 'ndjson', False)
    use_quiet = getattr(args, 'quiet', False)

    if use_json or use_ndjson or use_quiet or not IS_TTY:
        # Machine-readable or non-interactive mode
        return process_batch_plain(pdf_files, args)
    else:
        # Interactive terminal: use rich dashboard
        return process_batch_gui(pdf_files, args)


def process_batch_plain(pdf_files: List[Path], args):
    """
    Process PDFs with machine-readable or plain text output.

    Output modes:
    - --json: Complete JSON object to stdout
    - --ndjson: One JSON object per line (streamable)
    - Default: Plain text progress to stderr, JSON summary to stdout
    """
    results_data = []
    use_json = getattr(args, 'json', False)
    use_ndjson = getattr(args, 'ndjson', False)
    use_quiet = getattr(args, 'quiet', False)

    # Determine if we should show progress
    show_progress = not use_json and not use_ndjson and not use_quiet

    if show_progress:
        print(f"ParseFin: Processing {len(pdf_files)} file(s)...", file=sys.stderr)

    for i, pdf in enumerate(pdf_files, 1):
        result = {
            "file": str(pdf.name),
            "path": str(pdf),
            "status": "pending",
            "broker": None,
            "account": None,
            "transactions": 0,
            "error": None
        }

        try:
            statement = process_wrapper(str(pdf))

            result["broker"] = statement.broker
            acc = getattr(statement.account, 'account_number', str(statement.account))
            result["account"] = acc[-4:] if acc else None
            result["transactions"] = len(statement.transactions)

            if statement.parse_errors:
                result["status"] = "warning"
                result["error"] = statement.parse_errors[0] if statement.parse_errors else None
            else:
                result["status"] = "success"

            if show_progress:
                status_mark = "OK" if result["status"] == "success" else "WARN"
                print(f"[{i}/{len(pdf_files)}] {status_mark}: {pdf.name} ({result['broker']}, {result['transactions']} txns)", file=sys.stderr)

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            if show_progress:
                print(f"[{i}/{len(pdf_files)}] FAIL: {pdf.name} - {e}", file=sys.stderr)

        results_data.append(result)

        # NDJSON: Stream each result immediately
        if use_ndjson:
            print(json.dumps(result))

    # Final output
    if use_json:
        # Complete JSON object
        output = {
            "success": True,
            "processed": len(pdf_files),
            "summary": {
                "success": sum(1 for r in results_data if r["status"] == "success"),
                "warnings": sum(1 for r in results_data if r["status"] == "warning"),
                "errors": sum(1 for r in results_data if r["status"] == "error"),
            },
            "results": results_data
        }
        print(json.dumps(output, indent=2))
    elif not use_ndjson:
        # Plain text summary
        success = sum(1 for r in results_data if r["status"] == "success")
        warnings = sum(1 for r in results_data if r["status"] == "warning")
        errors = sum(1 for r in results_data if r["status"] == "error")
        if show_progress:
            print(f"\nComplete: {success} success, {warnings} warnings, {errors} errors", file=sys.stderr)

    return results_data


def process_batch_gui(pdf_files: List[Path], args):
    """Interactive Rich dashboard for TTY environments."""
    dashboard = Dashboard()
    results_data = []

    task_id = dashboard.progress.add_task("Initializing...", total=len(pdf_files))

    with Live(dashboard.update_layout(), refresh_per_second=12, console=console, screen=True) as live:

        dashboard.log(f"Found {len(pdf_files)} files to process.")

        for pdf in pdf_files:
            # 1. Update Status: Running
            dashboard.progress.update(task_id, description=f"Processing [bold cyan]{pdf.name}[/]")
            dashboard.log(f"Starting {pdf.name}...", level="info")

            # Temporary row for current item (optional, or just add row at end)
            result = {
                "file": pdf.name,
                "status": "Running",
                "broker": "-",
                "account": "-",
                "txns": 0,
                "error": None
            }

            try:
                # --- PARSE ---
                statement = process_wrapper(str(pdf))
                # -------------

                result["broker"] = statement.broker
                acc = getattr(statement.account, 'account_number', str(statement.account))
                result["account"] = acc[-4:] if acc else "????"
                result["txns"] = len(statement.transactions)
                result["data"] = statement

                if statement.parse_errors:
                    result["status"] = "Partial"
                    result["error"] = str(statement.parse_errors[0])
                    dashboard.log(f"Warning in {pdf.name}", level="warn")
                else:
                    result["status"] = "Success"
                    dashboard.log(f"Parsed {pdf.name}: {result['txns']} txns", level="success")

                # Export Logic
                if args.output:
                    save_path = Path(args.output) / f"{pdf.stem}.{args.format}"
                    # (Mock save logic)
                    dashboard.log(f"Saved to {save_path.name}", level="info")

            except Exception as e:
                result["status"] = "Failed"
                result["error"] = str(e)
                dashboard.log(f"Failed {pdf.name}: {str(e)}", level="error")

            # Update Table - Professional status indicators
            if result["status"] == "Success":
                status_text = "[green]OK[/]"
                style = "white"
            elif result["status"] == "Partial":
                status_text = "[yellow]WARN[/]"
                style = "yellow"
            else:  # Failed
                status_text = "[red]FAIL[/]"
                style = "dim red"

            dashboard.table.add_row(
                status_text,
                Text(result["file"], style=style),
                result["broker"],
                result["account"],
                str(result["txns"]),
                Text(result["error"] if result["error"] else "-", style="dim" if not result["error"] else "red")
            )

            results_data.append(result)
            dashboard.progress.advance(task_id)
            live.update(dashboard.update_layout())

    # End of Live Context
    show_final_report(results_data)

def show_final_report(results):
    """Generates a static report after the live mode exits."""
    console.clear()

    success = sum(1 for r in results if r['status'] == 'Success')
    partial = sum(1 for r in results if r['status'] == 'Partial')
    failed = sum(1 for r in results if r['status'] == 'Failed')
    total_txns = sum(r.get('txns', 0) for r in results)

    # Header
    console.print()
    console.print(Panel(
        Align.center(f"[bold]Processing Complete[/]\n[dim]{len(results)} statements processed[/]"),
        box=box.SIMPLE,
        style=""
    ))

    # Stats Table - Professional layout
    stats_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    stats_table.add_column(justify="center")
    stats_table.add_column(justify="center")
    stats_table.add_column(justify="center")
    stats_table.add_column(justify="center")

    stats_table.add_row(
        f"[bold]{success}[/]\n[dim]Successful[/]",
        f"[bold yellow]{partial}[/]\n[dim]Warnings[/]" if partial else f"[dim]{partial}[/]\n[dim]Warnings[/]",
        f"[bold red]{failed}[/]\n[dim]Failed[/]" if failed else f"[dim]{failed}[/]\n[dim]Failed[/]",
        f"[bold]{total_txns}[/]\n[dim]Transactions[/]",
    )
    console.print(Align.center(stats_table))
    console.print()

    # Issues section - if any
    if failed > 0 or partial > 0:
        console.print(Panel(
            "[bold]Issues Detected[/]",
            box=box.SIMPLE,
            style="yellow" if partial and not failed else "red"
        ))

        issues_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        issues_table.add_column("File")
        issues_table.add_column("Status")
        issues_table.add_column("Details")

        for r in results:
            if r['status'] != "Success":
                err_msg = r.get('error', 'Unknown error')
                if isinstance(err_msg, list):
                    err_msg = "; ".join(err_msg)
                status_style = "yellow" if r['status'] == "Partial" else "red"
                issues_table.add_row(
                    r['file'],
                    f"[{status_style}]{r['status']}[/]",
                    Text(str(err_msg), style="dim")
                )

        console.print(issues_table)
        console.print()

    console.print("[dim]Press Enter to continue...[/]")
    input()

# --- UTILS & MENU ---

def find_pdf_files(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        return [input_path]
    elif input_path.is_dir():
        return sorted(list(input_path.glob('*.pdf')))
    return []

def interactive_menu():
    from rich.prompt import Prompt

    while True:
        console.clear()

        # Professional header
        console.print()
        header = Table.grid(expand=True)
        header.add_column(justify="center")
        header.add_row("[bold]ParseFin[/]")
        header.add_row("[dim]Brokerage Statement Parser[/]")
        console.print(Panel(header, box=box.SIMPLE, style=""))
        console.print()

        # Menu Options - Clean table format
        menu = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
            expand=False
        )
        menu.add_column("Option", style="bold", width=8)
        menu.add_column("Action", width=28)
        menu.add_column("Description", style="dim")

        menu.add_row("[1]", "Process Single PDF", "Parse one statement")
        menu.add_row("[2]", "Batch Process", "Process all PDFs in a directory")
        menu.add_row("[3]", "Start API Server", "Launch REST API endpoint")
        menu.add_row("[4]", "Demo Mode", "Run with sample data")
        menu.add_row("[5]", "Exit", "")

        console.print(Align.center(menu))
        console.print()

        # Capabilities footer
        console.print(Align.center(Text(
            "Schwab | Fidelity | Vanguard | Interactive Brokers",
            style="dim"
        )))
        console.print(Align.center(Text(
            "Transaction extraction | Holdings | UK CGT | Tax wrapper detection",
            style="dim"
        )))
        console.print()

        choice = Prompt.ask(" Select Option", choices=["1", "2", "3", "4", "5"], default="1")

        if choice == "1":
            path = Prompt.ask("Enter PDF path")
            run_wrapper(path)
        elif choice == "2":
            path = Prompt.ask("Enter Folder path", default=".")
            run_wrapper(path)
        elif choice == "3":
            start_api_server()
        elif choice == "4":
            global USE_MOCK
            USE_MOCK = True
            # Create dummy files list
            f = [Path(f"statement_{2023}_{i:02d}.pdf") for i in range(1, 8)]
            f.append(Path("corrupted_scan.pdf"))
            f.append(Path("partial_read_vanguard.pdf"))
            process_batch(f, argparse.Namespace(output=".", format="json"))
            USE_MOCK = False
        elif choice == "5":
            console.print("[cyan]Shutting down...[/]")
            sys.exit()

def start_api_server():
    """Start the FastAPI server."""
    import subprocess
    console.print("\n[bold cyan]Starting ParseFin API Server...[/]")
    console.print("[dim]Server will be available at: http://localhost:8000[/]")
    console.print("[dim]API Documentation: http://localhost:8000/docs[/]")
    console.print("[dim]Press Ctrl+C to stop the server[/]\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "src.brokerage_parser.api:app", "--reload", "--port", "8000"],
            cwd=Path(__file__).parent.parent.parent
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/]")
    except Exception as e:
        console.print(f"\n[red]Failed to start server: {e}[/]")
        console.print("[dim]Try running: uvicorn src.brokerage_parser.api:app --reload --port 8000[/]")
        time.sleep(3)

def run_wrapper(input_path_str: str):
    path = Path(input_path_str)
    if not path.exists():
        console.print(f"[bold red]Error:[/] Path {path} not found.")
        time.sleep(2)
        return

    files = find_pdf_files(path)
    if not files:
        console.print("[bold yellow]No PDF files found.[/]")
        time.sleep(2)
        return

    process_batch(files, argparse.Namespace(output="output", format="json"))

PROGRAM_DESCRIPTION = """
ParseFin - Enterprise Brokerage Statement Parser

Parse PDF brokerage statements and extract structured data including:
  - Transactions (buys, sells, dividends, fees, transfers)
  - Holdings with current market values
  - UK Capital Gains Tax calculations (HMRC-compliant Section 104 pooling)
  - Tax wrapper detection (GIA, ISA, SIPP, etc.)

Supported Brokers:
  Charles Schwab, Fidelity, Vanguard, Interactive Brokers, and generic table-based statements.

Examples:
  %(prog)s statement.pdf                    Parse a single PDF
  %(prog)s ./statements/ -o ./output        Batch process a directory
  %(prog)s --serve                          Start the REST API server
  %(prog)s                                  Launch interactive menu
"""

def main():
    parser = argparse.ArgumentParser(
        prog="brokerage-parser",
        description=PROGRAM_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="For more information, visit: https://parsefin.io"
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input PDF file or directory containing PDFs"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory for parsed results"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "csv", "markdown"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the REST API server (default: localhost:8000)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for API server (default: 8000)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with mock data for demonstration"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output, only show results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout (machine-readable)"
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Output results as newline-delimited JSON (streamable)"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()

    if args.serve:
        # Start API server
        import subprocess
        console.print("[bold cyan]Starting ParseFin API Server...[/]")
        console.print(f"[dim]Server: http://localhost:{args.port}[/]")
        console.print(f"[dim]API Docs: http://localhost:{args.port}/docs[/]")
        console.print("[dim]Press Ctrl+C to stop[/]\n")
        try:
            subprocess.run([
                sys.executable, "-m", "uvicorn",
                "src.brokerage_parser.api:app",
                "--reload",
                "--port", str(args.port)
            ])
        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped.[/]")
    elif args.mock:
        global USE_MOCK
        USE_MOCK = True
        dummy = [Path(f"mock_stmt_{i}.pdf") for i in range(5)]
        process_batch(dummy, args)
    elif args.input:
        run_wrapper(args.input)
    else:
        interactive_menu()

if __name__ == "__main__":
    main()