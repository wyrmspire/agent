#!/bin/bash
# runsv.sh - Start model server and chat CLI
# Server runs in this terminal, chat opens in a new window

echo "🚀 Starting agent server + chat..."
echo ""

# Wait for server to be ready, then open chat CLI in a new terminal
(
    echo "⏳ Waiting for server to be ready..."
    # Wait up to 120 seconds for server to respond
    for i in {1..60}; do
        if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
            echo "✅ Server ready! Opening chat..."
            start bash -c "cd $(pwd) && python cli.py; echo ''; read -p 'Press Enter to close...'"
            exit 0
        fi
        sleep 2
    done
    echo "❌ Server didn't start in time"
) &

# Start server in current terminal (shows logs)
echo "📡 Server starting on http://localhost:8000"
echo "💬 Chat terminal will open when server is ready..."
echo ""
uvicorn servr.api:app --host 0.0.0.0 --port 8000

