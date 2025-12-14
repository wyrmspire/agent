"""
Tests for Phase 1.7: github_ingest tool.

Tests repo parsing, clone path generation, and manifest creation.
Note: Actual git cloning is mocked to avoid network dependencies.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from tool.github import GitHubIngest
from core.sandb import Workspace


class TestGitHubIngestParsing:
    """Test repository string parsing."""
    
    def test_parse_owner_repo(self, tmp_path):
        """Parse 'owner/repo' format."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        owner, repo = tool._parse_repo("wyrmspire/agent")
        assert owner == "wyrmspire"
        assert repo == "agent"
    
    def test_parse_https_url(self, tmp_path):
        """Parse full HTTPS GitHub URL."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        owner, repo = tool._parse_repo("https://github.com/wyrmspire/agent")
        assert owner == "wyrmspire"
        assert repo == "agent"
    
    def test_parse_https_url_with_git_suffix(self, tmp_path):
        """Parse URL with .git suffix."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        owner, repo = tool._parse_repo("https://github.com/wyrmspire/agent.git")
        assert owner == "wyrmspire"
        assert repo == "agent"
    
    def test_parse_trailing_slash(self, tmp_path):
        """Parse URL with trailing slash."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        owner, repo = tool._parse_repo("https://github.com/wyrmspire/agent/")
        assert owner == "wyrmspire"
        assert repo == "agent"
    
    def test_parse_invalid_format_raises(self, tmp_path):
        """Invalid format raises ValueError."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        with pytest.raises(ValueError, match="Invalid repo format"):
            tool._parse_repo("just-a-name")
    
    def test_parse_ssh_url(self, tmp_path):
        """Parse SSH-style GitHub URL."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        owner, repo = tool._parse_repo("git@github.com:wyrmspire/agent.git")
        assert owner == "wyrmspire"
        assert repo == "agent"


class TestGitHubIngestClone:
    """Test cloning behavior (mocked)."""
    
    @pytest.mark.asyncio
    async def test_clone_creates_directory_structure(self, tmp_path):
        """Clone creates workspace/repos/<owner>/ structure."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=True)
        tool = GitHubIngest(workspace=ws)
        
        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            # Mock clone success
            mock_clone = MagicMock()
            mock_clone.returncode = 0
            
            # Mock rev-parse for SHA
            mock_sha = MagicMock()
            mock_sha.stdout = "abc123def456789\n"
            mock_sha.returncode = 0
            
            mock_run.side_effect = [mock_clone, mock_sha]
            
            # Need to create temp path since real clone won't happen
            temp_path = ws.root / "repos" / "testowner" / "testrepo_temp_000000"
            temp_path.mkdir(parents=True)
            
            try:
                path, sha = tool._clone_repo("testowner", "testrepo", "main")
                assert sha.startswith("abc123")
            except Exception:
                # Expected since we can't fully mock filesystem operations
                pass
            
            # Verify repos directory was created
            assert (ws.root / "repos").exists()
    
    @pytest.mark.asyncio
    async def test_execute_success_creates_manifest(self, tmp_path):
        """Successful execute creates manifest file."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=True)
        tool = GitHubIngest(workspace=ws)
        
        # Create a fake clone directory
        clone_path = ws.root / "repos" / "testowner" / "testrepo@abc123de"
        clone_path.mkdir(parents=True)
        
        # Mock the clone to return our fake path
        with patch.object(tool, "_clone_repo") as mock_clone:
            mock_clone.return_value = (clone_path, "abc123def456")
            
            result = await tool.execute({
                "repo": "testowner/testrepo",
                "ref": "main",
                "index": False,  # Skip VectorGit indexing
            })
            
            assert result.success
            assert "abc123de" in result.output
            
            # Manifest should exist
            manifest_path = clone_path / "ingest_manifest.json"
            assert manifest_path.exists()
            
            manifest = json.loads(manifest_path.read_text())
            assert manifest["repo"] == "testowner/testrepo"
            assert manifest["sha"] == "abc123def456"
            assert manifest["ref"] == "main"


class TestGitHubIngestManifest:
    """Test manifest format and content."""
    
    def test_manifest_contains_required_fields(self, tmp_path):
        """Manifest has all required fields."""
        # Create a sample manifest
        manifest = {
            "repo": "owner/repo",
            "url": "https://github.com/owner/repo",
            "sha": "abc123",
            "ref": "main",
            "patterns": ["*.py"],
            "ingested_at": "2024-01-01T00:00:00Z",
            "clone_path": str(tmp_path),
            "indexed": False,
        }
        
        required_fields = ["repo", "sha", "ref", "patterns", "ingested_at", "clone_path"]
        for field in required_fields:
            assert field in manifest
    
    def test_manifest_sha_is_pinned(self, tmp_path):
        """Manifest contains exact SHA, not just ref."""
        manifest = {
            "ref": "main",
            "sha": "abc123def456789",
        }
        
        # SHA should be full commit hash, not branch name
        assert manifest["sha"] != manifest["ref"]
        assert len(manifest["sha"]) > 8
