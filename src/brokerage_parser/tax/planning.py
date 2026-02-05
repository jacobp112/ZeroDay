from decimal import Decimal
from typing import List, Optional, Dict, Any
from brokerage_parser.models import Position
from brokerage_parser.tax.allowances import AllowanceTracker

def identify_bed_and_isa_opportunity(
    gia_holdings: List[Position],
    isa_allowance_remaining: Decimal
) -> Optional[Dict[str, Any]]:
    """
    Identify potential Bed & ISA opportunities (moving assets from GIA to ISA).

    Logic:
    - If ISA allowance is available and GIA has assets.
    - Recommend moving assets up to the allowance.
    - Warn if the move amount exceeds the CGT allowance (potential tax event).
    """

    if isa_allowance_remaining <= Decimal("0.00"):
        return None

    # Calculate total GIA value
    gia_value = sum(p.market_value for p in gia_holdings)

    if gia_value <= Decimal("0.00"):
        return None

    # Calculate how much to move
    # We can move pending on what's lower: the remaining allowance or the total assets we have
    amount_to_move = min(isa_allowance_remaining, gia_value)

    if amount_to_move <= Decimal("0.00"):
        return None

    # Check for Capital Gains Tax warning
    # We use valid assumptions for MVP: If proceeds > annual exempt amount, warn user.
    # Ideally we'd calculate gain, but without cost basis for all, we use proceeds as a safe trigger.
    limits = AllowanceTracker.get_limits()
    cgt_allowance = limits.get("CGT_ALLOWANCE", Decimal("6000.00"))

    warning = None
    if amount_to_move > cgt_allowance:
        warning = (
            f"Warning: Moving £{amount_to_move:,.2f} exceeds the CGT Annual Exempt Amount "
            f"(£{cgt_allowance:,.2f}). This disposal may trigger a Capital Gains Tax report "
            f"or liability if you have significant gains."
        )

    return {
        "recommendation": "Bed & ISA Opportunity",
        "details": f"You have £{isa_allowance_remaining:,.2f} ISA allowance remaining and £{gia_value:,.2f} in taxable assets.",
        "action": f"Move £{amount_to_move:,.2f} from GIA to ISA to maximize tax efficiency.",
        "amount_to_move": str(amount_to_move),
        "cgt_warning": warning
    }
