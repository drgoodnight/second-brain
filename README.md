# Second Brain

A privacy-focused personal AI assistant that manages calendar, notes, and tasks through natural language via SimpleX Chat. All processing occurs on self-hosted infrastructure without cloud dependencies.

## Credits & Inspiration

This project is inspired by [Nate's Second Brain system](https://natesnewsletter.substack.com/p/grab-the-system-that-closes-open), which uses Zapier, Notion, and Slack to create a powerful thought capture system.

**Nate's Original Design:**
- 3 Zapier automations, 5 Notion databases, 1 Slack channel
- The Core Loop:
  1. Capture a thought in Slack (5 seconds)
  2. Zapier sends it to Claude/ChatGPT for classification
  3. AI returns structured JSON with category, fields, and confidence
  4. Zapier routes it to the correct Notion database
  5. Zapier replies in Slack confirming what it did
  6. Daily/weekly digests surface what matters

**This project adapts that concept for privacy-conscious self-hosters, and adds calendar management:**

| Nate's Stack | This Project | Benefit |
|--------------|--------------|---------|
| Slack | SimpleX Chat | End-to-end encrypted, no metadata |
| Zapier | n8n | Self-hosted, no cloud dependency |
| Notion | Obsidian API | Local markdown files, full ownership |
| Cloud AI | Local LLMs or cloud APIs | Optional fully local AI with Ollama |
| *(not included)* | Nextcloud Calendar | Full calendar management via natural language |

Same powerful workflow, plus calendar integration—everything runs on your own hardware.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/drgoodnight/second-brain.git
cd second-brain

# Make scripts executable
chmod +x scripts/*.sh
chmod +x simplex/start-simplex.sh

# Run setup
./scripts/setup.sh
```

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed installation instructions.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            SECOND BRAIN                 │
                         │                                         │
SimpleX Chat ──────────► │  n8n Hub                                │
  (Mobile/Desktop)       │    ├── Calendar Agent ──► Nextcloud     │
                         │    ├── Notes Agent ────► Obsidian API   │
                         │    ├── Search Agent ───► Obsidian API   │
                         │    └── Delete Agent ───► Obsidian API   │
                         │              │                          │
                         │              ▼                          │
                         │         ┌─────────┐                     │
                         │         │ Ollama  │ (optional)          │
                         │         │ Local AI│                     │
                         │         └─────────┘                     │
                         └─────────────────────────────────────────┘
                                    All Local / Self-Hosted
```

## Components

| Service | Port | Purpose |
|---------|------|---------|
| n8n | 5678 | Automation hub, workflow orchestration |
| Nextcloud | 8088 | Calendar (CalDAV) |
| Obsidian API | 8765 | Notes management (5 databases) |
| SimpleX Chat | 5225 | Encrypted messaging interface |
| SimpleX Bridge | - | Connects SimpleX ↔ n8n |
| Ollama | 11434 | Local AI inference (optional) |

---

## Features

### Calendar Management

| Command | Example |
|---------|---------|
| Query today | "what's on my calendar today?" |
| Query tomorrow | "tell me my schedule tomorrow" |
| Query specific date | "what's on the 9th Jan?" |
| Query this week | "what's on this week?" |
| Add event | "add meeting at 3pm tomorrow" |
| Add multiple | "add lunch at 1pm and meeting at 3pm" |
| Delete event | "cancel my 3pm meeting tomorrow" |

### Notes Management (Obsidian)

| Database | Purpose | Example |
|----------|---------|---------|
| People | Contact info | "add to Nikki she has good eye for photography" |
| Projects | Multi-step goals | "new project: Second Brain mobile app" |
| Ideas | Insights | "idea: AI-powered email sorter" |
| Admin | Tasks/todos | "task: renew passport by March" |
| Inbox Log | Audit trail | (automatic) |

### Delete with Confirmation

```
User: "delete photography"
System: "🔍 Found 3 matches:
         1. 👤 "Nikki" in people
         2. 💡 "photography NFT project" in ideas
         Reply with number (1-3) to delete, or 'cancel'."
User: "2"
System: "✅ Deleted: photography NFT project from ideas"
```

### Fix Misclassified Entries

When the AI isn't sure where something belongs, it goes to "Needs Review":

```
User: "fix: people"   → Moves last review item to People database
User: "fix: project"  → Moves last review item to Projects database
```

---

## Local AI Module (Optional)

For complete privacy, you can run AI inference locally using Ollama and Gemma 3 12B. This eliminates all external API calls.

### Requirements

- NVIDIA GPU with 12GB+ VRAM (e.g., RTX 4060 Ti 16GB, RTX 3080)
- NVIDIA Container Toolkit installed

### Quick Setup

```bash
# Enable local AI
./scripts/enable-local-ai.sh

# Run with local AI
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### Run Without Local AI (Cloud APIs)

```bash
# Standard startup (uses OpenAI or other cloud AI)
docker compose up -d
```

See [ollama/README.md](ollama/README.md) for detailed local AI setup instructions.

---

## Directory Structure

```
second-brain/
├── docker-compose.yml      # Core services
├── docker-compose.ollama.yml # Optional local AI overlay
├── .env.example            # Template (committed)
├── .env                    # Secrets (gitignored)
├── README.md
├── SETUP_GUIDE.md          # Detailed setup instructions
│
├── n8n-python/             # Custom n8n image with Python
│   └── Dockerfile
│
├── simplex/                # SimpleX Chat CLI
│   ├── Dockerfile
│   └── start-simplex.sh
│
├── obsidian-api/           # Notes API (FastAPI)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── ollama/                 # Local AI module (optional)
│   ├── README.md           # Quick start guide
│   ├── LOCAL_AI_SETUP.md   # Detailed setup
│   ├── N8N_OLLAMA_CONFIG.md # n8n workflow changes
│   ├── init-models.sh      # Model download script
│   └── prompts/
│       └── GEMMA3_PROMPTS.md
│
├── scripts/
│   ├── bridge.py           # SimpleX ↔ n8n connector
│   ├── setup.sh            # First-time setup
│   ├── backup.sh           # Backup script
│   ├── restore.sh          # Restore script
│   └── enable-local-ai.sh  # Local AI setup script
│
├── n8n/
│   └── workflows/          # Exported n8n workflow JSONs
│
└── data/                   # All persistent data (gitignored)
    ├── n8n/
    ├── nextcloud/
    ├── nextcloud-db/
    ├── vault/
    ├── simplex/
    ├── simplex-bridge/
    └── ollama/             # Model storage (~12GB)
```

---

## Configuration

All configuration is in `.env`. Key settings:

```bash
# n8n
N8N_BASIC_AUTH_PASSWORD=your-secure-password

# Nextcloud
NEXTCLOUD_DB_PASSWORD=your-db-password
NEXTCLOUD_PASSWORD=your-app-password  # For CalDAV access

# Timezone
TZ=Europe/London

# Local AI (optional - only if using Ollama)
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_MODEL=gemma3:12b
```

---

## Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh backups/second-brain-backup-20260122.tar.gz

# Automated backups (add to crontab)
0 2 * * * /path/to/second-brain/scripts/backup.sh --cron
```

---

## Remote Access

### With Tailscale (Recommended)

1. Install Tailscale on server and devices
2. Access services via Tailscale IP:
   - n8n: `http://100.x.x.x:5678`
   - Nextcloud: `http://100.x.x.x:8088`

### With Cloudflare Tunnel (For webhooks)

For external webhook access without opening ports:

```bash
cloudflared tunnel --url http://localhost:5678
```

---

## Documentation

- [Setup Guide](SETUP_GUIDE.md) - Complete installation instructions
- [SimpleX Bridge](SIMPLEX_BRIDGE.md) - Technical details on the messaging bridge
- [Local AI Setup](ollama/README.md) - Optional local AI module
- [Nate's Original Article](https://natesnewsletter.substack.com/p/grab-the-system-that-closes-open) - The inspiration for this project

---

## Troubleshooting

### Services won't start

```bash
docker compose logs -f
docker compose logs -f n8n
```

### SimpleX not connecting

```bash
docker compose logs -f simplex-bridge
docker compose logs -f simplex-chat-cli
```

### Ollama not responding

```bash
docker compose logs -f ollama
# Check GPU access
nvidia-smi
```

### Permission errors

```bash
sudo chown -R $USER:$USER data/
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

- [Nate](https://natesnewsletter.substack.com/) for the original Second Brain concept and workflow design
- [n8n](https://n8n.io/) for the amazing automation platform
- [SimpleX Chat](https://simplex.chat/) for truly private messaging
- [Nextcloud](https://nextcloud.com/) for self-hosted calendar
- [Obsidian](https://obsidian.md/) for the knowledge management philosophy
- [Ollama](https://ollama.ai/) for easy local LLM deployment
- [Google DeepMind](https://deepmind.google/) for the Gemma model family
