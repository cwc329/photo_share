FROM python:3.12-slim

WORKDIR /app

# System dependencies:
#   libimage-exiftool-perl — primary EXIF reader (full MakerNote, all brands)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data

# Python dependencies (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--log-config", "logging_uvicorn.yaml"]
