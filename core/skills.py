"""
core/skills.py - Dynamic Tool Compiler

This module uses introspection to convert Python functions into tool schemas.
It reads a Python script, extracts function signatures, and generates JSON schemas
automatically from type hints and docstrings.

Responsibilities:
- Parse Python AST to extract function definitions
- Generate JSON schemas from type hints
- Extract descriptions from docstrings
- Validate that functions have proper signatures

Rules:
- Functions must have type hints for all parameters
- Functions must have docstrings
- Return types are optional but recommended
- No security validation (handled by promote_skill tool)
"""

import ast
import inspect
import logging
from typing import Dict, Any, List, Optional, Callable, get_type_hints
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a parsed function."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    source_file: str
    function: Optional[Callable] = None


class SkillCompiler:
    """Compiler that turns Python functions into tool schemas.
    
    Uses AST parsing and inspection to:
    1. Extract function signatures
    2. Generate JSON schemas from type hints
    3. Extract descriptions from docstrings
    """
    
    # Mapping from Python types to JSON Schema types
    TYPE_MAPPING = {
        'str': 'string',
        'int': 'integer',
        'float': 'number',
        'bool': 'boolean',
        'list': 'array',
        'dict': 'object',
        'List': 'array',
        'Dict': 'object',
        'Any': 'string',  # Default to string for Any
    }
    
    def __init__(self):
        self.functions: Dict[str, FunctionInfo] = {}
    
    def parse_file(self, file_path: str) -> List[FunctionInfo]:
        """Parse a Python file and extract function information.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of FunctionInfo objects
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        try:
            with open(path, 'r') as f:
                source = f.read()
            
            # Parse AST
            tree = ast.parse(source)
            
            # Extract functions
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = self._parse_function(node, str(path))
                    if func_info:
                        functions.append(func_info)
                        self.functions[func_info.name] = func_info
            
            return functions
        
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return []
    
    def _parse_function(self, node: ast.FunctionDef, source_file: str) -> Optional[FunctionInfo]:
        """Parse a function definition node.
        
        Args:
            node: AST FunctionDef node
            source_file: Source file path
            
        Returns:
            FunctionInfo or None if function is invalid
        """
        try:
            name = node.name
            
            # Extract docstring
            description = ast.get_docstring(node) or f"Function {name}"
            # Use first line of docstring as description
            description = description.split('\n')[0].strip()
            
            # Extract parameters and generate schema
            schema = self._generate_schema(node)
            
            if not schema:
                logger.warning(f"Could not generate schema for {name}")
                return None
            
            return FunctionInfo(
                name=name,
                description=description,
                parameters=schema,
                source_file=source_file,
            )
        
        except Exception as e:
            logger.error(f"Failed to parse function: {e}")
            return None
    
    def _generate_schema(self, node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        """Generate JSON schema from function signature.
        
        Args:
            node: AST FunctionDef node
            
        Returns:
            JSON schema dict or None if invalid
        """
        properties = {}
        required = []
        
        for arg in node.args.args:
            arg_name = arg.arg
            
            # Skip 'self' parameter
            if arg_name == 'self':
                continue
            
            # Get type annotation
            if arg.annotation:
                type_info = self._parse_type_annotation(arg.annotation)
            else:
                logger.warning(f"Parameter {arg_name} has no type hint")
                type_info = {"type": "string"}  # Default to string
            
            properties[arg_name] = type_info
            
            # Check if parameter has default value
            defaults_offset = len(node.args.args) - len(node.args.defaults)
            arg_index = node.args.args.index(arg)
            has_default = arg_index >= defaults_offset
            
            if not has_default:
                required.append(arg_name)
        
        # Build schema
        schema = {
            "type": "object",
            "properties": properties,
        }
        
        if required:
            schema["required"] = required
        
        return schema
    
    def _parse_type_annotation(self, annotation: ast.expr) -> Dict[str, Any]:
        """Parse type annotation into JSON schema type.
        
        Args:
            annotation: AST annotation node
            
        Returns:
            JSON schema type dict
        """
        # Handle simple name types (str, int, float, etc.)
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            json_type = self.TYPE_MAPPING.get(type_name, "string")
            return {"type": json_type, "description": f"Parameter of type {type_name}"}
        
        # Handle subscripted types (List[str], Dict[str, int], etc.)
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                base_type = annotation.value.id
                
                if base_type in ['List', 'list']:
                    # Extract item type if possible
                    item_type = "string"  # Default
                    if isinstance(annotation.slice, ast.Name):
                        item_type = self.TYPE_MAPPING.get(annotation.slice.id, "string")
                    
                    return {
                        "type": "array",
                        "items": {"type": item_type},
                        "description": f"List of {item_type}s"
                    }
                
                elif base_type in ['Dict', 'dict']:
                    return {
                        "type": "object",
                        "description": "Dictionary object",
                        "additionalProperties": True
                    }
        
        # Handle Optional types
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id == 'Optional':
                    # Extract the inner type
                    inner = self._parse_type_annotation(annotation.slice)
                    inner["description"] = inner.get("description", "") + " (optional)"
                    return inner
        
        # Default fallback
        return {"type": "string", "description": "Parameter"}
    
    def get_function_schema(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get the JSON schema for a parsed function.
        
        Args:
            function_name: Name of function
            
        Returns:
            Complete tool schema or None if not found
        """
        if function_name not in self.functions:
            return None
        
        func_info = self.functions[function_name]
        
        return {
            "name": func_info.name,
            "description": func_info.description,
            "parameters": func_info.parameters,
        }
    
    def validate_function(self, file_path: str, function_name: str) -> tuple[bool, str]:
        """Validate that a function is suitable for promotion to a tool.
        
        Args:
            file_path: Path to Python file
            function_name: Name of function to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Parse the file
        functions = self.parse_file(file_path)
        
        if not functions:
            return False, "No functions found in file"
        
        # Find the target function
        func_info = None
        for f in functions:
            if f.name == function_name:
                func_info = f
                break
        
        if not func_info:
            return False, f"Function '{function_name}' not found"
        
        # Check for docstring
        if not func_info.description or func_info.description == f"Function {function_name}":
            return False, "Function must have a docstring"
        
        # Check for type hints
        if not func_info.parameters.get("properties"):
            return False, "Function must have type hints for parameters"
        
        return True, "Function is valid"


def load_function_from_file(file_path: str, function_name: str) -> Optional[Callable]:
    """Load a function from a Python file dynamically.
    
    Args:
        file_path: Path to Python file
        function_name: Name of function to load
        
    Returns:
        Function object or None if not found
    """
    try:
        # Read and compile the file
        with open(file_path, 'r') as f:
            source = f.read()
        
        # Create a namespace and execute the code
        namespace = {}
        exec(source, namespace)
        
        # Get the function
        if function_name in namespace:
            return namespace[function_name]
        else:
            logger.error(f"Function {function_name} not found in {file_path}")
            return None
    
    except Exception as e:
        logger.error(f"Failed to load function from {file_path}: {e}")
        return None
