"""
ParseFin Enterprise API

REST API wrapper for the brokerage statement parser orchestrator.
Provides enterprise clients with a simple endpoint to POST a PDF
and receive a structured JSON report.
"""
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status, Query
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from brokerage_parser import orchestrator, storage
from brokerage_parser.reporting.models import ClientReport

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Response Models for OpenAPI Documentation
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., example="healthy", description="Service health status")
    service: str = Field(..., example="ParseFin Enterprise API", description="Service name")


class ErrorDetail(BaseModel):
    """Error response detail model."""
    error: str = Field(..., example="validation_error", description="Error type identifier")
    message: str = Field(..., example="Invalid content type: text/plain. Expected application/pdf", description="Human-readable error message")


class PortfolioSummaryResponse(BaseModel):
    """Portfolio summary in the report."""
    total_value_gbp: str = Field(..., example="125000.00", description="Total portfolio value in GBP")
    cash_value_gbp: str = Field(..., example="5000.00", description="Cash balance in GBP")
    investments_value_gbp: str = Field(..., example="120000.00", description="Total investments value in GBP")
    currency: str = Field(default="GBP", example="GBP", description="Base currency")


class MetadataResponse(BaseModel):
    """Client metadata in the report."""
    client_name: str = Field(..., example="John Smith", description="Client name")
    report_date: str = Field(..., example="2024-01-31", description="Report generation date")
    broker_name: str = Field(..., example="Charles Schwab", description="Detected broker name")
    account_number: Optional[str] = Field(None, example="1234-5678", description="Account number")


class HoldingResponse(BaseModel):
    """Individual holding/position in the portfolio."""
    symbol: str = Field(..., example="AAPL", description="Ticker symbol")
    description: str = Field(..., example="Apple Inc.", description="Security description")
    quantity: str = Field(..., example="100.00", description="Number of shares/units")
    price: str = Field(..., example="185.50", description="Current price per share")
    market_value: str = Field(..., example="18550.00", description="Total market value")
    currency: str = Field(default="GBP", example="USD", description="Currency of the holding")


class ClientReportResponse(BaseModel):
    """Complete client report response."""
    metadata: MetadataResponse = Field(..., description="Client and report metadata")
    portfolio_summary: PortfolioSummaryResponse = Field(..., description="Portfolio value summary")
    holdings: List[HoldingResponse] = Field(..., description="List of portfolio holdings")

    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "client_name": "John Smith",
                    "report_date": "2024-01-31",
                    "broker_name": "Charles Schwab",
                    "account_number": "1234-5678"
                },
                "portfolio_summary": {
                    "total_value_gbp": "125000.00",
                    "cash_value_gbp": "5000.00",
                    "investments_value_gbp": "120000.00",
                    "currency": "GBP"
                },
                "holdings": [
                    {
                        "symbol": "AAPL",
                        "description": "Apple Inc.",
                        "quantity": "100.00",
                        "price": "185.50",
                        "market_value": "18550.00",
                        "currency": "USD"
                    }
                ]
            }
        }


# =============================================================================
# API Tags for Grouping Endpoints
# =============================================================================

tags_metadata = [
    {
        "name": "Parsing",
        "description": "Core parsing endpoints. Upload brokerage statement PDFs and receive structured JSON reports with transaction data, holdings, and tax calculations.",
    },
    {
        "name": "System",
        "description": "System endpoints for health checks, monitoring, and load balancer integration.",
    },
]


# =============================================================================
# FastAPI Application
# =============================================================================

