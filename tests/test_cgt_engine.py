import pytest
from decimal import Decimal
from datetime import date
from brokerage_parser.models import TransactionType, TaxWrapper
from brokerage_parser.models.domain import Transaction
from brokerage_parser.cgt.engine import CGTEngine
from brokerage_parser.cgt.models import MatchType

class TestCGTEngine:

    def mk_tx(self, date_str, type_name, qty, amount, tx_id, isin="ISIN123"):
        return Transaction(
            date=date.fromisoformat(date_str),
            type=type_name,
            description="Test",
            amount=Decimal(amount), # Cash flow (negative for buy)
            quantity=Decimal(qty),
            transaction_id=tx_id,
            isin=isin,
            # Implicit price calc from amount/qty
        )

    def test_section_104_simple(self):
        """
        Buy 100 @ 10, Buy 100 @ 20. Pool = 200 @ 30 (Avg 15). Sell 100.
        """
        txs = [
            self.mk_tx("2023-01-01", TransactionType.BUY, 100, "-1000", "t1"),
            self.mk_tx("2023-01-02", TransactionType.BUY, 100, "-2000", "t2"),
            self.mk_tx("2023-01-05", TransactionType.SELL, 100, "2500", "t3"), # Sell @ 25
        ]

        engine = CGTEngine()
        report = engine.calculate(txs)

        assert len(report.match_events) == 1
        event = report.match_events[0]

        assert event.match_type == MatchType.SECTION_104
        assert event.quantity == Decimal("100")
        assert event.allowable_cost == Decimal("1500") # Avg 15 * 100
        assert event.gain_gbp == Decimal("1000") # 2500 - 1500

    def test_same_day_rule(self):
        """
        Buy 100 and Sell 100 on same day. Matches directly.
        Ignore prior pool cost.
        """
        txs = [
            self.mk_tx("2023-01-01", TransactionType.BUY, 100, "-1000", "pool_buy"), # Creates pool entry
            self.mk_tx("2023-01-10", TransactionType.BUY, 100, "-2000", "same_day_buy"),
            self.mk_tx("2023-01-10", TransactionType.SELL, 100, "2500", "same_day_sell"),
        ]

        engine = CGTEngine()
        report = engine.calculate(txs)

        # Should have 1 event matching same_day_buy to same_day_sell
        assert len(report.match_events) == 1
        event = report.match_events[0]

        assert event.match_type == MatchType.SAME_DAY
        assert event.buy_transaction_id == "same_day_buy"
        assert event.allowable_cost == Decimal("2000") # Matched strictly to the specific buy
        assert event.gain_gbp == Decimal("500") # 2500 - 2000

    def test_bed_and_breakfast_rule(self):
        """
        T1: Buy 100 (Pool)
        T2: Sell 100
        T3: Buy 100 (10 days later) -> Matches T2 via BnB Rule
        """
        txs = [
            self.mk_tx("2023-01-01", TransactionType.BUY, 100, "-1000", "pool_buy"),
            self.mk_tx("2023-02-01", TransactionType.SELL, 100, "1500", "sell"),
            self.mk_tx("2023-02-10", TransactionType.BUY, 100, "-1200", "bnb_buy"),
        ]

        engine = CGTEngine()
        report = engine.calculate(txs)

        assert len(report.match_events) == 1
        event = report.match_events[0]

        assert event.match_type == MatchType.BED_AND_BREAKFAST
        assert event.buy_transaction_id == "bnb_buy"
        assert event.allowable_cost == Decimal("1200") # Matched to the FUTURE buy
        assert event.gain_gbp == Decimal("300") # 1500 - 1200

        # Verify pool is untouched?
        # Actually in this specific case, pool_buy is never sold.
        # But conceptually the loop works.

    def test_bnb_excludes_from_pool(self):
        """
        Crucial Safety Check:
        Date 1: Buy A (100)
        Date 2: Sell A (100)
        Date 3: Buy B (100) -> Matches Sell A (BnB)
        Date 4: Sell B (100) -> Should match Buy A (Pool), NOT Buy B (already used!)
        """
        txs = [
            self.mk_tx("2023-01-01", TransactionType.BUY, 100, "-1000", "buy_A"),
            self.mk_tx("2023-01-05", TransactionType.SELL, 100, "1500", "sell_A"),
            self.mk_tx("2023-01-10", TransactionType.BUY, 100, "-1200", "buy_B"),
            self.mk_tx("2023-02-01", TransactionType.SELL, 100, "2000", "sell_B"),
        ]

        engine = CGTEngine()
        report = engine.calculate(txs)

        events = sorted(report.match_events, key=lambda e: e.date)
        assert len(events) == 2

        # Event 1: Sell A matches Buy B (BnB)
        e1 = events[0]
        assert e1.sell_transaction_id == "sell_A"
        assert e1.match_type == MatchType.BED_AND_BREAKFAST
        assert e1.buy_transaction_id == "buy_B"

        # Event 2: Sell B matches Buy A (Pool)
        # Because Buy B was consumed by Sell A, it cannot be in the pool for Sell B.
        e2 = events[1]
        assert e2.sell_transaction_id == "sell_B"
        assert e2.match_type == MatchType.SECTION_104
        # Allowable cost should be from Buy A (1000)
        assert e2.allowable_cost == Decimal("1000")

    def test_isa_filtering(self):
        """
        Ensure ISA transactions are ignored.
        """
        txs = [
            self.mk_tx("2023-01-01", TransactionType.BUY, 100, "-1000", "isa_buy"),
            self.mk_tx("2023-01-02", TransactionType.SELL, 100, "1500", "isa_sell"),
        ]
        txs[0].tax_wrapper = TaxWrapper.ISA
        txs[1].tax_wrapper = TaxWrapper.ISA

        engine = CGTEngine()
        report = engine.calculate(txs)

        assert len(report.match_events) == 0
