from decimal import Decimal
from typing import Optional
from datetime import date

from brokerage_parser.models import TaxWrapper, TransactionType
from brokerage_parser.models.domain import ParsedStatement
from brokerage_parser.cgt.engine import CGTEngine
from brokerage_parser.costs.engine import CostAnalysisEngine
from brokerage_parser.tax.allowances import AllowanceTracker
from brokerage_parser.reporting.models import (
    ClientReport, ClientMetadata, PortfolioSummary, TaxPack
)

class ReportingEngine:
    """
    Orchestrates the generation of the consolidated Client Report.
    """

    def generate_report(self, statement: ParsedStatement) -> ClientReport:
        # 1. Metadata
        metadata = ClientMetadata(
            client_name="Client",  # Placeholder, usually enriched from CRM or filename
            report_date=date.today(),
            reporting_period_start=statement.period_start,
            reporting_period_end=statement.period_end,
            broker_name=statement.broker,
            account_number=statement.account.account_number if statement.account else "Unknown"
        )

        # 2. Portfolio Summary
        # Sum of gbp_market_value of positions
        total_value = Decimal("0.00")
        investments_value = Decimal("0.00")
        cash_value = Decimal("0.00")

        # Basic logic:
        # Investments = sum of positions
        # Cash = ending balance of account (if available) - investments?
        # Or usually account.ending_balance IS the total value (Cash + Investments).
        # Let's assume account.ending_balance is the Total Portfolio Value.
        # And positions sum is Investments.
        # Cash = Total - Investments.

        investments_value = sum(p.gbp_market_value or Decimal("0.00") for p in statement.positions)

        if statement.account and statement.account.ending_balance is not None:
            total_value = statement.account.ending_balance
            cash_value = total_value - investments_value
            # Handle slight calc drift if any
            if cash_value < 0:
                # Fallback: maybe ending_balance was just cash? Unlikely for "Portfolio Combined Value"
                # If ending_balance < investments, something is off, or ending_balance is just cash.
                # For now, trust the math but floor at 0 to avoid confusion unless it's an overdraft.
                pass
        else:
            # Fallback if no account summary
            total_value = investments_value
            cash_value = Decimal("0.00")

        summary = PortfolioSummary(
            total_value_gbp=total_value,
            cash_value_gbp=cash_value,
            investments_value_gbp=investments_value
        )

        # 3. Tax Pack
        # 3a. Allowances
        # Calculate contributions.
        # For ISA: Contributions are usually implicit (Deposits) or explicit Subscriptions.
        # But we need to distinguish between "Cash added" vs "Transfer In".
        # AllowanceTracker expects 'contributions'.
        # Let's sum 'TRANSFER_IN' and 'DEPOSIT' (if we had it)?
        # Actually TransactionType has TRANSFER_IN, but usually 'subs' are cash deposits.
        # Parsers usually map deposits to TRANSFER_IN or explicitly OTHER?
        # Let's check TransactionType: BUY, SELL, DIVIDEND, INTEREST, TRANSFER_IN, TRANSFER_OUT, FEE, OTHER.
        # We'll assume TRANSFER_IN is a contribution for allowance purposes for now.

        contributions = sum(
            t.amount for t in statement.transactions
            if t.type == TransactionType.TRANSFER_IN and t.amount > 0
        )

        # If we have explicit logic for "Subscription" in description, we could enhance here.

        allowance_status = AllowanceTracker.get_utilization_report(
            statement.tax_wrapper,
            contributions,
            tax_year="2023/2024" # Should ideally infer from statement date
        )

        # 3b. Costs
        cost_engine = CostAnalysisEngine()
        cost_report = cost_engine.analyze(statement.transactions)

        # 3c. CGT (Conditional)
        cgt_report = None
        if statement.tax_wrapper == TaxWrapper.GIA:
            cgt_engine = CGTEngine()
            cgt_report = cgt_engine.calculate(
                statement.transactions,
                statement.corporate_actions,
                tax_year="2023/2024"
            )

        tax_pack = TaxPack(
            tax_wrapper=statement.tax_wrapper.value,
            allowance_status=allowance_status,
            cgt_report=cgt_report,
            cost_report=cost_report
        )

        # 4. Assembly
        return ClientReport(
            metadata=metadata,
            portfolio_summary=summary,
            tax_pack=tax_pack,
            holdings=statement.positions,
            source_statement=statement
        )
