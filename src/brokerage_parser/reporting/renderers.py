from decimal import Decimal
from brokerage_parser.reporting.models import ClientReport

class MarkdownRenderer:
    @staticmethod
    def render(report: ClientReport) -> str:
        lines = []

        # Header
        m = report.metadata
        lines.append(f"# Client Report: {m.client_name}")
        lines.append(f"**Broker:** {m.broker_name} | **Account:** {m.account_number}")
        lines.append(f"**Period:** {m.reporting_period_start} to {m.reporting_period_end}")
        lines.append(f"**Date:** {m.report_date}")
        lines.append("")

        # Portfolio Summary
        s = report.portfolio_summary
        lines.append("## Executive Summary")
        lines.append(f"- **Total Portfolio Value:** £{s.total_value_gbp:,.2f}")
        lines.append(f"- **Investments:** £{s.investments_value_gbp:,.2f}")
        lines.append(f"- **Cash:** £{s.cash_value_gbp:,.2f}")
        lines.append("")

        # Holdings
        lines.append("## Holdings")
        if not report.holdings:
            lines.append("No holdings found.")
        else:
            # Simple table
            lines.append("| Symbol | Description | Quantity | Price | Value (GBP) |")
            lines.append("|---|---|---|---|---|")
            for p in report.holdings:
                val = p.gbp_market_value if p.gbp_market_value is not None else p.market_value
                price = p.price # already decimal
                lines.append(f"| {p.symbol} | {p.description} | {p.quantity:.4f} | {price:.2f} | {val:,.2f} |")
        lines.append("")

        # Tax Pack
        tp = report.tax_pack
        lines.append("## Tax Pack")
        lines.append(f"**Tax Wrapper:** {tp.tax_wrapper}")

        # Allowances
        a = tp.allowance_status
        lines.append("### Allowance Utilization")
        lines.append(f"- **Limit:** £{a.get('limit', 'N/A')}")
        lines.append(f"- **Used:** £{a.get('contributions', '0.00')}")
        lines.append(f"- **Remaining:** £{a.get('remaining', '0.00')}")
        lines.append(f"- **Status:** {a.get('status', 'Unknown')}")
        lines.append("")

        # CGT
        lines.append("### Capital Gains Tax (CGT)")
        if tp.cgt_report:
            cgt = tp.cgt_report
            lines.append(f"**Tax Year:** {cgt.tax_year}")
            lines.append(f"- **Total Realised Gains:** £{cgt.total_gains:,.2f}")
            lines.append(f"- **Total Proceeds:** £{cgt.total_proceeds:,.2f}")
            lines.append(f"- **Total Allowable Costs:** £{cgt.total_allowable_costs:,.2f}")

            if cgt.match_events:
                lines.append("\n#### Realised Events")
                lines.append("| Date | Security | Match Type | Qty | Gain (GBP) |")
                lines.append("|---|---|---|---|---|")
                for e in cgt.match_events:
                     # We assume we can get security info or just generic
                     # The event doesn't currently store Symbol, just Trans ID.
                     # For summary, we list the event.
                     lines.append(f"| {e.date} | {e.match_type.value} | {e.quantity:.4f} | {e.gain_gbp:,.2f} |")
            else:
                lines.append("\nNo taxable events in this period.")
        else:
            lines.append("Not applicable for this account type.")
        lines.append("")

        # Costs
        lines.append("## MiFID II Cost Disclosure")
        cr = tp.cost_report
        lines.append(f"**Total Costs:** £{cr.total_costs:,.2f}")

        if cr.items:
            lines.append("\n### Cost Breakdown")
            lines.append(f"- **Service Costs:** £{cr.total_service_costs:,.2f}")
            lines.append(f"- **Transaction Costs:** £{cr.total_transaction_costs:,.2f}")
            lines.append(f"- **Ancillary Costs:** £{cr.total_ancillary_costs:,.2f}")

            lines.append("\n### Itemized Costs")
            lines.append("| Date | Description | Category | Amount (GBP) |")
            lines.append("|---|---|---|---|")
            for item in cr.items:
                lines.append(f"| {item.date} | {item.description} | {item.category.name} | {item.amount_gbp:,.2f} |")
        else:
            lines.append("No explicit costs identified.")

        return "\n".join(lines)
