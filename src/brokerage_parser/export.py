import json
from pathlib import Path
from typing import Dict, Any
from brokerage_parser.models import ParsedStatement

def to_json(statement: ParsedStatement, path: str) -> None:
    """
    Exports the ParsedStatement to a JSON file.

    Args:
        statement: The ParsedStatement object.
        path: Destination file path.
    """
    data = statement.to_dict()
    json_str = json.dumps(data, indent=2)
    Path(path).write_text(json_str, encoding="utf-8")

def to_csv(statement: ParsedStatement, path: str) -> None:
    """
    Exports the transactions from the statement to a CSV file.

    Args:
        statement: The ParsedStatement object.
        path: Destination file path.
    """
    import pandas as pd

    if not statement.transactions:
        # Create empty CSV with headers if no transactions
        pd.DataFrame(columns=[
            "date", "type", "description", "amount",
            "symbol", "quantity", "price"
        ]).to_csv(path, index=False)
        return

    df = pd.DataFrame([t.to_dict() for t in statement.transactions])
    df.to_csv(path, index=False)

def to_dataframe(statement: ParsedStatement) -> Dict[str, Any]:
    """
    Converts statement data into Pandas DataFrames.

    Returns:
        Dict containing:
        - 'transactions': DataFrame of transactions
        - 'positions': DataFrame of positions
    """
    import pandas as pd

    tx_data = [t.to_dict() for t in statement.transactions]
    pos_data = [p.to_dict() for p in statement.positions]

    return {
        "transactions": pd.DataFrame(tx_data),
        "positions": pd.DataFrame(pos_data)
    }

def to_markdown(statement: ParsedStatement, path: str) -> None:
    """
    Exports the ParsedStatement to a Markdown report.
    """
    lines = []
    lines.append(f"# Brokerage Statement Report")
    lines.append(f"**Broker:** {statement.broker}")
    lines.append(f"**Account:** {statement.account.account_number if statement.account else 'N/A'}")
    lines.append(f"**Period:** {statement.period_start} to {statement.period_end}")
    lines.append("")

    lines.append("## Portfolio Summary")
    # Quick summary if available logic existed, else just basic counts
    lines.append(f"- **Total Transactions:** {len(statement.transactions)}")
    lines.append(f"- **Total Positions:** {len(statement.positions)}")
    lines.append("")

    lines.append("## Holdings")
    if statement.positions:
        lines.append("| Symbol | Description | Quantity | Price | Market Value |")
        lines.append("|---|---|---|---|---|")
        for p in statement.positions:
            lines.append(f"| {p.symbol} | {p.description} | {p.quantity} | {p.price} | {p.market_value} |")
    else:
        lines.append("_No holdings positions found._")
    lines.append("")

    lines.append("## Transactions")
    if statement.transactions:
        lines.append("| Date | Type | Description | Amount | Symbol |")
        lines.append("|---|---|---|---|---|")
        for t in statement.transactions:
            lines.append(f"| {t.date} | {t.type.value} | {t.description} | {t.amount} | {t.symbol or '-'} |")
    else:
        lines.append("_No transactions found._")

    Path(path).write_text("\n".join(lines), encoding="utf-8")
