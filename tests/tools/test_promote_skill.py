"""
Tests for tool/manager.py - Skill Promotion
"""

import unittest
import tempfile
import shutil
import asyncio
from pathlib import Path

from tool.manager import PromoteSkillTool, load_dynamic_skills
from tool.index import ToolRegistry
from core.types import ToolCall
from core.sandb import Workspace


class TestPromoteSkillTool(unittest.TestCase):
    """Test skill promotion functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary workspace
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Workspace(workspace_root=self.temp_dir)
        self.registry = ToolRegistry()
        self.tool = PromoteSkillTool(
            registry=self.registry,
            workspace=self.workspace
        )
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_skill(self, filename: str, content: str) -> str:
        """Helper to create a test skill file in workspace."""
        path = Path(self.temp_dir) / filename
        with open(path, 'w') as f:
            f.write(content)
        return filename  # Return relative path
    
    def test_tool_properties(self):
        """Test tool name and description."""
        self.assertEqual(self.tool.name, "promote_skill")
        self.assertIn("promote", self.tool.description.lower())
    
    def test_tool_schema(self):
        """Test tool parameter schema."""
        schema = self.tool.parameters
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("file_path", schema["properties"])
        self.assertIn("function_name", schema["properties"])
        self.assertIn("tool_name", schema["properties"])
        self.assertEqual(len(schema["required"]), 2)
    
    def test_promote_valid_skill(self):
        """Test promoting a valid skill."""
        # Create a valid skill file
        skill_file = self._create_test_skill("calculator.py", """
def add_numbers(a: int, b: int) -> int:
    \"\"\"Add two numbers together.\"\"\"
    return a + b
""")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="promote_skill",
                arguments={
                    "file_path": skill_file,
                    "function_name": "add_numbers",
                    "tool_name": "add"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertTrue(result.success)
            self.assertIn("promoted successfully", result.output)
            
            # Check that skill was copied to skills directory
            skills_dir = Path(self.temp_dir) / "skills"
            self.assertTrue(skills_dir.exists())
            self.assertTrue((skills_dir / "add.py").exists())
            
            # Check that tool was registered
            self.assertTrue(self.registry.has("add"))
        
        finally:
            loop.close()
    
    def test_promote_invalid_no_docstring(self):
        """Test that promotion fails without docstring."""
        skill_file = self._create_test_skill("bad.py", """
def bad_function(x: int) -> int:
    return x * 2
""")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="promote_skill",
                arguments={
                    "file_path": skill_file,
                    "function_name": "bad_function"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertFalse(result.success)
            self.assertIn("docstring", result.error.lower())
        
        finally:
            loop.close()
    
    def test_promote_missing_file(self):
        """Test that promotion fails with missing file."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="promote_skill",
                arguments={
                    "file_path": "nonexistent.py",
                    "function_name": "some_function"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertFalse(result.success)
            # Check for either message variant
            self.assertTrue("not found" in result.error.lower() or "does not exist" in result.error.lower())
        
        finally:
            loop.close()
    
    def test_promote_missing_function(self):
        """Test that promotion fails if function not found."""
        skill_file = self._create_test_skill("skill.py", """
def existing_function(x: int) -> int:
    \"\"\"An existing function.\"\"\"
    return x
""")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="promote_skill",
                arguments={
                    "file_path": skill_file,
                    "function_name": "nonexistent_function"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertFalse(result.success)
            self.assertIn("not found", result.error.lower())
        
        finally:
            loop.close()
    
    def test_list_skills(self):
        """Test listing canonized skills."""
        # Create some skills
        skills_dir = Path(self.temp_dir) / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        (skills_dir / "skill1.py").write_text("def f(): pass")
        (skills_dir / "skill2.py").write_text("def g(): pass")
        
        skills = self.tool.list_skills()
        
        self.assertEqual(len(skills), 2)
        self.assertIn("skill1.py", skills)
        self.assertIn("skill2.py", skills)
    
    def test_load_dynamic_skills(self):
        """Test loading dynamic skills on startup."""
        # Create skills directory with valid skill
        skills_dir = Path(self.temp_dir) / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        (skills_dir / "multiply.py").write_text("""
def multiply(x: int, y: int) -> int:
    \"\"\"Multiply two numbers.\"\"\"
    return x * y
""")
        
        # Load skills
        count = load_dynamic_skills(self.registry, skills_dir)
        
        self.assertEqual(count, 1)
        self.assertTrue(self.registry.has("multiply"))


if __name__ == "__main__":
    unittest.main()
