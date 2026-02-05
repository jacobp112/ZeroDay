import argparse
import sys
import json
import logging
from pathlib import Path
from brokerage_parser.orchestrator import process_statement

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(description="Brokerage Statement Parser CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: parse
    parse_parser = subparsers.add_parser("parse", help="Parse a brokerage statement PDF")
    parse_parser.add_argument("input_file", help="Path to the PDF file")
    parse_parser.add_argument("--output", "-o", help="Path to output file")
    parse_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format (default: json)")
    parse_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.command == "parse":
        setup_logging(args.verbose)

        try:
            result = process_statement(args.input_file)

            # Serialize
            output_data = result.to_dict()

            # Handle Output
            if args.format == "json":
                json_str = json.dumps(output_data, indent=2)
                if args.output:
                    Path(args.output).write_text(json_str)
                    print(f"Output saved to {args.output}")
                else:
                    print(json_str)
            elif args.format == "csv":
                # Basic CSV export for transactions
                import pandas as pd
                if not result.transactions:
                    print("No transactions found to export to CSV.")
                else:
                    df = pd.DataFrame([t.to_dict() for t in result.transactions])
                    if args.output:
                        df.to_csv(args.output, index=False)
                        print(f"Transactions saved to {args.output}")
                    else:
                        print(df.to_csv(index=False))

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
