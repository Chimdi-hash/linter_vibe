"""
LinterVibe Backend - GenLayer Contract Analyzer
Connects directly with GenLayer CLI for actual network reading and linting.
"""

import subprocess
import tempfile
import json
import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="LinterVibe Backend",
    description="GenLayer contract code quality analyzer",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (can be restricted to specific domains)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class AnalysisResponse(BaseModel):
    """Response model for contract analysis."""
    status: str = Field(..., description="'success' or 'error'")
    address: str = Field(..., description="The contract address analyzed")
    errors: list[str] = Field(default_factory=list, description="Critical errors found")
    warnings: list[str] = Field(default_factory=list, description="Warnings/suggestions")
    raw_code_snippet: Optional[str] = Field(
        None,
        description="First 1000 characters of contract code"
    )
    message: Optional[str] = Field(None, description="Error message if status is 'error'")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "LinterVibe Backend",
        "available_commands": {
            "genlayer_code": _check_command_available("genlayer"),
            "genvm_lint": _check_command_available("genvm-lint")
        }
    }


@app.get("/api/analyze-contract", response_model=AnalysisResponse)
async def analyze_contract(
    address: str = Query(
        ...,
        description="GenLayer contract address (0x-prefixed hex)",
        regex=r"^0x[a-fA-F0-9]{40}$",
        example="0x1234567890123456789012345678901234567890"
    )
) -> AnalysisResponse:
    """
    Analyze a GenLayer contract by fetching live code and running linting.
    
    This endpoint:
    1. Runs 'genlayer code <address>' to fetch the contract from the network
    2. Writes the code to a temporary file
    3. Runs 'genvm-lint check <file> --json' to analyze the code
    4. Returns structured JSON with errors, warnings, and code snippet
    
    Args:
        address: The contract address to analyze (must be 0x-prefixed)
    
    Returns:
        AnalysisResponse with status, errors, warnings, and code snippet
    """
    
    logger.info(f"Analyzing contract: {address}")
    
    try:
        # Step 1: Fetch contract code from GenLayer network
        logger.info(f"Fetching code for {address} from GenLayer network...")
        code = _fetch_contract_code(address)
        
        if not code:
            logger.warning(f"No code returned for {address}")
            return AnalysisResponse(
                status="error",
                address=address,
                message="Contract not found on GenLayer network or code is empty."
            )
        
        logger.info(f"Successfully fetched {len(code)} bytes for {address}")
        
        # Step 2: Run linting on the code
        logger.info(f"Running genvm-lint on {address}...")
        errors, warnings = _lint_contract_code(code)
        
        logger.info(
            f"Analysis complete for {address}: "
            f"errors={len(errors)}, warnings={len(warnings)}"
        )
        
        # Step 3: Prepare response
        code_snippet = code[:1000] + "..." if len(code) > 1000 else code
        
        return AnalysisResponse(
            status="success",
            address=address,
            errors=errors,
            warnings=warnings,
            raw_code_snippet=code_snippet
        )
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess error for {address}: {e}")
        error_message = f"GenLayer CLI error: {e.stderr or e.stdout or str(e)}"
        return AnalysisResponse(
            status="error",
            address=address,
            message=error_message
        )
    
    except Exception as e:
        logger.error(f"Unexpected error for {address}: {str(e)}", exc_info=True)
        return AnalysisResponse(
            status="error",
            address=address,
            message=f"Internal server error: {str(e)}"
        )


@app.post("/api/analyze-contract") # FIXED
async def analyze_contract_post(
    address: str = Query(
        ...,
        description="GenLayer contract address (0x-prefixed hex)",
        regex=r"^0x[a-fA-F0-9]{40}$",
        example="0x1234567890123456789012345678901234567890"
    )
) -> AnalysisResponse:
    """POST endpoint for contract analysis (delegates to GET handler)."""
    return await analyze_contract(address)


@app.get("/")
async def root():
    """API documentation."""
    return {
        "service": "LinterVibe Backend",
        "version": "1.0.0",
        "description": "GenLayer contract code quality analyzer with live network reading",
        "endpoints": {
            "health": "GET /health - Health check",
            "analyze": "GET /api/analyze-contract?address=0x... - Analyze contract",
            "docs": "GET /docs - Swagger UI documentation"
        },
        "requirements": {
            "genlayer_cli": "GenLayer CLI must be installed",
            "genvm_lint": "genvm-lint must be installed"
        },
        "example_request": "/api/analyze-contract?address=0x1234567890123456789012345678901234567890"
    }


