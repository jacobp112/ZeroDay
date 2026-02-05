from typing import Optional
from brokerage_parser.models import TaxWrapper

class TaxWrapperDetector:
    """
    Service to detect the tax wrapper type of a brokerage account based on
    statement text and metadata.
    """

    # Precedence matters: Check specific types before generic ones
    STRONG_SIGNALS = {
        TaxWrapper.JISA: ["Junior ISA", "Junior Individual Savings Account", "JISA"],
        TaxWrapper.LISA: ["Lifetime ISA", "Lifetime Individual Savings Account", "LISA"],
        TaxWrapper.ISA: ["Stocks & Shares ISA", "Individual Savings Account", " ISA "], # " ISA " with spaces to avoid substring matches
        TaxWrapper.SIPP: ["SIPP", "Self-Invested Personal Pension", "Pension Account"],
        TaxWrapper.GIA: ["General Investment Account", "Fund and Share Account", "Dealing Account", "Share Account"],
    }

    MEDIUM_SIGNALS = {
        TaxWrapper.ISA: ["Subscription Limit", "ISA Limit"],
        TaxWrapper.SIPP: ["Annual Allowance", "Pension Age"],
    }

    @classmethod
    def detect(cls, text: str, broker: str = "Unknown") -> TaxWrapper:
        """
        Analyze text and broker name to determine the tax wrapper.
        """
        text_upper = text.upper()

        # 1. Broker-Specific Overrides (High Confidence)
        if broker.lower() == "vanguard":
            if "ISA" in text_upper:
                return TaxWrapper.ISA
            # Vanguard "General Account" usually maps to GIA, but we'll let signals confirm

        if broker.lower() == "fidelity":
            if "PENSION" in text_upper or "SIPP" in text_upper:
                return TaxWrapper.SIPP

        # 2. Strong Signals (iterate in specific order)
        # Check specific ISAs (JISA, LISA) before generic ISA
        priority_order = [
            TaxWrapper.JISA,
            TaxWrapper.LISA,
            TaxWrapper.SIPP,
            TaxWrapper.ISA,
            TaxWrapper.GIA
        ]

        for wrapper in priority_order:
            keywords = cls.STRONG_SIGNALS.get(wrapper, [])
            for keyword in keywords:
                if keyword.upper() in text_upper:
                    return wrapper

        # 3. Medium Signals (Lower Confidence / Corroboration)
        # If we see "Subscription Limit", it's likely an ISA
        for keyword in cls.MEDIUM_SIGNALS.get(TaxWrapper.ISA, []):
            if keyword.upper() in text_upper:
                return TaxWrapper.ISA

        for keyword in cls.MEDIUM_SIGNALS.get(TaxWrapper.SIPP, []):
            if keyword.upper() in text_upper:
                return TaxWrapper.SIPP

        # 4. Fallback
        return TaxWrapper.UNKNOWN