DESCRIPTION = """
## Overview

ParseFin Enterprise API provides programmatic access to brokerage statement parsing capabilities.
Upload a PDF statement and receive a comprehensive structured JSON report suitable for integration
with wealth management platforms, portfolio analytics systems, and tax reporting workflows.

## Capabilities

| Capability | Description |
|------------|-------------|
| **Broker Detection** | Automatically identifies the source broker from statement content |
| **Transaction Extraction** | Parses buys, sells, dividends, interest, fees, and transfers |
| **Holdings Analysis** | Extracts current positions with quantities and market values |
| **Tax Calculations** | UK Capital Gains Tax calculations with HMRC-compliant Section 104 pooling |
| **Data Validation** | Integrity checks with detailed warnings for data discrepancies |

## Supported Brokers

- Charles Schwab
- Fidelity Investments
- Vanguard
- Interactive Brokers
- Generic table-based statements

## Quick Start

```bash
curl -X POST "https://api.parsefin.io/v1/parse" \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@statement.pdf"
```

---

*Designed for UK Wealth Managers | HMRC CGT Compliant*
"""

app = FastAPI(
    title="ParseFin Enterprise API",
    description=DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "ParseFin Support",
        "url": "https://parsefin.io/support",
        "email": "api-support@parsefin.io",
    },
    license_info={
        "name": "Enterprise License",
        "url": "https://parsefin.io/license",
    },
    terms_of_service="https://parsefin.io/terms",
)

