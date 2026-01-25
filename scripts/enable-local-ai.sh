#!/bin/bash
#
# Enable Local AI Module (Ollama + Gemma 3)
# 
# This script sets up the optional local AI for Second Brain.
# Requires: NVIDIA GPU with 12GB+ VRAM
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "╔════════════════════════════════════════════════════════╗"
echo "║     Second Brain - Local AI Module Setup               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check for NVIDIA GPU
echo "Checking for NVIDIA GPU..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found. Please install NVIDIA drivers."
    exit 1
fi

GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true)
if [ -z "$GPU_INFO" ]; then
    echo "❌ No NVIDIA GPU detected."
    exit 1
fi

echo "✓ Found GPU: $GPU_INFO"

# Check VRAM
VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
VRAM_GB=$((VRAM_MB / 1024))
echo "  VRAM: ${VRAM_GB}GB"

if [ "$VRAM_GB" -lt 12 ]; then
    echo ""
    echo "⚠ Warning: Less than 12GB VRAM detected."
    echo "  Gemma 3 12B Q8_0 requires ~12GB VRAM."
    echo "  Consider using a smaller quantization (Q4_K_M)."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for NVIDIA Container Toolkit
echo ""
echo "Checking NVIDIA Container Toolkit..."
if ! docker info 2>/dev/null | grep -q "Runtimes.*nvidia"; then
    echo "❌ NVIDIA Container Toolkit not configured for Docker."
    echo ""
    echo "Install with:"
    echo "  distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)"
    echo "  curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -"
    echo "  curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | \\"
    echo "      sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
    echo "  sudo apt update && sudo apt install -y nvidia-container-toolkit"
    echo "  sudo nvidia-ctk runtime configure --runtime=docker"
    echo "  sudo systemctl restart docker"
    echo ""
    exit 1
fi
echo "✓ NVIDIA Container Toolkit configured"

# Test Docker GPU access
echo ""
echo "Testing Docker GPU access..."
if ! docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi &> /dev/null; then
    echo "❌ Docker cannot access GPU."
    echo "  Try: sudo systemctl restart docker"
    exit 1
fi
echo "✓ Docker can access GPU"

# Create data directory
echo ""
echo "Creating Ollama data directory..."
mkdir -p "$PROJECT_ROOT/data/ollama"
echo "✓ Created data/ollama"

# Ensure ollama directory and scripts exist
echo ""
echo "Setting up Ollama configuration..."
mkdir -p "$PROJECT_ROOT/ollama"

if [ ! -f "$PROJECT_ROOT/ollama/init-models.sh" ]; then
    echo "❌ ollama/init-models.sh not found."
    echo "  Please ensure the ollama/ directory is properly set up."
    exit 1
fi
chmod +x "$PROJECT_ROOT/ollama/init-models.sh"
echo "✓ Configuration files ready"

# Check docker-compose.ollama.yml exists
if [ ! -f "$PROJECT_ROOT/docker-compose.ollama.yml" ]; then
    echo "❌ docker-compose.ollama.yml not found."
    echo "  Please ensure the file exists in the project root."
    exit 1
fi

# Add Ollama environment variables to .env if not present
echo ""
echo "Updating .env file..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    if ! grep -q "OLLAMA_HOST" "$PROJECT_ROOT/.env"; then
        echo "" >> "$PROJECT_ROOT/.env"
        echo "# ═══════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
        echo "# LOCAL AI (OLLAMA)" >> "$PROJECT_ROOT/.env"
        echo "# ═══════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
        echo "OLLAMA_HOST=ollama" >> "$PROJECT_ROOT/.env"
        echo "OLLAMA_PORT=11434" >> "$PROJECT_ROOT/.env"
        echo "OLLAMA_MODEL=gemma3:12b" >> "$PROJECT_ROOT/.env"
        echo "OLLAMA_NUM_PARALLEL=2" >> "$PROJECT_ROOT/.env"
        echo "OLLAMA_FLASH_ATTENTION=1" >> "$PROJECT_ROOT/.env"
        echo "✓ Added Ollama variables to .env"
    else
        echo "✓ Ollama variables already in .env"
    fi
else
    echo "⚠ No .env file found. Create one from .env.example first."
    exit 1
fi

# Network will be created by main docker-compose.yml
echo ""
echo "✓ Configuration ready"

# Start Ollama
echo ""
echo "════════════════════════════════════════════════════════"
echo "Ready to start Ollama!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "This will:"
echo "  1. Start the Ollama container with GPU access"
echo "  2. Download Gemma 3 12B (~12GB, may take 10-30 minutes)"
echo "  3. Run a quick test to verify it works"
echo ""
read -p "Start Ollama now? (Y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo ""
    echo "To start later, run:"
    echo "  cd $PROJECT_ROOT"
    echo "  docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d"
    exit 0
fi

cd "$PROJECT_ROOT"

echo ""
echo "Starting Ollama..."
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama

echo ""
echo "Waiting for Ollama to be ready..."
sleep 10

# Check if healthy
for i in {1..30}; do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✓ Ollama is running"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

# Start model initialization
echo ""
echo "Starting model download (this may take 10-30 minutes)..."
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up ollama-init

echo ""
echo "════════════════════════════════════════════════════════"
echo "                  Setup Complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Ollama is running at: http://localhost:11434"
echo "Model: gemma3:12b (or as configured in .env)"
echo ""
echo "Next steps:"
echo "  1. Read ollama/N8N_OLLAMA_CONFIG.md for n8n setup"
echo "  2. Update your n8n workflows to use Ollama"
echo "  3. Test with:"
echo "     curl http://localhost:11434/api/generate -d '{\"model\":\"gemma3:12b\",\"prompt\":\"Hello\"}'"
echo ""
echo "To run Second Brain with local AI:"
echo "  docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d"
echo ""
echo "To stop only Ollama:"
echo "  docker compose -f docker-compose.yml -f docker-compose.ollama.yml stop ollama"
echo ""
