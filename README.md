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

**This project adapts that concept for privacy-conscious self-hosters, and adds calendar management, voice capture, and local AI:**

| Nate's Stack | This Project | Benefit |
|--------------|--------------|---------|
| Slack | SimpleX Chat | End-to-end encrypted, no metadata |
| Zapier | n8n | Self-hosted, no cloud dependency |
| Notion | Obsidian API | Local markdown files, full ownership |
| Cloud AI | Ollama | Fully local inference on your own GPU |
| *(not included)* | Nextcloud Calendar | Full calendar management via natural language |
| *(not included)* | Whisper | Voice notes transcribed locally |

Same powerful workflow, plus calendar integration and voice capture—everything runs on your own hardware.

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

# Enable local AI (required for the AI features)
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed installation instructions.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            SECOND BRAIN                 │
                         │                                         │
SimpleX Chat ──────────► │  SimpleX Bridge v2                      │
  (Mobile/Desktop)       │    │   └── voice ──► Whisper (local)     │
       ▲                 │    ▼                                    │
       │                 │  n8n Hub                                │
       │                 │    ├── Calendar Agent ──► Nextcloud     │
       └─────────────────│    ├── Notes Agent ────► Obsidian API   │
         (replies)       │    ├── Search Agent ───► Obsidian API   │
                         │    ├── Delete Agent ───► Obsidian API   │
                         │    └── Chat ───────────► Ollama         │
                         │                                         │
                         │  Caddy ──► Nextcloud (HTTPS for iOS)    │
                         └─────────────────────────────────────────┘
                                    All Local / Self-Hosted
```

## Components

| Service | Port | Purpose |
|---------|------|---------|
| n8n | 5678 | Automation hub, workflow orchestration |
| Nextcloud | 8088 | Calendar (CalDAV) |
| Obsidian API | 8765 | Notes management (6 databases) |
| SimpleX Chat | 5225 | Encrypted messaging interface |
| SimpleX Bridge | — | Connects SimpleX ↔ n8n (v2, persistent WebSocket) |
| Whisper | 8766 | Local speech-to-text for voice notes |
| Ollama | 11434 | Local AI inference |
| Caddy | 443 | HTTPS reverse proxy — required for iOS CalDAV sync |

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
| Daily | Daily notes / journal | (date-based) |
| Inbox Log | Audit trail | (automatic) |

### Voice Capture

Send a voice message in SimpleX and the bridge forwards the audio to the local Whisper
container, transcribes it, and routes the resulting text through the same pipeline as a
typed message. Nothing leaves the machine.

### AI Chat

For general conversation and questions that aren't calendar or notes commands:

```
User: "do you dream?"
Bot:  "I do not sleep or dream like humans, but I am ready to help you
       capture and organize any insights or reflections you share."
```

Chat is handled by a direct HTTP call to Ollama's OpenAI-compatible endpoint
(`/v1/chat/completions`). Note this path is currently **stateless** — there is no memory
between messages, and the chat branch cannot call the calendar or notes tools. See
[Roadmap](#roadmap).

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

## Local AI Stack

This project uses a fully local AI stack for complete privacy.

### Ollama

- Intent classification (which agent should handle this message)
- Structured generation (ICS calendar events, notes classification JSON)
- General chat responses

The model is set via `OLLAMA_MODEL` in `.env`. Current default: `qwen3.5:9b`.

> **Note on reasoning models.** `qwen3.5:9b` emits an internal reasoning trace before its
> answer — roughly 2,000 completion tokens even for a trivial greeting. The reasoning is
> returned in a separate `reasoning` field so it doesn't pollute `content`, but expect
> chat replies to take 30–60 seconds. A non-reasoning model will feel far snappier if
> latency matters more than answer quality.

### Whisper

- `faster-whisper` with `large-v3`, running on the GPU
- OpenAI-compatible transcription endpoint
- Coexists with Ollama on a single 16GB card (~3GB Whisper + ~7GB for a 9B model)

### Requirements

- NVIDIA GPU with 12GB+ VRAM (developed on an RTX 4060 Ti 16GB)
- NVIDIA Container Toolkit installed
- 32GB+ system RAM recommended

### Quick Setup

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

See [ollama/README.md](ollama/README.md) for model configuration details.

### Optional: Clawdbot

Earlier versions routed chat through [Clawdbot](https://github.com/clawdbot/clawdbot), an
agent framework with session memory. It has been replaced by the direct Ollama call above,
but the integration and its security hardening remain available in
[CLAWDBOT_SECURITY_HARDENING.md](CLAWDBOT_SECURITY_HARDENING.md) and
`docker-compose.clawdbot.yml` if you want agentic capabilities with sandboxing.

---

## Directory Structure

```
second-brain/
├── docker-compose.yml               # Core services
├── docker-compose.ollama.yml        # Ollama local AI
├── docker-compose.clawdbot.yml      # Clawdbot (optional)
├── .env.example                     # Template (committed)
├── .env                             # Secrets (gitignored)
├── README.md
├── SETUP_GUIDE.md                   # Detailed setup instructions
├── SIMPLEX_BRIDGE.md                # Bridge technical notes
├── CLAWDBOT_SECURITY_HARDENING.md   # Optional Clawdbot setup & hardening
│
├── n8n-python/                      # Custom n8n image with Python
│   └── Dockerfile
│
├── simplex/                         # SimpleX Chat CLI
│   ├── Dockerfile
│   └── start-simplex.sh
│
├── simplex-bridge-v2/               # SimpleX ↔ n8n bridge (current)
│   ├── bridge_v2.py
│   ├── Dockerfile
│   ├── MIGRATION.md
│   └── N8N_WORKFLOWS.md
│
├── obsidian-api/                    # Notes API (FastAPI)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── whisper-local/                   # Local speech-to-text
│   ├── Dockerfile
│   ├── api.py
│   └── INTEGRATION.md
│
├── caddy/                           # HTTPS proxy for iOS CalDAV
│   ├── Caddyfile.example
│   ├── Caddyfile                    # Your config (gitignored)
│   └── IOS_CALDAV_SETUP.md
│
├── ollama/                          # Local AI module
│   ├── README.md
│   ├── init-models.sh
│   └── prompts/
│
├── scripts/
│   ├── setup.sh                     # First-time setup
│   ├── backup.sh                    # Backup script
│   ├── restore.sh                   # Restore script
│   ├── enable-local-ai.sh           # Local AI setup script
│   ├── renew-cert.sh                # Tailscale cert renewal (cron)
│   └── bridge.py                    # Legacy v1 bridge (superseded)
│
├── n8n/
│   ├── workflows/                   # Exported n8n workflow JSONs
│   └── scripts/                     # Code-node snippets & prompts
│
└── data/                            # All persistent data (gitignored)
    ├── n8n/
    ├── nextcloud/
    ├── nextcloud-db/
    ├── vault/                       # Your Obsidian markdown
    ├── simplex/
    ├── simplex-bridge/
    ├── whisper-models/
    ├── caddy/certs/
    └── ollama/                      # Model storage (~14GB)
