"""
Tests for tool/memory.py - Long-Term Memory Tool
"""

import unittest
import tempfile
import shutil
import asyncio
from pathlib import Path

from tool.memory import MemoryTool
from core.types import ToolCall


class TestMemoryTool(unittest.TestCase):
    """Test memory tool functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.persist_path = f"{self.temp_dir}/memory.pkl"
        self.tool = MemoryTool(persist_path=self.persist_path)
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_tool_properties(self):
        """Test tool name and description."""
        self.assertEqual(self.tool.name, "memory")
        self.assertIn("long-term memory", self.tool.description.lower())
    
    def test_tool_schema(self):
        """Test tool parameter schema."""
        schema = self.tool.parameters
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("operation", schema["properties"])
        self.assertIn("content", schema["properties"])
        self.assertIn("store", schema["properties"]["operation"]["enum"])
        self.assertIn("search", schema["properties"]["operation"]["enum"])
        self.assertEqual(len(schema["required"]), 1)  # only operation is required now
    
    def test_store_memory(self):
        """Test storing memories."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "store",
                    "content": "The capital of France is Paris",
                    "metadata": {"category": "geography"}
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertTrue(result.success)
            self.assertIn("Stored memory", result.output)
            self.assertEqual(self.tool.vector_store.count(), 1)
        
        finally:
            loop.close()
    
    def test_search_memory(self):
        """Test searching memories."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Store some memories
            store_call1 = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "store",
                    "content": "Python is a programming language"
                }
            )
            
            store_call2 = ToolCall(
                id="call_2",
                name="memory",
                arguments={
                    "operation": "store",
                    "content": "JavaScript is used for web development"
                }
            )
            
            loop.run_until_complete(self.tool.call(store_call1))
            loop.run_until_complete(self.tool.call(store_call2))
            
            # Search for Python
            search_call = ToolCall(
                id="call_3",
                name="memory",
                arguments={
                    "operation": "search",
                    "content": "Python"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(search_call))
            
            self.assertTrue(result.success)
            self.assertIn("Python", result.output)
        
        finally:
            loop.close()
    
    def test_search_no_results(self):
        """Test searching with no results."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            search_call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "search",
                    "content": "nonexistent content"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(search_call))
            
            self.assertTrue(result.success)
            self.assertIn("No memories found", result.output)
        
        finally:
            loop.close()
    
    def test_invalid_operation(self):
        """Test invalid operation."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "invalid_op",
                    "content": "test"
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertFalse(result.success)
            # Schema validation catches this
            self.assertIn("not one of", result.error)
        
        finally:
            loop.close()
    
    def test_missing_parameters(self):
        """Test missing required parameters."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "store"
                    # Missing 'content'
                }
            )
            
            result = loop.run_until_complete(self.tool.call(call))
            
            self.assertFalse(result.success)
            # Schema validation catches this
            self.assertIn("is required for operation", result.error)
        
        finally:
            loop.close()
    
    def test_persistence(self):
        """Test memory persistence across instances."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Store memory with first tool instance
            call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "store",
                    "content": "Persistent memory test"
                }
            )
            
            loop.run_until_complete(self.tool.call(call))
            
            # Create new tool instance with same persist path
            tool2 = MemoryTool(persist_path=self.persist_path)
            
            # Should have loaded the memory
            self.assertEqual(tool2.vector_store.count(), 1)
            
            # Search should find it
            search_call = ToolCall(
                id="call_2",
                name="memory",
                arguments={
                    "operation": "search",
                    "content": "Persistent"
                }
            )
            
            result = loop.run_until_complete(tool2.call(search_call))
            
            self.assertTrue(result.success)
            self.assertIn("Persistent", result.output)
        
        finally:
            loop.close()
    
    def test_get_stats(self):
        """Test getting memory statistics."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Add some memories
            call = ToolCall(
                id="call_1",
                name="memory",
                arguments={
                    "operation": "store",
                    "content": "Test memory"
                }
            )
            
            loop.run_until_complete(self.tool.call(call))
            
            stats = self.tool.get_stats()
            
            self.assertEqual(stats["total_memories"], 1)
            self.assertIn("persist_path", stats)
        
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
