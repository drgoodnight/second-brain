# Second Brain - Setup Guide

A complete guide to deploying your self-hosted AI personal assistant.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [First-Time Configuration](#first-time-configuration)
4. [Importing Workflows](#importing-workflows)
5. [Migrating Existing Data](#migrating-existing-data)
6. [Connecting SimpleX Chat](#connecting-simplex-chat)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)
9. [Useful Commands](#useful-commands)

---

## Prerequisites

### Hardware Requirements

- **Minimum:** 4GB RAM, 2 CPU cores, 20GB storage
- **Recommended:** 8GB RAM, 4 CPU cores, 100GB+ storage

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

4. **Skip recommended apps** (optional)
   - Click "Cancel" or install if desired

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

## Importing Workflows

### If You Have Existing Workflow JSON Files

1. **Open n8n:** http://localhost:5678

2. **Import each workflow:**
   - Click "Add workflow" (or the + button)
   - Click "Import from file"
   - Select your `.json` file
   - Click "Save"

3. **Recreate credentials:**
   
   Credentials are NOT included in workflow exports. You need to recreate:
   
   - **OpenAI API Key:**
     - Settings → Credentials → Add credential
     - Select "OpenAI API"
     - Paste your API key
   
   - **Other APIs** as needed

4. **Update credential references:**
   - Open each workflow
   - Find nodes with missing credentials (shown with ⚠️)
   - Select the correct credential from dropdown

5. **Activate workflows:**
   - Toggle the "Active" switch for each workflow

### If Starting Fresh

Import the example workflows from `n8n/workflows/` directory, then customize for your needs.

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

## Connecting SimpleX Chat

SimpleX Chat is your interface to the Second Brain.

### Step 1: Check SimpleX is Running

```bash
docker compose logs simplex-chat-cli
```

Look for: `simplex-chat: listening on port 5225`

### Step 2: Get Your Bot's Connection Link

```bash
# Connect to SimpleX container
docker exec -it simplex-chat-cli simplex-chat

# Inside SimpleX, create an address:
/address

# Copy the displayed link (starts with simplex:/)
# Type /quit to exit
```

### Step 3: Connect from Your Phone

1. **Install SimpleX Chat** on your phone (iOS/Android)

2. **Scan or paste the connection link**

3. **Send a test message:**
   ```
   what's on my calendar today?
   ```

### Step 4: Verify Bridge is Working

```bash
docker compose logs -f simplex-bridge
```

You should see messages being forwarded to n8n.

---

## Verification

### Check All Services Are Running

```bash
docker compose ps
```

**Expected output:**

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

# Restart all services
docker compose restart

# Restart specific service
docker compose restart n8n

# Stop all services
docker compose down

# Start all services
docker compose up -d
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

# SimpleX CLI
docker exec -it simplex-chat-cli simplex-chat
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| n8n | http://localhost:5678 | Automation workflows |
| Nextcloud | http://localhost:8088 | Calendar (CalDAV) |
| Obsidian API | http://localhost:8765 | Notes management |
| SimpleX | ws://localhost:5225 | Chat interface |

---

## Security Notes

- **Keep `.env` private** - never commit to git
- **Use strong passwords** for Nextcloud admin
- **Firewall** - only expose ports you need externally
- **Backups** - run `./scripts/backup.sh` regularly
- **Updates** - keep Docker and images updated

---

## Getting Help

- Check [Troubleshooting](#troubleshooting) section
- Review logs: `docker compose logs -f`
- Open an issue on GitHub

---

## License

MIT License - See LICENSE file for details.