```

---

## Configuration

All configuration is in `.env`. Key settings:

```bash
# n8n
N8N_BASIC_AUTH_PASSWORD=your-secure-password
N8N_BLOCK_ENV_ACCESS_IN_NODE=false   # required for $env in Code nodes

# Nextcloud
NEXTCLOUD_DB_PASSWORD=your-db-password
NEXTCLOUD_PASSWORD=your-app-password  # For CalDAV access

# Timezone
TZ=Europe/London

# Local AI
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_MODEL=qwen3.5:9b

# Whisper
WHISPER_MODEL=large-v3

# Tailscale cert (iOS CalDAV via Caddy)
TAILSCALE_DOMAIN=your-machine.your-tailnet.ts.net
CERT_OWNER=your-username
```

---

## Operations

### Everyday commands

Ollama lives in an overlay compose file, so both files must be named or Compose will treat
Ollama as an orphan. A shell alias saves a lot of typing:

```bash
alias dc='docker compose -f ~/projects/second-brain/docker-compose.yml -f ~/projects/second-brain/docker-compose.ollama.yml'

dc ps                       # status of all services
dc up -d                    # start everything
dc logs -f simplex-bridge   # follow the bridge
```

> **Never run `docker compose ... --remove-orphans`** unless every compose file is named on
> the command line — it will delete services defined in the files you left out.

### Health checks

```bash
curl -s http://localhost:5678/healthz     # n8n     → "ok"
curl -s http://localhost:8088/status.php  # Nextcloud → installed: true
curl -s http://localhost:8765/health      # Obsidian API
curl -s http://localhost:8766/health      # Whisper
curl -s http://localhost:11434/api/tags   # Ollama — lists installed models
```

### After a reboot

All services use `restart: unless-stopped` and come back automatically. Note that
`depends_on` conditions are **only** honoured by `docker compose up`, not by the Docker
daemon on boot — so services may start out of order and flap for a minute before settling.
Wait two minutes before diagnosing anything.

### Cold start from stopped

Bringing services up a tier at a time makes failures much easier to read than starting
everything at once:

```bash
dc up -d nextcloud-db          # watch for InnoDB "ready for connections"
dc up -d nextcloud nextcloud-cron
dc up -d n8n obsidian-api
dc up -d simplex-chat-cli whisper
dc up -d simplex-bridge caddy
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

The `data/vault/` directory is small but irreplaceable — it holds every note. Verify your
backups actually restore rather than assuming they do.

---

## Remote Access

### With Tailscale (Recommended)

1. Install Tailscale on the server and your devices
2. Reach services by MagicDNS name **including the port**:
   - n8n: `http://your-machine.your-tailnet.ts.net:5678`
   - Nextcloud: `http://your-machine.your-tailnet.ts.net:8088`
   - Nextcloud over HTTPS via Caddy: `https://your-machine.your-tailnet.ts.net`

Omitting the port sends the browser to port 80, where nothing is listening.

### iOS Calendar Sync (CalDAV)

