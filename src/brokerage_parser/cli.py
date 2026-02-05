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
custom_theme = Theme({
    "brand": "bold cyan",
    "header.bg": "rgb(30,30,40)",
    "table.border": "dim cyan",
    "row.running": "italic yellow",
    "status.success": "bold green",
    "status.warning": "bold yellow",
    "status.error": "bold red",
    "log.time": "dim white",
    "log.msg": "white",
    "money": "green",
})

console = Console(theme=custom_theme)

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
        table = Table(expand=True, border_style="table.border", box=box.ROUNDED, header_style="bold white on #202020")
        table.add_column("St", width=4, justify="center")
        table.add_column("File Name", ratio=1)
        table.add_column("Broker", width=14)
        table.add_column("Acct #", width=10)
        table.add_column("Txns", justify="right", width=6)
        table.add_column("Msg", width=20, style="dim")
        return table

    def get_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            "[brand]⚡ Brokerage[/]Parser [bold]PRO[/]",
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M')}[/]"
        )
        return Panel(grid, style="white on #151515", box=box.HEAVY_HEAD)

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
        self.layout["table"].update(Panel(self.table, title="Batch Processing", border_style="dim blue"))
        self.layout["log"].update(self.get_log_panel())
        self.layout["footer"].update(Panel(self.progress, title="Progress", border_style="dim blue"))
        return self.layout

# --- MAIN LOGIC ---

def process_batch_gui(pdf_files: List[Path], args):
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

            # Update Table
            status_icon = "✅"
            style = "white"

            if result["status"] == "Partial":
                status_icon = "⚠️"
                style="yellow"
            elif result["status"] == "Failed":
                status_icon = "❌"
                style="dim red"

            dashboard.table.add_row(
                status_icon,
                Text(result["file"], style=style),
                result["broker"],
                result["account"],
                str(result["txns"]),
                Text(result["error"] if result["error"] else "OK", style="dim" if not result["error"] else "red")
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
    console.print(Panel(
        Align.center(f"[bold]Batch Processing Complete[/]\nProcessed {len(results)} files in total"),
        style="white on blue"
    ))

    # Stats Grid
    grid = Table.grid(expand=True, padding=(1, 2))
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)

    grid.add_row(
        Panel(f"[bold green]{success}[/]\nSuccess", style="green"),
        Panel(f"[bold yellow]{partial}[/]\nWarnings", style="yellow"),
        Panel(f"[bold red]{failed}[/]\nFailed", style="red"),
        Panel(f"[bold cyan]{total_txns}[/]\nTotal Txns", style="cyan"),
    )
    console.print(grid)

    # Detailed Error Tree
    if failed > 0 or partial > 0:
        tree = Tree("[bold red]⚠️ Issues Requiring Attention")
        for r in results:
            if r['status'] != "Success":
                node = tree.add(f"[bold]{r['file']}[/] ({r['status']})")
                err_msg = r.get('error', 'Unknown error')
                if isinstance(err_msg, list): err_msg = "; ".join(err_msg)
                node.add(f"[dim red]{err_msg}")

        console.print(Panel(tree, title="Debug Report", border_style="red"))

    console.print("\n[dim]Press Enter to return to menu...[/]")
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

        # Fancy Logo
        console.print(
            Panel.fit(
                "[bold cyan]BROKERAGE PARSER[/] [dim]CLI v2.0[/]\n"
                "[dim white]Automated Financial Data Extraction Tool[/]",
                border_style="cyan"
            ),
            justify="center"
        )
        console.print()

        # Menu Options
        menu = Table.grid(padding=1)
        menu.add_column(style="bold cyan", justify="right")
        menu.add_column(style="white")

        menu.add_row("1.", "Process Single PDF")
        menu.add_row("2.", "Batch Process Directory")
        menu.add_row("3.", "Run UI Simulation (Mock Mode)")
        menu.add_row("4.", "Exit")

        console.print(Panel(menu, title="Main Menu", border_style="dim white", expand=False))

        choice = Prompt.ask(" Select Option", choices=["1", "2", "3", "4"], default="1")

        if choice == "1":
            path = Prompt.ask("Enter PDF path")
            run_wrapper(path)
        elif choice == "2":
            path = Prompt.ask("Enter Folder path", default=".")
            run_wrapper(path)
        elif choice == "3":
            global USE_MOCK
            USE_MOCK = True
            # Create dummy files list
            f = [Path(f"statement_{2023}_{i:02d}.pdf") for i in range(1, 8)]
            f.append(Path("corrupted_scan.pdf"))
            f.append(Path("partial_read_vanguard.pdf"))
            process_batch_gui(f, argparse.Namespace(output=".", format="json"))
            USE_MOCK = False
        elif choice == "4":
            console.print("[cyan]Shutting down...[/]")
            sys.exit()

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

    process_batch_gui(files, argparse.Namespace(output="output", format="json"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Input file or directory")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--mock", action="store_true", help="Run mock simulation")

    args = parser.parse_args()

    if args.mock:
        global USE_MOCK
        USE_MOCK = True
        dummy = [Path(f"mock_stmt_{i}.pdf") for i in range(5)]
        process_batch_gui(dummy, args)
    elif args.input:
        run_wrapper(args.input)
    else:
        interactive_menu()

if __name__ == "__main__":
    main()