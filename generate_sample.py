import fitz  # PyMuPDF
from pathlib import Path

# Mock Data from your tests
SCHWAB_TEXT = """
Charles Schwab & Co., Inc.
Statement Date: January 31, 2023
Statement Period: January 1, 2023 to January 31, 2023
Account Number: 1234-5678

Transaction Detail
01/01/23    Buy 10 Shares AAPL @ 150.00                    -1500.00
01/15/23    Sell 5 Shares MSFT                             750.00
01/20/23    Cash Dividend AAPL                             10.50
01/25/23    Reinvestment AAPL 0.07 Shares @ 150.00         -10.50
02/01/23    Bank Interest                                  0.45
02/05/23    Service Fee                                    -25.00
02/10/23    Journaled In (Cash)                            5000.00
02/15/23    Wire Transfer Out                              -1000.00

Account Holdings
AAPL Apple Inc 100 150.00 15000.00
MSFT Microsoft Corp 50 300.00 15000.00
Total
"""

FIDELITY_TEXT = """
Fidelity Investments
Statement Date: 01/31/2023
Account Activity for 01/01/2023 - 01/31/2023
Account Number X12-345678

Activity
02/01/23    YOU BOUGHT GOOGL 10 Shares @ 100.00      -1000.00
02/05/23    YOU SOLD MSFT 5 Shares @ 200.00          1000.00
02/10/23    DIVIDEND RECEIVED AAPL                   50.00
02/15/23    REINVESTMENT AAPL 0.5 Shares @ 100.00    -50.00

Holdings
GOOGL Alphabet Inc 10 100.00 1000.00
AAPL Apple Inc 50 150.00 7500.00
Total
"""

VANGUARD_TEXT = """
The Vanguard Group
Statement date: January 31, 2023
For the period January 1, 2023, to January 31, 2023
Account Number 9876-54321

Activity Detail
03/01/23    Buy Vanguard 500 Index Fund Admiral Shares VFIAX    -3000.00
03/05/23    Redemption Vanguard Total Bond Market VBTLX         1000.00
03/10/23    Dividend Received VFIAX                             45.50
03/10/23    Dividend Reinvestment VFIAX                         -45.50
03/15/23    Exchange Out Vanguard Growth Index VIGAX            -5000.00
03/15/23    Exchange In Vanguard Value Index VIVAX              5000.00

Investment Holdings
Vanguard 500 Index Fund Admiral Shares VFIAX 100.000 400.00 40000.00
Vanguard Total Bond Market Index Fund VBTLX 500.000 10.00 5000.00
Total
"""

def create_pdf(filename, text):
    doc = fitz.open()
    page = doc.new_page()
    # Insert text with simple formatting
    # fontsize 10, fontname "helv" (Helvetica is standard)
    page.insert_text((50, 50), text, fontsize=10, fontname="helv", lineheight=1.5)
    doc.save(filename)
    print(f"Created {filename}")

def main():
    output_dir = Path("samples")
    output_dir.mkdir(exist_ok=True)

    create_pdf(output_dir / "schwab_sample.pdf", SCHWAB_TEXT)
    create_pdf(output_dir / "fidelity_sample.pdf", FIDELITY_TEXT)
    create_pdf(output_dir / "vanguard_sample.pdf", VANGUARD_TEXT)

if __name__ == "__main__":
    main()