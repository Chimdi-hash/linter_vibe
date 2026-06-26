# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import ast
import json
import re
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass, asdict
from genlayer import *


@dataclass
class AnalysisResult:
    """Container for analysis results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    info: Dict[str, Any]


class GenLayerContractAnalyzer(ast.NodeVisitor):
    """Analyzer for GenLayer contract code."""
    
    REQUIRED_DECORATORS = {"genvm_callable", "require_deterministic", "contract"}
    
    FORBIDDEN_FUNCTIONS = {
        "datetime.now", "datetime.utcnow", "time.time", "time.localtime",
        "time.gmtime", "time.monotonic", "random.random", "random.randint",
        "random.choice", "random.sample", "random.shuffle", "secrets.token_hex",
        "secrets.token_bytes", "secrets.randbelow", "os.urandom", "os.getpid",
        "os.getenv", "uuid.uuid4", "uuid.uuid1", "requests.get", "requests.post",
        "urllib.request.urlopen"
    }
    
    FORBIDDEN_IMPORTS = {
        "datetime", "time", "random", "secrets", "uuid", "os", "requests", "urllib"
    }
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.decorators_found = set()
        self.functions_defined = []
        self.imports_used = []
        self.forbidden_calls = []
        self.current_function = ""
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions_defined.append(node.name)
        
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self.decorators_found.add(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                self.decorators_found.add(decorator.attr)
        
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
        
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = ""
    
    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._get_call_name(node)
        
        if call_name:
            for forbidden in self.FORBIDDEN_FUNCTIONS:
                if call_name == forbidden or call_name.endswith("." + forbidden.split(".")[-1]):
                    self.forbidden_calls.append((call_name, node.lineno))
                    self.errors.append(
                        f"Non-deterministic function '{call_name}' called "
                        f"in '{self.current_function}' at line {node.lineno}"
                    )
        
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            self.imports_used.append(module_name)
            if module_name in self.FORBIDDEN_IMPORTS:
                self.warnings.append(f"Potentially non-deterministic import '{module_name}' at line {node.lineno}")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module_name = node.module.split(".")[0]
            self.imports_used.append(module_name)
            if module_name in self.FORBIDDEN_IMPORTS:
                imported_names = [alias.name for alias in node.names]
                self.warnings.append(f"Potentially non-deterministic import from '{module_name}' ({', '.join(imported_names)}) at line {node.lineno}")
        self.generic_visit(node)
    
    @staticmethod
    def _get_call_name(node: ast.Call) -> str:
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


def analyze_contract_code(code: str) -> Dict[str, Any]:
    result = AnalysisResult(
        is_valid=True,
        errors=[],
        warnings=[],
        info={"functions": [], "decorators": [], "imports": [], "forbidden_calls": []}
    )
    
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.is_valid = False
        result.errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return asdict(result)
    
    analyzer = GenLayerContractAnalyzer()
    analyzer.visit(tree)
    
    result.errors.extend(analyzer.errors)
    result.warnings.extend(analyzer.warnings)
    result.info["functions"] = analyzer.functions_defined
    result.info["decorators"] = list(analyzer.decorators_found)
    result.info["imports"] = list(set(analyzer.imports_used))
    result.info["forbidden_calls"] = [{"function": call, "line": line} for call, line in analyzer.forbidden_calls]
    
    if not analyzer.decorators_found:
        result.warnings.append("No GenLayer decorators found. Contract functions should be decorated.")
    
    result.is_valid = len(result.errors) == 0
    return asdict(result)


class LinterVibeContract(gl.Contract):
    """
    Intelligent Contract for LinterVibe.
    Fetches another contract's source code and analyzes it deterministically.
    """
    
    analyses: TreeMap[str, str]

    def __init__(self):
        self.analyses = TreeMap()
        
    @gl.public.write
    def perform_vibe_check(self, target_address: str) -> str:
        """
        Uses an eq_principle block to fetch the source code from GenLayer RPC.
        Then analyzes the code deterministically and stores the result.
        """
        
        # Non-deterministic fetcher function
        def fetch_code() -> str:
            import urllib.request
            import json
            import base64
            
            url = "https://studio.genlayer.com/api"
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "gen_getContractCode",
                "params": [target_address]
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=payload, headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            })
            try:
                response = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                data = json.loads(response)
                
                if "result" in data and data["result"]:
                    encoded_code = data["result"]
                    return base64.b64decode(encoded_code).decode('utf-8')
            except Exception:
                pass
            return ""

        # Fetch using eq_principle to ensure validator consensus on the returned code
        code = gl.eq_principle.strict_eq(fetch_code)
        
        if not code:
            err_result = json.dumps({
                "analysis": {
                    "is_valid": False,
                    "errors": [f"Failed to fetch contract code for {target_address} from GenLayer RPC."],
                    "warnings": [],
                    "info": {"functions": [], "decorators": [], "imports": [], "forbidden_calls": []}
                },
                "source_data": {"source_code": ""},
                "remark": "Target contract could not be analyzed due to fetch failure."
            })
            self.analyses[target_address] = err_result
            return err_result
            
        # Analyze the code deterministically
        analysis_dict = analyze_contract_code(code)
        
        # Prepare full payload
        full_payload = {
            "analysis": analysis_dict,
            "source_data": {"source_code": code}
        }
        
        # Generate a validator remark using LLM consensus
        def get_llm_context() -> str:
            snippet = code[:1000] if len(code) > 1000 else code
            return (
                f"Contract address: {target_address}\n"
                f"Is Valid: {analysis_dict['is_valid']}\n"
                f"Errors: {len(analysis_dict['errors'])}\n"
                f"Warnings: {len(analysis_dict['warnings'])}\n"
                f"Code snippet: {snippet}"
            )
            
        llm_remark = gl.eq_principle.prompt_non_comparative(
            get_llm_context,
            task="Write a short, engaging 1-sentence 'vibe check' remark (max 15 words) evaluating this smart contract's code quality.",
            criteria="The result must be a short, engaging remark (max 20 words) about the contract's code quality based on the context."
        )
        
        full_payload["remark"] = llm_remark
        json_result = json.dumps(full_payload)
        
        # Persist to state
        self.analyses[target_address] = json_result
        return json_result
        
    @gl.public.view
    def get_vibe_check_result(self, target_address: str) -> str:
        """
        Retrieves the JSON analysis payload from state.
        """
        if target_address in self.analyses:
            return self.analyses[target_address]
        return ""
