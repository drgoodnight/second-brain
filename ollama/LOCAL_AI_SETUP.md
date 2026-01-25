# Local AI Setup Guide

Complete guide for setting up Ollama with Gemma 3 12B on your Second Brain system.

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| RAM | 32GB | 64GB |
| Storage | 20GB free | 50GB free |
| CUDA | 11.8+ | 12.x |

### Tested Configurations

- ✅ **RTX 4060 Ti 16GB** - Optimal, runs Q8_0 with room to spare
- ✅ **RTX 3080 10GB** - Good, may need Q6_K quantization
- ✅ **RTX 4070 12GB** - Good, runs Q8_0
- ⚠️ **RTX 3060 12GB** - Works but tight on VRAM
- ❌ **GTX 1080 8GB** - Not enough VRAM for 12B model

---

## Prerequisites

### 1. NVIDIA Drivers

Verify your drivers are installed:

```bash
nvidia-smi
```

You should see your GPU listed with driver version 525+ and CUDA 11.8+.

### 2. NVIDIA Container Toolkit

This allows Docker to access your GPU.

```bash
# Check if already installed
docker run --rm --gpus all ubuntu nvidia-smi
```

If that fails, install the toolkit:

```bash
# Add the repository
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

# Verify
docker run --rm --gpus all ubuntu nvidia-smi
```

> **Note:** The test uses the `ubuntu` image (not `nvidia/cuda`) because it's more reliable and `nvidia-smi` is mounted from the host driver.

---

## Installation

### Automated Setup

```bash
cd ~/second-brain
./scripts/enable-local-ai.sh
```

The script will:
1. Check for NVIDIA GPU and drivers
2. Verify Docker GPU access
3. Create data directories
4. Add environment variables to `.env`
5. Start Ollama and download the model

### Manual Setup

If the automated setup fails or you prefer manual control:

#### Step 1: Create directories

```bash
mkdir -p data/ollama
```

#### Step 2: Add to .env

```bash
cat >> .env << 'EOF'

# ══════════════════════════════════════════════════════════════════
# LOCAL AI (OLLAMA)
# ══════════════════════════════════════════════════════════════════
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_MODEL=gemma3:12b
OLLAMA_NUM_PARALLEL=2
OLLAMA_FLASH_ATTENTION=1
EOF
```

#### Step 3: Start Ollama

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama
```

#### Step 4: Pull the model

```bash
docker exec ollama ollama pull gemma3:12b
```

This downloads ~12GB and takes 10-30 minutes.

#### Step 5: Verify

```bash
curl http://localhost:11434/api/generate -d '{"model":"gemma3:12b","prompt":"Hello","stream":false}'
```

---

## Usage

### Starting with Local AI

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### Starting without Local AI (cloud APIs)

```bash
docker compose up -d
```

### Stopping only Ollama

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml stop ollama
```

---

## Model Options

| Model | VRAM | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| `gemma3:12b` | ~12GB | ⭐⭐⭐⭐⭐ | Medium | Default, best quality |
| `gemma3:12b-q4_K_M` | ~7GB | ⭐⭐⭐⭐ | Fast | Lower VRAM GPUs |
| `gemma3:4b` | ~4GB | ⭐⭐⭐ | Very Fast | Quick tasks |
| `llama3.2:3b` | ~3GB | ⭐⭐⭐ | Very Fast | Minimal resources |
| `mistral:7b` | ~6GB | ⭐⭐⭐⭐ | Fast | Good balance |

### Changing Models

```bash
# Pull new model
docker exec ollama ollama pull mistral:7b

# Update .env
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=mistral:7b/' .env

# Restart to apply
docker compose -f docker-compose.yml -f docker-compose.ollama.yml restart ollama
```

### Removing Models

```bash
# List models
docker exec ollama ollama list

# Remove a model
docker exec ollama ollama rm gemma3:12b
```

---

## Troubleshooting

### "Address already in use" on port 11434

You have Ollama running directly on the host:

```bash
# Stop host Ollama
sudo systemctl stop ollama
sudo systemctl disable ollama

# Then start Docker version
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### "Container ollama is unhealthy"

The healthcheck may time out during first startup. Pull the model manually:

```bash
# Start Ollama without waiting for health
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama

# Wait a moment, then pull manually
sleep 10
docker exec ollama ollama pull gemma3:12b
```

### "CUDA out of memory"

Your GPU doesn't have enough VRAM for the model:

```bash
# Use a smaller quantization
docker exec ollama ollama pull gemma3:12b-q4_K_M
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=gemma3:12b-q4_K_M/' .env
```

### Docker can't access GPU

```bash
# Verify nvidia-container-toolkit is configured
cat /etc/docker/daemon.json
# Should contain "nvidia" runtime

# Restart Docker
sudo systemctl restart docker

# Test
docker run --rm --gpus all ubuntu nvidia-smi
```

### Slow inference

1. **Check GPU is being used:**
   ```bash
   nvidia-smi
   # Should show ollama process using GPU memory
   ```

2. **Reduce context window:**
   Add to `.env`:
   ```
   OLLAMA_NUM_CTX=2048
   ```

3. **First request is slow** - This is normal, the model loads into GPU memory on first use.

### Connection refused from n8n

```bash
# Check Ollama is running
docker compose ps | grep ollama

# Test from n8n container
docker exec n8n curl http://ollama:11434/api/tags
```

---

## Performance Tuning

### Environment Variables

Add these to `.env` to tune performance:

```bash
# Number of parallel requests (default: 2)
OLLAMA_NUM_PARALLEL=2

# Max models loaded at once (default: 1)
OLLAMA_MAX_LOADED_MODELS=1

# Enable flash attention (default: 1)
OLLAMA_FLASH_ATTENTION=1

# Context window size (lower = faster, less memory)
OLLAMA_NUM_CTX=4096

# Keep model in memory (default: 5m)
OLLAMA_KEEP_ALIVE=10m
```

### Monitoring

```bash
# Watch GPU usage
watch -n 1 nvidia-smi

# View Ollama logs
docker compose logs -f ollama

# Check loaded models
curl http://localhost:11434/api/ps
```

---

## Security Notes

- Ollama API has **no authentication** - only expose internally
- The API is only accessible within Docker network + localhost
- For external access, use a reverse proxy with authentication
- No data leaves your machine when using local AI

---

## Uninstalling

To remove local AI and switch back to cloud:

```bash
# Stop Ollama
docker compose -f docker-compose.yml -f docker-compose.ollama.yml down ollama

# Remove data (optional - deletes downloaded models)
rm -rf data/ollama

# Remove env vars (optional)
sed -i '/^# .*LOCAL AI/,/^OLLAMA_/d' .env

# Run without Ollama overlay
docker compose up -d
```
