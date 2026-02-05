from decimal import Decimal
from typing import Tuple

class Section104Pool:
    """
    Represents a Section 104 Holding (Pool) for a single security.
    Tracks the total number of shares and total allowable cost.
    """
    def __init__(self):
        self.total_quantity = Decimal("0.00")
        self.total_cost = Decimal("0.00")

    def add(self, quantity: Decimal, cost: Decimal):
        """
        Add shares to the pool (Acquisition).
        """
        if quantity <= 0:
            return # Should define behavior for 0 quantity?

        self.total_quantity += quantity
        self.total_cost += cost

    def adjust_quantity(self, ratio: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Adjust the pool quantity by a ratio (e.g. for Stock Splits).
        Total cost remains unchanged.
        Returns (old_quantity, new_quantity).
        """
        old_quantity = self.total_quantity
        self.total_quantity = self.total_quantity * ratio
        return old_quantity, self.total_quantity

    def remove(self, quantity: Decimal) -> Decimal:
        """
        Remove shares from the pool (Disposal).
        Returns the allowable cost for the removed quantity based on the average.
        """
        if quantity <= 0:
            return Decimal("0.00")

        if self.total_quantity == 0:
            # Handling disposal with empty pool (error state effectively, or negative position)
            # In strict CGT calc, you can't sell what you don't have, but shorts might exist.
            # For this engine, we assume long-only or pre-validated data.
            # Returning 0 cost implies 100% gain, which is a safe default for "missing data".
            return Decimal("0.00")

        # Calculate average cost per share
        # Fraction: (quantity_sold / total_pool_quantity) * total_pool_cost
        # Doing it this way avoids rounding issues with "per share" price on small lots

        # Determine the cost proportion
        cost_for_qty = (quantity / self.total_quantity) * self.total_cost

        # Rounding is tricky in tax.
        # Standard practice: Round to 2DP? Or keep precision?
        # We'll keep full precision for internal calc, round at reporting if needed.
        # But `cost_for_qty` effectively becomes a realised cost.

        # Update pool state
        self.total_quantity -= quantity
        self.total_cost -= cost_for_qty

        # Handle floating point leftovers near zero
        if self.total_quantity <= Decimal("0.000001"): # Epsilon check
            self.total_quantity = Decimal("0.00")
            self.total_cost = Decimal("0.00")

        return cost_for_qty

    @property
    def average_cost_per_share(self) -> Decimal:
        if self.total_quantity == 0:
            return Decimal("0.00")
        return self.total_cost / self.total_quantity
