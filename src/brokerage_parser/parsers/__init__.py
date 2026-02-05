from typing import Optional, List
from brokerage_parser.parsers.base import Parser
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser
from brokerage_parser.extraction import TableData

__all__ = ["get_parser", "get_supported_brokers"]

def get_parser(broker_name: str, text: str, tables: Optional[List[TableData]] = None) -> Optional[Parser]:
    """
    Factory function to return the correct parser instance.

    Args:
        broker_name: Normalized broker name (schwab, fidelity, vanguard).
        text: The full text of the statement.
        tables: Optional list of extracted tables.

    Returns:
        Instance of a Parser subclass or None if not supported.
    """
    broker = broker_name.lower().strip()
    tables = tables or []

    if broker == "schwab":
        return SchwabParser(text, tables)
    elif broker == "fidelity":
        return FidelityParser(text, tables)
    elif broker == "vanguard":
        return VanguardParser(text, tables)
    else:
        return None

def get_supported_brokers() -> list[str]:
    return ["schwab", "fidelity", "vanguard"]
