FROM tensorflow/tensorflow:2.15.0-gpu

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (excluding tensorflow, already in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir tensorflow==2.15.0 --upgrade 2>/dev/null; true

# Copy source code
COPY src/ ./src/
COPY data/telemetry/config/ ./data/telemetry/config/

# Default entrypoint
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--client", "cda"]
