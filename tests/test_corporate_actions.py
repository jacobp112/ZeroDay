from decimal import Decimal
from datetime import date
import pytest
from brokerage_parser.models import Transaction, TransactionType, CorporateAction, CorporateActionType
from brokerage_parser.cgt.engine import CGTEngine
from brokerage_parser.cgt.models import MatchType

def test_forward_split():
    # Buy 100 @ £100 (Total £10,000)
    # Split 2:1 -> 200 shares
    # Sell 200 @ £60 (Total £12,000) -> Gain £2,000

    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.BUY, description="Buy", amount=Decimal("-10000"), quantity=Decimal("100"), price=Decimal("100"))
    split = CorporateAction(
        date=date(2023, 6, 1),
        type=CorporateActionType.STOCK_SPLIT,
        source_isin="UNKNOWN",
        description="Split",
        ratio_from=Decimal("1"),
        ratio_to=Decimal("2")
    )
    t2 = Transaction(date=date(2023, 12, 1), type=TransactionType.SELL, description="Sell", amount=Decimal("12000"), quantity=Decimal("200"), price=Decimal("60"))

    engine = CGTEngine()
    report = engine.calculate([t1, t2], corporate_actions=[split])

    assert len(report.match_events) == 2 # 1 Split + 1 Sell

    split_event = [e for e in report.match_events if e.match_type == MatchType.CORPORATE_ACTION][0]
    assert split_event.quantity == Decimal("100") # +100 shares
    assert split_event.gain_gbp == Decimal("0.00")

    sell_event = [e for e in report.match_events if e.match_type == MatchType.SECTION_104][0]
    assert sell_event.quantity == Decimal("200")
    assert sell_event.proceeds == Decimal("12000")
    assert sell_event.allowable_cost == Decimal("10000") # Original cost preserved
    assert sell_event.gain_gbp == Decimal("2000")

def test_reverse_split():
    # Buy 100 @ £10 (Total £1,000)
    # Reverse Split 1:10 -> 10 shares
    # Sell 10 @ £150 (Total £1,500) -> Gain £500

    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.BUY, description="Buy", amount=Decimal("-1000"), quantity=Decimal("100"), price=Decimal("10"))
    split = CorporateAction(
        date=date(2023, 6, 1),
        type=CorporateActionType.REVERSE_SPLIT,
        source_isin="UNKNOWN",
        description="Rev Split",
        ratio_from=Decimal("10"),
        ratio_to=Decimal("1")
    )
    t2 = Transaction(date=date(2023, 12, 1), type=TransactionType.SELL, description="Sell", amount=Decimal("1500"), quantity=Decimal("10"), price=Decimal("150"))

    engine = CGTEngine()
    report = engine.calculate([t1, t2], corporate_actions=[split])

    rev_split_event = [e for e in report.match_events if e.match_type == MatchType.CORPORATE_ACTION][0]
    assert rev_split_event.quantity == Decimal("-90") # 100 -> 10, change is -90

    sell_event = [e for e in report.match_events if e.match_type == MatchType.SECTION_104][0]
    assert sell_event.quantity == Decimal("10")
    assert sell_event.allowable_cost == Decimal("1000")
    assert sell_event.gain_gbp == Decimal("500")

def test_interleaved_events():
    # Buy 100 @ 10 = 1000
    # Split 2:1 -> 200 @ 1000 (avg 5)
    # Buy 100 @ 6 = 600
    # Pool: 300 shares, Cost 1600 (avg 5.333)
    # Sell 300 @ 10 = 3000 -> Gain 1400

    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.BUY, description="Buy1", amount=Decimal("-1000"), quantity=Decimal("100"))
    split = CorporateAction(date=date(2023, 6, 1), type=CorporateActionType.STOCK_SPLIT, source_isin="UNKNOWN", description="Split", ratio_from=Decimal("1"), ratio_to=Decimal("2"))
    t2 = Transaction(date=date(2023, 7, 1), type=TransactionType.BUY, description="Buy2", amount=Decimal("-600"), quantity=Decimal("100"))
    t3 = Transaction(date=date(2023, 12, 1), type=TransactionType.SELL, description="Sell", amount=Decimal("3000"), quantity=Decimal("300"))

    engine = CGTEngine()
    report = engine.calculate([t1, t2, t3], corporate_actions=[split])

    sell_event = [e for e in report.match_events if e.match_type == MatchType.SECTION_104][0]
    assert sell_event.quantity == Decimal("300")
    assert sell_event.allowable_cost == Decimal("1600")
    assert sell_event.gain_gbp == Decimal("1400")

def test_same_day_ordering():
    # Buy 100 @ 100 = 10000
    # Split 2:1 on Dec 1 -> 200 shares
    # Sell 200 on Dec 1
    # Should handle split first.

    t1 = Transaction(date=date(2023, 1, 1), type=TransactionType.BUY, description="Buy", amount=Decimal("-10000"), quantity=Decimal("100"))
    split = CorporateAction(date=date(2023, 12, 1), type=CorporateActionType.STOCK_SPLIT, source_isin="UNKNOWN", description="Split", ratio_from=Decimal("1"), ratio_to=Decimal("2"))
    t2 = Transaction(date=date(2023, 12, 1), type=TransactionType.SELL, description="Sell", amount=Decimal("12000"), quantity=Decimal("200"))

    engine = CGTEngine()
    report = engine.calculate([t1, t2], corporate_actions=[split])

    # Check if split happened
    split_events = [e for e in report.match_events if e.match_type == MatchType.CORPORATE_ACTION]
    assert len(split_events) == 1

    # Check if sell matched 200 (if split didn't happen, we'd have only 100 in pool and a problem/partial match)
    sell_events = [e for e in report.match_events if e.match_type == MatchType.SECTION_104]
    assert len(sell_events) == 1
    assert sell_events[0].quantity == Decimal("200")
    assert sell_events[0].allowable_cost == Decimal("10000")
