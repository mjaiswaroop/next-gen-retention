#!/bin/bash
# start_combined.sh - Script to run FastAPI, Celery, and Streamlit in a single container.

# Export the port Render gives us for Streamlit to bind to
export STREAMLIT_SERVER_PORT=${PORT:-8501}
export API_BASE="http://localhost:8000"

echo "Running Pre-start Database Migrations and Seeding..."
chmod +x prestart.sh
./prestart.sh

echo "Starting FastAPI Backend..."
# Run FastAPI in the background on port 8000
uvicorn app:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

echo "Starting Celery Worker..."
# Run Celery worker in the background
celery -A tasks.celery_app worker --loglevel=info &
CELERY_PID=$!

echo "Starting Streamlit Dashboard on port $STREAMLIT_SERVER_PORT..."
# Run Streamlit in the foreground so the container doesn't exit
streamlit run dashboard.py --server.port $STREAMLIT_SERVER_PORT --server.address 0.0.0.0

# If Streamlit crashes or exits, kill the background processes
kill $FASTAPI_PID
kill $CELERY_PID
