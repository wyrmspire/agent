"""
tool/manager.py - Skill Management Tool

This module implements the promote_skill tool that allows the agent
to upgrade Python scripts into registered tools.

Responsibilities:
- Validate skill scripts (syntax, type hints, docstrings)
- Move validated scripts to workspace/skills/
- Register skills as dynamic tools
- Hot-reload the tool registry

Rules:
- All validation must pass before promotion
- Skills must be in workspace (not source code)
- One skill per file
- Skills execute via pyexe for safety
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.types import ToolResult
from core.skills import SkillCompiler
from core.sandb import get_default_workspace, WorkspaceError
from .bases import BaseTool
from .dynamic import DynamicTool
from .index import ToolRegistry

logger = logging.getLogger(__name__)


class PromoteSkillTool(BaseTool):
    """Tool for promoting Python scripts to registered skills.
    
    Workflow:
    1. Validate script (syntax, type hints, docstrings)
    2. Lint for quality
    3. Move to workspace/skills/
    4. Register as dynamic tool
    5. Make available immediately
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        workspace: Optional[Any] = None,
    ):
        """Initialize promote_skill tool.
        
        Args:
            registry: Tool registry to register new skills
            workspace: Workspace instance
        """
        self.registry = registry
        self.workspace = workspace or get_default_workspace()
        self.compiler = SkillCompiler()
        self.skills_dir = Path(self.workspace.base_path) / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def name(self) -> str:
        return "promote_skill"
    
    @property
    def description(self) -> str:
        return "Promote a Python function to a registered tool. Validates syntax, type hints, and docstrings, then makes it available as a tool."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to Python file containing the function (relative to workspace)"
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function to promote"
                },
                "tool_name": {
                    "type": "string",
                    "description": "Optional custom name for the tool (defaults to function name)"
                }
            },
            "required": ["file_path", "function_name"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Promote a skill to a registered tool.
        
        Args:
            arguments: file_path, function_name, optional tool_name
            
        Returns:
            ToolResult with promotion status
        """
        file_path = arguments.get("file_path", "")
        function_name = arguments.get("function_name", "")
        tool_name = arguments.get("tool_name", function_name)
        
        if not file_path or not function_name:
            return ToolResult(
                tool_call_id="",
                output="",
                error="Missing required parameters: file_path and function_name",
                success=False,
            )
        
        try:
            # Resolve file path in workspace
            try:
                source_path = self.workspace.resolve_read(file_path)
            except WorkspaceError as e:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"File not in workspace: {e}",
                    success=False,
                )
            
            if not source_path.exists():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"File not found: {file_path}",
                    success=False,
                )
            
            # Step 1: Validate the function
            is_valid, error_msg = self.compiler.validate_function(
                str(source_path),
                function_name
            )
            
            if not is_valid:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Validation failed: {error_msg}",
                    success=False,
                )
            
            # Step 2: Test execution (syntax check)
            test_result = await self._test_execution(str(source_path))
            if not test_result[0]:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Execution test failed: {test_result[1]}",
                    success=False,
                )
            
            # Step 3: Move to skills directory (canonization)
            skill_filename = f"{tool_name}.py"
            skill_path = self.skills_dir / skill_filename
            
            # Copy the file
            shutil.copy2(source_path, skill_path)
            logger.info(f"Canonized skill to: {skill_path}")
            
            # Step 4: Parse function info
            functions = self.compiler.parse_file(str(skill_path))
            func_info = None
            for f in functions:
                if f.name == function_name:
                    func_info = f
                    break
            
            if not func_info:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Function {function_name} not found after parsing",
                    success=False,
                )
            
            # Step 5: Register as dynamic tool
            if self.registry:
                dynamic_tool = DynamicTool(
                    func_info=func_info,
                    skill_file=str(skill_path),
                )
                
                # Override name if custom tool_name provided
                if tool_name != function_name:
                    func_info.name = tool_name
                
                try:
                    self.registry.register(dynamic_tool)
                    logger.info(f"Registered dynamic tool: {tool_name}")
                except ValueError as e:
                    # Tool already exists - update it
                    self.registry.unregister(tool_name)
                    self.registry.register(dynamic_tool)
                    logger.info(f"Updated dynamic tool: {tool_name}")
            
            output = f"""Skill promoted successfully!

Tool Name: {tool_name}
Function: {function_name}
Location: skills/{skill_filename}
Description: {func_info.description}

The tool is now available for use.
"""
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to promote skill: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Promotion failed: {e}",
                success=False,
            )
    
    async def _test_execution(self, file_path: str) -> tuple[bool, str]:
        """Test that a skill file can execute without errors.
        
        Args:
            file_path: Path to skill file
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Try to compile the file
            with open(file_path, 'r') as f:
                source = f.read()
            
            compile(source, file_path, 'exec')
            
            return True, "Syntax is valid"
        
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Compilation error: {e}"
    
    def list_skills(self) -> list:
        """List all canonized skills.
        
        Returns:
            List of skill file names
        """
        if not self.skills_dir.exists():
            return []
        
        return [f.name for f in self.skills_dir.glob("*.py")]


def load_dynamic_skills(
    registry: ToolRegistry,
    skills_dir: Optional[Path] = None,
) -> int:
    """Load all dynamic skills from skills directory.
    
    Args:
        registry: Tool registry to register skills
        skills_dir: Optional custom skills directory
        
    Returns:
        Number of skills loaded
    """
    if skills_dir is None:
        workspace = get_default_workspace()
        skills_dir = Path(workspace.base_path) / "skills"
    
    if not skills_dir.exists():
        logger.info(f"Skills directory does not exist: {skills_dir}")
        return 0
    
    compiler = SkillCompiler()
    loaded = 0
    
    for skill_file in skills_dir.glob("*.py"):
        try:
            # Parse functions
            functions = compiler.parse_file(str(skill_file))
            
            for func_info in functions:
                # Skip private functions
                if func_info.name.startswith('_'):
                    continue
                
                # Create and register dynamic tool
                dynamic_tool = DynamicTool(
                    func_info=func_info,
                    skill_file=str(skill_file),
                )
                
                try:
                    registry.register(dynamic_tool)
                    logger.info(f"Loaded dynamic skill: {func_info.name}")
                    loaded += 1
                except ValueError:
                    # Already registered, skip
                    logger.debug(f"Skill already registered: {func_info.name}")
        
        except Exception as e:
            logger.error(f"Failed to load skill {skill_file}: {e}")
    
    return loaded
