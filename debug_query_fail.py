
import pytest
from pathlib import Path
from tool.vectorgit import VectorGit
import tempfile
import shutil

def reproduce_failure():
    # Mimic fixture
    tmp_path = Path(tempfile.mkdtemp())
    print(f"Temp path: {tmp_path}")
    
    try:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        
        # File 1
        (repo_dir / "db.py").write_text("""
def connect_db():
    print('Connecting to postgres')
    return True

def query_users():
    return 'SELECT * FROM users'
""")
        
        # File 2
        (repo_dir / "ui.py").write_text("""
def render_button():
    print('Rendering submit button')
    
def handle_click():
    print('Button clicked')
""")
        
        ws = tmp_path / "workspace"
        ws.mkdir()
        vg = VectorGit(workspace_path=str(ws))
        
        print("Ingesting...")
        count = vg.ingest(str(repo_dir))
        print(f"Ingested count: {count}")
        
        print(f"Chunks: {list(vg.chunk_manager.chunks.keys())}")
        
        # Query
        results = vg.query("postgres")
        print(f"Query results: {len(results)}")
        
        if len(results) == 0:
            print("FAILURE REPRODUCED")
        else:
            print("SUCCESS (Cannot reproduce)")
            
    finally:
        shutil.rmtree(tmp_path)

if __name__ == "__main__":
    reproduce_failure()
