FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg libsndfile1 git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py model.py /app/
COPY utils/ /app/utils/

RUN python -c "from model import SenseVoiceSmall; SenseVoiceSmall.from_pretrained(model='iic/SenseVoiceSmall', device='cpu')"

ENV SENSEVOICE_DEVICE=cpu PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "3"]
