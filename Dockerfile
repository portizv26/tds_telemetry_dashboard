FROM tensorflow/tensorflow:2.15.0-gpu

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install only runtime Python dependencies (tensorflow already in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --ignore-installed \
    "pandas>=2.0.0" \
    "numpy>=1.24.0" \
    "pyarrow>=12.0.0" \
    "pyyaml>=6.0" \
    "pydantic>=2.0" \
    "pydantic-settings>=2.0" \
    "python-json-logger>=2.0" \
    "python-dateutil>=2.8.0" \
    "boto3>=1.42.40" \
    "openai>=2.16.0" \
    "openpyxl>=3.1.5" \
    "tqdm>=4.65.0" \
    "python-dotenv>=1.0.0" \
    "scikit-learn>=1.3.0" \
    "joblib>=1.3.0" \
    "scipy>=1.11.0"

# Copy source code
COPY src/ ./src/
COPY data/telemetry/config/ ./data/telemetry/config/

# Default entrypoint
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--client", "cda"]
