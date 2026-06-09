"""
GenLayer contract code analyzer.
Checks for required decorators, forbidden non-deterministic functions,
and returns a JSON summary of errors and warnings.
"""

import ast
import re
import json
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass, asdict


@dataclass
class AnalysisResult:
    """Container for analysis results."""
    contract_name: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    info: Dict[str, Any]


class GenLayerContractAnalyzer(ast.NodeVisitor):
    """Analyzer for GenLayer contract code."""
    
    # GenLayer-specific decorators
    REQUIRED_DECORATORS = {
        "genvm_callable",
        "require_deterministic",
        "contract",
    }
    
    # Non-deterministic functions that should be flagged
    FORBIDDEN_FUNCTIONS = {
        # datetime and time
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "time.localtime",
        "time.gmtime",
        "time.monotonic",
        
        # random and secrets
        "random.random",
        "random.randint",
        "random.choice",
        "random.sample",
        "random.shuffle",
        "secrets.token_hex",
        "secrets.token_bytes",
        "secrets.randbelow",
        
        # OS and system
        "os.urandom",
        "os.getpid",
        "os.getenv",
        "uuid.uuid4",
        "uuid.uuid1",
        
        # External calls
        "requests.get",
        "requests.post",
        "urllib.request.urlopen",
    }
    
    # Non-deterministic imports
    FORBIDDEN_IMPORTS = {
        "datetime",
        "time",
        "random",
        "secrets",
        "uuid",
        "os",
        "requests",
        "urllib",
    }
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.decorators_found: Set[str] = set()
        self.functions_defined: List[str] = []
        self.imports_used: List[str] = []
        self.forbidden_calls: List[Tuple[str, int]] = []
        self.current_function: str = ""
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self.functions_defined.append(node.name)
        
        # Extract decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self.decorators_found.add(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                self.decorators_found.add(decorator.attr)
        
        # Check if main contract function has required decorators
        if node.name not in ["__init__", "__name__"]:
            has_required_decorator = any(
                decorator in self.decorators_found
                for decorator in ["genvm_callable", "require_deterministic"]
            )
            if not has_required_decorator:
                self.warnings.append(
                    f"Function '{node.name}' at line {node.lineno} "
                    "missing GenLayer decorator (genvm_callable or require_deterministic)"
                )
        
        # Visit function body
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = ""
    
    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        call_name = self._get_call_name(node)
        
        if call_name:
            # Check for forbidden functions
            for forbidden in self.FORBIDDEN_FUNCTIONS:
                if call_name == forbidden or call_name.endswith("." + forbidden.split(".")[-1]):
                    self.forbidden_calls.append((call_name, node.lineno))
                    self.errors.append(
                        f"Non-deterministic function '{call_name}' called "
                        f"in '{self.current_function}' at line {node.lineno}"
                    )
        
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            self.imports_used.append(module_name)
            
            if module_name in self.FORBIDDEN_IMPORTS:
                self.warnings.append(
                    f"Potentially non-deterministic import '{module_name}' "
                    f"at line {node.lineno}"
                )
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statement."""
        if node.module:
            module_name = node.module.split(".")[0]
            self.imports_used.append(module_name)
            
            if module_name in self.FORBIDDEN_IMPORTS:
                imported_names = [alias.name for alias in node.names]
                self.warnings.append(
                    f"Potentially non-deterministic import from '{module_name}' "
                    f"({', '.join(imported_names)}) at line {node.lineno}"
                )
        
        self.generic_visit(node)
    
    @staticmethod
    def _get_call_name(node: ast.Call) -> str:
        """Extract function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


def analyze_contract_code(code: str, contract_name: str = "Contract") -> Dict[str, Any]:
    """
    Analyze GenLayer contract code for decorators and forbidden functions.
    
    Args:
        code: The contract source code as a string
        contract_name: Name of the contract being analyzed
    
    Returns:
        Dictionary with analysis results
    """
    
    result = AnalysisResult(
        contract_name=contract_name,
        is_valid=True,
        errors=[],
        warnings=[],
        info={
            "functions": [],
            "decorators": [],
            "imports": [],
            "forbidden_calls": []
        }
    )
    
    # Try to parse the code
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.is_valid = False
        result.errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return asdict(result)
    
    # Run analyzer
    analyzer = GenLayerContractAnalyzer()
    analyzer.visit(tree)
    
    # Collect results
    result.errors.extend(analyzer.errors)
    result.warnings.extend(analyzer.warnings)
    
    result.info["functions"] = analyzer.functions_defined
    result.info["decorators"] = list(analyzer.decorators_found)
    result.info["imports"] = list(set(analyzer.imports_used))
    result.info["forbidden_calls"] = [
        {"function": call, "line": line}
        for call, line in analyzer.forbidden_calls
    ]
    
    # Check for at least one decorated function
    if not analyzer.decorators_found:
        result.warnings.append(
            "No GenLayer decorators found. Contract functions should be decorated."
        )
    
    # Determine validity
    result.is_valid = len(result.errors) == 0
    
    return asdict(result)


