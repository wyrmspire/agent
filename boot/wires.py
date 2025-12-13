"""
boot/wires.py - Dependency Wiring

This module wires up all dependencies for the agent system.
It's the dependency injection container.

Responsibilities:
- Create and configure all components
- Wire dependencies between components
- Return a container with all services

Components to wire:
- Model gateway (gate/)
- Tools (tool/)
- Agent flows (flow/)
- Memory stores (store/)
- Rule engine (core/rules.py)

Rules:
- All components created here
- No business logic
- Just instantiation and wiring
"""

from typing import Dict, Any
from dataclasses import dataclass

# Core imports
from core.rules import get_default_engine, RuleEngine

# These imports will be added as we create the modules
# from gate.lmstd import LMStudioGateway
# from tool.index import ToolRegistry
# from flow.loops import AgentLoop
# from store.short import ShortMemory


@dataclass
class Dependencies:
    """Container for all agent dependencies.
    
    This is what gets passed around the application.
    Everything the agent needs is in here.
    """
    config: Dict[str, Any]
    rule_engine: RuleEngine
    # model_gateway: ModelGateway  # Will add when gate/ is created
    # tool_registry: ToolRegistry  # Will add when tool/ is created
    # agent_loop: AgentLoop        # Will add when flow/ is created
    # short_memory: ShortMemory    # Will add when store/ is created


def wire_dependencies(config: Dict[str, Any]) -> Dependencies:
    """Wire up all dependencies.
    
    Args:
        config: Configuration dictionary from setup.py
        
    Returns:
        Dependencies container with all services
    """
    print("🔌 Wiring dependencies...")
    
    # Create rule engine
    rule_engine = get_default_engine()
    print("   ✓ Rule engine")
    
    # Create model gateway
    # model_gateway = LMStudioGateway(
    #     base_url=config["model_url"],
    #     model=config["model"],
    # )
    # print(f"   ✓ Model gateway ({config['model']})")
    
    # Create tool registry
    # tool_registry = ToolRegistry()
    # if config["enable_shell"]:
    #     tool_registry.register(ShellTool())
    # if config["enable_files"]:
    #     tool_registry.register(FilesTool())
    # if config["enable_fetch"]:
    #     tool_registry.register(FetchTool())
    # print(f"   ✓ Tool registry ({len(tool_registry.tools)} tools)")
    
    # Create memory stores
    # short_memory = ShortMemory()
    # print("   ✓ Short memory")
    
    # Create agent loop
    # agent_loop = AgentLoop(
    #     gateway=model_gateway,
    #     tools=tool_registry,
    #     memory=short_memory,
    #     rule_engine=rule_engine,
    #     max_steps=config["max_steps"],
    # )
    # print("   ✓ Agent loop")
    
    # Assemble dependencies
    deps = Dependencies(
        config=config,
        rule_engine=rule_engine,
    )
    
    return deps
