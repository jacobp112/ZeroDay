# Brokerage Statement Parser

[![CI](https://github.com/jacobp112/ZeroDay/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobp112/ZeroDay/actions/workflows/ci.yml)

A robust CLI tool to extract transaction data from brokerage statements (PDF) using Python.
Supports modern digital PDFs as well as scanned documents via OCR.

## Features

*   **Privacy First**: Runs 100% locally. No data leaves your machine.
*   **Comprehensive Extraction**:
    *   **Native Text**: Fast extraction for digital PDFs via `PyMuPDF`.
    *   **Table Recognition**: Extracts structured data from grid formats.
    *   **OCR Support**: Handles scanned or image-based statements (requires Tesseract).
    *   **Implicit Column Detection**: Smartly infers columns for older, non-standard layouts.
*   **Data Integrity Validation**: Mathematically verifies transaction sums against reported account balances to ensure accuracy.
*   **Batch Processing**: Process entire directories of statements at once with a rich terminal UI.
*   **Output**: Export parsed data to JSON or CSV.

## Supported Brokers

| Broker | Status | Notes |
| :--- | :--- | :--- |
| **Schwab** | Stable | Full Support (Text + Tables + OCR) |
| **Fidelity** | Beta | Full Support (Text + Tables + OCR) |
| **Vanguard** | Beta | Full Support (Text + Tables + OCR) |

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

3.  **(Optional) Install Tesseract OCR:**
    To enable OCR for scanned documents, you must install Tesseract separately and ensure it's in your PATH.
    *   **Windows**: [Installer](https://github.com/UB-Mannheim/tesseract/wiki)
    *   **macOS**: `brew install tesseract`
    *   **Linux**: `sudo apt install tesseract-ocr`

## Usage

### Command Line Interface (CLI)

The tool provides a rich CLI to parse statements.

**Basic Usage:**
```bash
# Process a single file
brokerage-parser parse statements/schwab_jan23.pdf -o output.json
```

**Batch Processing:**
```bash
# Process an entire directory of statements
brokerage-parser parse statements/ --output results/
```
*Displays a rich progress bar and summary table of results.*

**Options:**
*   `--output <file/dir>`, `-o <file/dir>`: Save output to a file (single mode) or directory (batch mode).
*   --format <json|csv>: Output format (default: `json`).
*   `--verbose`, `-v`: Enable debug logging.

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

    # Check for validation warnings
    if statement.integrity_warnings:
        print("Warnings:", statement.integrity_warnings)

    for tx in statement.transactions:
        print(f"{tx.date}: {tx.description} - ${tx.amount}")

except ValueError as e:
    print(f"Error: {e}")
```

## Development

Run tests:
```bash
poetry run pytest
```
