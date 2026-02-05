from decimal import Decimal
from datetime import date
import pytest
from brokerage_parser.models import Transaction, TransactionType
from brokerage_parser.costs.engine import CostAnalysisEngine
from brokerage_parser.costs.models import CostCategory

def test_service_costs():
    # Management Fee
    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.FEE, description="Quarterly Management Fee", amount=Decimal("-150.00"))
    # Custody Fee
    t2 = Transaction(date=date(2023, 2, 1), type=TransactionType.FEE, description="Custody Charge", amount=Decimal("-20.00"))

    engine = CostAnalysisEngine()
    report = engine.analyze([t1, t2])

    assert len(report.items) == 2
    assert report.total_service_costs == Decimal("170.00")
    assert report.items[0].category == CostCategory.SERVICE_COST
    assert report.items[1].category == CostCategory.SERVICE_COST

def test_transaction_costs():
    # SDRT
    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.FEE, description="SDRT on BUY VOD", amount=Decimal("-50.00"))
    # Commission
    t2 = Transaction(date=date(2023, 1, 1), type=TransactionType.OTHER, description="Brokerage Commission", amount=Decimal("-12.95"))

    engine = CostAnalysisEngine()
    report = engine.analyze([t1, t2])

    assert report.total_transaction_costs == Decimal("62.95")
    assert report.items[0].category == CostCategory.TRANSACTION_COST

def test_ancillary_costs():
    # Wire Transfer
    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.FEE, description="Wire Transfer Out", amount=Decimal("-25.00"))

    engine = CostAnalysisEngine()
    report = engine.analyze([t1])

    assert report.total_ancillary_costs == Decimal("25.00")
    assert report.items[0].category == CostCategory.ANCILLARY_COST

def test_ignore_positive_amounts():
    # CRITICAL: Wire Transfer In (Deposit) shouldn't be a cost
    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.TRANSFER_IN, description="Wire Transfer In", amount=Decimal("10000.00"))

    engine = CostAnalysisEngine()
    report = engine.analyze([t1])

    assert len(report.items) == 0
    assert report.total_costs == Decimal("0.00")

def test_no_double_counting():
    # Ensure regex priority works or at least handling
    # "SDRT" vs "Fee" - standard priority
    pass

def test_mixed_case_handling():
    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.FEE, description="mgmt fee", amount=Decimal("-10.00"))

    engine = CostAnalysisEngine()
    report = engine.analyze([t1])

    assert report.total_service_costs == Decimal("10.00")
