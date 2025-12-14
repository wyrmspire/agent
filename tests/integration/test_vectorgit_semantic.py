import asyncio
import shutil
import unittest
import os
import sys
from pathlib import Path

# Fix import path
sys.path.append(str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from tool.vectorgit import VectorGit
from gate.gemini import GeminiGateway

# Load env from .env in project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

class TestVectorGitIntegration(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("workspace/test_vectorgit")
        self.data_dir = self.workspace / "data"
        self.repo_dir = self.workspace / "repo"
        
        # Cleanup
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dummy repo files
        (self.repo_dir / "payment.py").write_text("def process_payment(amount: float):\n    print('Processing payment')\n")
        (self.repo_dir / "auth.py").write_text("def login(user, password):\n    pass\n")
        
        self.api_key = os.getenv("GEMINI_API_KEY")

    def test_semantic_workflow(self):
        """Test ingest -> embed -> search workflow."""
        if not self.api_key:
            print("Skipping test_semantic_workflow: No GEMINI_API_KEY")
            return
            
        async def run_test():
            # 1. Setup components
            gateway = GeminiGateway(api_key=self.api_key)
            vg = VectorGit(workspace_path=str(self.workspace))
            
            # 2. Ingest
            count = await vg.ingest_async(str(self.repo_dir), gateway=gateway)
            self.assertEqual(count, 2)
            
            # 3. Verify storage
            self.assertTrue((vg.index_dir / "vectors" / "embeddings.npz").exists())
            self.assertTrue((vg.index_dir / "vectors" / "vectors_manifest.json").exists())
            
            # 4. Semantic Search
            # Try a very obvious query first: "password"
            results = await vg.query_async("password", gateway=gateway, top_k=2)
            
            print("\nQuery: 'password'")
            for r in results:
                print(f"  {r['source_path']}: {r.get('score', 0):.4f}")
                
            self.assertTrue(len(results) > 0)
            self.assertIn("auth.py", results[0]["source_path"])
            
            # Now try "payment"
            results = await vg.query_async("payment", gateway=gateway, top_k=2)
            print("\nQuery: 'payment'")
            for r in results:
                print(f"  {r['source_path']}: {r.get('score', 0):.4f}")
            
            self.assertIn("payment.py", results[0]["source_path"])
            
        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
