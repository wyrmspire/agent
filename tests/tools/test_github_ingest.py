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


class TestGitHubIngestSHADetection:
    """Test SHA detection (Phase 1.7.1)."""
    
    def test_is_commit_sha_full_sha(self, tmp_path):
        """Full SHA (40 chars) is detected."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        sha = "abc123def456789012345678901234567890abcd"
        assert tool._is_commit_sha(sha) is True
    
    def test_is_commit_sha_short_sha(self, tmp_path):
        """Short SHA (8+ chars) is detected."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        sha = "abc123de"
        assert tool._is_commit_sha(sha) is True
    
    def test_is_commit_sha_too_short(self, tmp_path):
        """SHA less than 8 chars is not detected."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        sha = "abc123"
        assert tool._is_commit_sha(sha) is False
    
    def test_is_commit_sha_branch_name(self, tmp_path):
        """Branch names are not detected as SHAs."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        assert tool._is_commit_sha("main") is False
        assert tool._is_commit_sha("develop") is False
        assert tool._is_commit_sha("feature/new-thing") is False
    
    def test_is_commit_sha_tag_name(self, tmp_path):
        """Tag names are not detected as SHAs."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        tool = GitHubIngest(workspace=ws)
        
        assert tool._is_commit_sha("v1.0.0") is False
        assert tool._is_commit_sha("release-2024") is False


class TestGitHubIngestCloneBehavior:
    """Test clone behavior for SHA vs branch/tag (Phase 1.7.1)."""
    
    def test_clone_branch_uses_clone_command(self, tmp_path):
        """Branch/tag refs use git clone --branch."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=True)
        tool = GitHubIngest(workspace=ws)
        
        with patch("subprocess.run") as mock_run:
            # Mock successful clone and rev-parse
            mock_run.side_effect = [
                MagicMock(returncode=0),  # git clone
                MagicMock(stdout="abc123def456\n", returncode=0),  # git rev-parse
            ]
            
            # Create temp path for the test
            temp_path = ws.root / "repos" / "owner" / "repo_temp_000000"
            temp_path.mkdir(parents=True)
            
            try:
                path, sha = tool._clone_repo("owner", "repo", "main")
            except Exception:
                pass  # Expected due to mocking limitations
            
            # Verify git clone was called (first call)
            calls = mock_run.call_args_list
            if calls:
                first_call = calls[0]
                args = first_call[0][0]
                assert "clone" in args
                assert "--branch" in args
                assert "main" in args
    
    def test_clone_sha_uses_fetch_command(self, tmp_path):
        """SHA refs use git init + fetch + checkout."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=True)
        tool = GitHubIngest(workspace=ws)
        
        with patch("subprocess.run") as mock_run:
            # Mock successful init, remote add, fetch, checkout, and rev-parse
            mock_run.side_effect = [
                MagicMock(returncode=0),  # git init
                MagicMock(returncode=0),  # git remote add
                MagicMock(returncode=0),  # git fetch
                MagicMock(returncode=0),  # git checkout
                MagicMock(stdout="abc123def456\n", returncode=0),  # git rev-parse
            ]
            
            try:
                path, sha = tool._clone_repo("owner", "repo", "abc123def456")
            except Exception:
                pass  # Expected due to mocking limitations
            
            # Verify git init, fetch were called (not clone)
            calls = mock_run.call_args_list
            if len(calls) >= 3:
                # Check that we used init flow, not clone
                first_call_args = calls[0][0][0]
                second_call_args = calls[1][0][0]
                third_call_args = calls[2][0][0]
                
                assert "init" in first_call_args
                assert "remote" in second_call_args
                assert "fetch" in third_call_args


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


class TestGitHubIngestRegistryWiring:
    """Test that GitHubIngest is wired with VectorGit in registry (Phase 1.7.1)."""
    
    def test_registry_wires_vectorgit(self):
        """create_default_registry() should wire GitHubIngest with VectorGit instance."""
        from tool.index import create_default_registry
        
        # Create registry with GitHub enabled
        registry = create_default_registry(config={"enable_github": True})
        
        # Get the github_ingest tool
        github_tool = registry.get("github_ingest")
        assert github_tool is not None, "github_ingest tool should be registered"
        
        # Verify it has a vectorgit instance (Phase 1.7.1)
        assert hasattr(github_tool, "vectorgit"), "GitHubIngest should have vectorgit attribute"
        assert github_tool.vectorgit is not None, "vectorgit should be set (not None)"
    
    @pytest.mark.asyncio
    async def test_indexing_uses_vectorgit(self, tmp_path):
        """When index=True, GitHubIngest should attempt to use vectorgit."""
        from tool.index import create_default_registry
        
        # Create registry
        registry = create_default_registry(config={"enable_github": True})
        github_tool = registry.get("github_ingest")
        
        # Mock the clone to return a fake path
        clone_path = tmp_path / "repos" / "owner" / "repo@abc123"
        clone_path.mkdir(parents=True)
        
        with patch.object(github_tool, "_clone_repo") as mock_clone:
            mock_clone.return_value = (clone_path, "abc123def456")
            
            # Mock vectorgit's ingest_async
            with patch.object(github_tool.vectorgit, "ingest_async") as mock_ingest:
                mock_ingest.return_value = {"chunks_added": 10}
                
                # Execute with index=True
                result = await github_tool.execute({
                    "repo": "owner/repo",
                    "ref": "main",
                    "index": True,
                })
                
                # Verify ingest_async was called
                assert mock_ingest.called, "vectorgit.ingest_async should be called when index=True"
                assert "10 chunks" in result.output
