
import asyncio
import os
import shutil
import tempfile
import random
from pathlib import Path
from datetime import datetime, timezone
import pytest

from core.taskqueue import TaskQueue, Checkpoint, TaskStatus
from core.patch import PatchManager
from tool.vectorgit import VectorGit
from store.chunks import ChunkManager

@pytest.fixture
def stress_env():
    """Create a temporary environment for stress testing."""
    tmp_dir = tempfile.mkdtemp()
    workspace = Path(tmp_dir)
    
    # Setup directories
    (workspace / "queue").mkdir()
    (workspace / "patches").mkdir()
    (workspace / "vectors").mkdir()
    
    # Create a dummy project structure
    project_root = workspace / "project"
    project_root.mkdir()
    (project_root / "src").mkdir()
    
    for i in range(10):
        (project_root / "src" / f"file_{i}.py").write_text(f"def func_{i}():\n    pass\n")
        
    yield {
        "root": tmp_dir,
        "workspace": str(workspace),
        "project": str(project_root)
    }
    
    shutil.rmtree(tmp_dir)

@pytest.mark.asyncio
async def test_queue_saturation(stress_env):
    """Stress test the TaskQueue with rapid add/next/done cycles."""
    print("\n[STRESS] Starting Queue Saturation Test...")
    
    queue = TaskQueue(workspace_path=stress_env["workspace"])
    num_tasks = 100
    
    # 1. Rapidly add tasks
    print(f"Adding {num_tasks} tasks...")
    for i in range(num_tasks):
        queue.add_task(
            objective=f"Stress Task {i}",
            inputs=[f"input_{i}"],
            acceptance="Done"
        )
    
    stats = queue.get_stats()
    assert stats["total_tasks"] == num_tasks
    assert stats["status_counts"]["queued"] == num_tasks
    print("All tasks queued successfully.")
    
    # 2. Process tasks sequentially (simulate worker)
    print("Processing tasks...")
    processed = 0
    while True:
        task = queue.get_next()
        if not task:
            break
        
        # Simulate quick work
        checkpoint = Checkpoint(
            task_id=task.task_id,
            what_was_done="stressed",
            what_changed=[],
            what_next="next",
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat()
        )
        queue.mark_done(task.task_id, checkpoint)
        processed += 1
        
        if processed % 20 == 0:
            print(f"Processed {processed}...")
            
    assert processed == num_tasks
    stats = queue.get_stats()
    assert stats["status_counts"]["done"] == num_tasks
    print("Queue Saturation Test PASSED.")

@pytest.mark.asyncio
async def test_vectorgit_ingest_stress(stress_env):
    """Stress test VectorGit ingestion with many files."""
    print("\n[STRESS] Starting VectorGit Ingest Stress Test...")
    
    project_root = Path(stress_env["project"])
    
    # Create 100 files
    print("Generating 100 source files...")
    for i in range(100):
        content = f"""
def function_{i}():
    '''Docstring for function {i}'''
    x = {i} * 2
    return x
"""
        (project_root / "src" / f"stress_{i}.py").write_text(content)
        
    vg = VectorGit(workspace_path=stress_env["workspace"])
    
    # Ingest
    print("Ingesting...")
    start_time = datetime.now()
    count = await vg.ingest_async(str(project_root))
    duration = (datetime.now() - start_time).total_seconds()
    
    print(f"Ingested {count} chunks in {duration:.2f}s")
    
    # Verify
    # Each file has 1 function -> 1 chunk approx
    assert count >= 100 
    
    # Search stress
    print("Running 50 queries...")
    for i in range(50):
        target = random.randint(0, 99)
        results = await vg.query_async(f"function_{target}")
        assert len(results) > 0
        assert f"function_{target}" in results[0]["snippet"]
        
    print("VectorGit Stress Test PASSED.")

@pytest.mark.asyncio
async def test_patch_conflict_stress(stress_env):
    """Test creating many patches, some conflicting."""
    print("\n[STRESS] Starting Patch Conflict Test...")
    
    # Correct instantiation
    pm = PatchManager(
        workspace_dir=stress_env["workspace"]
    )
    
    # 1. Create 10 valid patches
    print("Creating 10 patches...")
    patch_ids = []
    for i in range(10):
        diff = f"""--- a/src/file_0.py
+++ b/src/file_0.py
@@ -1,2 +1,3 @@
 def func_0():
     pass
+    # Comment {i}
"""
        # Correct arguments
        res = pm.create_patch(
            title=f"Patch {i}",
            description="desc",
            target_files=["src/file_0.py"],
            plan_content="plan",
            diff_content=diff,
            tests_content="test"
        )
        patch_ids.append(res.patch_id)
        
    assert len(pm.list_patches()) == 10
    print("Patches created.")
    
    # 2. Verify all are pending
    for pid in patch_ids:
        p = pm.get_patch(pid)
        assert p.status == "proposed"
        
    print("Patch Conflict Test PASSED.")

if __name__ == "__main__":
    # Allow running directly
    import pytest
    pytest.main([__file__, "-v"])
