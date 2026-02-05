from typing import Optional
from brokerage_parser.parsers.base import Parser
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser

__all__ = ["get_parser", "get_supported_brokers"]

def get_parser(broker_name: str, text: str) -> Optional[Parser]:
    """
    Factory function to return the correct parser instance.

    Args:
        broker_name: Normalized broker name (schwab, fidelity, vanguard).
        text: The full text of the statement.

    Returns:
        Instance of a Parser subclass or None if not supported.
    """
    broker = broker_name.lower().strip()

    if broker == "schwab":
        return SchwabParser(text)
    elif broker == "fidelity":
        return FidelityParser(text)
    elif broker == "vanguard":
        return VanguardParser(text)
    else:
        return None

def get_supported_brokers() -> list[str]:
    return ["schwab", "fidelity", "vanguard"]
