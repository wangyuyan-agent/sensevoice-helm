import os, re, time, subprocess
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from typing_extensions import Annotated
from typing import List, Optional
from enum import Enum
import torchaudio
from model import SenseVoiceSmall
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from io import BytesIO

TARGET_FS = 16000

class Language(str, Enum):
    auto = "auto"
    zh = "zh"
    en = "en"
    yue = "yue"
    ja = "ja"
    ko = "ko"
    nospeech = "nospeech"

model_dir = "iic/SenseVoiceSmall"
m, kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device=os.getenv("SENSEVOICE_DEVICE", "cpu"))
m.eval()

regex = r"<\|.*\|>"

app = FastAPI()


def _load_audio_via_torchaudio(audio_bytes: bytes):
    """Load audio with torchaudio, returns mono 16kHz tensor."""
    data, sr = torchaudio.load(BytesIO(audio_bytes))
    if sr != TARGET_FS:
        data = torchaudio.transforms.Resample(orig_freq=sr, new_freq=TARGET_FS)(data)
    return data.mean(0)


def _load_audio_via_ffmpeg(audio_bytes: bytes):
    """Fallback: use ffmpeg for formats torchaudio can't handle (e.g. ogg/opus from Discord)."""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", "pipe:0",
         "-f", "s16le", "-acodec", "pcm_s16le",
         "-ar", str(TARGET_FS), "-ac", "1", "pipe:1"],
        input=audio_bytes, capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {proc.stderr[-500:].decode(errors='replace')}")
    raw = proc.stdout
    if len(raw) % 2 != 0:
        raw = raw[:-1]
    if len(raw) == 0:
        return None
    import torch
    return torch.from_numpy(
        np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    )


def _load_audio(audio_bytes: bytes):
    """Try torchaudio first, fall back to ffmpeg."""
    try:
        return _load_audio_via_torchaudio(audio_bytes)
    except Exception:
        return _load_audio_via_ffmpeg(audio_bytes)


def _infer_single(audio_tensor, language="auto"):
    """Run inference on a single audio tensor, return cleaned text."""
    if audio_tensor is None:
        return ""
    res = m.inference(
        data_in=[audio_tensor],
        language=language,
        use_itn=True,
        ban_emo_unk=False,
        key=["audio"],
        fs=TARGET_FS,
        **kwargs,
    )
    if not res or len(res[0]) == 0:
        return ""
    return rich_transcription_postprocess(res[0][0].get("text", ""))


# ── OpenAI-compatible endpoint ──────────────────────────────

@app.post("/v1/audio/transcriptions")
async def openai_transcribe(
    file: UploadFile = File(...),
    model: str = Form("iic/SenseVoiceSmall"),
    language: Optional[str] = Form(None),
    response_format: str = Form("json"),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Audio file too large")

    try:
        audio = _load_audio(audio_bytes)
        text = _infer_single(audio, language or "auto")
    except Exception as e:
        raise HTTPException(500, str(e))

    if response_format == "text":
        return text
    return {"text": text}


@app.get("/v1/models")
async def list_models():
    return {"data": [{
        "id": "iic/SenseVoiceSmall",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "alibaba",
    }]}


# ── Original SenseVoice endpoints ───────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<html><body><a href='./docs'>API Docs</a></body></html>"


@app.post("/api/v1/asr")
async def turn_audio_to_text(
    files: Annotated[List[UploadFile], File(description="wav or mp3 audios in 16KHz")],
    keys: Annotated[str, Form(description="name of each audio joined with comma")] = None,
    lang: Annotated[Language, Form(description="language of audio content")] = "auto",
):
    audios = []
    for file in files:
        audio_bytes = await file.read()
        audios.append(_load_audio(audio_bytes))

    if not keys:
        key = [f.filename for f in files]
    else:
        key = keys.split(",")

    res = m.inference(
        data_in=[a for a in audios if a is not None],
        language=lang,
        use_itn=False,
        ban_emo_unk=False,
        key=key,
        fs=TARGET_FS,
        **kwargs,
    )
    if len(res) == 0:
        return {"result": []}
    for it in res[0]:
        it["raw_text"] = it["text"]
        it["clean_text"] = re.sub(regex, "", it["text"], 0, re.MULTILINE)
        it["text"] = rich_transcription_postprocess(it["text"])
    return {"result": res[0]}
