# Clawdbot Security Hardening Guide for Second Brain

## Overview

This guide covers integrating Clawdbot into your Second Brain system with proper security hardening for use with local Ollama/Gemma 3 12B.

**Key Principle:** Gemma 3 12B has weaker prompt injection resistance than frontier models. We restrict dangerous tools and rely on tool deny lists for security (sandbox disabled due to Docker-in-Docker limitations).

---

## Quick Start

```bash
# Run the setup script
./scripts/setup-clawdbot.sh
```

The script handles everything: cloning source, building Docker image, creating config, and starting Clawdbot.

---

## Architecture

```
SimpleX App → SimpleX Bridge → n8n → Clawdbot Gateway → Ollama (Gemma 3 12B)
                                         ↓
                                   HTTP API (/v1/chat/completions)
```

Clawdbot runs as an internal service on `second-brain-net`. It's invoked by n8n via HTTP API for AI reasoning tasks, not as a standalone messaging endpoint.

---

## Configuration Schema (Important!)

Clawdbot's config schema is **strict**. Here are the gotchas we discovered:

| Issue | Wrong | Correct |
|-------|-------|---------|
| CPU limit | `"cpus": "1.0"` | `"cpus": 1.0` (number, not string) |
| Bind address | `"bind": "0.0.0.0"` | `"bind": "lan"` (enum only) |
| Tools location | `agents.defaults.tools` | `agents.list[].tools` |
| Channels disable | `"enabled": false` | Just omit the channel |
| Model config | Root-level `"model"` | `agents.defaults.model` or `models.providers` |
| Memory config | Root-level `"memory"` | Not a config key - memory is a plugin |
| Session pruning | `"session.pruning"` | Does not exist |
| Ollama baseUrl | `http://ollama:11434` | `http://ollama:11434/v1` (needs /v1) |
| Ollama API | (missing) | `"api": "openai-completions"` (required) |
| Ollama auth | (missing) | `"apiKey": "ollama-local"` (dummy value required) |
| Context window | `8192` | `32000` (minimum 16000 required) |

### Valid `gateway.bind` Values

- `"auto"` - Automatic detection
- `"lan"` - Local network (recommended for Docker)
- `"loopback"` - localhost only
- `"tailnet"` - Tailscale network
- `"custom"` - Custom binding

---

## Working Configuration

### clawdbot.json

```json
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
```

### docker-compose.clawdbot.yml

```yaml
# Clawdbot integration for Second Brain
# Built from source: https://github.com/clawdbot/clawdbot
#
# Usage: docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d

services:
  clawdbot-gateway:
    image: clawdbot:local
    container_name: clawdbot-gateway
    restart: unless-stopped
    environment:
      - HOME=/home/node
      - NODE_ENV=production
      - CLAWDBOT_CONFIG_PATH=/config/clawdbot.json
      - CLAWDBOT_STATE_DIR=/state
      - CLAWDBOT_WORKSPACE_DIR=/workspace
      - CLAWDBOT_GATEWAY_TOKEN=${CLAWDBOT_GATEWAY_TOKEN:?Required}
      - CLAWDBOT_HOOKS_TOKEN=${CLAWDBOT_HOOKS_TOKEN}
      - CLAWDBOT_DISABLE_BONJOUR=1
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      - TZ=${TZ:-Europe/London}
    volumes:
      - ./data/clawdbot/config:/config:ro
      - ./data/clawdbot/state:/state
      - ./data/clawdbot/workspace:/workspace
      - ./data/vault:/vault:ro
    networks:
      - second-brain-net
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:18789/__clawdbot__/canvas/ | grep -q Clawdbot"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    command:
      [
        "node",
        "dist/index.js",
        "gateway",
        "--bind",
        "lan",
        "--port",
        "18789"
      ]

networks:
  second-brain-net:
    name: second-brain-net
    driver: bridge
```

**Important Notes:**
- No `external: true` for network - it's defined in main compose file
- `--bind lan` not `--bind 0.0.0.0`
- Healthcheck uses `/__clawdbot__/canvas/` (no `/health` endpoint)
- No memory limits - Clawdbot needs ~2GB+ RAM or it OOMs

---

## Security Settings Explained

### Tools Configuration

| Tool | Status | Why |
|------|--------|-----|
| `read` | ✅ ALLOW | Read files in workspace |
| `write` | ❌ DENY | File modification |
| `edit` | ❌ DENY | File editing |
| `apply_patch` | ❌ DENY | Code patching |
| `exec` | ❌ DENY | Shell execution |
| `process` | ❌ DENY | Process management |
| `browser` | ❌ DENY | Browser automation |
| `web_search` | ❌ DENY | Exfiltration risk |
| `web_fetch` | ❌ DENY | Fetch external content |
| `elevated` | ❌ DENY | Host-level access |

**Note:** `memory` tool was removed from allow list as it's a plugin that may not be enabled.

### Sandbox Configuration

Sandbox is **disabled** (`"mode": "off"`) because:
- Clawdbot runs inside Docker
- Docker-in-Docker requires privileged mode (security risk)
- Tool deny list provides security instead