def _check_command_available(command: str) -> bool:
    """Check if a command is available in the system."""
    try:
        subprocess.run(
            ["which" if os.name != "nt" else "where", command],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _fetch_contract_code(address: str) -> Optional[str]:
    """
    Fetch contract code using 'genlayer code <address>' CLI command.
    
    Args:
        address: The contract address to fetch
    
    Returns:
        The contract source code as a string, or None if fetch fails
    
    Raises:
        subprocess.CalledProcessError: If the CLI command fails
    """
    
    try:
        logger.debug(f"Running: genlayer code {address}")
        
        result = subprocess.run(
            ["genlayer", "code", address],
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        
        code = result.stdout.strip()
        
        if not code:
            logger.warning(f"genlayer code returned empty output for {address}")
            return None
        
        return code
    
    except subprocess.TimeoutExpired:
        logger.error(f"genlayer code command timed out for {address}")
        raise RuntimeError("GenLayer CLI command timed out")
    
    except FileNotFoundError:
        logger.error("genlayer CLI not found. Please install GenLayer CLI.")
        raise RuntimeError(
            "GenLayer CLI not found. Install with: pip install genlayer"
        )
    
    except subprocess.CalledProcessError as e:
        logger.error(
            f"genlayer code failed for {address}: {e.stderr or e.stdout}"
        )
        if "not found" in (e.stderr or "").lower():
            raise RuntimeError("Contract not found on GenLayer network")
        raise


def _lint_contract_code(code: str) -> tuple[list[str], list[str]]:
    """
    Lint contract code using 'genvm-lint check <file> --json' CLI command.
    
    Args:
        code: The contract source code to lint
    
    Returns:
        Tuple of (errors, warnings) lists
    
    Raises:
        subprocess.CalledProcessError: If the CLI command fails critically
    """
    
    errors = []
    warnings = []
    
    # Write code to temporary file
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        
        logger.debug(f"Wrote code to temporary file: {tmp_path}")
    
    except IOError as e:
        logger.error(f"Failed to create temporary file: {e}")
        raise RuntimeError(f"Failed to create temporary file: {e}")
    
    try:
        # Run genvm-lint
        logger.debug(f"Running: genvm-lint check {tmp_path} --json")
        
        result = subprocess.run(
            ["genvm-lint", "check", tmp_path, "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse JSON output
        if result.stdout.strip():
            try:
                lint_output = json.loads(result.stdout)
                
                # Extract errors and warnings from JSON
                if isinstance(lint_output, dict):
                    errors = lint_output.get("errors", [])
                    warnings = lint_output.get("warnings", [])
                
                elif isinstance(lint_output, list):
                    for item in lint_output:
                        if isinstance(item, dict):
                            if item.get("level") == "error":
                                errors.append(item.get("message", "Unknown error"))
                            elif item.get("level") in ["warning", "info"]:
                                warnings.append(item.get("message", "Unknown warning"))
                
                logger.debug(
                    f"Parsed lint output: {len(errors)} errors, {len(warnings)} warnings"
                )
            
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse genvm-lint JSON output: {e}")
                # Try to extract meaningful information from stderr
                if result.stderr:
                    warnings.append(f"Lint output parse error: {result.stderr[:200]}")
        
        # If the command exited with non-zero, still try to extract errors
        if result.returncode != 0 and result.stderr:
            logger.info(f"genvm-lint returned code {result.returncode}")
            stderr_lines = result.stderr.strip().split('\n')
            for line in stderr_lines[-5:]:  # Last 5 lines
                if line.strip():
                    errors.append(line.strip())
        
        return errors, warnings
    
    except subprocess.TimeoutExpired:
        logger.error("genvm-lint command timed out")
        errors.append("Linting timed out - code may be too large or complex")
        return errors, warnings
    
    except FileNotFoundError:
        logger.error("genvm-lint CLI not found")
        warnings.append(
            "genvm-lint not found. Install with: pip install genvm-lint"
        )
        return [], warnings
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug(f"Cleaned up temporary file: {tmp_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file: {e}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("LinterVibe Backend - GenLayer Contract Analyzer")
    print("="*70)
    print("\nStarting server at http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nRequirements:")
    print("  - GenLayer CLI: pip install genlayer")
    print("  - genvm-lint: pip install genvm-lint")
    print("\nExample request:")
    print("  curl 'http://localhost:8000/api/analyze-contract?address=0x...'")
    print("\n" + "="*70 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
