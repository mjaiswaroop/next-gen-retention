#!/usr/bin/env bash
set -e

echo "Starting Retention Core pre-start script..."

# 1. Run database migrations
echo "Running database migrations..."
alembic upgrade head

# 2. Seed database
echo "Seeding default database records..."
python seed_admin.py

echo "Pre-start complete!"