def analyze_code_from_file(filepath: str) -> Dict[str, Any]:
    """
    Analyze a contract code file.
    
    Args:
        filepath: Path to the Python file
    
    Returns:
        Dictionary with analysis results
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        
        # Extract contract name from filename or code
        contract_name = filepath.split("/")[-1].split(".")[0]
        return analyze_contract_code(code, contract_name)
    
    except FileNotFoundError:
        return {
            "contract_name": "",
            "is_valid": False,
            "errors": [f"File not found: {filepath}"],
            "warnings": [],
            "info": {}
        }
    except IOError as e:
        return {
            "contract_name": "",
            "is_valid": False,
            "errors": [f"Error reading file: {e}"],
            "warnings": [],
            "info": {}
        }


def print_analysis_report(analysis: Dict[str, Any]) -> None:
    """
    Print a formatted analysis report.
    
    Args:
        analysis: Analysis result dictionary
    """
    print(f"\n{'='*70}")
    print(f"GenLayer Contract Analysis: {analysis['contract_name']}")
    print(f"{'='*70}")
    
    # Status
    status = "✓ VALID" if analysis["is_valid"] else "✗ INVALID"
    print(f"\nStatus: {status}")
    
    # Errors
    if analysis["errors"]:
        print(f"\n❌ ERRORS ({len(analysis['errors'])}):")
        for error in analysis["errors"]:
            print(f"   • {error}")
    else:
        print(f"\n✓ No errors found")
    
    # Warnings
    if analysis["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(analysis['warnings'])}):")
        for warning in analysis["warnings"]:
            print(f"   • {warning}")
    else:
        print(f"\n✓ No warnings")
    
    # Info
    info = analysis["info"]
    print(f"\n📋 INFO:")
    print(f"   Functions defined: {len(info.get('functions', []))}")
    if info.get("functions"):
        print(f"     → {', '.join(info['functions'])}")
    
    print(f"   Decorators found: {len(info.get('decorators', []))}")
    if info.get("decorators"):
        print(f"     → {', '.join(info['decorators'])}")
    
    print(f"   Imports: {len(info.get('imports', []))}")
    if info.get("imports"):
        print(f"     → {', '.join(info['imports'])}")
    
    if info.get("forbidden_calls"):
        print(f"   Forbidden calls: {len(info['forbidden_calls'])}")
        for call in info['forbidden_calls']:
            print(f"     → {call['function']} (line {call['line']})")


if __name__ == "__main__":
    # Example 1: Valid contract
    valid_contract = """
from genvm_decorators import genvm_callable, require_deterministic

class MyContract:
    def __init__(self):
        self.value = 0
    
    @genvm_callable
    @require_deterministic
    def set_value(self, new_value: int) -> None:
        self.value = new_value
    
    @genvm_callable
    def get_value(self) -> int:
        return self.value
"""
    
    # Example 2: Invalid contract (uses datetime)
    invalid_contract = """
import datetime
from genvm_decorators import genvm_callable

class BadContract:
    @genvm_callable
    def get_timestamp(self):
        return datetime.datetime.now()
    
    def process_data(self):
        import random
        return random.randint(1, 100)
"""
    
    # Example 3: Contract with warnings
    warning_contract = """
import os

def helper_function():
    value = 42
    return value

class PartialContract:
    def process(self):
        return helper_function()
"""
    
    print("\n" + "="*70)
    print("EXAMPLE 1: Valid GenLayer Contract")
    print("="*70)
    result1 = analyze_contract_code(valid_contract, "MyContract")
    print(json.dumps(result1, indent=2))
    print_analysis_report(result1)
    
    print("\n" + "="*70)
    print("EXAMPLE 2: Invalid Contract (Non-deterministic functions)")
    print("="*70)
    result2 = analyze_contract_code(invalid_contract, "BadContract")
    print(json.dumps(result2, indent=2))
    print_analysis_report(result2)
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Contract with Warnings (Missing decorators)")
    print("="*70)
    result3 = analyze_contract_code(warning_contract, "PartialContract")
    print(json.dumps(result3, indent=2))
    print_analysis_report(result3)