# CORS Configuration
origins = [
    "http://localhost:5173",  # Vite default
    "http://localhost:3000",  # React default
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_value(value: Any) -> Any:
    """
    Recursively serialize a value to JSON-compatible types.

    Handles:
    - Decimal -> str (to preserve precision)
    - date -> ISO format string
    - Enum -> value
    - dataclass -> dict
    - list/dict -> recursive serialization
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return serialize_report(value)
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    return value


def serialize_report(report: Any) -> Dict[str, Any]:
    """
    Convert a dataclass (ClientReport or nested dataclasses) to a
    JSON-serializable dictionary.

    Args:
        report: A dataclass instance to serialize.

    Returns:
        A dictionary with all values converted to JSON-compatible types.
    """
    if not is_dataclass(report) or isinstance(report, type):
        return serialize_value(report)

    result = {}
    for key, value in asdict(report).items():
        result[key] = serialize_value(value)
    return result


@app.get(
    "/health",
    tags=["System"],
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API service is running and healthy. Use this endpoint for load balancer health checks and monitoring systems.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy", "service": "ParseFin Enterprise API"}
                }
            }
        }
    }
)
async def health_check():
    """
    ## Health Check Endpoint

    Returns the current health status of the ParseFin Enterprise API.

    **Use Cases:**
    - Load balancer health probes
    - Kubernetes liveness/readiness checks
    - Monitoring and alerting systems
    """
    return HealthResponse(status="healthy", service="ParseFin Enterprise API")


@app.post(
    "/v1/parse",
    tags=["Parsing"],
    response_class=JSONResponse,
    summary="Parse Brokerage Statement",
    description="Upload a brokerage statement PDF and receive a comprehensive structured JSON report.",
    responses={
        200: {
            "description": "Successfully parsed statement",
            "content": {
                "application/json": {
                    "example": {
                        "metadata": {
                            "client_name": "John Smith",
                            "report_date": "2024-01-31",
                            "broker_name": "Charles Schwab",
                            "account_number": "1234-5678"
                        },
                        "portfolio_summary": {
                            "total_value_gbp": "125000.00",
                            "cash_value_gbp": "5000.00",
                            "investments_value_gbp": "120000.00"
                        },
                        "holdings": [
                            {"symbol": "AAPL", "quantity": "100", "market_value": "18550.00"}
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Bad Request - Invalid file type or corrupt PDF",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_content_type": {
                            "summary": "Wrong file type",
                            "value": {
                                "detail": {
                                    "error": "invalid_content_type",
                                    "message": "Invalid content type: text/plain. Expected application/pdf"
                                }
                            }
                        },
                        "validation_error": {
                            "summary": "PDF validation failed",
                            "value": {
                                "detail": {
                                    "error": "validation_error",
                                    "message": "File not found or empty"
                                }
                            }
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error - Processing failure",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": "processing_error",
                            "message": "An error occurred while processing the statement"
                        }
                    }
                }
            }
        }
    }
)
async def parse_statement(
    file: UploadFile = File(..., description="PDF brokerage statement to parse"),
    include_sources: bool = Query(False, description="Include source lineage data (bounding boxes) in the response")
):
    """
    ## Parse Brokerage Statement

    Upload a PDF brokerage statement and receive a comprehensive JSON report.

    ### Supported Brokers
    - **Charles Schwab** - Monthly/quarterly statements
    - **Fidelity** - Account statements
    - **Vanguard** - Investment reports
    - **Interactive Brokers** - Activity statements
    - **Generic** - Any table-based statement

    ### What You Get Back

    | Section | Contents |
    |---------|----------|
    | **Metadata** | Broker name, account number, statement dates |
    | **Portfolio Summary** | Total value, cash, investments in GBP |
    | **Holdings** | All positions with quantities and values |
    | **Transactions** | Buys, sells, dividends, fees, transfers |
    | **Tax Pack** | UK CGT calculations (for GIA accounts) |

    ### Example Request

    ```bash
    curl -X POST "http://localhost:8000/v1/parse" \\
      -F "file=@my_statement.pdf"
    ```
    """
    # 1. Validate content-type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_content_type",
                "message": f"Invalid content type: {file.content_type}. Expected application/pdf",
                "expected": "application/pdf",
                "received": file.content_type,
            }
        )

    temp_path = None
    try:
        # 2. Create thread-safe temporary file
        # Using NamedTemporaryFile with delete=False for thread safety:
        # - Each request gets a unique filename (uses os.urandom())
        # - Atomic OS-level file creation prevents race conditions
        # - We close the handle before passing to PyMuPDF, then clean up in finally
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".pdf",
            delete=False  # We'll clean up manually in finally block
        ) as temp_file:
            temp_path = temp_file.name
            # Stream file contents to temp file (avoids loading entire file into RAM)
            shutil.copyfileobj(file.file, temp_file)

        logger.info(f"Processing uploaded file: {file.filename} -> {temp_path}")

        # 3. Process the statement using the orchestrator (with optional source tracking)
        report: ClientReport = orchestrator.process_statement(temp_path, include_sources=include_sources)

        # 4. Store the document for later retrieval (if successful parse)
        # We re-read the temp file to calculate ID and store
        file_id = storage.store_document(Path(temp_path))
        logger.info(f"Stored document with ID: {file_id}")

        # 5. Serialize and return the report
        serialized = serialize_report(report)
        # Inject document ID into metadata for frontend retrieval
        if "metadata" in serialized and isinstance(serialized["metadata"], dict):
            serialized["metadata"]["document_id"] = file_id

        return JSONResponse(
            content=serialized,
            status_code=200,
        )

    except ValueError as e:
        # File not found, empty, validation errors, or parse errors
        logger.warning(f"Validation error processing {file.filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(e),
            }
        )
    except Exception as e:
        # Unexpected errors during processing
        logger.exception(f"Error processing statement: {file.filename}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": f"An error occurred while processing the statement: {str(e)}",
            }
        )
    finally:
        # 5. Clean up temporary file (guaranteed execution)
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except OSError as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")


@app.get(
    "/v1/documents/{doc_id}/content",
    tags=["Parsing"],
    summary="Get Document Content",
    description="Retrieve the original PDF content for a processed document.",
    responses={
        200: {
            "description": "PDF file content",
            "content": {"application/pdf": {}}
        },
        404: {"description": "Document not found"}
    }
)
async def get_document_content(doc_id: str):
    """
    Retrieve the raw PDF content for a given document ID.
    Used by the frontend to display the original statement.
    """
    path = storage.get_document_path(doc_id)
    if not path:
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(path, media_type="application/pdf", filename=f"{doc_id}.pdf")
