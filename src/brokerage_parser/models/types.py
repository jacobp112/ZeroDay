from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaxWrapper(str, Enum):
    GIA = "GIA"                       # General Investment Account
    ISA = "ISA"                       # Individual Savings Account
    JISA = "JISA"                     # Junior ISA
    LISA = "LISA"                     # Lifetime ISA
    SIPP = "SIPP"                     # Self-Invested Personal Pension
    SSAS = "SSAS"                     # Small Self-Administered Scheme
    OFFSHORE_BOND = "OFFSHORE_BOND"   # Offshore investment bond
    ONSHORE_BOND = "ONSHORE_BOND"     # Onshore investment bond
    UNKNOWN = "UNKNOWN"

class CorporateActionType(str, Enum):
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    MERGER = "MERGER"
    SPIN_OFF = "SPIN_OFF"
    RETURN_OF_CAPITAL = "RETURN_OF_CAPITAL"
    SCRIP_DIVIDEND = "SCRIP_DIVIDEND"
    TENDER_OFFER = "TENDER_OFFER"
    NAME_CHANGE = "NAME_CHANGE"

class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    FEE = "FEE"
    OTHER = "OTHER"

class ExtractionMethod(str, Enum):
    NATIVE_TEXT = "native_text"
    NATIVE_TABLE = "native_table"
    OCR = "ocr"
    REGEX_FALLBACK = "regex_fallback"
    IMPLICIT_TABLE = "implicit_table"
    INFERRED = "inferred"
    VISUAL_HEURISTIC = "visual_heuristic"
    LLM_FALLBACK = "llm_fallback"