### Channels

All messaging channels (WhatsApp, Telegram, Discord, etc.) are **disabled by omission**. Your SimpleX interface handles all user interaction through n8n.

---

## n8n Integration

Clawdbot exposes an **OpenAI-compatible HTTP API** for easy integration with n8n.

### HTTP Request Node Configuration

| Setting | Value |
|---------|-------|
| Method | `POST` |
| URL | `http://clawdbot-gateway:18789/v1/chat/completions` |
| Authentication | Header Auth |
| Header 1 | `Authorization: Bearer <CLAWDBOT_GATEWAY_TOKEN>` |
| Header 2 | `x-clawdbot-agent-id: second-brain` |
| Header 3 | `Content-Type: application/json` |

### Request Body

```json
{
  "model": "clawdbot",
  "messages": [
    {
      "role": "user",
      "content": "={{ $json.message }}"
    }
  ],
  "user": "={{ $json.sender_id || $json.contactId || 'simplex-user' }}"
}
```

The `user` field provides session persistence - same user ID = same conversation context.

### Response Format

```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "clawdbot",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The response text here"
      },
      "finish_reason": "stop"
    }
  ]
}
```

### Extract Response (Code Node)

```javascript
const response = $input.first().json;
const content = response.choices?.[0]?.message?.content || "Sorry, I couldn't process that.";

return [{
  json: {
    reply: content
  }
}];
```

---

## Workspace Files (System Prompt)

Clawdbot uses markdown files in the workspace for system prompts:

### AGENTS.md

```markdown
# Second Brain Assistant

You are a helpful AI assistant integrated into a personal Second Brain system.

## Your Capabilities
- Complex reasoning and analysis
- Answering questions thoughtfully
- Helping with planning and decision-making

## Guidelines
- Keep responses focused and helpful
- Ask clarifying questions when needed
- Be honest when you don't know something
```

### MEMORY.md

```markdown
# Memory

## User Information
- (Add remembered facts here)

## Important Notes
- (Important information goes here)
```

Location: `data/clawdbot/workspace/second-brain/`

---

## File Permissions

```bash
# Required for security audit to pass
chmod 700 data/clawdbot/config
chmod 600 data/clawdbot/config/clawdbot.json
chmod 700 data/clawdbot/state
chmod 755 data/clawdbot/workspace
```

---

## Building from Source

Clawdbot doesn't have an official Docker image yet. Build locally:

```bash
# Clone
git clone https://github.com/clawdbot/clawdbot.git ~/projects/clawdbot

# Build (takes 5-10 minutes)
cd ~/projects/clawdbot
docker build -t clawdbot:local .
```

---

## Useful Commands

```bash
# Start
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway

# Stop
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml stop clawdbot-gateway

# Logs
docker logs -f clawdbot-gateway

# Status
docker exec clawdbot-gateway node dist/index.js status

# Rebuild after source update
cd ~/projects/clawdbot && git pull && docker build -t clawdbot:local .
```

---

## Testing the API

```bash
TOKEN=$(grep CLAWDBOT_GATEWAY_TOKEN ~/projects/second-brain/.env | cut -d= -f2)

docker exec clawdbot-gateway curl -sS http://localhost:18789/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "x-clawdbot-agent-id: second-brain" \
  -d '{
    "model": "clawdbot",
    "messages": [{"role":"user","content":"Hello!"}]
  }'
```

Expected response:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you today?"
    }
  }]
}
```

---

## Troubleshooting

### Config Invalid Errors

Check the [Configuration Schema](#configuration-schema-important) section. Most common issues:
- `cpus` as string instead of number
- Invalid `bind` value (must be enum)
- `tools` in wrong location
- Missing `api` or `apiKey` in Ollama provider
- `contextWindow` below 16000

### Out of Memory

Don't set memory limits in docker-compose. Clawdbot needs 2GB+ RAM.

### "Unhandled API in mapOptionsForApi: undefined"

Missing `api` field in Ollama provider config. Add:
```json
"api": "openai-completions"
```

### "No API key found for provider ollama"

Add dummy API key to Ollama provider:
```json
"apiKey": "ollama-local"
```

### "Model context window too small"

Increase `contextWindow` to at least 16000 (we use 32000).

### Gateway Token Mismatch

Ensure `CLAWDBOT_GATEWAY_TOKEN` in `.env` matches what the container sees:
```bash
docker exec clawdbot-gateway printenv | grep CLAWDBOT_GATEWAY_TOKEN
```

### "spawn docker EACCES"

Sandbox is trying to use Docker-in-Docker. Set `sandbox.mode: "off"`.

---

## Security Checklist

- [x] Config file permissions are 600
- [x] All messaging channels disabled (omitted from config)
- [x] Sandbox mode is "off" (Docker-in-Docker not supported)
- [x] Dangerous tools in deny list
- [x] elevated.enabled is false
- [x] No ports exposed to host (internal network only)
- [x] Gateway auth mode is "token"
- [x] controlUi is disabled
- [x] HTTP API enabled for n8n only

---

*Last updated: January 2026*
