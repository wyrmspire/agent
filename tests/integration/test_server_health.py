"""
tests/integration/test_server_health.py - Server Health Tests

Verifies that the model server can start and respond to health checks.
This validates Phase 1.0 requirement: "server path first-class"
"""

import unittest
import asyncio
import httpx
from pathlib import Path
import sys
import subprocess
import time
import socket

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


class TestServerHealth(unittest.TestCase):
    """Test server health and basic functionality."""
    
    @unittest.skip("Requires model files - manual test only")
    def test_server_health_endpoint(self):
        """Test that server health endpoint responds correctly.
        
        Note: This test is skipped by default because it requires:
        1. Model files to be present
        2. Sufficient GPU/CPU resources
        3. Long startup time
        
        Run manually with: pytest tests/integration/test_server_health.py -v -s
        """
        # Check if server is already running
        if not is_port_in_use(8000):
            self.skipTest("Server not running on port 8000")
        
        async def check_health():
            async with httpx.AsyncClient() as client:
                # Health check
                response = await client.get("http://localhost:8000/health", timeout=5.0)
                self.assertEqual(response.status_code, 200)
                
                data = response.json()
                self.assertIn("status", data)
                
                return data
        
        result = asyncio.run(check_health())
        print(f"Server health: {result}")
    
    def test_server_module_imports(self):
        """Test that server modules can be imported without errors.
        
        Note: servr/api.py requires bitsandbytes which is optional.
        We only test the non-model parts of the server.
        """
        try:
            # Test server infrastructure (no model dependencies)
            from servr import servr
            from servr import routs
            self.assertTrue(True, "Server infrastructure modules imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import server modules: {e}")
    
    def test_server_configuration(self):
        """Test that server configuration is loadable."""
        from boot.setup import load_config
        
        config = load_config()
        
        # Check that essential config keys exist
        self.assertIn("model", config)
        self.assertIn("model_url", config)
        self.assertIn("max_steps", config)
        
        # Verify default values
        self.assertIsInstance(config["max_steps"], int)
        self.assertGreater(config["max_steps"], 0)


if __name__ == "__main__":
    unittest.main()
