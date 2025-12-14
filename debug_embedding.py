import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from gate.gemini import GeminiGateway

# Load env from .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ No GEMINI_API_KEY in .env")
    exit(1)

async def main():
    print("🌟 Testing Gemini Embeddings...")
    gateway = GeminiGateway(api_key=api_key)
    
    texts = ["Hello world", "Vector search is cool"]
    try:
        embeddings = await gateway.embed(texts)
        print(f"✅ Generated {len(embeddings)} embeddings")
        print(f"   Vector dim: {len(embeddings[0])}")
        print(f"   Sample: {embeddings[0][:3]}...")
    except Exception as e:
        print(f"❌ Embedding failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
