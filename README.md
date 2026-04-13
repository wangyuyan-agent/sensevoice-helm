# SenseVoice Small Helm Chart

A Helm chart for [SenseVoice Small](https://github.com/FunAudioLLM/SenseVoice) — Alibaba's multilingual speech recognition model, wrapped as an OpenAI-compatible STT API.

Supports: zh, en, ja, ko, yue (Cantonese), and auto-detect.

## Install

### OCI Registry (recommended)

```bash
helm install sensevoice oci://ghcr.io/wangyuyan-agent/sensevoice-helm \
  -n openclaw --create-namespace
```

Install a specific version:

```bash
helm install sensevoice oci://ghcr.io/wangyuyan-agent/sensevoice-helm \
  --version 0.1.0 \
  -n openclaw --create-namespace
```

Upgrade:

```bash
helm upgrade sensevoice oci://ghcr.io/wangyuyan-agent/sensevoice-helm -n openclaw
```

### Verify

```bash
curl http://localhost:8000/v1/models
```

## API

Fully compatible with the [OpenAI Audio API](https://platform.openai.com/docs/api-reference/audio/createTranscription):

```bash
# OpenAI-compatible transcription
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "model=iic/SenseVoiceSmall" \
  -F "language=zh"

# Response: {"text": "你好世界"}
```

Works with any OpenAI SDK client:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
result = client.audio.transcriptions.create(
    model="iic/SenseVoiceSmall",
    file=open("audio.wav", "rb"),
)
print(result.text)
```

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/audio/transcriptions` | OpenAI Whisper-compatible transcription |
| GET | `/v1/models` | List available models |
| POST | `/api/v1/asr` | Original SenseVoice batch API |

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `ghcr.io/wangyuyan-agent/sensevoice-small` | Docker image |
| `image.tag` | `2025.12.30` | Image tag (tracks upstream commit date) |
| `resources.limits.memory` | `3584Mi` | Memory limit — model needs ~3.4G at steady state |
| `resources.limits.cpu` | `1.5` | CPU limit |
| `hostPort.enabled` | `true` | Expose on host localhost |
| `hostPort.port` | `8000` | Host port number |
| `env.SENSEVOICE_DEVICE` | `cpu` | Device (`cpu` or `cuda`) |

## Minimum VPS Requirements

SenseVoice Small loads a ~900M parameter model entirely into RAM.

| Resource | Minimum (STT only) | Recommended (with other services) |
|----------|--------------------|------------------------------------|
| RAM | 5 GiB | 8 GiB |
| CPU | 1 vCPU (slow inference) | 2 vCPU |
| Disk | 15 GiB | 20 GiB |
| Swap | 2 GiB (required) | 4 GiB |

Memory breakdown (steady state):

| Component | Memory |
|-----------|--------|
| SenseVoice model + runtime | ~3.4 GiB |
| k3s server + containerd | ~450 MiB |
| CoreDNS + system pods | ~60 MiB |
| Linux OS | ~300 MiB |

CPU is only consumed during inference (~1-1.5 cores for a few seconds per request). Idle usage is negligible (<0.3%).

### Memory Sizing

SenseVoice Small loads a ~900M parameter model into memory. On CPU:

- Steady state: ~3.4 GiB
- Peak during loading: ~3.5 GiB
- **Do NOT set memory limit below 3584Mi** — the pod will OOMKill during model loading

If you have a GPU, set `env.SENSEVOICE_DEVICE: cuda` and the memory footprint drops significantly.

## Auto-Upgrade

### GitHub Actions (upstream tracking)

The `check-upstream.yml` workflow runs daily at 06:00 UTC:
- Checks [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) for new commits
- If changed: syncs code → bumps Chart.yaml → triggers `release.yml`
- If unchanged: skips silently

The `release.yml` workflow triggers on Chart.yaml changes:
- Builds Docker image → pushes to GHCR
- Packages Helm chart → pushes OCI to GHCR
- Creates GitHub Release

### Local cron (VPS auto-upgrade)

```bash
# sensevoice-autoupgrade.sh checks OCI registry for new chart versions
# Add to crontab:
30 3 * * * bash ~/sensevoice-autoupgrade.sh >> ~/Backups/sensevoice/autoupgrade.log 2>&1
```

## Uninstall

```bash
helm uninstall sensevoice -n openclaw
```

## Access

With `hostPort.enabled: true` (default), the STT API is available at `localhost:8000` on the host machine. Any process on the host can call it — not just k3s pods.

```bash
# From host (systemd services, scripts, etc.)
curl http://localhost:8000/v1/audio/transcriptions -F "file=@audio.wav" -F "model=iic/SenseVoiceSmall"

# From k3s pods in the same namespace
curl http://sensevoice-sensevoice-helm:8000/v1/audio/transcriptions ...

# From k3s pods in other namespaces
curl http://sensevoice-sensevoice-helm.openclaw.svc:8000/v1/audio/transcriptions ...
```

### Security

`hostPort` binds to `0.0.0.0` — without a firewall, the STT API is exposed to the public internet. Block external access:

```bash
# iptables (immediate)
sudo iptables -t raw -I PREROUTING -p tcp --dport 8000 \
  ! -s 127.0.0.0/8 -m addrtype ! --src-type LOCAL -j DROP

# Or use your cloud provider's security group to block port 8000 from external traffic
```

If you only need k3s-internal access, set `hostPort.enabled: false` in values.yaml.

## Design Notes

- **No official Helm chart exists** for SenseVoice — this chart wraps the upstream Python code with a FastAPI server providing OpenAI API compatibility
- **startupProbe** is critical — model loading takes 30-60s on CPU; without it, liveness probes kill the pod before it's ready
- **Recreate strategy** — single replica ML model; RollingUpdate would require 2x memory during transitions
- **hostPort** — enables `localhost:8000` access from host processes (e.g. Discord bots) without NodePort/Ingress overhead
