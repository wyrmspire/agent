#!/usr/bin/env python3
"""
vectorgit.py - VectorGit CLI

Entry point for the VectorGit durable memory system.
Usage:
    python vectorgit.py ingest <path>
    python vectorgit.py query "<query>" --topk 8
    python vectorgit.py explain "<question>" --topk 8
"""

import argparse
import sys
import asyncio
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tool.vectorgit import VectorGit
from boot.setup import load_config, setup_logging


async def main():
    """Main CLI entry point."""
    setup_logging()
    config = load_config()
    
    parser = argparse.ArgumentParser(description="VectorGit: Durable Memory for Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest repository into memory")
    ingest_parser.add_argument("path", help="Path to repository or file")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query memory (keyword search)")
    query_parser.add_argument("query", help="Search query")
    query_parser.add_argument("--topk", type=int, default=8, help="Number of results")
    
    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain concepts using memory")
    explain_parser.add_argument("question", help="Question to answer")
    explain_parser.add_argument("--topk", type=int, default=8, help="Number of chunks to retrieve")
    explain_parser.add_argument("--gemini", action="store_true", help="Use Gemini API")
    explain_parser.add_argument("--mock", action="store_true", help="Use Mock Gateway")
    
    args = parser.parse_args()
    
    # Initialize VectorGit
    vg = VectorGit()
    
    if args.command == "ingest":
        try:
            count = vg.ingest(args.path)
            print(f"✅ Ingested {count} chunks from {args.path}")
        except Exception as e:
            print(f"❌ Ingest failed: {e}")
            return 1
            
    elif args.command == "query":
        try:
            results = vg.query(args.query, top_k=args.topk)
            print(f"Found {len(results)} results for '{args.query}':\n")
            
            for i, res in enumerate(results, 1):
                print(f"[{i}] {res['source_path']} (lines {res['start_line']}-{res['end_line']})")
                print(f"    ID: {res['chunk_id']}")
                # Print a small snippet/preview
                snippet = res['content'].replace('\n', ' ')[:100]
                print(f"    Content: {snippet}...")
                print()
        except Exception as e:
            print(f"❌ Query failed: {e}")
            return 1
            
    elif args.command == "explain":
        try:
            # Setup gateway
            if args.mock:
                from gate.mock import MockGateway
                gateway = MockGateway()
            elif args.gemini or config.get("gateway") == "gemini":
                from gate.gemini import GeminiGateway
                api_key = config.get("gemini_api_key")
                if not api_key:
                    print("❌ GEMINI_API_KEY not found")
                    return 1
                gateway = GeminiGateway(api_key=api_key, model=config.get("gemini_model"))
            else:
                 # Default: local model server
                from gate.db import LMStudioGateway
                gateway = LMStudioGateway(
                    base_url=config.get("model_url"),
                    model=config.get("model"),
                )
            
            print(f"🤖 Generating explanation for: '{args.question}'...")
            answer = await vg.explain(args.question, gateway, top_k=args.topk)
            print("\nAnswer:\n")
            print(answer)
            print()
            
            await gateway.close()
            
        except Exception as e:
            print(f"❌ Explain failed: {e}")
            return 1
            
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nGoodbye!")
