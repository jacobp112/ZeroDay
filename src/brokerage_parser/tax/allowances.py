from decimal import Decimal
from typing import Dict, Any
from brokerage_parser.models import TaxWrapper

class AllowanceTracker:
    """
    Tracks and calculates remaining allowances for different tax wrappers.
    Designed to be extensible for future tax years.
    """

    # Configuration for Tax Years
    TAX_YEAR_LIMITS = {
        "2023/2024": {
            TaxWrapper.ISA: Decimal("20000.00"),
            TaxWrapper.JISA: Decimal("9000.00"),
            TaxWrapper.LISA: Decimal("4000.00"),
            TaxWrapper.SIPP: Decimal("60000.00"), # Annual Allowance
            "CGT_ALLOWANCE": Decimal("6000.00"),
        },
        "2024/2025": {
            TaxWrapper.ISA: Decimal("20000.00"),
            TaxWrapper.JISA: Decimal("9000.00"),
            TaxWrapper.LISA: Decimal("4000.00"),
            TaxWrapper.SIPP: Decimal("60000.00"),
            "CGT_ALLOWANCE": Decimal("3000.00"),
        }
    }

    CURRENT_TAX_YEAR = "2023/2024"

    @classmethod
    def get_limits(cls, tax_year: str = None) -> Dict[str, Decimal]:
        year = tax_year or cls.CURRENT_TAX_YEAR
        return cls.TAX_YEAR_LIMITS.get(year, cls.TAX_YEAR_LIMITS[cls.CURRENT_TAX_YEAR])

    @classmethod
    def calculate_remaining_allowance(cls, wrapper: TaxWrapper, contributions: Decimal, tax_year: str = None) -> Decimal:
        """
        Calculate how much allowance is remaining for a valid wrapper.
        Returns 0 if wrapper has no explicit limit logic implemented here (e.g. GIA).
        """
        limits = cls.get_limits(tax_year)

        # LISA limit is part of the overall ISA limit, but here we treat it as the specific cap for the LISA account itself
        limit = limits.get(wrapper)

        if limit is None:
            return Decimal("0.00")

        remaining = limit - contributions
        return max(Decimal("0.00"), remaining)

    @classmethod
    def get_utilization_report(cls, wrapper: TaxWrapper, contributions: Decimal, tax_year: str = None) -> Dict[str, Any]:
        """
        Returns a dictionary with usage statistics.
        """
        limits = cls.get_limits(tax_year)
        limit = limits.get(wrapper)

        if limit is None:
            return {
                "wrapper": wrapper.value,
                "status": "No Limit / Unknown",
                "contributions": str(contributions)
            }

        remaining = cls.calculate_remaining_allowance(wrapper, contributions, tax_year)
        used_percentage = (contributions / limit) * 100 if limit > 0 else Decimal("0.00")

        status = "Within Limit"
        if contributions > limit:
            status = "Exceeded"
        elif contributions == limit:
            status = "Maxed Out"

        return {
            "wrapper": wrapper.value,
            "limit": str(limit),
            "contributions": str(contributions),
            "remaining": str(remaining),
            "used_percentage": f"{used_percentage:.1f}%",
            "status": status,
            "tax_year": tax_year or cls.CURRENT_TAX_YEAR
        }
