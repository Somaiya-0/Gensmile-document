#!/bin/bash
# Idempotent: seed_local.py checks for existing accounts before creating any,
# so it's safe to run on every deploy.
set -e
source /var/app/venv/*/bin/activate
cd /var/app/current
python3 seed_local.py || true