iOS requires HTTPS for CalDAV, which is what the Caddy service provides. See
[caddy/IOS_CALDAV_SETUP.md](caddy/IOS_CALDAV_SETUP.md) for first-time setup.

#### Certificate Renewal

Caddy serves a **static copy** of a Tailscale-issued Let's Encrypt certificate from
`data/caddy/certs/`. Tailscale renews its own copy automatically, but nothing propagates
it to Caddy — so after 90 days the copy expires and iOS silently stops syncing.

This is automated by `scripts/renew-cert.sh`, run monthly from root's crontab:

```
0 4 1 * * /path/to/second-brain/scripts/renew-cert.sh >> /var/log/tailscale-cert-renew.log 2>&1
```

Set `TAILSCALE_DOMAIN` (and optionally `CERT_OWNER`) in `.env`.

> **Snap caveat.** If Tailscale is installed as a snap it cannot write files to arbitrary
> paths *even under sudo*, so `tailscale cert --cert-file <path>` fails with
> "permission denied". The certificate **is** still fetched into
> `/var/snap/tailscale/common/certs/` — only the export step fails. The renewal script
> therefore ignores that error and copies from Tailscale's own store.

Manual renewal:

```bash
sudo ./scripts/renew-cert.sh
echo | openssl s_client -connect your-machine.your-tailnet.ts.net:443 2>/dev/null \
  | openssl x509 -noout -dates
```

### With Cloudflare Tunnel (For webhooks)

For external webhook access without opening ports:

```bash
cloudflared tunnel --url http://localhost:5678
```

---

## Documentation

- [Setup Guide](SETUP_GUIDE.md) — Complete installation instructions
- [SimpleX Bridge](SIMPLEX_BRIDGE.md) — Technical details on the messaging bridge
- [Bridge v2 Migration](simplex-bridge-v2/MIGRATION.md) — Upgrading from the v1 bridge
- [Local AI Setup](ollama/README.md) — Ollama local AI module
- [Whisper Integration](whisper-local/INTEGRATION.md) — Voice transcription
- [iOS CalDAV Setup](caddy/IOS_CALDAV_SETUP.md) — HTTPS proxy and iPhone calendar sync
- [Clawdbot Security](CLAWDBOT_SECURITY_HARDENING.md) — Optional Clawdbot setup & hardening
- [Nate's Original Article](https://natesnewsletter.substack.com/p/grab-the-system-that-closes-open) — The inspiration for this project

---

## Troubleshooting

### Services won't start

```bash
dc logs -f
dc logs -f n8n
```

### The bot receives messages but never replies

Check that the router workflow is **Active** in n8n — a deactivated workflow means its
production webhook path doesn't exist, so the bridge posts into a void:

```bash
docker exec n8n n8n list:workflow --active=true
```

Then verify the webhook is registered. A GET to a POST-only webhook is a harmless probe:

```bash
curl -s -i http://localhost:5678/webhook/simplex-in | head -5
```

*"This webhook is not registered for GET requests"* means the path exists — that's success.

### The bridge replays old messages on startup

The bridge stores deduplication state in the file named by `SIMPLEX_STATE_FILE`. If that
variable is unset or points outside the mounted volume, state is lost whenever the
container is recreated and SimpleX's local history gets reprocessed as new. Confirm the
log line reads `Loaded state for N contact(s)` rather than `No previous state found`.

### SimpleX not connecting

```bash
dc logs -f simplex-bridge
dc logs -f simplex-chat-cli
```

The bridge runs startup health checks against SimpleX, n8n and Whisper and prints a pass or
fail for each — usually enough to localise the problem immediately.

### Ollama not responding

```bash
dc logs -f ollama
curl -s http://localhost:11434/api/tags   # is the configured model actually present?
nvidia-smi                                 # GPU visible?
```

### iPhone calendar stopped syncing

Almost always an expired certificate — see [Certificate Renewal](#certificate-renewal).
Diagnostic shortcut: if the SimpleX bot still answers calendar questions but the iPhone
does not sync, it's the cert. n8n reaches Nextcloud directly over the Docker network and
bypasses Caddy entirely, so the two fail independently.

### Permission errors

```bash
sudo chown -R $USER:$USER data/
```

---

## Roadmap

- Rebuild the chat branch as an n8n **AI Agent** node with conversation memory keyed per
  SimpleX contact, and expose calendar and notes as agent *tools* rather than as separate
  classifier-routed branches
- **Error workflow** that reports failures back over SimpleX, so a broken node produces a
  message rather than silence
- A **`status` command** returning the health of every service in one reply
- Deterministic fast paths for common phrasings, to skip model inference entirely
- **Undo** on write operations
- Automated nightly export of n8n workflows into git

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
- [Alibaba Qwen](https://github.com/QwenLM) and [Google DeepMind](https://deepmind.google/) for the open models
- [OpenAI Whisper](https://github.com/openai/whisper) and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for local speech recognition
- [Caddy](https://caddyserver.com/) for painless HTTPS
- [Clawdbot](https://github.com/clawdbot/clawdbot) for the AI agent framework
