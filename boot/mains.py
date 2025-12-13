"""
boot/mains.py - Entry Point

This is the main entry point for the agent server.
It initializes all components and starts the server.

Responsibilities:
- Parse command line arguments
- Load configuration
- Wire up dependencies (via wires.py)
- Start the server
- Handle graceful shutdown

Rules:
- No business logic here
- Just coordination and startup
- All wiring delegated to wires.py
"""

import sys
import signal
import asyncio
from typing import Optional

from .setup import load_config, setup_logging
from .wires import wire_dependencies


class AgentServer:
    """Main agent server class."""
    
    def __init__(self, config: dict):
        self.config = config
        self.dependencies = None
        self.running = False
    
    async def start(self) -> None:
        """Start the agent server."""
        print(f"🚀 Starting Agent Server")
        print(f"   Model: {self.config.get('model', 'qwen2.5-coder')}")
        print(f"   Port: {self.config.get('port', 8000)}")
        
        # Wire up all dependencies
        self.dependencies = wire_dependencies(self.config)
        
        # Start HTTP server (if enabled)
        if self.config.get('enable_http', True):
            await self._start_http_server()
        
        self.running = True
        print("✅ Agent Server ready")
    
    async def _start_http_server(self) -> None:
        """Start HTTP API server."""
        # This will be implemented when servr/ is created
        pass
    
    async def stop(self) -> None:
        """Stop the agent server gracefully."""
        print("\n🛑 Stopping Agent Server...")
        self.running = False
        
        # Cleanup dependencies
        if self.dependencies:
            # Close connections, save state, etc.
            pass
        
        print("✅ Agent Server stopped")


async def main() -> int:
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = load_config()
    
    # Create server
    server = AgentServer(config)
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def handle_shutdown(sig, frame):
        print(f"\nReceived signal {sig}")
        loop.create_task(server.stop())
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Start server
    try:
        await server.start()
        
        # Keep running until stopped
        while server.running:
            await asyncio.sleep(1)
        
        return 0
    
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1


def run() -> None:
    """Synchronous entry point for CLI."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Bye!")
        sys.exit(0)


if __name__ == "__main__":
    run()
