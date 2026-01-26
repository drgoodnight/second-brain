#!/bin/bash
#
# Clawdbot Setup Script for Second Brain
# 
# This script will:
# 1. Clone and build Clawdbot from source (no official Docker image yet)
# 2. Create directory structure
# 3. Generate security tokens
# 4. Create configuration files
# 5. Start Clawdbot
#
# Usage: ./scripts/setup-clawdbot.sh
#
# Prerequisites:
# - Docker and Docker Compose
# - Your Second Brain stack running (second-brain-net network exists)
# - Ollama running
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CLAWDBOT_SOURCE_DIR="${CLAWDBOT_SOURCE_DIR:-$HOME/projects/clawdbot}"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Clawdbot Setup for Second Brain                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_ROOT"

# ============================================
# STEP 1: Pre-flight checks
# ============================================
echo -e "${YELLOW}[1/8] Running pre-flight checks...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi
echo "  ✓ Docker found"

# Check docker compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found.${NC}"
    exit 1
fi
echo "  ✓ Docker Compose found"

# Check git
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git not found. Please install git first.${NC}"
    exit 1
fi
echo "  ✓ Git found"

# Check if second-brain-net exists
if ! docker network inspect second-brain-net &> /dev/null; then
    echo -e "${RED}❌ Docker network 'second-brain-net' not found.${NC}"
    echo "  Please start your Second Brain stack first."
    exit 1
fi
echo "  ✓ second-brain-net network exists"

# Check if Ollama is running
if ! docker ps --format '{{.Names}}' | grep -q "^ollama$"; then
    echo -e "${YELLOW}⚠ Ollama container not running. Clawdbot will fail to start without it.${NC}"
    read -p "  Continue anyway? (y/N): " continue_without_ollama
    if [[ ! "$continue_without_ollama" =~ ^[Yy]$ ]]; then
        echo "  Please start Ollama first:"
        echo "  docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama"
        exit 1
    fi
else
    echo "  ✓ Ollama is running"
fi

echo -e "${GREEN}  Pre-flight checks passed!${NC}"
echo ""

# ============================================
# STEP 2: Clone/Update Clawdbot source
# ============================================
echo -e "${YELLOW}[2/8] Setting up Clawdbot source code...${NC}"

if [ -d "$CLAWDBOT_SOURCE_DIR" ]; then
    echo "  Found existing Clawdbot source at $CLAWDBOT_SOURCE_DIR"
    read -p "  Update to latest? (Y/n): " update_source
    if [[ ! "$update_source" =~ ^[Nn]$ ]]; then
        cd "$CLAWDBOT_SOURCE_DIR"
        git pull origin main
        echo "  ✓ Updated Clawdbot source"
    else
        echo "  ✓ Using existing source"
    fi
else
    echo "  Cloning Clawdbot repository..."
    mkdir -p "$(dirname "$CLAWDBOT_SOURCE_DIR")"
    git clone https://github.com/clawdbot/clawdbot.git "$CLAWDBOT_SOURCE_DIR"
    echo "  ✓ Cloned Clawdbot to $CLAWDBOT_SOURCE_DIR"
fi

cd "$PROJECT_ROOT"
echo ""

# ============================================
# STEP 3: Build Clawdbot Docker image
# ============================================
echo -e "${YELLOW}[3/8] Building Clawdbot Docker image (this may take 5-10 minutes)...${NC}"

# Check if image already exists
if docker images | grep -q "^clawdbot.*local"; then
    echo "  Found existing clawdbot:local image"
    read -p "  Rebuild? (y/N): " rebuild_image
    if [[ "$rebuild_image" =~ ^[Yy]$ ]]; then
        echo "  Building clawdbot:local from source..."
        docker build -t clawdbot:local -f "$CLAWDBOT_SOURCE_DIR/Dockerfile" "$CLAWDBOT_SOURCE_DIR"
        echo "  ✓ Built clawdbot:local"
    else
        echo "  ✓ Using existing image"
    fi
else
    echo "  Building clawdbot:local from source..."
    docker build -t clawdbot:local -f "$CLAWDBOT_SOURCE_DIR/Dockerfile" "$CLAWDBOT_SOURCE_DIR"
    echo "  ✓ Built clawdbot:local"
fi
echo ""

# ============================================
# STEP 4: Create directory structure
# ============================================
echo -e "${YELLOW}[4/8] Creating directory structure...${NC}"

mkdir -p "$PROJECT_ROOT/data/clawdbot/config"
mkdir -p "$PROJECT_ROOT/data/clawdbot/state"
mkdir -p "$PROJECT_ROOT/data/clawdbot/workspace/second-brain"

