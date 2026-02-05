import pytest
from brokerage_parser.detection import detect_broker

def test_detect_schwab():
    text = "Welcome to your Charles Schwab account statement. Visit schwab.com."
    broker, confidence = detect_broker(text)
    assert broker == "schwab"
    assert confidence == 0.9

def test_detect_fidelity():
    text = "Fidelity Investments. P.O. Box 1234. fidelity.com"
    broker, confidence = detect_broker(text)
    assert broker == "fidelity"
    assert confidence == 0.9

def test_detect_vanguard():
    text = "The Vanguard Group, Inc. Client services."
    broker, confidence = detect_broker(text)
    assert broker == "vanguard"
    assert confidence >= 0.6

def test_detect_unknown():
    text = "Some random document with no broker name."
    broker, confidence = detect_broker(text)
    assert broker == "unknown"
    assert confidence == 0.0

def test_detect_empty_or_none():
    assert detect_broker("") == ("unknown", 0.0)
    assert detect_broker(None) == ("unknown", 0.0)

def test_detect_single_keyword_confidence():
    text = "Just one mention of fidelity in here."
    broker, confidence = detect_broker(text)
    assert broker == "fidelity"
    assert confidence == 0.6
