# Local AI Module (Ollama + Gemma 3)

This optional module adds fully local AI processing to your Second Brain using Ollama and Google's Gemma 3 12B model.

## Why Local AI?

- **Complete Privacy**: Your data never leaves your machine
- **No API Costs**: No per-token charges after initial setup
- **Offline Capable**: Works without internet connection
- **Full Control**: Customize models and parameters as needed

## Hardware Requirements

| Component | Minimum | Recommended (Your Setup ✓) |
|-----------|---------|---------------------------|
| GPU | NVIDIA 8GB VRAM | RTX 4060 Ti 16GB |
| RAM | 32GB | 64GB |
| Storage | 20GB free | 50GB+ free |
| CUDA | 11.8+ | 12.8 |

Your system (Ryzen 7 5800X, RTX 4060 Ti 16GB, 64GB RAM) is ideal for Q8_0 quantization.

## Quick Start

### 1. Enable NVIDIA Container Toolkit

If not already installed:

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

# Verify
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 2. Start Ollama

```bash
cd ~/second-brain

# Start with the Ollama overlay
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Watch model download progress (first run only, ~12GB download)
docker compose logs -f ollama-init
```

### 3. Verify Installation

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test the model
curl http://localhost:11434/api/generate -d '{
  "model": "gemma3:12b",
  "prompt": "What is 2+2?",
  "stream": false
}'
```

### 4. Configure n8n

See [N8N_OLLAMA_CONFIG.md](N8N_OLLAMA_CONFIG.md) for updating your n8n workflows.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SECOND BRAIN                         │
│                                                         │
│  n8n Hub                                                │
│    ├── Classify Intent ────┐                            │
│    ├── Generate ICS ───────┼──► Ollama ──► Gemma 3 12B  │
│    ├── Notes Classification┘       │                    │
│    └── Chat Responses ─────────────┘                    │
│                                                         │
│  Instead of:  OpenAI API ($$$, cloud)                   │
│  Now using:   Local Ollama (free, private)              │
└─────────────────────────────────────────────────────────┘
```

---

## Model Details

### Gemma 3 12B

- **Developer**: Google DeepMind
- **Parameters**: 12 billion
- **Quantization**: Q8_0 (highest quality that fits 16GB VRAM)
- **VRAM Usage**: ~12GB
- **Context Window**: 8192 tokens
- **Strengths**: 
  - Excellent instruction following
  - Strong JSON output formatting
  - Good reasoning capabilities
  - Efficient for its size

### Performance Expectations

| Task | Approximate Speed |
|------|-------------------|
| Intent Classification | ~0.5-1 second |
| ICS Generation | ~1-2 seconds |
| Notes Classification | ~0.5-1 second |
| Chat Response (short) | ~1-2 seconds |
| Chat Response (long) | ~5-10 seconds |

---

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Ollama Configuration
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_MODEL=gemma3:12b

# Optional: Adjust based on your hardware
OLLAMA_NUM_PARALLEL=2      # Concurrent requests (2 for 16GB VRAM)
OLLAMA_NUM_CTX=4096        # Context window (reduce if OOM)
OLLAMA_NUM_GPU=999         # Layers on GPU (999 = all)
```

### Ollama API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/generate` | Text completion (used for ICS generation) |
| `POST /api/chat` | Chat completion (used for conversations) |
| `GET /api/tags` | List loaded models |
| `POST /api/pull` | Download new models |

---

## Troubleshooting

### Model Won't Load (Out of Memory)

```bash
# Check GPU memory
nvidia-smi

# If using too much VRAM, try smaller quantization
docker exec ollama ollama pull gemma3:12b-q4_K_M
```

Then update your n8n workflows to use `gemma3:12b-q4_K_M`.

### Slow Responses

1. **Check GPU utilization**: `watch -n 1 nvidia-smi`
2. **Ensure model is on GPU**: Look for "GPU Memory" usage
3. **Reduce context if needed**: Lower `OLLAMA_NUM_CTX`

### Connection Refused

```bash
# Check Ollama is running
docker compose logs ollama

# Verify network
docker network inspect automation_net | grep ollama

# Test from n8n container
docker exec n8n curl http://ollama:11434/api/tags
```

### Model Download Stuck

```bash
# Check download progress
docker exec ollama ollama list

# Restart download
docker compose restart ollama-init

# Or pull manually
docker exec -it ollama ollama pull gemma3:12b
```

---

## Alternative Models

If Gemma 3 12B doesn't suit your needs:

| Model | VRAM | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `gemma3:12b` | 12GB | Medium | Best | Default choice |
| `gemma3:12b-q4_K_M` | 7GB | Fast | Good | Lower VRAM systems |
| `llama3.2:3b` | 3GB | Very Fast | Moderate | Quick classifications only |
| `mistral:7b` | 6GB | Fast | Good | Alternative to Gemma |
| `qwen2.5:14b` | 14GB | Medium | Excellent | If you have headroom |

To switch models:

```bash
# Pull new model
docker exec ollama ollama pull mistral:7b

# Update .env
OLLAMA_MODEL=mistral:7b

# Restart n8n
docker compose restart n8n
```

---

## Monitoring

### GPU Usage

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi

# Or use nvtop (install: sudo apt install nvtop)
nvtop
```

### Ollama Logs

```bash
docker compose logs -f ollama
```

### Request Statistics

Ollama exposes basic metrics at `http://localhost:11434/api/ps` showing loaded models and memory usage.

---

## Disabling Local AI

To switch back to cloud AI:

```bash
# Stop Ollama services
docker compose -f docker-compose.yml -f docker-compose.ollama.yml down ollama ollama-init

# Or just run without the overlay
docker compose up -d
```

Then reconfigure your n8n workflows to use OpenAI credentials.

---

## Security Notes

- Ollama API has **no authentication** by default
- Only exposed on `localhost:11434` - not accessible externally
- Internal Docker network (`automation_net`) access only
- No data leaves your machine

For external access (not recommended), add authentication via reverse proxy.
