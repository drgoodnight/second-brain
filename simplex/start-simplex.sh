#!/bin/bash
#
# SimpleX Chat CLI startup script
# Starts simplex-chat with WebSocket API enabled for n8n bridge integration
#

set -e

# Configuration from environment
SIMPLEX_PORT="${SIMPLEX_PORT:-5225}"
SIMPLEX_LOG_LEVEL="${SIMPLEX_LOG_LEVEL:-warn}"
SIMPLEX_DATA_DIR="${SIMPLEX_DATA_DIR:-/home/simplex/.simplex}"
SIMPLEX_DB_PREFIX="$SIMPLEX_DATA_DIR/simplex"

echo "============================================"
echo "SimpleX Chat CLI Starting"
echo "============================================"
echo "Port: $SIMPLEX_PORT"
echo "Log Level: $SIMPLEX_LOG_LEVEL"
echo "Data Dir: $SIMPLEX_DATA_DIR"
echo "DB Prefix: $SIMPLEX_DB_PREFIX"
echo "============================================"

# Ensure data directory exists
mkdir -p "$SIMPLEX_DATA_DIR"

# Check if profile exists
if [ -f "${SIMPLEX_DB_PREFIX}_chat.db" ]; then
    echo ""
    echo "✓ Profile found: ${SIMPLEX_DB_PREFIX}_chat.db"
    echo ""
    
    # SimpleX only listens on localhost, so we use socat to expose it
    # Start socat in background to proxy 0.0.0.0:5225 -> 127.0.0.1:5226
    INTERNAL_PORT=5226
    
    echo "Starting socat proxy: 0.0.0.0:$SIMPLEX_PORT -> 127.0.0.1:$INTERNAL_PORT"
    socat TCP-LISTEN:${SIMPLEX_PORT},fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:${INTERNAL_PORT} &
    SOCAT_PID=$!
    
    # Give socat a moment to start
    sleep 1
    
    echo "Starting SimpleX Chat on 127.0.0.1:$INTERNAL_PORT..."
    echo ""
    
    # Trap to clean up socat on exit
    trap "kill $SOCAT_PID 2>/dev/null" EXIT
    
    #Create the files folder to receive the voice messages

    mkdir -p "$SIMPLEX_DATA_DIR/files"

    # Start simplex-chat (it will bind to localhost:INTERNAL_PORT)
    exec /usr/local/bin/simplex-chat \
        -p "$INTERNAL_PORT" \
        -d "$SIMPLEX_DB_PREFIX" \
        --log-level "$SIMPLEX_LOG_LEVEL" \
        #--files-folder "$SIMPLEX_DATA_DIR/files" \
        -f 
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
    echo "║  3. Enter display name when prompted                       ║"
    echo "║                                                            ║"
    echo "║  4. Type /quit to exit                                     ║"
    echo "║                                                            ║"
    echo "║  5. docker compose up -d                                   ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    sleep 60
    exit 1
fi
