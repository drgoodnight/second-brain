# 🤖 Local AI Module for Second Brain

> **Optional module** - Adds fully local AI processing using Ollama and Gemma 3 12B.

This module replaces cloud AI (OpenAI, Anthropic) with a locally-hosted model, giving you complete privacy and eliminating API costs.

## ✨ What You Get

| Feature | Cloud AI | Local AI (This Module) |
|---------|----------|------------------------|
| Privacy | Data sent to cloud | 100% local |
| Cost | ~$0.01-0.03 per interaction | Free after setup |
| Speed | ~1-2s (network latency) | ~0.5-2s (local) |
| Offline | ❌ | ✅ |
| Customization | Limited | Full control |

## 📋 Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| RAM | 32GB | 64GB |
| Storage | 20GB free | 50GB free |
| CUDA | 11.8+ | 12.x |

### Tested Configurations

- ✅ RTX 4060 Ti 16GB + Ryzen 7 5800X + 64GB RAM (optimal)
- ✅ RTX 3080 10GB + any modern CPU + 32GB RAM
- ⚠️ RTX 3060 12GB - works but tight on VRAM
- ❌ GTX 1080 - not enough VRAM for 12B model

## 🚀 Quick Start

```bash
# 1. Navigate to your Second Brain directory
cd ~/second-brain

# 2. Run the setup script
./scripts/enable-local-ai.sh

# 3. Wait for model download (~12GB, 10-30 minutes)

# 4. Test it works
curl http://localhost:11434/api/generate -d '{"model":"gemma3:12b","prompt":"Hello"}'
```

## 📁 Files Included

```
ollama/
├── LOCAL_AI_SETUP.md        # Detailed setup guide
├── N8N_OLLAMA_CONFIG.md     # n8n workflow configuration
├── init-models.sh           # Model download script
├── env.example.ollama       # Environment variables
└── prompts/
    └── GEMMA3_PROMPTS.md    # Optimized prompts for Gemma 3

scripts/
└── enable-local-ai.sh       # One-click setup script

docker-compose.ollama.yml    # Docker Compose overlay
```

## 🔧 Manual Setup

If you prefer manual setup over the script:

### 1. Install NVIDIA Container Toolkit

```bash
# Add repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 2. Create Data Directory

```bash
mkdir -p data/ollama
```

### 3. Add to .env

```bash
echo "" >> .env
echo "# Local AI" >> .env
echo "OLLAMA_HOST=ollama" >> .env
echo "OLLAMA_PORT=11434" >> .env
echo "OLLAMA_MODEL=gemma3:12b" >> .env
```

### 4. Start Ollama

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

### 5. Pull the Model

```bash
docker exec ollama ollama pull gemma3:12b
```

## ⚙️ n8n Configuration

After Ollama is running, update your n8n workflows:

1. **Create Ollama credential** in n8n Settings → Credentials
2. **Replace AI nodes** with HTTP Request nodes pointing to `http://ollama:11434`
3. **Add JSON parsing** Code nodes after Ollama calls
4. **Test each workflow** path

See [N8N_OLLAMA_CONFIG.md](ollama/N8N_OLLAMA_CONFIG.md) for detailed instructions.

## 🎯 Model Options

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| `gemma3:12b` (default) | 12GB | ⭐⭐⭐⭐⭐ | Medium |
| `gemma3:12b-q4_K_M` | 7GB | ⭐⭐⭐⭐ | Fast |
| `llama3.2:3b` | 3GB | ⭐⭐⭐ | Very Fast |
| `mistral:7b` | 6GB | ⭐⭐⭐⭐ | Fast |

To use a different model:

```bash
# Pull the model
docker exec ollama ollama pull mistral:7b

# Update .env
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=mistral:7b/' .env
```

## 🔍 Monitoring

```bash
# Watch GPU usage
watch -n 1 nvidia-smi

# View Ollama logs
docker compose logs -f ollama

# Check loaded models
curl http://localhost:11434/api/ps
```

## 🛠️ Troubleshooting

### "CUDA out of memory"

```bash
# Use smaller quantization
docker exec ollama ollama pull gemma3:12b-q4_K_M
# Update OLLAMA_MODEL in .env
```

### Slow responses

1. Check GPU is being used: `nvidia-smi` should show process
2. Reduce context window: Add `OLLAMA_NUM_CTX=2048` to .env
3. Ensure model is loaded: First request after restart is slower

### Connection refused

```bash
# Check Ollama is running
docker compose ps | grep ollama

# Check network
docker exec n8n curl http://ollama:11434/api/tags
```

## 🔄 Switching Back to Cloud AI

To disable local AI and use cloud providers:

```bash
# Stop Ollama
docker compose -f docker-compose.yml -f docker-compose.ollama.yml down ollama

# Run without Ollama overlay
docker compose up -d

# Reconfigure n8n workflows for OpenAI
```

## 📊 Performance Comparison

Tested on RTX 4060 Ti 16GB:

| Task | Gemma 3 12B | OpenAI GPT-4o-mini |
|------|-------------|-------------------|
| Intent classification | 0.4s | 0.8s |
| ICS generation | 1.2s | 1.0s |
| Notes classification | 0.5s | 0.7s |
| Chat (short) | 0.8s | 0.6s |
| Chat (long) | 4s | 3s |

Local inference is competitive and sometimes faster due to no network latency.

## 🔐 Security

- Ollama API has no authentication (internal use only)
- Only accessible within Docker network + localhost
- No data leaves your machine
- For external access, use a reverse proxy with auth

## 📚 Further Reading

- [Ollama Documentation](https://ollama.ai/docs)
- [Gemma 3 Model Card](https://ai.google.dev/gemma)
- [n8n Ollama Integration](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmollama/)
