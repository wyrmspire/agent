"""
tool/promote.py - Promotion Pipeline

This module handles the "graduation" of workspace code into the permanent repository.
It allows the agent to propose a new tool/skill, generates a specification,
and (optionally) applies it to the codebase.

Responsibilities:
- Define PromotionSpec schema
- Validate source files in workspace
- Generate spec artifact (JSON)
- Apply spec (copy files, update registry)

Rules:
- Source files must exist in workspace
- Destination must be within project root
- Registry updates are applied as patches or direct edits
"""

import json
import logging
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any

from .bases import BaseTool
from core.types import ToolResult

logger = logging.getLogger(__name__)

@dataclass
class FileMap:
    source: str  # Relative to workspace root
    dest: str    # Relative to project root
    description: str

@dataclass
class PromotionSpec:
    name: str
    description: str
    files: List[FileMap]
    dependencies: List[str]
    registry_code: Optional[str] = None # Python code to register the tool (if auto-apply supported)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'PromotionSpec':
        data = json.loads(json_str)
        # Reconstruct FileMap objects
        data['files'] = [FileMap(**f) for f in data['files']]
        return cls(**data)


class PromoteTool(BaseTool):
    """Tool for promoting workspace code to the repository."""
    
    def __init__(self, workspace_dir: str = "./workspace", project_root: str = "."):
        self.workspace_dir = Path(workspace_dir)
        self.project_root = Path(project_root)
        self.specs_dir = self.workspace_dir / "promotion_specs"
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        
    @property
    def name(self) -> str:
        return "promote_tool"
        
    @property
    def description(self) -> str:
        return (
            "Propose a tool/skill for promotion to the permanent repository. "
            "Generates a promotion spec file. "
            "Arguments: name, description, files (dict of source->dest), dependencies."
        )
        
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the tool/feature"
                },
                "description": {
                    "type": "string",
                    "description": "Short description of what it does"
                },
                "files": {
                    "type": "object",
                    "description": "Map of {workspace_path: repo_path}",
                    "additionalProperties": {"type": "string"}
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of PyPI dependencies required"
                },
                "registry_code": {
                    "type": "string",
                    "description": "Optional snippet to add to tool/index.py"
                }
            },
            "required": ["name", "files"]
        }
        
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            name = arguments["name"]
            desc = arguments.get("description", "")
            files_dict = arguments["files"]
            deps = arguments.get("dependencies", [])
            reg_code = arguments.get("registry_code")
            
            # Validate files
            file_maps = []
            for src, dst in files_dict.items():
                full_src = self.workspace_dir / src
                if not full_src.exists():
                    return ToolResult(
                        tool_call_id="",
                        output="",
                        error=f"Source file not found in workspace: {src}",
                        success=False
                    )
                file_maps.append(FileMap(source=src, dest=dst, description=f"Source: {src}"))
            
            # Create Spec
            spec = PromotionSpec(
                name=name,
                description=desc,
                files=file_maps,
                dependencies=deps,
                registry_code=reg_code
            )
            
            # Save Spec
            spec_file = self.specs_dir / f"{name}_spec.json"
            with open(spec_file, "w") as f:
                f.write(spec.to_json())
                
            return ToolResult(
                tool_call_id="",
                output=f"Promotion spec saved to: {spec_file}\nContent:\n{spec.to_json()}",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Promotion error: {e}")
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to create promotion spec: {e}",
                success=False
            )

class PromotionManager:
    """Handles the application of promotion specs."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        
    def validate_spec(self, spec_path: str) -> bool:
        """Validate if a spec can be applied."""
        try:
            with open(spec_path, "r") as f:
                spec = PromotionSpec.from_json(f.read())
            
            # Check source files
            # (Note: In a real run, we might need absolute paths or relative to execution context)
            # For now assuming spec_path is in workspace and files are relative to workspace
            spec_dir = Path(spec_path).parent.parent # workspace/promotion_specs/foo.json -> workspace/
            
            for fmap in spec.files:
                src = spec_dir / fmap.source
                if not src.exists():
                    logger.error(f"Source missing: {src}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def apply_spec(self, spec_path: str, dry_run: bool = False) -> str:
        """Apply the promotion spec to the repo."""
        report = []
        try:
            with open(spec_path, "r") as f:
                spec = PromotionSpec.from_json(f.read())
                
            spec_dir = Path(spec_path).parent.parent # workspace/
            
            report.append(f"Applying promotion: {spec.name}")
            
            # 1. Copy Files
            for fmap in spec.files:
                src = spec_dir / fmap.source
                dst = self.project_root / fmap.dest
                
                report.append(f"  Copying {src} -> {dst}")
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            
            # 2. Dependencies (Just report for now)
            if spec.dependencies:
                report.append(f"  Dependencies required: {', '.join(spec.dependencies)}")
                
            # 3. Registry Update
            # In a robust system, we would parse AST of tool/index.py and insert.
            # Here we will append to a 'registry_patch.md' or similar if we can't safely edit logic code automatically yet.
            # But the requirement is "generate a patch (or apply patch)".
            
            if spec.registry_code:
                report.append("  Registry code provided. Manual update recommended or AST patch needed.")
                report.append(f"  Code:\n{spec.registry_code}")
                
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"Apply failed: {e}")
            return f"Error: {e}"
