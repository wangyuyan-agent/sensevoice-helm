# SenseVoice Small Helm Chart

OpenAI-compatible STT service powered by [SenseVoice Small](https://github.com/FunAudioLLM/SenseVoice).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/audio/transcriptions` | OpenAI Whisper-compatible transcription |
| GET | `/v1/models` | List available models |
| POST | `/api/v1/asr` | Original SenseVoice batch API |

## Install

```bash
helm install sensevoice oci://ghcr.io/wangyuyan-agent/sensevoice-helm -n openclaw --create-namespace
```

## Upgrade

```bash
helm upgrade sensevoice oci://ghcr.io/wangyuyan-agent/sensevoice-helm -n openclaw
```

## Auto-upgrade

Add to crontab:
```bash
0 3 * * * bash /home/ubuntu/sensevoice-autoupgrade.sh >> /home/ubuntu/Backups/sensevoice/autoupgrade.log 2>&1
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.tag` | `2025.12.30` | Image tag (tracks upstream date) |
| `resources.limits.memory` | `3584Mi` | Memory limit (model needs ~3.4G) |
| `resources.limits.cpu` | `1.5` | CPU limit |
| `hostPort.enabled` | `true` | Expose on host for localhost access |
| `hostPort.port` | `8000` | Host port number |
| `env.SENSEVOICE_DEVICE` | `cpu` | Device (cpu/cuda) |

## Upstream Tracking

GitHub Actions checks [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) daily.
On new commits: syncs code → builds image → bumps chart → pushes to GHCR.
