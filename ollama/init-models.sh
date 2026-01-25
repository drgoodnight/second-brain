#!/bin/bash
#
# Initialize Ollama models for Second Brain
# This script runs once on first setup to download the default model.
#

set -e

MODEL="${OLLAMA_MODEL:-gemma3:12b}"
OLLAMA_API="${OLLAMA_HOST:-ollama:11434}"

echo "╔════════════════════════════════════════════════════════╗"
echo "║     Ollama Model Initialization                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Model: $MODEL"
echo "Ollama API: $OLLAMA_API"
echo ""

# Wait for Ollama to be ready (with retry logic)
echo "Waiting for Ollama to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -sf "http://${OLLAMA_API}/api/tags" > /dev/null 2>&1; then
        echo "✓ Ollama is ready"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "  Waiting for Ollama... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
    sleep 5
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "❌ Ollama did not become ready in time"
    echo ""
    echo "You can manually pull the model later:"
    echo "  docker exec ollama ollama pull $MODEL"
    exit 1
fi

# Check if model already exists
echo ""
echo "Checking for existing model..."
if curl -sf "http://${OLLAMA_API}/api/tags" | grep -q "\"name\":\"${MODEL}\""; then
    echo "✓ Model $MODEL already downloaded"
    echo ""
    echo "To update the model, run:"
    echo "  docker exec ollama ollama pull $MODEL"
    exit 0
fi

# Pull the model
echo ""
echo "Downloading $MODEL..."
echo "This may take 10-30 minutes depending on your connection."
echo ""

# Use ollama CLI to pull (connects to the ollama service)
OLLAMA_HOST="http://${OLLAMA_API}" ollama pull "$MODEL"

echo ""
echo "════════════════════════════════════════════════════════"
echo "✓ Model $MODEL downloaded successfully!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Test with:"
echo "  curl http://localhost:11434/api/generate -d '{\"model\":\"$MODEL\",\"prompt\":\"Hello\"}'"
echo ""
