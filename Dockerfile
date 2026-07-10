# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile for Retention Core v3.0
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies needed for compiling numerical libraries
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app
RUN chmod +x prestart.sh
RUN chmod +x start_combined.sh

# Render provides $PORT for the web service. We use start_combined.sh to run both Streamlit and FastAPI.
CMD ["./start_combined.sh"]
