# Second Brain - Setup Guide

A complete guide to deploying your self-hosted AI personal assistant.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [First-Time Configuration](#first-time-configuration)
4. [Connecting SimpleX Chat](#connecting-simplex-chat)
5. [Importing Workflows](#importing-workflows)
6. [Local AI Setup (Optional)](#local-ai-setup-optional)
7. [Migrating Existing Data](#migrating-existing-data)
8. [Verification](#verification)
9. [Troubleshooting](#troubleshooting)
10. [Useful Commands](#useful-commands)

---

## Prerequisites

### Hardware Requirements

- **Minimum:** 4GB RAM, 2 CPU cores, 20GB storage
- **Recommended:** 8GB RAM, 4 CPU cores, 100GB+ storage
- **For Local AI:** NVIDIA GPU with 12GB+ VRAM, 32GB+ RAM, 50GB+ storage

### Software Requirements

**Install Docker and Docker Compose:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-v2

# Start Docker and enable on boot
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (avoids needing sudo)
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

**Verify installation:**

```bash
docker --version        # Should show Docker version 24.x or higher
docker compose version  # Should show Docker Compose version v2.x
```

### Git (for cloning the repo)

```bash
sudo apt install -y git
```

---

## Installation

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/drgoodnight/second-brain.git
cd second-brain
```

### 2. Make Scripts Executable

```bash
chmod +x scripts/*.sh
chmod +x simplex/start-simplex.sh
```

### 3. Run Setup Script

```bash
./scripts/setup.sh
```

This will:
- Create all required data directories
- Generate `.env` file with random passwords
- Build Docker images
- Start all services
- Run health checks

**Expected output:**

```
╔════════════════════════════════════════════════════════╗
║           Second Brain - Setup Script                  ║
╚════════════════════════════════════════════════════════╝

Checking prerequisites...
✓ Docker and Docker Compose found

Creating data directories...
✓ Data directories created

Creating .env file from template...
✓ .env file created with generated passwords

...

════════════════════════════════════════════════════════
                    Setup Complete!
════════════════════════════════════════════════════════

Services:
  • n8n:          http://localhost:5678
  • Nextcloud:    http://localhost:8088
  • Obsidian API: http://localhost:8765
  • SimpleX:      ws://localhost:5225
```

---

## First-Time Configuration

### Step 1: Configure Nextcloud

1. **Open Nextcloud** in your browser:
   ```
   http://localhost:8088
   ```

2. **Create admin account:**
   - Enter a username (e.g., `admin`)
   - Enter a strong password
   - Click "Install"

3. **Wait for installation** (2-5 minutes)
   - Nextcloud will set up the database
   - You may see a loading screen

4. **Install recommended apps OR install Calendar manually:**
   
   **Option A:** Click "Install recommended apps" - this includes Calendar
   
   **Option B:** Skip recommended apps, then install Calendar manually:
   - Click your profile icon (top right)
   - Click "Apps"
   - Go to "Office & text" category
   - Find "Calendar" and click "Install"

### Step 2: Create Nextcloud App Password

This password allows n8n to access your calendar.

1. **Go to Settings:**
   - Click your profile icon (top right)
   - Click "Settings"

2. **Navigate to Security:**
   - Left sidebar → "Security"

3. **Create app password:**
   - Scroll to "Devices & sessions"
   - Enter app name: `n8n`
   - Click "Create new app password"

4. **Copy the password**
   - It looks like: `xxxxx-xxxxx-xxxxx-xxxxx-xxxxx`
   - **Save this somewhere** - you can't see it again!

### Step 3: Add App Password to Environment

```bash
nano ~/second-brain/.env
```

Find this line:
```
NEXTCLOUD_PASSWORD=YOUR_NEXTCLOUD_APP_PASSWORD
```

Replace with your actual password:
```
NEXTCLOUD_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
```

Save and exit (Ctrl+X, Y, Enter).

### Step 4: Restart n8n

```bash
cd ~/second-brain
docker compose restart n8n
```

### Step 5: Access n8n

1. **Open n8n:**
   ```
   http://localhost:5678
   ```

2. **Log in with credentials from `.env`:**
   ```bash
   # View your generated credentials
   grep N8N_BASIC_AUTH .env
   ```
   
   Default username is `admin`, password was auto-generated.

---

## Connecting SimpleX Chat

SimpleX Chat is your interface to the Second Brain. **This requires a one-time manual setup.**

### Why Manual Setup?

SimpleX CLI requires an interactive terminal (TTY) to create a user profile. It cannot be automated because it prompts for a display name during first-time setup. This only needs to be done once - after that, the profile persists and the container starts automatically.

### Step 1: Stop the SimpleX Container

After initial `docker compose up -d`, the SimpleX container will show an error because no profile exists yet. This is expected.

```bash
docker compose stop simplex-chat-cli
```

### Step 2: Create the SimpleX Profile (Interactive)

Run SimpleX interactively to create your profile:

```bash
docker compose run -it --rm simplex-chat-cli \
  simplex-chat -d /home/simplex/.simplex/simplex
```

> **Important:** The `-d` flag specifies a database **name prefix**, not a directory. Using `-d /home/simplex/.simplex/simplex` creates the database files inside the mounted volume at `data/simplex/`.

### Step 3: Complete the Setup Prompts

When SimpleX starts, you'll see:

```
SimpleX Chat v6.4.7.1
...
No user profiles found, it will be created now.
Please choose your display name.
It will be sent to your contacts when you connect.
It is only stored on your device and you can change it later.
display name:
```

1. **Enter your bot's display name:**
   ```
   second-brain
   ```

2. **Enable auto-accept for incoming connections:**
   ```
   /auto_accept on
   ```
   
   This is **critical** - without this, you'll need to manually accept every connection request from your phone or other devices.

3. **Get your connection address** (save this for connecting from your phone):
   ```
   /address
   ```
   
   You'll see output like:
   ```
   Your chat address:
   simplex:/invite#/?v=2-7&smp=...
   ```
   
   **Copy and save this entire link** - you'll need it to connect from your phone's SimpleX app.

4. **Exit SimpleX:**
   ```
   /quit
   ```

### Step 4: Verify Profile Was Created

Check that the database files now exist:

```bash
ls -la data/simplex/
```

You should see files including:
```
simplex_chat.db
simplex_agent.db
simplex_chat.db-shm
simplex_chat.db-wal
```

### Step 5: Start All Services

```bash
docker compose up -d
```

### Step 6: Verify SimpleX is Running

```bash
docker compose logs simplex-chat-cli
```

You should now see:
```
============================================
SimpleX Chat CLI Starting
============================================
Port: 5225
Log Level: warn
Data Dir: /home/simplex/.simplex
DB Prefix: /home/simplex/.simplex/simplex
Bot Name: second-brain
============================================

✓ Profile found: /home/simplex/.simplex/simplex_chat.db

Starting SimpleX Chat with WebSocket API on port 5225...
```

### Step 7: Connect from Your Phone

1. **Install SimpleX Chat** on your phone (iOS App Store / Android Play Store)

2. **Add a new contact:**
   - Tap the **+** button
   - Select "Connect via link" or scan QR code
   - Paste the address you saved in Step 3 (the `simplex:/invite#/...` link)

3. **Accept the connection** when prompted

4. **Send a test message:**
   ```
   what's on my calendar today?
   ```

### Step 8: Verify Bridge is Working

```bash
docker compose logs -f simplex-bridge
```

You should see messages being forwarded to n8n:
```
[OK] Posted: contactId=1 itemId=43 from="YourName" text='what's on my calendar today?' | Response: {"success":true}
```

---

## Importing Workflows

### Setting Up Workflow Folders

Organize your workflows in n8n with this folder structure:

```
second brain/
├── SimpleX_SecondBrain_Router    # Main router workflow
├── obsidian/
│   └── (obsidian-related workflows)
└── calendar/
    └── (calendar-related workflows)
```

**To create folders in n8n:**
1. Open n8n: http://localhost:5678
2. In the left sidebar, click the **+** next to "Workflows"
3. Select "Create folder"
4. Create `second brain`, then inside it create `obsidian` and `calendar`

### Importing Workflow Files

1. **Open n8n:** http://localhost:5678

2. **Start from scratch:**
   - Click "Add workflow" (or the + button)

3. **Import the workflow:**
   - Click the **three dots menu** (⋮) in the top right corner
   - Click "Import from file"
   - Select your `.json` file
   - Click "Save"

4. **Move to correct folder:**
   - From the workflows list, drag the workflow to the appropriate folder:
     - `SimpleX_SecondBrain_Router` → `second brain/`
     - Obsidian workflows → `second brain/obsidian/`
     - Calendar workflows → `second brain/calendar/`

5. **Repeat for all workflows**

### Recreating Credentials

Credentials are NOT included in workflow exports. You need to recreate:

- **OpenAI API Key** (if using cloud AI):
  - Settings → Credentials → Add credential
  - Select "OpenAI API"
  - Paste your API key

- **Other APIs** as needed

> **Note:** If you're using local AI with Ollama, you don't need OpenAI credentials. See [Local AI Setup](#local-ai-setup-optional).

### Updating Credential References

- Open each workflow
- Find nodes with missing credentials (shown with ⚠️)
- Select the correct credential from dropdown

### Activating Workflows

- Toggle the "Active" switch for each workflow

### If Starting Fresh

Import the example workflows from `n8n/workflows/` directory, then customize for your needs.

---

## Local AI Setup (Optional)

For complete privacy, you can run AI inference locally using Ollama and Gemma 3 12B. This eliminates all external API calls—your data never leaves your machine.

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| RAM | 32GB | 64GB |
| Storage | 20GB free | 50GB free |
| CUDA | 11.8+ | 12.x |

**Tested configurations:**
- ✅ RTX 4060 Ti 16GB, RTX 3080 10GB, RTX 4070 12GB
- ⚠️ RTX 3060 12GB (works but tight on VRAM)
- ❌ GPUs with less than 8GB VRAM

### Step 1: Install NVIDIA Container Toolkit

```bash
# Add NVIDIA container toolkit repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU access from Docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Step 2: Run the Setup Script

```bash
cd ~/second-brain
./scripts/enable-local-ai.sh
```

This will:
- Check for NVIDIA GPU and drivers
- Verify Docker can access the GPU
- Create `data/ollama/` directory
- Add Ollama variables to `.env`
- Start Ollama container
- Download Gemma 3 12B model (~12GB, takes 10-30 minutes)
- Run a quick test

### Step 3: Start with Local AI

From now on, start Second Brain with the Ollama overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### Step 4: Configure n8n for Ollama

See [ollama/N8N_OLLAMA_CONFIG.md](ollama/N8N_OLLAMA_CONFIG.md) for detailed instructions on updating your n8n workflows to use local AI instead of OpenAI.

**Quick summary:**
1. Replace OpenAI nodes with HTTP Request nodes pointing to `http://ollama:11434`
2. Add JSON parsing Code nodes after Ollama calls
3. Use the optimized prompts from `ollama/prompts/GEMMA3_PROMPTS.md`

### Step 5: Verify Ollama is Working

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test inference
curl http://localhost:11434/api/generate -d '{
  "model": "gemma3:12b",
  "prompt": "Say hello",
  "stream": false
}'
```

### Running Without Local AI

If you don't have a compatible GPU or prefer cloud AI:

```bash
# Standard startup (uses OpenAI or other cloud APIs)
docker compose up -d
```

### Switching Between Local and Cloud AI

You can switch anytime:

```bash
# With local AI
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Without local AI (stop Ollama, use cloud)
docker compose down
docker compose up -d
```

### Alternative Models

If Gemma 3 12B is too large for your GPU:

```bash
# Pull a smaller model
docker exec ollama ollama pull gemma3:12b-q4_K_M  # ~7GB VRAM
# or
docker exec ollama ollama pull mistral:7b          # ~6GB VRAM
# or  
docker exec ollama ollama pull llama3.2:3b         # ~3GB VRAM

# Update .env
nano .env
# Change: OLLAMA_MODEL=gemma3:12b-q4_K_M
```

---

## Migrating Existing Data

If you're moving from another machine with existing Second Brain data:

### Option A: Using Backup/Restore Scripts

**On your old machine:**

```bash
cd ~/second-brain
./scripts/backup.sh
# Creates: backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

**Transfer to new machine:**

```bash
scp ~/second-brain/backups/second-brain-backup-*.tar.gz user@newmachine:~/second-brain/backups/
```

**On new machine:**

```bash
cd ~/second-brain
./scripts/restore.sh backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

### Option B: Manual Copy

**Transfer specific data directories:**

```bash
# From old machine to new machine
scp -r old-machine:~/second-brain/data/vault/* ~/second-brain/data/vault/
scp -r old-machine:~/second-brain/data/n8n/* ~/second-brain/data/n8n/
scp -r old-machine:~/second-brain/data/simplex/* ~/second-brain/data/simplex/
```

**Restart services after copying:**

```bash
docker compose restart
```

---

## Verification

### Check All Services Are Running

```bash
docker compose ps
```

**Expected output (without local AI):**

```
NAME                STATUS              PORTS
n8n                 Up (healthy)        0.0.0.0:5678->5678/tcp
nextcloud           Up                  0.0.0.0:8088->80/tcp
nextcloud-cron      Up
nextcloud-db        Up (healthy)
obsidian-api        Up (healthy)        0.0.0.0:8765->8000/tcp
simplex-bridge      Up
simplex-chat-cli    Up                  0.0.0.0:5225->5225/tcp
```

**With local AI, you'll also see:**

```
ollama              Up (healthy)        0.0.0.0:11434->11434/tcp
```

### Test Each Service

**n8n:**
```bash
curl -s http://localhost:5678/healthz
# Should return: {"status":"ok"}
```

**Obsidian API:**
```bash
curl -s http://localhost:8765/health
# Should return: {"status":"healthy",...}
```

**Nextcloud:**
```bash
curl -s http://localhost:8088/status.php
# Should return JSON with "installed":true
```

**Ollama (if enabled):**
```bash
curl -s http://localhost:11434/api/tags
# Should return JSON with model list
```

### Test End-to-End

Send a message via SimpleX Chat:
```
add meeting at 3pm tomorrow
```

Check:
1. Bridge logs show the message received
2. n8n workflow executes
3. Calendar event appears in Nextcloud

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs for the specific container
docker compose logs n8n
docker compose logs nextcloud
docker compose logs simplex-chat-cli

# Rebuild if needed
docker compose down
docker compose build --no-cache
docker compose up -d
```

### SimpleX Shows "No Profile Found" Error

This is expected on first run. Follow the [Connecting SimpleX Chat](#connecting-simplex-chat) section to create the profile interactively.

**Quick fix:**

```bash
# 1. Stop the container
docker compose stop simplex-chat-cli

# 2. Create profile interactively
docker compose run -it --rm simplex-chat-cli \
  simplex-chat -d /home/simplex/.simplex/simplex

# 3. Enter display name: second-brain
# 4. Type /quit to exit

# 5. Start all services
docker compose up -d
```

### SimpleX Profile Lost After Restart

If your SimpleX profile disappears after container restart, check that:

1. **Volume mount exists:** `data/simplex/` directory exists on host
2. **Files are present:** `ls -la data/simplex/` shows `.db` files
3. **Permissions are correct:** `sudo chown -R $USER:$USER data/simplex/`

### n8n Can't Connect to Nextcloud

1. Verify NEXTCLOUD_PASSWORD in `.env` is correct
2. Restart n8n: `docker compose restart n8n`
3. Check Nextcloud is accessible: `curl http://localhost:8088`

### SimpleX Bridge Not Forwarding Messages

```bash
# Check bridge logs
docker compose logs -f simplex-bridge

# Verify n8n webhook is accessible
curl -X POST http://localhost:5678/webhook/simplex-in \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

### Ollama Not Responding

```bash
# Check Ollama logs
docker compose logs -f ollama

# Check GPU is accessible
nvidia-smi

# Check model is loaded
curl http://localhost:11434/api/tags

# Test inference
curl http://localhost:11434/api/generate -d '{"model":"gemma3:12b","prompt":"Hi"}'
```

### Ollama Out of Memory

If you see CUDA out of memory errors:

```bash
# Use a smaller quantization
docker exec ollama ollama pull gemma3:12b-q4_K_M

# Update .env
nano .env
# Change OLLAMA_MODEL to the smaller model

# Restart
docker compose -f docker-compose.yml -f docker-compose.ollama.yml restart ollama
```

### Permission Errors

```bash
# Fix ownership of data directories
sudo chown -R $USER:$USER data/
```

### Database Issues

```bash
# Reset Nextcloud database (WARNING: deletes all data)
docker compose down
sudo rm -rf data/nextcloud-db/*
docker compose up -d
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a
```

---

## Useful Commands

### Daily Operations

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f n8n
docker compose logs -f simplex-bridge
docker compose logs -f ollama

# Restart all services
docker compose restart

# Restart specific service
docker compose restart n8n

# Stop all services
docker compose down

# Start all services (without local AI)
docker compose up -d

# Start all services (with local AI)
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# List backups
ls -la backups/

# Restore from backup
./scripts/restore.sh backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild containers
docker compose build

# Restart with new images
docker compose up -d
```

### Accessing Containers

```bash
# Shell into n8n
docker exec -it n8n /bin/bash

# Shell into Nextcloud
docker exec -it nextcloud /bin/bash

# SimpleX CLI (if profile already exists)
docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex

# Ollama CLI
docker exec -it ollama ollama list
```

### SimpleX Management

```bash
# Get your connection address again
docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex
# Then type: /address
# Then type: /quit

# Reset SimpleX profile (start fresh)
docker compose stop simplex-chat-cli
sudo rm -rf data/simplex/*
# Then follow "Connecting SimpleX Chat" section again
```

### Ollama Management

```bash
# List models
docker exec ollama ollama list

# Pull a new model
docker exec ollama ollama pull mistral:7b

# Remove a model
docker exec ollama ollama rm gemma3:12b

# Check GPU usage
nvidia-smi
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| n8n | http://localhost:5678 | Automation workflows |
| Nextcloud | http://localhost:8088 | Calendar (CalDAV) |
| Obsidian API | http://localhost:8765 | Notes management |
| SimpleX | ws://localhost:5225 | Chat interface |
| Ollama | http://localhost:11434 | Local AI (optional) |

---

## Security Notes

- **Keep `.env` private** - never commit to git
- **Use strong passwords** for Nextcloud admin
- **Firewall** - only expose ports you need externally
- **Backups** - run `./scripts/backup.sh` regularly
- **Updates** - keep Docker and images updated
- **Local AI** - Ollama API has no authentication (internal use only)

---

## Getting Help

- Check [Troubleshooting](#troubleshooting) section
- Review logs: `docker compose logs -f`
- Local AI docs: [ollama/README.md](ollama/README.md)
- Open an issue on GitHub

---

## License

MIT License - See LICENSE file for details.
