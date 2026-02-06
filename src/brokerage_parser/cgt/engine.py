from typing import List, Dict, Optional
from decimal import Decimal
from datetime import timedelta
from dataclasses import dataclass
import copy

from brokerage_parser.models import TransactionType, TaxWrapper, CorporateActionType
from brokerage_parser.models.domain import Transaction, CorporateAction
from brokerage_parser.cgt.models import MatchEvent, MatchType, CGTReport
from brokerage_parser.cgt.pool import Section104Pool

@dataclass
class MutableTransaction:
    """
    Wrapper around Transaction to track remaining quantity during the multi-pass process.
    """
    original: Transaction
    remaining_quantity: Decimal

    @property
    def date(self):
        return self.original.date

    @property
    def id(self):
        return self.original.transaction_id or "unknown"

    @property
    def total_proceeds_or_cost(self):
        # We need the total value. For Buys it's cost (neg amount usually, but we need positive magnitude)
        # For Sells it's proceeds.
        # Assuming Transaction.amount is net cash flow (Buy = negative, Sell = positive)
        # But we also have price * quantity.
        # Let's rely on standardizing to positive magnitude for cost/proceeds here.
        if self.original.gbp_amount:
            return abs(self.original.gbp_amount)
        return abs(self.original.amount)

class CGTEngine:
    """
    Calculates Capital Gains according to UK HMRC Share Matching Rules:
    1. Same Day
    2. Bed & Breakfast (30 Days)
    3. Section 104 Pool
    """

    def calculate(self, transactions: List[Transaction], corporate_actions: List[CorporateAction] = None, tax_year: str = "2023/2024") -> CGTReport:
        report = CGTReport(tax_year=tax_year)
        corporate_actions = corporate_actions or []

        # 0. Filter and prep
        # Filter for GIA/UNKNOWN
        # Ignore wrappers like ISA/SIPP
        # Also strictly we only care about BUY/SELL (and maybe Corp Actions later, but for MVP Buy/Sell)
        relevant_txs = [
            t for t in transactions
            if t.type in (TransactionType.BUY, TransactionType.SELL)
            and (not hasattr(t, 'tax_wrapper') or t.tax_wrapper not in (TaxWrapper.ISA, TaxWrapper.SIPP, TaxWrapper.JISA, TaxWrapper.LISA))
        ]

        if not relevant_txs:
            return report

        # Group by security (ISIN or Symbol)
        # Prefer ISIN
        by_security = {}
        for tx in relevant_txs:
            key = tx.isin or tx.symbol or "UNKNOWN"
            if key not in by_security:
                by_security[key] = {"txs": [], "actions": []}
            by_security[key]["txs"].append(tx)

        # Distribute corporate actions to securities
        for action in corporate_actions:
             key = action.source_isin or "UNKNOWN" # Logic implies we match by source ISIN
             if key in by_security:
                 by_security[key]["actions"].append(action)

        for security in by_security:
            self._process_security(by_security[security]["txs"], by_security[security]["actions"], report)

        return report

    def _process_security(self, transactions: List[Transaction], corporate_actions: List[CorporateAction], report: CGTReport):
        # Sort strictly by date, then by type (Buy before Sell on same day?
        # HMRC: "All shares acquired on the same day are treated as acquired in a single transaction".
        # Same for disposals.
        # For matching "Same Day", we just match Buy to Sell on that day.

        sorted_txs = sorted(transactions, key=lambda t: t.date)

        # Wrap in MutableTransaction
        # Using list index or ID map might be easier, but let's use objects
        mutable_txs = [MutableTransaction(t, t.quantity or Decimal(0)) for t in sorted_txs]

        # Split into Buys and Sells for easier indexing, but keep reference to main list
        # Actually, iterating the main list is safer to keep logic clean.

        # PASS 1: SAME DAY
        self._pass_same_day(mutable_txs, report)

        # PASS 2: BED AND BREAKFAST (30 Days)
        self._pass_bed_and_breakfast(mutable_txs, report)

        # PASS 3: SECTION 104 POOL
        self._pass_section_104(mutable_txs, corporate_actions, report)

    def _pass_same_day(self, txs: List[MutableTransaction], report: CGTReport):
        """
        Match Sells to Buys occurring on the EXACT SAME date.
        """
        # Group by date
        by_date = {}
        for tx in txs:
            if tx.remaining_quantity > 0:
                d = tx.date
                if d not in by_date: by_date[d] = []
                by_date[d].append(tx)

        for d, day_txs in by_date.items():
            buys = [t for t in day_txs if t.original.type == TransactionType.BUY]
            sells = [t for t in day_txs if t.original.type == TransactionType.SELL]

            # Match efficiently
            # We iterate sells and try to fill from buys
            for sell in sells:
                if sell.remaining_quantity <= 0: continue

                for buy in buys:
                    if buy.remaining_quantity <= 0: continue
                    if sell.remaining_quantity <= 0: break

                    self._execute_match(sell, buy, MatchType.SAME_DAY, report)

    def _pass_bed_and_breakfast(self, txs: List[MutableTransaction], report: CGTReport):
        """
        Match Sells to Buys occurring within the NEXT 30 days.
        """
        # We need to iterate Sells chronologically
        # For each Sell, look ahead in the list for Buys in window

        # Ensure we are sorted strictly
        txs.sort(key=lambda t: t.date)

        for i, sell in enumerate(txs):
            if sell.original.type != TransactionType.SELL: continue
            if sell.remaining_quantity <= 0: continue

            sell_date = sell.date
            window_end = sell_date + timedelta(days=30)

            # Look ahead
            for j in range(i + 1, len(txs)):
                buy = txs[j]
                if buy.original.type != TransactionType.BUY: continue
                if buy.remaining_quantity <= 0: continue

                # Check 30 day window
                # Start date is strictly > sell date (same day handled above)
                # HMRC: "acquired within the 30 days following the day of disposal"
                if buy.date <= sell_date: continue # Should be filtered by i+1 but double check sorting stability
                if buy.date > window_end:
                    # Optimization: Since sorted by date, if we pass window we can stop looking for this sell?
                    # Yes, provided list is sorted by date.
                    break

                # We have a match candidate
                self._execute_match(sell, buy, MatchType.BED_AND_BREAKFAST, report)

                if sell.remaining_quantity <= 0:
                    break

    def _pass_section_104(self, txs: List[MutableTransaction], corporate_actions: List[CorporateAction], report: CGTReport):
        """
        Chronological pass.
        Buys add to pool.
        Sells consume from pool.
        Corporate Actions adjust pool.
        """
        pool = Section104Pool()

        # Merge timeline: (Date, Priority, Object)
        # Priority: 0 for CorporateAction, 1 for Transaction (Action happens BEFORE trade on same day)
        timeline = []

        # Add transactions that still have quantity
        for tx in txs:
            if tx.remaining_quantity > 0:
                # Use date, 1 as priority
                timeline.append((tx.date, 1, tx))

        # Add corporate actions
        for action in corporate_actions:
            # Use date, 0 as priority
            timeline.append((action.date, 0, action))

        # Sort strictly by date, then priority
        timeline.sort(key=lambda x: (x[0], x[1]))

        for date, priority, item in timeline:
            if priority == 0:
                # It's a Corporate Action
                action: CorporateAction = item

                if action.type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
                    if action.ratio_from != 0:
                        ratio = action.ratio_to / action.ratio_from
                        old_qty, new_qty = pool.adjust_quantity(ratio)

                        # Log the event (Tax Neutral)
                        event = MatchEvent(
                            sell_transaction_id="", # NA
                            buy_transaction_id=None,
                            match_type=MatchType.CORPORATE_ACTION,
                            quantity=new_qty - old_qty, # Change in quantity
                            proceeds=Decimal("0.00"),
                            allowable_cost=Decimal("0.00"),
                            gain_gbp=Decimal("0.00"),
                            date=action.date.isoformat()
                        )
                        report.add_event(event)

            else:
                # It's a Transaction
                tx: MutableTransaction = item

                if tx.original.type == TransactionType.BUY:
                    # Add to pool
                    # Calculate cost proportionate to the remaining quantity!
                    # If we used half the buy for a Same Day match, we only add half the cost here.
                    ratio = tx.remaining_quantity / tx.original.quantity
                    cost_to_add = tx.total_proceeds_or_cost * ratio

                    pool.add(tx.remaining_quantity, cost_to_add)

                    # Consume it fully so it doesn't get used again (conceptually it's now in the pool)
                    tx.remaining_quantity = Decimal(0)

                elif tx.original.type == TransactionType.SELL:
                    # Remove from pool
                    qty_to_process = tx.remaining_quantity

                    # Calculate pro-rated proceeds
                    ratio = qty_to_process / tx.original.quantity
                    proceeds = tx.total_proceeds_or_cost * ratio

                    # Remove from pool (gets cost basis)
                    cost_basis = pool.remove(qty_to_process)

                    gain = proceeds - cost_basis

                    event = MatchEvent(
                        sell_transaction_id=tx.id,
                        buy_transaction_id=None, # Pool
                        match_type=MatchType.SECTION_104,
                        quantity=qty_to_process,
                        proceeds=proceeds,
                        allowable_cost=cost_basis,
                        gain_gbp=gain,
                        date=tx.date.isoformat()
                    )
                    report.add_event(event)

                    tx.remaining_quantity = Decimal(0)

    def _execute_match(self, sell: MutableTransaction, buy: MutableTransaction, match_type: MatchType, report: CGTReport):
        """
        Helper to execute a matched trade pair (Same Day or BnB).
        Decrements quantities and records the event.
        """
        match_qty = min(sell.remaining_quantity, buy.remaining_quantity)

        # Calculate proportional values
        # Sell Proceeds
        sell_ratio = match_qty / sell.original.quantity
        proceeds = sell.total_proceeds_or_cost * sell_ratio

        # Buy Cost
        buy_ratio = match_qty / buy.original.quantity
        cost = buy.total_proceeds_or_cost * buy_ratio

        gain = proceeds - cost

        # Record
        event = MatchEvent(
            sell_transaction_id=sell.id,
            buy_transaction_id=buy.id,
            match_type=match_type,
            quantity=match_qty,
            proceeds=proceeds,
            allowable_cost=cost,
            gain_gbp=gain,
            date=sell.date.isoformat()
        )
        report.add_event(event)

        # Decrement
        sell.remaining_quantity -= match_qty
        buy.remaining_quantity -= match_qty
