#!/bin/bash
# rungem.sh - Run agent with Gemini API
# Uses GEMINI_API_KEY from .env for faster development iteration

echo "🌟 Starting agent with Gemini API..."
echo ""

# Check if GEMINI_API_KEY is set in .env (not .env.example!)
if ! grep -q "GEMINI_API_KEY=" .env 2>/dev/null || [ -z "$(grep 'GEMINI_API_KEY=' .env | cut -d'=' -f2)" ]; then
    echo "❌ GEMINI_API_KEY not found in .env"
    echo "   Add: GEMINI_API_KEY=your_key_here"
    exit 1
fi

# Run CLI with --gemini flag
python cli.py --gemini
