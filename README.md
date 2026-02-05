# Brokerage Statement Parser (MVP)

[![CI](https://github.com/jacobp112/ZeroDay/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobp112/ZeroDay/actions/workflows/ci.yml)

A local CLI tool to extract transaction data from brokerage statements (PDF) using pure Python.
Designed for student/lightweight environments without admin rights (no Tesseract/Poppler required).

## Features

*   **Privacy First**: Runs 100% locally. No data leaves your machine.
*   **Lightweight**: Uses `PyMuPDF` for fast native text extraction.
*   **Broker Support**: Auto-detection logic for:
    *   Charles Schwab
    *   Fidelity Investments
    *   Vanguard
*   **Output**: Export parsed data to JSON or CSV.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/jacobp112/ZeroDay.git
    cd ZeroDay
    ```

2.  Install dependencies (using Poetry):
    ```bash
    poetry install
    ```

    *Alternatively, with standard pip:*
    ```bash
    pip install .
    ```

## Usage

### Command Line Interface (CLI)

The tool provides a simple CLI to parse statements.

**Basic Usage:**
```bash
# Using poetry
poetry run brokerage-parser parse path/to/statement.pdf

# Or if installed via pip
brokerage-parser parse path/to/statement.pdf
```

**Options:**
*   `--output <file>`, `-o <file>`: Save output to a file (default: print to stdout).
*   `--format <json|csv>`: Output format (default: `json`).
    *   `json`: Full statement details (account info, dates, positions, transactions).
    *   `csv`: Exports the *transactions* list only.
*   `--verbose`, `-v`: Enable debug logging.

**Examples:**

```bash
# Save as JSON
brokerage-parser parse statements/schwab_jan23.pdf -o output.json

# Save transactions as CSV
brokerage-parser parse statements/fidelity_feb23.pdf --format csv -o transactions.csv
```

### Python API

You can use the parser logic in your own scripts:

```python
from brokerage_parser import process_statement

try:
    # Process the PDF
    statement = process_statement("path/to/statement.pdf")

    # Access data
    print(f"Broker: {statement.broker}")
    print(f"Account: {statement.account_number}")

    for tx in statement.transactions:
        print(f"{tx.date}: {tx.description} - ${tx.amount}")

except ValueError as e:
    print(f"Error: {e}")
```

## Supported Brokers

| Broker | Status | Notes |
| :--- | :--- | :--- |
| **Schwab** | Alpha | Basic regex parsing for transactions |
| **Fidelity** | Alpha | Placeholder logic |
| **Vanguard** | Alpha | Placeholder logic |

> **Note**: This is an MVP. Parsing logic relies on regular expressions. If a statement format changes, extraction may fail.

## Development

Run tests:
```bash
poetry run pytest
```
