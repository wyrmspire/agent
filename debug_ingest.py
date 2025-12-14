
import logging
import sys
from pathlib import Path
from store.chunks import ChunkManager

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger("store.chunks")

def debug_ingest_dir():
    print("DEBUG INGEST DIR STARTED")
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = Path(tmp) / "test_repo"
        repo_dir.mkdir()
        (repo_dir / "example.py").write_text("def hello():\n    print('Hello World')\n")
        (repo_dir / "README.md").write_text("# Title\nContent")
        
        subdir = repo_dir / "utils"
        subdir.mkdir()
        (subdir / "helper.py").write_text("class Helper:\n    pass\n")
        
        chunks_dir = Path(tmp) / "chunks"
        manifest = Path(tmp) / "manifest.json"
        
        cm = ChunkManager(str(chunks_dir), str(manifest))
        
        # Test ingest directory
        print(f"Ingesting directory: {repo_dir}")
        count = cm.ingest_directory(str(repo_dir), recursive=True)
        print(f"Ingested count: {count}")
        
        # List chunks
        print(f"Chunks in memory: {len(cm.chunks)}")
        for cid, meta in cm.chunks.items():
            print(f"  {cid}: {meta.source_path}")

if __name__ == "__main__":
    debug_ingest_dir()
