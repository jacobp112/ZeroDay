import pytest
from decimal import Decimal
from brokerage_parser.tax.detection import TaxWrapperDetector
from brokerage_parser.tax.allowances import AllowanceTracker
from brokerage_parser.tax.planning import identify_bed_and_isa_opportunity
from brokerage_parser.models import TaxWrapper, Position

class TestTaxWrapperDetector:

    def test_strong_signals_isa(self):
        text = "This is a statement for your Stocks & Shares ISA account."
        assert TaxWrapperDetector.detect(text) == TaxWrapper.ISA

        text = "Account Type: Individual Savings Account"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.ISA

        # Case insensitive
        text = "stocks & shares isa"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.ISA

    def test_strong_signals_sipp(self):
        text = "Your Self-Invested Personal Pension Statement"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.SIPP

        text = "SIPP Valuation"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.SIPP

    def test_strong_signals_jisa(self):
        text = "Type: Junior ISA"
        # JISA should take precedence over ISA
        assert TaxWrapperDetector.detect(text) == TaxWrapper.JISA

    def test_strong_signals_lisa(self):
        text = "Product: Lifetime ISA"
        # LISA should take precedence over ISA
        assert TaxWrapperDetector.detect(text) == TaxWrapper.LISA

    def test_broker_specific_vanguard(self):
        # Vanguard specific logic
        text = "This is an ISA statement"
        assert TaxWrapperDetector.detect(text, broker="Vanguard") == TaxWrapper.ISA

    def test_broker_specific_fidelity(self):
        # Fidelity specific logic
        text = "Your Pension Plan"
        assert TaxWrapperDetector.detect(text, broker="Fidelity") == TaxWrapper.SIPP

    def test_unknown_defaults(self):
        text = "Just a regular statement with no strong keywords"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.UNKNOWN

        # Ambiguous but not strong enough
        text = "Investment Report"
        assert TaxWrapperDetector.detect(text) == TaxWrapper.UNKNOWN

class TestAllowanceTracker:

    def test_isa_allowance_2023_2024(self):
        limit = AllowanceTracker.get_limits("2023/2024")[TaxWrapper.ISA]
        assert limit == Decimal("20000.00")

        # Test calculation
        contributions = Decimal("15000.00")
        remaining = AllowanceTracker.calculate_remaining_allowance(TaxWrapper.ISA, contributions)
        assert remaining == Decimal("5000.00")

    def test_pension_allowance(self):
        # Pension limit 60k
        contributions = Decimal("10000.00")
        remaining = AllowanceTracker.calculate_remaining_allowance(TaxWrapper.SIPP, contributions)
        assert remaining == Decimal("50000.00")

    def test_over_allowance(self):
        contributions = Decimal("25000.00")
        remaining = AllowanceTracker.calculate_remaining_allowance(TaxWrapper.ISA, contributions)
        assert remaining == Decimal("0.00")

        report = AllowanceTracker.get_utilization_report(TaxWrapper.ISA, contributions)
        assert report["status"] == "Exceeded"
        assert report["used_percentage"] == "125.0%"

    def test_unknown_wrapper_allowance(self):
        # UNKNOWN or GIA should return 0 remaining / no limit
        remaining = AllowanceTracker.calculate_remaining_allowance(TaxWrapper.GIA, Decimal("100.00"))
        assert remaining == Decimal("0.00")

class TestPlanning:

    def test_bed_and_isa_no_allowance(self):
        # No allowance remaining -> No opportunity
        gia_holdings = [Position(symbol="A", description="A", quantity=Decimal(1), price=Decimal(10), market_value=Decimal(1000))]
        isa_allowance_remaining = Decimal("0.00")

        opp = identify_bed_and_isa_opportunity(gia_holdings, isa_allowance_remaining)
        assert opp is None

    def test_bed_and_isa_no_gia_assets(self):
        # No GIA assets -> No opportunity
        gia_holdings = []
        isa_allowance_remaining = Decimal("5000.00")

        opp = identify_bed_and_isa_opportunity(gia_holdings, isa_allowance_remaining)
        assert opp is None

    def test_bed_and_isa_valid_opportunity(self):
        # GIA has 10k, Allowance has 5k -> Move 5k
        gia_holdings = [Position(symbol="A", description="A", quantity=Decimal(1), price=Decimal(1), market_value=Decimal("10000.00"))]
        isa_allowance_remaining = Decimal("5000.00")

        opp = identify_bed_and_isa_opportunity(gia_holdings, isa_allowance_remaining)

        assert opp is not None
        assert opp["amount_to_move"] == "5000.00"
        # 5k is < 6k CGT allowance, so no warning
        assert opp["cgt_warning"] is None

    def test_bed_and_isa_cgt_warning(self):
        # GIA has 20k, Allowance has 20k -> Move 20k
        # This exceeds CGT allowance of 6k -> Expect warning
        gia_holdings = [Position(symbol="A", description="A", quantity=Decimal(1), price=Decimal(1), market_value=Decimal("20000.00"))]
        isa_allowance_remaining = Decimal("20000.00")

        opp = identify_bed_and_isa_opportunity(gia_holdings, isa_allowance_remaining)

        assert opp is not None
        assert opp["amount_to_move"] == "20000.00"
        assert opp["cgt_warning"] is not None
        assert "exceeds the CGT Annual Exempt Amount" in opp["cgt_warning"]
