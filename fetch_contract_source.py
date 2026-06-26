"""
Fetch deployed contract source code from GenLayer JSON-RPC endpoint.
Supports fallback to local emulator or alternative RPC methods.
"""

import requests
from typing import Optional, Dict, Any
import json


def fetch_contract_source(
    contract_address: str,
    rpc_endpoint: Optional[str] = None,
    local_emulator_url: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Fetch contract source code from GenLayer JSON-RPC endpoint.
    
    Args:
        contract_address: The contract address to fetch source code for (0x-prefixed)
        rpc_endpoint: GenLayer JSON-RPC endpoint URL (defaults to public endpoint)
        local_emulator_url: Local emulator URL for fallback (e.g., http://localhost:8545)
        timeout: Request timeout in seconds
    
    Returns:
        Dict containing 'source_code', 'compiler_version', 'contract_name', etc.
        Returns empty dict if source code cannot be fetched.
    
    Raises:
        ValueError: If contract address is invalid
        requests.RequestException: If network request fails
    """
    
    # Validate contract address
    if not contract_address.startswith("0x") or len(contract_address) != 42:
        raise ValueError(f"Invalid contract address: {contract_address}")
    
    # Default to GenLayer Studio Network endpoint
    if rpc_endpoint is None:
        rpc_endpoint = "https://studio.genlayer.com/api"
    
    # Try GenLayer custom RPC method first
    try:
        result = _fetch_via_genlayer_rpc(contract_address, rpc_endpoint, timeout)
        if result:
            return result
    except requests.RequestException as e:
        print(f"GenLayer RPC endpoint failed: {e}")
    
    # Fallback to local emulator
    if local_emulator_url:
        try:
            result = _fetch_via_local_emulator(contract_address, local_emulator_url, timeout)
            if result:
                return result
        except requests.RequestException as e:
            print(f"Local emulator failed: {e}")
    
    # Fallback to standard RPC methods (fetch bytecode and metadata)
    try:
        result = _fetch_via_standard_rpc(contract_address, rpc_endpoint, timeout)
        if result:
            return result
    except requests.RequestException as e:
        print(f"Standard RPC method failed: {e}")
    
    return {"error": "Could not fetch contract source code"}


def _fetch_via_genlayer_rpc(
    contract_address: str, rpc_endpoint: str, timeout: int
) -> Optional[Dict[str, Any]]:
    """
    Attempt to fetch contract source via GenLayer's custom RPC method.
    GenLayer uses 'gen_getContractCode' which returns base64 encoded source.
    """
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "gen_getContractCode",
        "params": [contract_address]
    }
    
    try:
        response = requests.post(
            rpc_endpoint,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            print(f"RPC Error: {data['error']}")
            return None
        
        if "result" in data and data["result"]:
            import base64
            encoded_code = data["result"]
            try:
                decoded_code = base64.b64decode(encoded_code).decode('utf-8')
            except Exception as decode_err:
                print(f"Failed to decode base64 contract code: {decode_err}")
                decoded_code = encoded_code # Fallback to raw if not actually base64
                
            return {
                "source_code": decoded_code,
                "compiler_version": "genvm",
                "contract_name": f"Contract_{contract_address[:8]}",
                "abi": [],
                "method": "gen_getContractCode"
            }
    
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Failed to fetch via GenLayer RPC: {e}")
    
    return None


def _fetch_via_local_emulator(
    contract_address: str, emulator_url: str, timeout: int
) -> Optional[Dict[str, Any]]:
    """
    Attempt to fetch contract source from GenLayer local emulator.
    Local emulator may store source code in contract storage or state.
    """
    headers = {"Content-Type": "application/json"}
    
    # Try custom local emulator method
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "gen_getContractSource",
        "params": [contract_address]
    }
    
    try:
        response = requests.post(
            emulator_url,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "result" in data and data["result"]:
            return {
                "source_code": data["result"].get("source_code", ""),
                "compiler_version": data["result"].get("compiler_version", ""),
                "contract_name": data["result"].get("contract_name", ""),
                "abi": data["result"].get("abi", []),
                "method": "local_emulator"
            }
    
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Failed to fetch via local emulator: {e}")
    
    return None


def _fetch_via_standard_rpc(
    contract_address: str, rpc_endpoint: str, timeout: int
) -> Optional[Dict[str, Any]]:
    """
    Fallback: Fetch contract bytecode and attempt to extract metadata.
    This won't get the source code directly but can retrieve bytecode and metadata.
    """
    headers = {"Content-Type": "application/json"}
    
    # Fetch bytecode using standard eth_getCode RPC method
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getCode",
        "params": [contract_address, "latest"]
    }
    
    try:
        response = requests.post(
            rpc_endpoint,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "result" in data and data["result"] and data["result"] != "0x":
            bytecode = data["result"]
            
            # Extract metadata hash from bytecode (last 43 bytes for IPFS hash)
            # Solidity appends metadata CBOR encoding at the end
            metadata_hash = _extract_metadata_hash(bytecode)
            
            return {
                "bytecode": bytecode,
                "bytecode_length": len(bytecode) // 2,
                "metadata_hash": metadata_hash,
                "method": "eth_getCode",
                "note": "Source code not available; bytecode retrieved. Use metadata_hash to fetch from IPFS if needed."
            }
        else:
            return {"error": "Contract not found or has empty bytecode"}
    
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Failed to fetch via standard RPC: {e}")
    
    return None


def _extract_metadata_hash(bytecode: str) -> Optional[str]:
    """
    Extract IPFS metadata hash from contract bytecode.
    Solidity stores metadata hash in CBOR format at the end of bytecode.
    """
    if not bytecode.startswith("0x"):
        return None
    
    try:
        # Remove '0x' prefix and convert to bytes
        bytecode_hex = bytecode[2:]
        
        # Metadata hash is typically the last 43 hex chars (IPFS CIDv0 hash)
        # Look for CBOR encoding markers
        if len(bytecode_hex) >= 86:
            # Extract last 43 bytes (86 hex chars)
            metadata_section = bytecode_hex[-86:]
            return f"0x{metadata_section}"
    except Exception as e:
        print(f"Failed to extract metadata hash: {e}")
    
    return None


if __name__ == "__main__":
    # Example usage
    contract_address = "0x1234567890123456789012345678901234567890"
    
    # Try with default GenLayer endpoint
    result = fetch_contract_source(
        contract_address,
        rpc_endpoint="https://studio.genlayer.com/api"
    )
    
    print("Contract Source Code Fetch Result:")
    print(json.dumps(result, indent=2))
    
    # Example with local emulator fallback
    result_with_fallback = fetch_contract_source(
        contract_address,
        rpc_endpoint="https://studio.genlayer.com/api",
        local_emulator_url="http://localhost:8545"
    )
    
    print("\nWith Local Emulator Fallback:")
    print(json.dumps(result_with_fallback, indent=2))