echo "  ✓ Created data/clawdbot/config"
echo "  ✓ Created data/clawdbot/state"
echo "  ✓ Created data/clawdbot/workspace"
echo ""

# ============================================
# STEP 5: Generate security tokens
# ============================================
echo -e "${YELLOW}[5/8] Generating security tokens...${NC}"

GATEWAY_TOKEN=$(openssl rand -hex 32)
HOOKS_TOKEN=$(openssl rand -hex 32)

# Check if tokens already exist in .env
if grep -q "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠ Clawdbot tokens already exist in .env${NC}"
    read -p "  Overwrite existing tokens? (y/N): " overwrite_tokens
    if [[ "$overwrite_tokens" =~ ^[Yy]$ ]]; then
        sed -i '/CLAWDBOT_GATEWAY_TOKEN/d' "$PROJECT_ROOT/.env"
        sed -i '/CLAWDBOT_HOOKS_TOKEN/d' "$PROJECT_ROOT/.env"
    else
        echo "  Keeping existing tokens."
        GATEWAY_TOKEN=$(grep "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" | cut -d= -f2)
        HOOKS_TOKEN=$(grep "CLAWDBOT_HOOKS_TOKEN" "$PROJECT_ROOT/.env" | cut -d= -f2)
    fi
fi

# Add tokens to .env if not already there
if ! grep -q "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo "" >> "$PROJECT_ROOT/.env"
    echo "# ══════════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
    echo "# CLAWDBOT INTEGRATION" >> "$PROJECT_ROOT/.env"
    echo "# ══════════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
    echo "CLAWDBOT_GATEWAY_TOKEN=$GATEWAY_TOKEN" >> "$PROJECT_ROOT/.env"
    echo "CLAWDBOT_HOOKS_TOKEN=$HOOKS_TOKEN" >> "$PROJECT_ROOT/.env"
    echo "  ✓ Added tokens to .env"
fi
echo ""

# ============================================
# STEP 6: Create clawdbot.json
# ============================================
echo -e "${YELLOW}[6/8] Creating clawdbot.json configuration...${NC}"

# NOTE: Clawdbot config schema is strict. Key learnings:
# - cpus must be a number (1.0), not a string ("1.0")
# - gateway.bind must be: "auto", "lan", "loopback", "tailnet", or "custom"
# - tools go in agents.list[].tools, NOT in agents.defaults.tools
# - channels don't have an "enabled" field - just omit them
# - "model" and "memory" are NOT root-level keys
# - "session.pruning" does not exist
# - Ollama provider needs: baseUrl with /v1 suffix, api: "openai-completions", apiKey (dummy)
# - contextWindow must be >= 16000 for Clawdbot
# - sandbox.mode: "off" when running in Docker (can't do Docker-in-Docker)
# - HTTP API must be enabled for n8n integration

