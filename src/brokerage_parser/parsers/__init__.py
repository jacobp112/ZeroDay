from typing import Optional, List
from brokerage_parser.parsers.base import Parser
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser
from brokerage_parser.parsers.generic import GenericParser
from brokerage_parser.extraction import TableData

__all__ = ["get_parser", "get_supported_brokers"]

from typing import Optional, Type
from brokerage_parser.parsers.base import Parser

def get_parser(broker_name: str) -> Optional[Type[Parser]]:
    """
    Factory function to return the correct parser class.

    Args:
        broker_name: Normalized broker name (schwab, fidelity, vanguard).

    Returns:
        The Parser class (not instance) or None.
    """
    broker = broker_name.lower().strip()

    if broker == "schwab":
        return SchwabParser
    elif broker == "fidelity":
        return FidelityParser
    elif broker == "vanguard":
        return VanguardParser
    elif broker == "unknown":
         # Use GenericParser as fallback for unknown brokers to attempt table extraction
         return GenericParser

    return None

def get_supported_brokers() -> list[str]:
    return ["schwab", "fidelity", "vanguard"]
