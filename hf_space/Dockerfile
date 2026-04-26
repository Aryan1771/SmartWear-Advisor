# hf_space/Dockerfile
# HuggingFace Space — Docker SDK
# Exposes FastAPI on port 7860 (HF standard port).

FROM python:3.11-slim

# System deps for dlib (face_recognition) and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake \
        libopenblas-dev liblapack-dev \
        libx11-dev libgtk-3-dev \
        libglib2.0-0 libsm6 libxext6 libxrender-dev \
        libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create persistent directories for encodings (populated by users at runtime)
RUN mkdir -p data/encodings models

# HuggingFace Spaces run on port 7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
