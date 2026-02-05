from typing import Tuple, Optional

def detect_broker(text: Optional[str]) -> Tuple[str, float]:
    """
    Detects the broker from extracted PDF text based on keywords.

    Analyses the first 1000 characters of the text for broker-specific keywords.
    Returns the broker name and a confidence score.

    Brokers supported:
    - Schwab ("schwab", "charles schwab", "schwab.com")
    - Fidelity ("fidelity", "fidelity investments", "fidelity.com")
    - Vanguard ("vanguard", "the vanguard group")

    Args:
        text: Combined text from all pages (or just first page).

    Returns:
        tuple[str, float]: (broker_name, confidence_score)
        - broker_name: "schwab" | "fidelity" | "vanguard" | "unknown"
        - confidence_score: 0.0 to 1.0
    """
    if not text:
        return "unknown", 0.0

    text_lower = text.lower()[:1000] # Normalize and check header

    keywords = {
        "schwab": ["schwab", "charles schwab", "schwab.com"],
        "fidelity": ["fidelity", "fidelity investments", "fidelity.com"],
        "vanguard": ["vanguard", "the vanguard group"]
    }

    best_broker = "unknown"
    max_matches = 0

    for broker, keys in keywords.items():
        matches = sum(1 for key in keys if key in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_broker = broker

    if max_matches == 0:
        return "unknown", 0.0
    elif max_matches == 1:
        return best_broker, 0.6
    else:
        return best_broker, 0.9
