#!/usr/bin/env python3
"""
cli.py - Simple CLI for Day 1 Testing

This is a minimal CLI chat loop for smoke testing the agent.
It demonstrates the core flow: prompt → model → tool → answer.

Usage:
    python cli.py

This will start an interactive chat session. Type 'quit' or 'exit' to stop.
"""

import asyncio
import sys
import os
import uuid
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.types import MessageRole
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import get_default_engine
# from gate.lmstd import LMStudioGateway  # Removed per user request
from tool.index import create_default_registry
from flow.loops import AgentLoop
from flow.plans import create_system_prompt
from boot.setup import load_config, setup_logging


async def main():
    """Main CLI entry point."""
    # Setup
    setup_logging()
    config = load_config()
    
    print("[Agent CLI]")
    print("=" * 50)
    print(f"Model: {config['model']}")
    print(f"URL: {config['model_url']}")
    print(f"Max steps: {config['max_steps']}")
    print("=" * 50)
    print("\nType 'quit' or 'exit' to stop\n")
    
    # Parse args
    import argparse
    parser = argparse.ArgumentParser(description="Agent CLI")
    parser.add_argument("--mock", action="store_true", help="Use mock model instead of real server")
    parser.add_argument("--gemini", action="store_true", help="Use Gemini API (requires GEMINI_API_KEY)")
    parser.add_argument("--test-embed", type=str, help="Test embedding generation for text")
    parser.add_argument("--promote", type=str, help="Apply a promotion spec file (JSON) to the repo")
    args = parser.parse_args()

    # Create gateway based on config/args
    try:
        if args.mock:
            print("[MOCK] Using MOCK Gateway (no real model connection)")
            from gate.mock import MockGateway
            gateway = MockGateway()
        
        elif args.gemini or config.get("gateway") == "gemini" or config.get("gemini_api_key"):
            # Use Gemini API
            api_key = config.get("gemini_api_key")
            if not api_key:
                print("[ERROR] GEMINI_API_KEY not set in .env")
                return 1
            
            from gate.gemini import GeminiGateway
            
            primary_model = config.get("gemini_model", "gemini-2.5-flash")
            escalation_model = config.get("gemini_escalation_model", "")
            
            if escalation_model:
                # Phase 4: Use EscalatingGateway with model switching
                from gate.escalating import EscalatingGateway
                print(f"[GEMINI] Using Escalating Gateway: primary={primary_model}, escalation={escalation_model}")
                
                primary_gateway = GeminiGateway(api_key=api_key, model=primary_model)
                escalation_gateway = GeminiGateway(api_key=api_key, model=escalation_model)
                gateway = EscalatingGateway(primary_gateway, escalation_gateway)
            else:
                # Single model mode
                print(f"[GEMINI] Using Gemini API ({primary_model})")
                gateway = GeminiGateway(api_key=api_key, model=primary_model)
            
            # Health check
            print("Checking Gemini API...")
            healthy = await gateway.health_check()
            if not healthy:
                print("[ERROR] Cannot connect to Gemini API")
                print("   Check your GEMINI_API_KEY")
                return 1
            
            print("[OK] Connected to Gemini API\n")
        
        else:
            # Default: Local / OpenAI Compatible
            from gate.openai_compat import OpenAICompatGateway
            
            model_url = config.get("model_url", "http://localhost:1234/v1")
            model_name = config.get("model", "local-model")
            
            print(f"[LOCAL] Connecting to {model_url} ({model_name})")
            gateway = OpenAICompatGateway(
                base_url=model_url,
                model=model_name,
            )
            
            # Health check
            print("Checking model gateway...")
            healthy = await gateway.health_check()
            if not healthy:
                print(f"[ERROR] Cannot connect to model gateway at {model_url}")
                print(f"   Make sure your local server (Qwen/vLLM/etc) is running.")
                return 1
            
            print("[OK] Connected to local model\n")
            
    except Exception as e:
        print(f"[ERROR] Error connecting to gateway: {e}")
        return 1
    
    # Validation mode: Test embedding
    if args.test_embed:
        print(f"\n[TEST] Generating embedding for: '{args.test_embed}'")
        try:
            from gate.bases import EmbeddingGateway
            if isinstance(gateway, EmbeddingGateway):
                vec = await gateway.embed_single(args.test_embed)
                print(f"[OK] Generated vector: dim={len(vec)}, sample={vec[:3]}...")
                return 0
            else:
                print(f"[ERROR] Gateway {type(gateway).__name__} does not support embeddings")
                return 1
        except Exception as e:
            print(f"[ERROR] Embedding failed: {e}")
            return 1
            
    if args.promote:
        print(f"\n[PROMOTION] Applying spec: {args.promote}")
        try:
            from tool.promote import PromotionManager
            manager = PromotionManager(project_root=".")
            report = manager.apply_spec(args.promote)
            print(report)
            return 0
        except Exception as e:
            print(f"[ERROR] Promotion failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    # Create tool registry
    tools = create_default_registry(config)
    print(f"[OK] Loaded {tools.count} tools: {', '.join(tools.list())}")
    
    # Build chunk index for search_chunks tool (Phase 0.6)
    # Only index project code, NOT workspace (to avoid indexing random files)
    chunk_tool = tools.get("search_chunks")
    if chunk_tool:
        project_root = Path(__file__).parent
        # Index only specific project directories, not workspace
        project_dirs = ["tool", "core", "flow", "boot", "store", "gate", "model"]
        for subdir in project_dirs:
            subdir_path = project_root / subdir
            if subdir_path.exists():
                chunk_tool.chunk_manager.ingest_directory(str(subdir_path))
        chunk_tool.chunk_manager.save_manifest()
        stats = chunk_tool.chunk_manager.get_stats()
        print(f"[OK] Indexed {stats['total_chunks']} code chunks for search (project code only)")
    
    # Create rule engine
    rules = get_default_engine()
    print("[OK] Loaded safety rules\n")
    
    # Create agent loop
    loop = AgentLoop(
        gateway=gateway,
        tools=tools,
        rule_engine=rules,
        max_steps=config["max_steps"],
        temperature=config["temperature"],
    )
    
    # Create state
    conversation_id = str(uuid.uuid4())
    state = AgentState(
        conversation=ConversationState(id=conversation_id),
        execution=ExecutionContext(
            run_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            max_steps=config["max_steps"],
        ),
    )
    
    # Add system message
    from core.types import Message
    from core.context import get_workspace_context
    
    # Build workspace context for prompt injection (Phase 2)
    project_context = get_workspace_context("workspace")
    print(f"[OK] Built workspace context: {len(project_context.get('data_files', []))} data files, {len(project_context.get('standard_dirs', []))} dirs")
    
    # Cleanup stale tasks on startup (Phase 6)
    try:
        from core.taskqueue import TaskQueue
        queue = TaskQueue()
        cleanup_counts = queue.cleanup_stale_tasks()
        if any(cleanup_counts.values()):
            print(f"[OK] Queue cleanup: {cleanup_counts}")
    except Exception as e:
        print(f"[WARN] Queue cleanup skipped: {e}")
    
    system_prompt = create_system_prompt(tools.get_tool_definitions(), project_context=project_context)
    state.conversation.add_message(Message(
        role=MessageRole.SYSTEM,
        content=system_prompt,
    ))
    
    print("Ready! Start chatting:\n")
    
    # Autonomous mode tracking
    auto_continue_prompt = None  # If set, auto-send this instead of waiting for user
    
    # States that require user input (true blockers - VERY restrictive)
    # Only block when agent EXPLICITLY asks for user input
    BLOCKER_PATTERNS = [
        "please specify which",  # Disambiguation
        "which would you prefer",
        "awaiting your input",
        "please clarify your",
        "need you to choose",
    ]
    
    def is_blocker(response_text: str) -> bool:
        """Check if response indicates a true blocker needing user input.
        
        Very restrictive - only blocks on explicit user input requests.
        Normal errors like 'not found' should self-recover.
        """
        text_lower = response_text.lower()
        return any(pattern in text_lower for pattern in BLOCKER_PATTERNS)
    
    def check_queue_pending() -> bool:
        """Check if there are pending tasks in the queue."""
        try:
            from core.taskqueue import TaskQueue
            queue = TaskQueue()
            pending = queue.list_tasks(status="queued")
            return len(pending) > 0
        except:
            return False
    
    # Chat loop
    while True:
        try:
            # Check for auto-continue or get user input
            if auto_continue_prompt:
                user_input = auto_continue_prompt
                auto_continue_prompt = None
                print(f"You: [auto-continue] {user_input[:50]}...")
            else:
                user_input = input("You: ").strip()
            
            if not user_input:
                # Check if queue has pending tasks
                if check_queue_pending():
                    auto_continue_prompt = "Continue with the next queued task. Use queue_next."
                    print("\n[AUTO] Pending queue tasks detected, continuing...")
                continue
            
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\nGoodbye!")
                break
            
            # Run agent
            print("\nAgent: ", end="", flush=True)
            
            result = await loop.run(state, user_input)
            
            if result.success:
                print(result.final_answer)
                print(f"\n({result.steps_taken} steps)\n")
                
                # Check if we should auto-continue
                # 1. If queue has pending tasks and response doesn't indicate completion
                # 2. If there were tool errors (agent should self-correct)
                has_pending = check_queue_pending()
                
                # Check for tool errors in the response that are self-recoverable
                has_recoverable_error = any(phrase in result.final_answer.lower() for phrase in [
                    "invalid argument", "missing required", "failed to",
                    "error:", "exception:", "could not", 
                ])
                
                # Check if this is a true blocker
                is_blocked = is_blocker(result.final_answer)
                
                # PRIORITY: If queue has work, ALWAYS continue (even on errors)
                if has_pending:
                    # Queue has work - continue autonomously, highest priority
                    auto_continue_prompt = "Continue working. Check queue_next for pending tasks."
                    print("[AUTO] Queue has pending tasks, continuing...\n")
                elif has_recoverable_error:
                    # Tool error - agent should self-correct
                    auto_continue_prompt = "The previous tool call had an error. Review the error, fix it, and try again."
                    print("[AUTO] Recoverable error, self-correcting...\n")
                elif is_blocked:
                    # True blocker - wait for user (only if nothing else to do)
                    print("[BLOCKED] Agent needs clarification. Please provide input.\n")
                    
            else:
                print(f"Error: {result.error}\n")
                # On run error, let agent try to recover
                if "rate limit" not in str(result.error).lower():
                    auto_continue_prompt = f"The agent encountered an error: {result.error}. Please try a different approach."
            
            # Reset execution context for next turn
            state.execution = ExecutionContext(
                run_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                max_steps=config["max_steps"],
                available_tools=state.execution.available_tools,
            )
        
        except KeyboardInterrupt:
            print("\n\n[Interrupted] Type 'quit' to exit or continue chatting.")
            auto_continue_prompt = None  # Clear any auto-continue on interrupt
        except Exception as e:
            print(f"\n\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
    
    # Phase 5: Generate session summary before exit
    try:
        if state.execution.current_step > 0:  # Only if work was done
            print("\n[Generating session summary...]")
            summary_result = await loop.run(state, 
                "Briefly summarize this session in 2-3 sentences: what was accomplished, what's pending, key learnings. Be concise."
            )
            if summary_result.success:
                sessions_dir = Path("workspace/sessions")
                sessions_dir.mkdir(parents=True, exist_ok=True)
                (sessions_dir / "latest.md").write_text(
                    f"# Last Session Summary\n\n{summary_result.final_answer}\n",
                    encoding="utf-8"
                )
                print(f"[OK] Session summary saved")
    except Exception as e:
        print(f"[WARN] Could not save session summary: {e}")
    
    # Cleanup
    await gateway.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
