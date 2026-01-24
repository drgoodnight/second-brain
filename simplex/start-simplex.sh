#!/bin/bash
#
# SimpleX Chat CLI startup script
# Starts simplex-chat with WebSocket API enabled for n8n bridge integration
#
# IMPORTANT: SimpleX requires interactive profile creation on first run.
# If no profile exists, this script will show instructions and wait.
#

set -e

# Configuration from environment
SIMPLEX_PORT="${SIMPLEX_PORT:-5225}"
SIMPLEX_LOG_LEVEL="${SIMPLEX_LOG_LEVEL:-warn}"
SIMPLEX_DATA_DIR="${SIMPLEX_DATA_DIR:-/home/simplex/.simplex}"
SIMPLEX_BOT_NAME="${SIMPLEX_BOT_NAME:-second-brain}"

# The -d flag is a database NAME PREFIX, not a directory!
# -d /home/simplex/.simplex/simplex creates:
#   /home/simplex/.simplex/simplex_chat.db
#   /home/simplex/.simplex/simplex_agent.db
SIMPLEX_DB_PREFIX="$SIMPLEX_DATA_DIR/simplex"

echo "============================================"
echo "SimpleX Chat CLI Starting"
echo "============================================"
echo "Port: $SIMPLEX_PORT"
echo "Log Level: $SIMPLEX_LOG_LEVEL"
echo "Data Dir: $SIMPLEX_DATA_DIR"
echo "DB Prefix: $SIMPLEX_DB_PREFIX"
echo "Bot Name: $SIMPLEX_BOT_NAME"
echo "============================================"

# Ensure data directory exists
mkdir -p "$SIMPLEX_DATA_DIR"

# Check if profile exists
if [ -f "${SIMPLEX_DB_PREFIX}_chat.db" ]; then
    echo ""
    echo "✓ Profile found: ${SIMPLEX_DB_PREFIX}_chat.db"
    echo ""
    echo "Starting SimpleX Chat with WebSocket API on port $SIMPLEX_PORT..."
    echo ""
    
    # Start simplex-chat with WebSocket API
    exec /usr/local/bin/simplex-chat \
        -p "$SIMPLEX_PORT" \
        -d "$SIMPLEX_DB_PREFIX" \
        --log-level "$SIMPLEX_LOG_LEVEL"
else
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           FIRST-TIME SETUP REQUIRED                        ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║  SimpleX requires interactive profile creation.            ║"
    echo "║                                                            ║"
    echo "║  Run these commands on your host:                          ║"
    echo "║                                                            ║"
    echo "║  1. docker compose stop simplex-chat-cli                   ║"
    echo "║                                                            ║"
    echo "║  2. docker compose run -it --rm simplex-chat-cli \\        ║"
    echo "║       simplex-chat -d /home/simplex/.simplex/simplex       ║"
    echo "║                                                            ║"
    echo "║  3. Enter display name when prompted: $SIMPLEX_BOT_NAME"
    echo "║                                                            ║"
    echo "║  4. Enable auto-accept for incoming connections:           ║"
    echo "║       /auto_accept on                                      ║"
    echo "║                                                            ║"
    echo "║  5. Type /address to get your connection link              ║"
    echo "║     (save this to connect from your phone)                 ║"
    echo "║                                                            ║"
    echo "║  6. Type /quit to exit                                     ║"
    echo "║                                                            ║"
    echo "║  7. docker compose up -d                                   ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Waiting for profile to be created..."
    echo "(This container will auto-restart and check again)"
    echo ""
    
    # Wait before exiting so docker doesn't restart-loop too fast
    sleep 60
    exit 1
fi