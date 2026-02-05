import pytest
from decimal import Decimal
from datetime import date
from brokerage_parser.models import (
    ParsedStatement, Position, Transaction, TransactionType, TaxWrapper, AccountSummary
)
from brokerage_parser.reporting.engine import ReportingEngine
from brokerage_parser.reporting.renderers import MarkdownRenderer

@pytest.fixture
def base_statement():
    return ParsedStatement(
        broker="TestBroker",
        statement_date=date(2024, 4, 6),
        period_start=date(2023, 4, 6),
        period_end=date(2024, 4, 5),
        account=AccountSummary(
            account_number="123456",
            account_type="Individual",
            beginning_balance=Decimal("1000.00"),
            ending_balance=Decimal("1100.00") # Implies 100 profit or deposit
        ),
        positions=[],
        transactions=[],
        tax_wrapper=TaxWrapper.UNKNOWN
    )

def test_gia_reporting_flow(base_statement):
    """
    Test that a GIA account triggers CGT calculation and produces a valid report.
    """
    stmt = base_statement
    stmt.tax_wrapper = TaxWrapper.GIA
    stmt.positions = [
        Position(
            symbol="AAPL", description="Apple", quantity=Decimal("10"),
            price=Decimal("150"), market_value=Decimal("1500"), gbp_market_value=Decimal("1200")
        )
    ]

    # Add transactions for CGT and Costs
    stmt.transactions = [
        # Buy
        Transaction(
            date=date(2023, 5, 1), type=TransactionType.BUY, description="Buy Apple",
            amount=Decimal("-1000"), quantity=Decimal("10"), price=Decimal("100"),
            gbp_amount=Decimal("1000") # Cost
        ),
        # Sell (Gain)
        Transaction(
            date=date(2023, 6, 1), type=TransactionType.SELL, description="Sell Apple",
            amount=Decimal("1200"), quantity=Decimal("5"), price=Decimal("240"),
            gbp_amount=Decimal("1200") # Proceeds
        ),
        # Cost (Management Fee)
        Transaction(
            date=date(2023, 7, 1), type=TransactionType.FEE, description="Management Fee",
            amount=Decimal("-10"), gbp_amount=Decimal("-10")
        )
    ]

    engine = ReportingEngine()
    report = engine.generate_report(stmt)

    # Verify Structure
    assert report.metadata.broker_name == "TestBroker"
    assert report.portfolio_summary.investments_value_gbp == Decimal("1200")

    # Verify Tax Pack - CGT should be PRESENT for GIA
    assert report.tax_pack.tax_wrapper == "GIA"
    assert report.tax_pack.cgt_report is not None
    # We sold 5, bought 10 at 100 (total 1000).
    # Sold 5 at 240 (1200). Cost for 5 is 500. Gain = 700.
    # CGT Engine logic: (Proceeds 1200 - Cost 500) = 700.
    assert report.tax_pack.cgt_report.total_gains == Decimal("700")

    # Verify Costs
    assert report.tax_pack.cost_report.total_costs == Decimal("10")

    # Verify Renderer
    renderer = MarkdownRenderer()
    output = renderer.render(report)
    print(output)

    assert "Client Report" in output
    assert "**Tax Wrapper:** GIA" in output
    assert "**Total Realised Gains:** £700.00" in output
    assert "Management Fee" in output

def test_isa_reporting_flow(base_statement):
    """
    Test that an ISA account SKIPS CGT calculation but tracks allowances.
    """
    stmt = base_statement
    stmt.tax_wrapper = TaxWrapper.ISA

    # Add Subs
    stmt.transactions = [
        Transaction(
            date=date(2023, 5, 1), type=TransactionType.TRANSFER_IN, description="Subscription",
            amount=Decimal("5000"), gbp_amount=Decimal("5000")
        ),
         # Buy/Sell (should be ignored for CGT)
        Transaction(
            date=date(2023, 5, 2), type=TransactionType.BUY, description="Buy Apple",
            amount=Decimal("-1000"), quantity=Decimal("10"), price=Decimal("100"),
            gbp_amount=Decimal("1000")
        ),
        Transaction(
            date=date(2023, 6, 1), type=TransactionType.SELL, description="Sell Apple",
            amount=Decimal("1200"), quantity=Decimal("5"), price=Decimal("240"),
            gbp_amount=Decimal("1200")
        ),
    ]

    engine = ReportingEngine()
    report = engine.generate_report(stmt)

    assert report.tax_pack.tax_wrapper == "ISA"
    assert report.tax_pack.cgt_report is None # Crucial check

    # Check Allowance
    # ISA Limit 20k. Used 5k.
    assert report.tax_pack.allowance_status["status"] == "Within Limit"
    assert report.tax_pack.allowance_status["contributions"] == "5000"

    # Verify Renderer
    renderer = MarkdownRenderer()
    output = renderer.render(report)

    assert "**Tax Wrapper:** ISA" in output
    assert "Not applicable for this account type" in output # Under CGT
