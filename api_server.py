"""
FastAPI endpoint for analyzing GenLayer contracts.
Fetches contract source code and runs linting analysis.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uvicorn
import logging

from fetch_contract_source import fetch_contract_source
from analyze_genlayer_contract import analyze_contract_code


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GenLayer Contract Analyzer",
    description="API for analyzing GenLayer contract source code",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class ContractSourceResponse(BaseModel):
    """Response from source code fetching."""
    contract_address: str
    source_code: Optional[str] = None
    compiler_version: Optional[str] = None
    contract_name: Optional[str] = None
    abi: Optional[list] = None
    bytecode: Optional[str] = None
    method: str = Field(..., description="Method used to fetch the source")
    error: Optional[str] = None


class AnalysisErrorDetail(BaseModel):
    """Single error detail."""
    message: str
    line_number: Optional[int] = None


class AnalysisWarningDetail(BaseModel):
    """Single warning detail."""
    message: str
    line_number: Optional[int] = None


class ContractAnalysisResponse(BaseModel):
    """Response from contract analysis."""
    contract_address: str
    contract_name: str
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    info: Dict[str, Any] = Field(..., description="Additional contract information")


class FullAnalysisResponse(BaseModel):
    """Complete analysis response with source and analysis."""
    contract_address: str
    source_data: ContractSourceResponse
    analysis: ContractAnalysisResponse


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GenLayer Contract Analyzer"
    }


@app.get("/api/analyze-contract", response_model=FullAnalysisResponse, tags=["Analysis"])
async def analyze_contract(
    address: str = Query(
        ...,
        description="GenLayer contract address (0x-prefixed hex)",
        regex=r"^0x[a-fA-F0-9]{40}$",
        example="0x1234567890123456789012345678901234567890"
    ),
    rpc_endpoint: Optional[str] = Query(
        None,
        description="GenLayer JSON-RPC endpoint URL",
        example="https://rpc.genLayer.org"
    ),
    local_emulator_url: Optional[str] = Query(
        None,
        description="Local GenLayer emulator URL for fallback",
        example="http://localhost:8545"
    )
) -> FullAnalysisResponse:
    """
    Analyze a GenLayer contract by fetching its source code and running linting checks.
    
    This endpoint:
    1. Fetches the contract source code from the GenLayer RPC endpoint
    2. Runs the contract analyzer to check for:
       - Required decorators (@genvm_callable, @require_deterministic, @contract)
       - Forbidden non-deterministic functions (datetime, random, etc.)
       - Missing imports or syntax errors
    3. Returns a comprehensive analysis as JSON
    
    Args:
        address: The contract address to analyze (must be 0x-prefixed)
        rpc_endpoint: Optional GenLayer RPC endpoint (defaults to public endpoint)
        local_emulator_url: Optional local emulator URL for fallback
    
    Returns:
        FullAnalysisResponse with source data and analysis results
    
    Raises:
        HTTPException: If contract address is invalid or analysis fails
    """
    
    logger.info(f"Analyzing contract: {address}")
    
    try:
        # Fetch contract source code
        logger.info(f"Fetching source code for {address}")
        source_data = fetch_contract_source(
            contract_address=address,
            rpc_endpoint=rpc_endpoint,
            local_emulator_url=local_emulator_url,
            timeout=10
        )
        
        # Check if source code was retrieved
        if "error" in source_data:
            logger.warning(f"Could not fetch source for {address}: {source_data['error']}")
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch source code for contract {address}. "
                       f"The endpoint may not be public yet or the contract doesn't exist."
            )
        
        # Extract source code for analysis
        source_code = source_data.get("source_code")
        if not source_code:
            logger.warning(f"No source code returned for {address}")
            raise HTTPException(
                status_code=404,
                detail=f"No source code available for contract {address}. "
                       f"Retrieved data: {source_data}"
            )
        
        # Run contract analysis
        logger.info(f"Running analysis on contract code for {address}")
        analysis = analyze_contract_code(
            code=source_code,
            contract_name=source_data.get("contract_name", "Unknown")
        )
        
        # Prepare source response
        source_response = ContractSourceResponse(
            contract_address=address,
            source_code=source_code if len(source_code) < 50000 else source_code[:50000] + "...",
            compiler_version=source_data.get("compiler_version"),
            contract_name=source_data.get("contract_name"),
            abi=source_data.get("abi"),
            bytecode=source_data.get("bytecode"),
            method=source_data.get("method", "unknown"),
            error=source_data.get("error")
        )
        
        # Prepare analysis response
        analysis_response = ContractAnalysisResponse(
            contract_address=address,
            contract_name=analysis["contract_name"],
            is_valid=analysis["is_valid"],
            errors=analysis["errors"],
            warnings=analysis["warnings"],
            info=analysis["info"]
        )
        
        logger.info(
            f"Analysis complete for {address}: "
            f"valid={analysis['is_valid']}, "
            f"errors={len(analysis['errors'])}, "
            f"warnings={len(analysis['warnings'])}"
        )
        
        return FullAnalysisResponse(
            contract_address=address,
            source_data=source_response,
            analysis=analysis_response
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing contract {address}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/analyze-contract/schema", tags=["Documentation"])
async def analysis_schema():
    """Get the schema for analysis results."""
    return {
        "description": "Contract analysis endpoint schema",
        "endpoints": {
            "GET /api/analyze-contract": {
                "description": "Analyze a GenLayer contract by address",
                "parameters": {
                    "address": "0x-prefixed contract address (required)",
                    "rpc_endpoint": "GenLayer JSON-RPC endpoint URL (optional)",
                    "local_emulator_url": "Local emulator URL for fallback (optional)"
                }
            }
        },
        "analysis_fields": {
            "is_valid": "Whether the contract is valid (no errors)",
            "errors": "List of critical errors found",
            "warnings": "List of warnings",
            "info": {
                "functions": "Functions defined in the contract",
                "decorators": "GenLayer decorators found",
                "imports": "Imported modules",
                "forbidden_calls": "Non-deterministic function calls detected"
            }
        }
    }


@app.post("/api/analyze-code", response_model=ContractAnalysisResponse, tags=["Analysis"])
async def analyze_code_direct(
    code: str = Query(..., description="Python contract code to analyze"),
    contract_name: Optional[str] = Query(
        "DirectAnalysis",
        description="Name for the contract being analyzed"
    )
) -> ContractAnalysisResponse:
    """
    Analyze contract code directly without fetching from chain.
    
    Args:
        code: The Python contract code to analyze
        contract_name: Optional name for the contract
    
    Returns:
        ContractAnalysisResponse with analysis results
    """
    
    logger.info(f"Direct code analysis for {contract_name}")
    
    try:
        analysis = analyze_contract_code(code=code, contract_name=contract_name)
        
        return ContractAnalysisResponse(
            contract_address="N/A (direct analysis)",
            contract_name=analysis["contract_name"],
            is_valid=analysis["is_valid"],
            errors=analysis["errors"],
            warnings=analysis["warnings"],
            info=analysis["info"]
        )
    
    except Exception as e:
        logger.error(f"Error analyzing code: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error analyzing code: {str(e)}"
        )


@app.get("/", tags=["Documentation"])
async def root():
    """API documentation."""
    return {
        "service": "GenLayer Contract Analyzer API",
        "version": "1.0.0",
        "description": "Fetch and analyze GenLayer contract source code",
        "endpoints": {
            "health": "GET /health - Health check",
            "analyze_contract": "GET /api/analyze-contract?address=0x... - Fetch and analyze contract",
            "analyze_code": "POST /api/analyze-code - Analyze contract code directly",
            "schema": "GET /api/analyze-contract/schema - Get API schema",
            "docs": "GET /docs - Swagger UI documentation",
            "redoc": "GET /redoc - ReDoc documentation"
        },
        "example_requests": {
            "fetch_and_analyze": "/api/analyze-contract?address=0x1234567890123456789012345678901234567890",
            "with_custom_rpc": "/api/analyze-contract?address=0x...&rpc_endpoint=https://rpc.genLayer.org",
            "with_local_emulator": "/api/analyze-contract?address=0x...&local_emulator_url=http://localhost:8545"
        }
    }


if __name__ == "__main__":
    print("Starting GenLayer Contract Analyzer API...")
    print("Available at http://localhost:8000")
    print("Swagger UI: http://localhost:8000/docs")
    print("ReDoc: http://localhost:8000/redoc")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
