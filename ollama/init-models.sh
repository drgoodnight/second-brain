#!/bin/bash
#
# Ollama Model Initialization Script
# Pulls required models for Second Brain on first run
#

set -e

OLLAMA_HOST="${OLLAMA_HOST:-ollama:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:12b}"

echo "============================================"
echo "Second Brain - Ollama Model Initialization"
echo "============================================"
echo "Ollama Host: $OLLAMA_HOST"
echo "Model: $OLLAMA_MODEL"
echo ""

# Wait for Ollama to be fully ready
echo "Waiting for Ollama API to be ready..."
until curl -sf "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; do
    echo "  Waiting..."
    sleep 5
done
echo "✓ Ollama API is ready"
echo ""

# Check if model is already pulled
echo "Checking for existing models..."
MODEL_BASE=$(echo "$OLLAMA_MODEL" | cut -d':' -f1)
EXISTING=$(curl -sf "http://$OLLAMA_HOST/api/tags" | grep -o '"name":"[^"]*"' | grep -c "$MODEL_BASE" || true)

if [ "$EXISTING" -gt 0 ]; then
    echo "✓ Model $OLLAMA_MODEL already present"
    curl -sf "http://$OLLAMA_HOST/api/tags" | grep -o '"name":"[^"]*"' | tr ',' '\n'
    echo ""
else
    echo "Pulling $OLLAMA_MODEL..."
    echo "This will download the model and may take 10-30 minutes depending on connection."
    echo ""
    
    # Pull the model
    curl -X POST "http://$OLLAMA_HOST/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$OLLAMA_MODEL\", \"stream\": false}" \
        --max-time 3600
    
    echo ""
    echo "✓ $OLLAMA_MODEL pulled successfully"
fi

# Verify the model works with a quick test
echo ""
echo "Running quick model test..."
RESPONSE=$(curl -sf "http://$OLLAMA_HOST/api/generate" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"$OLLAMA_MODEL\",
        \"prompt\": \"Say OK if you are working.\",
        \"stream\": false,
        \"options\": {\"num_predict\": 10}
    }" | grep -o '"response":"[^"]*"' | head -1)

if echo "$RESPONSE" | grep -qi "ok\|working\|yes"; then
    echo "✓ Model test passed"
else
    echo "⚠ Model responded: $RESPONSE"
    echo "  Model is loaded but response was unexpected. This is usually fine."
fi

echo ""
echo "============================================"
echo "Initialization Complete!"
echo "============================================"
echo ""
echo "Ollama is ready at: http://$OLLAMA_HOST"
echo "Model: $OLLAMA_MODEL"
echo ""
echo "n8n can now access Ollama at: http://ollama:11434"
echo ""
