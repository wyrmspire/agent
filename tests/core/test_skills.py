"""
Tests for core/skills.py - Skill Compiler
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from core.skills import SkillCompiler, load_function_from_file


class TestSkillCompiler(unittest.TestCase):
    """Test skill compiler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.compiler = SkillCompiler()
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_skill(self, filename: str, content: str) -> str:
        """Helper to create a test skill file."""
        path = Path(self.temp_dir) / filename
        with open(path, 'w') as f:
            f.write(content)
        return str(path)
    
    def test_parse_simple_function(self):
        """Test parsing a simple function with type hints."""
        skill_file = self._create_test_skill("test.py", """
def calculate_sum(a: int, b: int) -> int:
    \"\"\"Calculate the sum of two numbers.\"\"\"
    return a + b
""")
        
        functions = self.compiler.parse_file(skill_file)
        
        self.assertEqual(len(functions), 1)
        func = functions[0]
        self.assertEqual(func.name, "calculate_sum")
        self.assertIn("sum", func.description.lower())
        self.assertEqual(func.parameters["type"], "object")
        self.assertIn("a", func.parameters["properties"])
        self.assertIn("b", func.parameters["properties"])
        self.assertEqual(func.parameters["required"], ["a", "b"])
    
    def test_parse_function_with_defaults(self):
        """Test parsing function with default parameters."""
        skill_file = self._create_test_skill("test.py", """
def greet(name: str, greeting: str = "Hello") -> str:
    \"\"\"Greet someone with a custom message.\"\"\"
    return f"{greeting}, {name}!"
""")
        
        functions = self.compiler.parse_file(skill_file)
        
        self.assertEqual(len(functions), 1)
        func = functions[0]
        # Only 'name' is required, 'greeting' has default
        self.assertEqual(func.parameters["required"], ["name"])
        self.assertIn("greeting", func.parameters["properties"])
    
    def test_parse_function_with_list_type(self):
        """Test parsing function with List type hint."""
        skill_file = self._create_test_skill("test.py", """
from typing import List

def calculate_average(numbers: List[float]) -> float:
    \"\"\"Calculate the average of a list of numbers.\"\"\"
    return sum(numbers) / len(numbers)
""")
        
        functions = self.compiler.parse_file(skill_file)
        
        self.assertEqual(len(functions), 1)
        func = functions[0]
        props = func.parameters["properties"]
        self.assertEqual(props["numbers"]["type"], "array")
        self.assertIn("items", props["numbers"])
    
    def test_parse_function_with_dict_type(self):
        """Test parsing function with Dict type hint."""
        skill_file = self._create_test_skill("test.py", """
from typing import Dict

def process_config(config: Dict[str, str]) -> str:
    \"\"\"Process a configuration dictionary.\"\"\"
    return str(config)
""")
        
        functions = self.compiler.parse_file(skill_file)
        
        self.assertEqual(len(functions), 1)
        func = functions[0]
        props = func.parameters["properties"]
        self.assertEqual(props["config"]["type"], "object")
    
    def test_validate_function_success(self):
        """Test validation of a valid function."""
        skill_file = self._create_test_skill("test.py", """
def multiply(x: int, y: int) -> int:
    \"\"\"Multiply two integers.\"\"\"
    return x * y
""")
        
        is_valid, error = self.compiler.validate_function(skill_file, "multiply")
        
        self.assertTrue(is_valid)
        self.assertEqual(error, "Function is valid")
    
    def test_validate_function_no_docstring(self):
        """Test validation fails without docstring."""
        skill_file = self._create_test_skill("test.py", """
def multiply(x: int, y: int) -> int:
    return x * y
""")
        
        is_valid, error = self.compiler.validate_function(skill_file, "multiply")
        
        self.assertFalse(is_valid)
        self.assertIn("docstring", error.lower())
    
    def test_validate_function_not_found(self):
        """Test validation fails if function doesn't exist."""
        skill_file = self._create_test_skill("test.py", """
def multiply(x: int, y: int) -> int:
    \"\"\"Multiply two integers.\"\"\"
    return x * y
""")
        
        is_valid, error = self.compiler.validate_function(skill_file, "divide")
        
        self.assertFalse(is_valid)
        self.assertIn("not found", error)
    
    def test_get_function_schema(self):
        """Test getting complete function schema."""
        skill_file = self._create_test_skill("test.py", """
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b
""")
        
        self.compiler.parse_file(skill_file)
        schema = self.compiler.get_function_schema("add")
        
        self.assertIsNotNone(schema)
        self.assertEqual(schema["name"], "add")
        self.assertIn("Add", schema["description"])
        self.assertIn("parameters", schema)
    
    def test_load_function_from_file(self):
        """Test dynamically loading a function."""
        skill_file = self._create_test_skill("test.py", """
def square(n: int) -> int:
    \"\"\"Square a number.\"\"\"
    return n * n
""")
        
        func = load_function_from_file(skill_file, "square")
        
        self.assertIsNotNone(func)
        self.assertEqual(func(5), 25)
        self.assertEqual(func(10), 100)
    
    def test_parse_multiple_functions(self):
        """Test parsing file with multiple functions."""
        skill_file = self._create_test_skill("test.py", """
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

def subtract(a: int, b: int) -> int:
    \"\"\"Subtract two numbers.\"\"\"
    return a - b

def multiply(a: int, b: int) -> int:
    \"\"\"Multiply two numbers.\"\"\"
    return a * b
""")
        
        functions = self.compiler.parse_file(skill_file)
        
        self.assertEqual(len(functions), 3)
        names = [f.name for f in functions]
        self.assertIn("add", names)
        self.assertIn("subtract", names)
        self.assertIn("multiply", names)


if __name__ == "__main__":
    unittest.main()
