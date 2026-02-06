from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, Any
from datetime import date

from brokerage_parser.models.domain import ParsedStatement, Position
from brokerage_parser.cgt.models import CGTReport
from brokerage_parser.costs.models import CostReport

@dataclass
class ClientMetadata:
    client_name: str
    report_date: date
    reporting_period_start: Optional[date]
    reporting_period_end: Optional[date]
    broker_name: str
    account_number: Optional[str]

@dataclass
class PortfolioSummary:
    total_value_gbp: Decimal
    cash_value_gbp: Decimal
    investments_value_gbp: Decimal
    currency: str = "GBP"

@dataclass
class TaxPack:
    tax_wrapper: str
    allowance_status: Dict[str, Any]
    cgt_report: Optional[CGTReport]
    cost_report: CostReport

@dataclass
class ClientReport:
    """
    The unified "Source of Truth" report for the wealth manager.
    """
    metadata: ClientMetadata
    portfolio_summary: PortfolioSummary
    tax_pack: TaxPack
    holdings: List[Position]
    source_statement: ParsedStatement