cat > "$PROJECT_ROOT/data/clawdbot/config/clawdbot.json" << 'CLAWDBOT_CONFIG'
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "lan",
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    },
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  },

  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "authorization",
      "bearer"
    ]
  },

  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/gemma3:12b"
      },
      "workspace": "/workspace",
      "sandbox": {
        "mode": "off"
      }
    },
    "list": [
      {
        "id": "second-brain",
        "workspace": "/workspace/second-brain",
        "identity": {
          "name": "Second Brain Assistant",
          "emoji": "🧠"
        },
        "tools": {
          "profile": "minimal",
          "allow": [
            "read"
          ],
          "deny": [
            "write",
            "edit",
            "apply_patch",
            "exec",
            "process",
            "browser",
            "web_search",
            "web_fetch"
          ],
          "elevated": {
            "enabled": false
          }
        }
      }
    ]
  },

  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://ollama:11434/v1",
        "apiKey": "ollama-local",
        "api": "openai-completions",
        "models": [
          {
            "id": "gemma3:12b",
            "name": "Gemma 3 12B",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32000,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
CLAWDBOT_CONFIG

echo "  ✓ Created clawdbot.json"
echo ""

# ============================================
# STEP 7: Create workspace files
# ============================================
echo -e "${YELLOW}[7/8] Creating workspace files...${NC}"

# Create AGENTS.md for system prompt
cat > "$PROJECT_ROOT/data/clawdbot/workspace/second-brain/AGENTS.md" << 'AGENTS_MD'
# Second Brain Assistant

You are a helpful AI assistant integrated into a personal Second Brain system. You help the user with complex reasoning, analysis, and remembering information.

## Your Capabilities
- Complex reasoning and analysis
- Remembering information the user tells you
- Answering questions thoughtfully
- Helping with planning and decision-making

## Your Personality
- Friendly but concise
- Thoughtful and thorough when needed
- You remember what the user tells you across conversations

## Guidelines
- Keep responses focused and helpful
- Ask clarifying questions when needed
- Remember important information the user shares
- Be honest when you don't know something
AGENTS_MD

# Create MEMORY.md for persistent facts
cat > "$PROJECT_ROOT/data/clawdbot/workspace/second-brain/MEMORY.md" << 'MEMORY_MD'
# Memory

## User Information
- (Clawdbot will add remembered facts here)

## Important Notes
- (Important information goes here)
MEMORY_MD

echo "  ✓ Created AGENTS.md"
echo "  ✓ Created MEMORY.md"
echo ""

# ============================================
# STEP 8: Set permissions & start
# ============================================
echo -e "${YELLOW}[8/8] Setting permissions and starting Clawdbot...${NC}"

# Set permissions - IMPORTANT: 600 for config to pass security audit
chmod 700 "$PROJECT_ROOT/data/clawdbot/config"
chmod 600 "$PROJECT_ROOT/data/clawdbot/config/clawdbot.json"
chmod 700 "$PROJECT_ROOT/data/clawdbot/state"
chmod 755 "$PROJECT_ROOT/data/clawdbot/workspace"

echo "  ✓ Set restrictive permissions (600 for config)"

# Start with Ollama dependency
if docker ps --format '{{.Names}}' | grep -q "^ollama$"; then
    echo "  Starting with Ollama dependency..."
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway
else
    echo -e "${YELLOW}  ⚠ Ollama not running. Starting Clawdbot anyway (may fail)...${NC}"
    docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ Clawdbot may fail to start without Ollama running${NC}"
    }
fi

echo ""

# ============================================
# Verification
# ============================================
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    Setup Complete!                      ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Wait for container to start
echo "Waiting for Clawdbot to start..."
sleep 15

# Check if running
if docker ps --format '{{.Names}}' | grep -q "^clawdbot-gateway$"; then
    echo -e "${GREEN}✓ Clawdbot container is running${NC}"
    
    # Check canvas endpoint
    CANVAS=$(docker exec clawdbot-gateway curl -sf http://localhost:18789/__clawdbot__/canvas/ 2>/dev/null | grep -c "Clawdbot" || echo "0")
    if [ "$CANVAS" -gt 0 ]; then
        echo -e "${GREEN}✓ Clawdbot gateway is responding${NC}"
    else
        echo -e "${YELLOW}⚠ Gateway still starting (check logs)${NC}"
    fi
    
    # Test HTTP API
    TOKEN=$(grep "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" | cut -d= -f2)
    API_TEST=$(docker exec clawdbot-gateway curl -sS --max-time 30 http://localhost:18789/v1/chat/completions \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -H "x-clawdbot-agent-id: second-brain" \
      -d '{"model":"clawdbot","messages":[{"role":"user","content":"Say hi"}]}' 2>/dev/null | grep -c "choices" || echo "0")
    
    if [ "$API_TEST" -gt 0 ]; then
        echo -e "${GREEN}✓ HTTP API is working${NC}"
    else
        echo -e "${YELLOW}⚠ HTTP API not responding yet (may need more time)${NC}"
    fi
else
    echo -e "${RED}❌ Clawdbot container not running${NC}"
    echo "  Check logs: docker logs clawdbot-gateway"
fi

echo ""
echo "Configuration:"
echo "  • Clawdbot source:   $CLAWDBOT_SOURCE_DIR"
echo "  • Config file:       data/clawdbot/config/clawdbot.json"
echo "  • State directory:   data/clawdbot/state/"
echo "  • Workspace:         data/clawdbot/workspace/"
echo "  • Docker Compose:    docker-compose.clawdbot.yml"
echo ""
echo "Security Settings:"
echo "  • All channels:      DISABLED (using SimpleX via n8n)"
echo "  • Sandbox mode:      OFF (Docker-in-Docker not supported)"
echo "  • Dangerous tools:   BLOCKED (exec, write, browser, etc.)"
echo "  • HTTP API:          ENABLED for n8n integration"
echo ""
echo "n8n Integration:"
echo "  • URL:               http://clawdbot-gateway:18789/v1/chat/completions"
echo "  • Auth Header:       Authorization: Bearer <CLAWDBOT_GATEWAY_TOKEN>"
echo "  • Agent Header:      x-clawdbot-agent-id: second-brain"
echo ""
echo "Commands:"
echo "  • View logs:         docker logs -f clawdbot-gateway"
echo "  • Check status:      docker exec clawdbot-gateway node dist/index.js status"
echo "  • Restart:           docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml restart clawdbot-gateway"
echo "  • Stop:              docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml stop clawdbot-gateway"
echo ""
echo -e "${GREEN}Clawdbot is now integrated with your Second Brain! 🧠🦞${NC}"
echo ""
