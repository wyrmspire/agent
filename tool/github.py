"""
tool/github.py - GitHub Repository Ingestion Tool (Phase 1.7)

Clones and vectorizes public GitHub repos with SHA pinning for reproducibility.
Use this to find reference code before starting a project.

Personal tools, not for resale - but engineering is sane:
every run is pinned to a commit SHA, not "whatever main was today."
"""

import json
import subprocess
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.types import ToolResult
from core.sandb import Workspace, WorkspaceError, get_default_workspace
from core.patch import BlockedBy, create_tool_error, format_tool_error
from .bases import BaseTool, create_json_schema

logger = logging.getLogger(__name__)


class GitHubIngest(BaseTool):
    """Clone and vectorize a public GitHub repository.
    
    Clones to workspace/repos/<owner>/<repo>@<sha>/ with manifest.
    Optionally indexes with VectorGit for search.
    """
    
    def __init__(
        self,
        workspace: Optional[Workspace] = None,
        vectorgit = None,  # VectorGit instance for indexing
    ):
        """Initialize GitHub ingest tool.
        
        Args:
            workspace: Workspace instance (uses default if None)
            vectorgit: VectorGit instance for indexing cloned repos
        """
        self.workspace = workspace or get_default_workspace()
        self.vectorgit = vectorgit
    
    @property
    def name(self) -> str:
        return "github_ingest"
    
    @property
    def description(self) -> str:
        return (
            "Clone a public GitHub repository and optionally index it for search. "
            "Pins to a specific SHA for reproducibility. "
            "Use this to find reference code before starting a project."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "repo": {
                    "type": "string",
                    "description": "Repository as 'owner/repo' or full GitHub URL (public repos only)",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch, tag, or commit SHA (default: main)",
                },
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to index (default: ['*.py', '*.md'])",
                },
                "index": {
                    "type": "boolean",
                    "description": "Whether to index with VectorGit (default: true)",
                },
            },
            required=["repo"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Clone and optionally index a GitHub repository."""
        repo = arguments["repo"]
        ref = arguments.get("ref", "main")
        patterns = arguments.get("patterns", ["*.py", "*.md"])
        should_index = arguments.get("index", True)
        
        try:
            # Parse repo string
            owner, repo_name = self._parse_repo(repo)
            logger.info(f"Ingesting {owner}/{repo_name} @ {ref}")
            
            # Clone to workspace/repos/<owner>/<repo>@<sha>/
            clone_path, sha = self._clone_repo(owner, repo_name, ref)
            
            # Create manifest
            manifest = {
                "repo": f"{owner}/{repo_name}",
                "url": f"https://github.com/{owner}/{repo_name}",
                "sha": sha,
                "ref": ref,
                "patterns": patterns,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "clone_path": str(clone_path),
                "indexed": should_index and self.vectorgit is not None,
            }
            manifest_path = clone_path / "ingest_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            logger.info(f"Created manifest at {manifest_path}")
            
            # Index with VectorGit if available and requested
            chunks_indexed = 0
            if should_index and self.vectorgit:
                chunks_indexed = await self._index_repo(clone_path, patterns)
                manifest["chunks_indexed"] = chunks_indexed
                manifest_path.write_text(json.dumps(manifest, indent=2))
            
            # Build output
            output_lines = [
                f"✅ Cloned {owner}/{repo_name}@{sha[:8]}",
                f"📁 Path: {clone_path}",
                f"📋 Manifest: {manifest_path}",
            ]
            if should_index and self.vectorgit:
                output_lines.append(f"🔍 Indexed: {chunks_indexed} chunks")
            else:
                output_lines.append("⏭️ Indexing skipped (use search_chunks after manual review)")
            
            return ToolResult(
                tool_call_id="",
                output="\n".join(output_lines),
                success=True,
            )
        
        except subprocess.CalledProcessError as e:
            error = create_tool_error(
                blocked_by=BlockedBy.RUNTIME,
                error_code="GIT_CLONE_FAILED",
                message=f"Git clone failed: {e.stderr.decode() if e.stderr else str(e)}",
                context={"repo": repo, "ref": ref},
            )
            return ToolResult(
                tool_call_id="",
                output="",
                error=format_tool_error(error),
                success=False,
            )
        except ValueError as e:
            error = create_tool_error(
                blocked_by=BlockedBy.VALIDATION,
                error_code="INVALID_REPO",
                message=str(e),
                context={"repo": repo},
            )
            return ToolResult(
                tool_call_id="",
                output="",
                error=format_tool_error(error),
                success=False,
            )
        except Exception as e:
            logger.exception(f"GitHub ingest failed: {e}")
            error = create_tool_error(
                blocked_by=BlockedBy.RUNTIME,
                error_code="GITHUB_INGEST_ERROR",
                message=f"GitHub ingest failed: {e}",
                context={"repo": repo},
            )
            return ToolResult(
                tool_call_id="",
                output="",
                error=format_tool_error(error),
                success=False,
            )
    
    def _parse_repo(self, repo: str) -> tuple:
        """Parse 'owner/repo' or URL into (owner, repo_name).
        
        Args:
            repo: Repository string
            
        Returns:
            Tuple of (owner, repo_name)
            
        Raises:
            ValueError: If repo format is invalid
        """
        repo = repo.strip()
        
        if "github.com" in repo:
            # Extract from URL: https://github.com/owner/repo or git@github.com:owner/repo
            if "github.com/" in repo:
                parts = repo.split("github.com/")[-1].rstrip("/").split("/")
            elif "github.com:" in repo:
                parts = repo.split("github.com:")[-1].rstrip("/").split("/")
            else:
                raise ValueError(f"Unrecognized GitHub URL format: {repo}")
            
            if len(parts) >= 2:
                owner = parts[0]
                repo_name = parts[1].replace(".git", "")
                return owner, repo_name
            else:
                raise ValueError(f"Could not parse owner/repo from URL: {repo}")
        
        elif "/" in repo:
            # Simple owner/repo format
            parts = repo.split("/")
            if len(parts) == 2:
                return parts[0], parts[1]
            else:
                raise ValueError(f"Expected 'owner/repo' format, got: {repo}")
        
        else:
            raise ValueError(
                f"Invalid repo format: {repo}. "
                "Use 'owner/repo' or 'https://github.com/owner/repo'"
            )
    
    def _clone_repo(self, owner: str, repo_name: str, ref: str) -> tuple:
        """Clone repo and return (path, sha).
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            ref: Branch, tag, or commit SHA
            
        Returns:
            Tuple of (clone_path, sha)
        """
        repos_dir = self.workspace.root / "repos" / owner
        repos_dir.mkdir(parents=True, exist_ok=True)
        
        url = f"https://github.com/{owner}/{repo_name}.git"
        temp_path = repos_dir / f"{repo_name}_temp_{datetime.now().strftime('%H%M%S')}"
        
        logger.info(f"Cloning {url} @ {ref} to {temp_path}")
        
        # Clone with depth 1 for efficiency
        # Use --single-branch to only fetch the specified ref
        clone_cmd = [
            "git", "clone",
            "--depth", "1",
            "--single-branch",
            "--branch", ref,
            url,
            str(temp_path),
        ]
        
        try:
            subprocess.run(
                clone_cmd,
                check=True,
                capture_output=True,
                timeout=120,  # 2 minute timeout
            )
        except subprocess.TimeoutExpired:
            if temp_path.exists():
                shutil.rmtree(temp_path, ignore_errors=True)
            raise RuntimeError(f"Clone timed out after 120 seconds")
        
        # Get actual SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        sha = result.stdout.strip()
        logger.info(f"Cloned at SHA: {sha}")
        
        # Rename to final path with SHA suffix
        final_path = repos_dir / f"{repo_name}@{sha[:8]}"
        
        if final_path.exists():
            # Already have this exact SHA, remove temp clone
            logger.info(f"Already have {final_path}, removing duplicate")
            shutil.rmtree(temp_path, ignore_errors=True)
        else:
            # Move to final location
            temp_path.rename(final_path)
            logger.info(f"Moved to {final_path}")
        
        return final_path, sha
    
    async def _index_repo(self, path: Path, patterns: list) -> int:
        """Index repo with VectorGit.
        
        Args:
            path: Path to cloned repo
            patterns: File patterns to index
            
        Returns:
            Number of chunks indexed
        """
        if not self.vectorgit:
            return 0
        
        logger.info(f"Indexing {path} with patterns {patterns}")
        
        try:
            # Use VectorGit's async ingest method
            result = await self.vectorgit.ingest_async(str(path))
            chunks = result.get("chunks_added", 0) if isinstance(result, dict) else 0
            logger.info(f"Indexed {chunks} chunks")
            return chunks
        except Exception as e:
            logger.warning(f"Indexing failed (non-fatal): {e}")
            return 0
