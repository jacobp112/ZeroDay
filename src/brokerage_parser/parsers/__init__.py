from typing import Optional, List, Union, Type
from brokerage_parser.parsers.base import Parser
from brokerage_parser.parsers.schwab import SchwabParser
from brokerage_parser.parsers.fidelity import FidelityParser
from brokerage_parser.parsers.vanguard import VanguardParser
from brokerage_parser.parsers.generic import GenericParser

__all__ = ["get_parser", "get_supported_brokers"]

def get_parser(broker_name: str, text: str = None, tables: List = None) -> Optional[Union[Type[Parser], Parser]]:
    """
    Factory function to return the correct parser class or instance.

    Args:
        broker_name: Normalized broker name (schwab, fidelity, vanguard, unknown).
        text: Optional. If provided, returns an instantiated parser with this text.
        tables: Optional. Tables list for GenericParser (only used for unknown broker).

    Returns:
        The Parser class (not instance) if text is None, otherwise an instance.
        Returns None if broker is not supported or unknown without tables.
    """
    broker = broker_name.lower().strip()

    parser_class = None
    if broker == "schwab":
        parser_class = SchwabParser
    elif broker == "fidelity":
        parser_class = FidelityParser
    elif broker == "vanguard":
        parser_class = VanguardParser
    elif broker == "unknown":
        # Use GenericParser as fallback ONLY if tables are provided
        if tables:
            parser_class = GenericParser
        else:
            return None

    if parser_class is None:
        return None

    # If text is provided, return an instance; otherwise return the class
    if text is not None:
        if parser_class == GenericParser:
            # GenericParser takes (text, tables)
            return parser_class(text, tables or [])
        return parser_class(text)
    return parser_class

def get_supported_brokers() -> list[str]:
    return ["schwab", "fidelity", "vanguard"]
