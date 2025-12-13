"""
tests/tools/test_chunk_search.py - Tests for chunk search tool

Tests the chunk search tool functionality.
"""

import tempfile
from pathlib import Path

from tool.chunk_search import ChunkSearchTool
from store.chunks import ChunkManager


async def test_chunk_search_tool_basic():
    """Test basic chunk search tool execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def calculate_sum(a, b):
    '''Calculate sum of two numbers'''
    return a + b

def calculate_product(a, b):
    '''Calculate product of two numbers'''
    return a * b
""")
        
        # Create chunk manager and ingest
        chunk_manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        chunk_manager.ingest_file(str(test_file))
        
        # Create tool
        tool = ChunkSearchTool(chunk_manager=chunk_manager)
        
        # Execute search
        result = await tool.execute({
            "query": "sum",
            "k": 5,
        })
        
        assert result.success
        assert "CHUNK_ID:" in result.output
        assert "calculate_sum" in result.output.lower()


async def test_chunk_search_tool_with_filters():
    """Test chunk search with filters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Python and Markdown files
        py_file = Path(tmpdir) / "code.py"
        py_file.write_text("def process_data(): pass")
        
        md_file = Path(tmpdir) / "docs.md"
        md_file.write_text("# Processing Data\nHow to process data.")
        
        # Create chunk manager and ingest
        chunk_manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        chunk_manager.ingest_file(str(py_file))
        chunk_manager.ingest_file(str(md_file))
        
        # Create tool
        tool = ChunkSearchTool(chunk_manager=chunk_manager)
        
        # Search with Python filter
        result = await tool.execute({
            "query": "data",
            "k": 5,
            "filters": {"file_type": ".py"}
        })
        
        assert result.success
        assert ".py" in result.output
        assert ".md" not in result.output


async def test_chunk_search_tool_no_results():
    """Test chunk search with no results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def example(): pass")
        
        # Create chunk manager and ingest
        chunk_manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        chunk_manager.ingest_file(str(test_file))
        
        # Create tool
        tool = ChunkSearchTool(chunk_manager=chunk_manager)
        
        # Search for non-existent content
        result = await tool.execute({
            "query": "nonexistent_function_xyz",
            "k": 5,
        })
        
        assert result.success
        assert "No chunks found" in result.output
        assert "SUGGESTION" in result.output


async def test_chunk_search_tool_missing_query():
    """Test chunk search with missing query parameter."""
    tool = ChunkSearchTool()
    
    # Execute without query
    result = await tool.execute({
        "k": 5,
    })
    
    assert not result.success
    assert "Missing required parameter" in result.error


async def test_chunk_search_tool_rebuild_index():
    """Test rebuilding chunk index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_file1 = Path(tmpdir) / "test1.py"
        test_file1.write_text("def func1(): pass")
        
        test_file2 = Path(tmpdir) / "test2.py"
        test_file2.write_text("def func2(): pass")
        
        # Create chunk manager
        chunk_manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        
        # Create tool
        tool = ChunkSearchTool(chunk_manager=chunk_manager)
        
        # Rebuild index
        status = tool.rebuild_index(tmpdir)
        
        assert "Total chunks:" in status
        assert "New chunks:" in status
        assert chunk_manager.get_stats()["total_chunks"] > 0


if __name__ == "__main__":
    import asyncio
    
    # Run tests
    asyncio.run(test_chunk_search_tool_basic())
    print("✓ test_chunk_search_tool_basic")
    
    asyncio.run(test_chunk_search_tool_with_filters())
    print("✓ test_chunk_search_tool_with_filters")
    
    asyncio.run(test_chunk_search_tool_no_results())
    print("✓ test_chunk_search_tool_no_results")
    
    asyncio.run(test_chunk_search_tool_missing_query())
    print("✓ test_chunk_search_tool_missing_query")
    
    asyncio.run(test_chunk_search_tool_rebuild_index())
    print("✓ test_chunk_search_tool_rebuild_index")
    
    print("\nAll chunk search tool tests passed!")
