#!/usr/bin/env python3
"""
examples/phase08_demo.py - Phase 0.8 Demonstration

This script demonstrates the Phase 0.8A (VectorGit) and 
Phase 0.8B (Task Queue) features working together.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tool.vectorgit import VectorGit
from core.taskqueue import TaskQueue, Checkpoint
from datetime import datetime, timezone


async def demo_vectorgit():
    """Demonstrate VectorGit v0 capabilities."""
    print("\n" + "="*60)
    print("Phase 0.8A: VectorGit v0 Demo")
    print("="*60 + "\n")
    
    # Initialize VectorGit
    vg = VectorGit(workspace_path="/tmp/demo_workspace")
    
    # Ingest current project
    print("📥 Ingesting repository...")
    repo_path = Path(__file__).parent.parent
    count = vg.ingest(str(repo_path / "core"))
    print(f"✅ Ingested {count} chunks from core/\n")
    
    # Query for code
    print("🔍 Querying for 'TaskQueue'...")
    results = vg.query("TaskQueue", top_k=3)
    print(f"Found {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        print(f"[{i}] {result['source_path']} (lines {result['start_line']}-{result['end_line']})")
        print(f"    Chunk ID: {result['chunk_id']}")
        print(f"    Type: {result['chunk_type']}, Name: {result.get('name', 'N/A')}")
        print()


async def demo_task_queue():
    """Demonstrate Task Queue v0 capabilities."""
    print("\n" + "="*60)
    print("Phase 0.8B: Task Queue v0 Demo")
    print("="*60 + "\n")
    
    # Initialize TaskQueue
    queue = TaskQueue(workspace_path="/tmp/demo_workspace")
    
    # Add tasks
    print("📝 Adding tasks to queue...\n")
    
    task_ids = []
    for i in range(1, 4):
        task_id = queue.add_task(
            objective=f"Process batch {i} of data",
            inputs=[f"data_batch_{i}.csv"],
            acceptance=f"Batch {i} processed successfully",
            max_tool_calls=10,
            max_steps=5,
        )
        task_ids.append(task_id)
        print(f"✅ Added {task_id}: Process batch {i}")
    
    print()
    
    # Process tasks one by one
    print("⚙️  Processing tasks sequentially...\n")
    
    for i in range(3):
        # Get next task
        task = queue.get_next()
        if not task:
            print("No more tasks in queue")
            break
        
        print(f"📋 Working on {task.task_id}: {task.objective}")
        
        # Simulate work
        await asyncio.sleep(0.1)
        
        # Mark as done with checkpoint
        checkpoint = Checkpoint(
            task_id=task.task_id,
            what_was_done=f"Processed {task.objective}",
            what_changed=[f"output_{i+1}.csv"],
            what_next="Process next batch" if i < 2 else "All batches complete",
            blockers=[],
            citations=[f"chunk_abc{i+1}"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        queue.mark_done(task.task_id, checkpoint)
        print(f"✅ Completed {task.task_id}\n")
    
    # Show stats
    stats = queue.get_stats()
    print("📊 Queue Statistics:")
    print(f"   Total tasks: {stats['total_tasks']}")
    print(f"   Queued: {stats['status_counts']['queued']}")
    print(f"   Running: {stats['status_counts']['running']}")
    print(f"   Done: {stats['status_counts']['done']}")
    print(f"   Failed: {stats['status_counts']['failed']}")
    print()
    
    # Show checkpoints
    print("📄 Checkpoints created:")
    checkpoint_dir = Path(queue.checkpoints_dir)
    for checkpoint_file in checkpoint_dir.glob("*.md"):
        print(f"   - {checkpoint_file.name}")


async def main():
    """Run both demos."""
    print("\n" + "="*60)
    print("Phase 0.8 Complete Demo")
    print("VectorGit v0 + Task Queue v0")
    print("="*60)
    
    # Demo VectorGit
    await demo_vectorgit()
    
    # Demo Task Queue
    await demo_task_queue()
    
    print("\n" + "="*60)
    print("✅ Phase 0.8 Demo Complete!")
    print("="*60 + "\n")
    
    print("Key Takeaways:")
    print("  • VectorGit provides deterministic code chunking and retrieval")
    print("  • Task Queue enables bounded execution with resume capability")
    print("  • Both systems work independently and complement each other")
    print("  • Ready for Phase 0.9: Vector embeddings + semantic search\n")


if __name__ == "__main__":
    asyncio.run(main())
